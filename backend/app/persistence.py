"""Shared Postgres state with atomic manager updates; local JSON remains supported."""
import json
import os
import threading
import time
import zlib
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path

_connection = ContextVar("planner_database_connection", default=None)
_writing = ContextVar("planner_database_write", default=False)
_versions = {}
# Reuse database connections inside a warm server instance. Opening a new TLS
# connection to a remote Postgres costs hundreds of milliseconds, and one page
# view triggers several requests; this was the main cause of slow hosted pages.
_pool = []
_pool_lock = threading.Lock()
POOL_SIZE = 4
IDLE_CHECK_SECONDS = 30


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


def _acquire(url):
    """An idle pooled connection (checked if it sat unused for a while), else a new one."""
    import psycopg
    while True:
        with _pool_lock:
            item = _pool.pop() if _pool else None
        if item is None:
            return psycopg.connect(url, connect_timeout=15, prepare_threshold=None), False
        connection, idle_since = item
        if connection.closed or connection.broken:
            continue
        if time.monotonic() - idle_since > IDLE_CHECK_SECONDS:
            try:
                connection.execute("SELECT 1")
                connection.rollback()
            except psycopg.Error:
                connection.close()
                continue
        return connection, True


def reset_pool():
    """Drop every pooled connection, e.g. after the database closed them."""
    with _pool_lock:
        items, _pool[:] = list(_pool), []
    for connection, _ in items:
        try:
            connection.close()
        except Exception:
            pass


def _release(connection, reusable):
    import psycopg.pq
    if reusable and not connection.closed and not connection.broken and connection.info.transaction_status == psycopg.pq.TransactionStatus.IDLE:
        with _pool_lock:
            if len(_pool) < POOL_SIZE:
                _pool.append((connection, time.monotonic()))
                return
    try:
        connection.close()
    except Exception:
        pass


@contextmanager
def session(write=False):
    if not configured() or _connection.get() is not None:
        yield
        return
    import psycopg
    url = os.environ["DATABASE_URL"]
    initialize(url)
    try:
        connection, pooled = _acquire(url)
        if write:
            try:
                # Serializes approvals and capacity reservations across server instances.
                connection.execute("SELECT pg_advisory_xact_lock(684918257)")
            except psycopg.OperationalError:
                if not pooled:
                    raise
                # The database dropped this idle connection; start again on a fresh one.
                connection.close()
                reset_pool()
                connection, pooled = _acquire(url)
                connection.execute("SELECT pg_advisory_xact_lock(684918257)")
        reusable = False
        token = _connection.set(connection)
        write_token = _writing.set(write)
        try:
            yield
            # Commit explicitly; commit() raises if the connection was lost, so a
            # save that never happened is never reported as successful.
            connection.commit()
            reusable = True
        except BaseException:
            # A rolled-back request may already have changed the worker's
            # in-memory objects; force their next read back from Postgres.
            _versions.clear()
            try:
                if not connection.closed:
                    connection.rollback()
                    reusable = True
            except psycopg.Error:
                reusable = False
            raise
        finally:
            _writing.reset(write_token)
            _connection.reset(token)
            _release(connection, reusable)
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
