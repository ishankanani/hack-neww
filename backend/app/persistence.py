"""Shared Postgres state with atomic manager updates; local JSON remains supported."""
import json
import os
import zlib
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path

_connection = ContextVar("planner_database_connection", default=None)
_writing = ContextVar("planner_database_write", default=False)
_versions = {}


class StorageUnavailable(RuntimeError):
    pass


def configured():
    return bool(os.environ.get("DATABASE_URL"))

def writing():
    return _writing.get()


def document_key(path):
    root = Path(os.environ.get("STORE_DIR", "store")).resolve()
    return str(Path(path).resolve().relative_to(root)).replace("\\", "/")


@lru_cache(maxsize=1)
def initialize(url):
    import psycopg
    try:
        with psycopg.connect(url, connect_timeout=15, prepare_threshold=None) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS dachser_state (name text PRIMARY KEY, payload bytea NOT NULL, version bigint NOT NULL DEFAULT 1, updated_at timestamptz NOT NULL DEFAULT now())")
    except psycopg.Error:
        raise StorageUnavailable("Shared storage could not be reached. Please try again.") from None


@contextmanager
def session(write=False):
    if not configured() or _connection.get() is not None:
        yield
        return
    import psycopg
    url = os.environ["DATABASE_URL"]
    initialize(url)
    try:
        with psycopg.connect(url, connect_timeout=15, prepare_threshold=None) as connection:
            token = _connection.set(connection)
            write_token = _writing.set(write)
            try:
                if write:
                    # Serializes approvals and capacity reservations across server instances.
                    connection.execute("SELECT pg_advisory_xact_lock(684918257)")
                yield
                # Commit explicitly. psycopg's context manager silently skips the
                # commit when the connection is already closed, which would report
                # a save that never happened; commit() raises in that case instead.
                connection.commit()
            except BaseException:
                # A rolled-back request may already have changed the worker's
                # in-memory objects; force their next read back from Postgres.
                _versions.clear()
                raise
            finally:
                _writing.reset(write_token)
                _connection.reset(token)
    except psycopg.Error:
        # The failure may come from the commit itself, after save() already
        # recorded a version that never landed. Forget every cached version so
        # the next read reloads committed state instead of trusting memory.
        _versions.clear()
        raise StorageUnavailable("Shared storage could not complete this request. No successful save was confirmed; please try again.") from None


def encode(value):
    # Route geometries repeat across comparison snapshots. Compressing them keeps
    # the existing prototype records small without discarding approved evidence.
    return zlib.compress(json.dumps(value, separators=(",", ":"), default=str).encode(), 6)


def load(key, fallback, force=False):
    if not configured(): return fallback if force else None
    with session():
        connection = _connection.get()
        row = connection.execute("SELECT version FROM dachser_state WHERE name=%s", (key,)).fetchone()
        if row is None:
            connection.execute("INSERT INTO dachser_state(name,payload) VALUES(%s,%s) ON CONFLICT DO NOTHING", (key, encode(fallback)))
            row = connection.execute("SELECT version FROM dachser_state WHERE name=%s", (key,)).fetchone()
        if not force and _versions.get(key) == row[0]: return None
        payload, version = connection.execute("SELECT payload,version FROM dachser_state WHERE name=%s", (key,)).fetchone()
        _versions[key] = version
        return json.loads(zlib.decompress(bytes(payload)))


def save(key, value):
    if not configured(): return False
    with session(write=True):
        row = _connection.get().execute("INSERT INTO dachser_state(name,payload) VALUES(%s,%s) ON CONFLICT(name) DO UPDATE SET payload=EXCLUDED.payload, version=dachser_state.version+1, updated_at=now() RETURNING version", (key, encode(value))).fetchone()
        _versions[key] = row[0]
    return True


def exists(key):
    with session():
        return _connection.get().execute("SELECT 1 FROM dachser_state WHERE name=%s", (key,)).fetchone() is not None
