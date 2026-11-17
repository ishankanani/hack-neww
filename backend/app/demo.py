"""Isolated, deterministic judge demo using captured OSRM geometry."""
import json, os, re
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from .operations import Operations
from . import persistence

# One Operations object per demo session, reused while its stored version is
# unchanged. Rebuilding it reopened the database twice per sample shipment.
_sessions = {}


@lru_cache(maxsize=1)
def _road_records():
    return json.loads((Path(__file__).resolve().parents[2]/"data"/"demo_roads.json").read_text())


def _operations(session, directory):
    key = f"demo/{session}/operations.json"
    cached = _sessions.get(session)
    if persistence.configured():
        if cached is not None:
            fresh = persistence.load(key, cached.data)  # None while the version is unchanged
            if fresh is not None:
                cached.data = fresh
            return cached
        if not persistence.exists(key) and not (directory/"operations.json").exists(): raise ValueError("Unknown demo session")
    elif not (directory/"operations.json").exists(): raise ValueError("Unknown demo session")
    ops = Operations(directory)
    if persistence.configured():
        _sessions[session] = ops
    return ops


def context(base, session):
    if not re.fullmatch(r"[a-f0-9]{12}",session): raise ValueError("Invalid demo session")
    directory=Path(os.environ.get("STORE_DIR","store"))/"demo"/session
    with persistence.session():
        operations=_operations(session, directory)
    nodes={k:base["network"]["nodes"][k] for k in ("R16","R10","R21")}
    records=_road_records()
    lookup={((nodes[r["from"]]["lat"],nodes[r["from"]]["lon"]),(nodes[r["to"]]["lat"],nodes[r["to"]]["lon"])):r for r in records}
    def leg(a,b):
        row=lookup.get((tuple(a),tuple(b)))
        if row is None: return {"geometry":None,"source":"DEMO: connection unavailable"}
        return {**row,"source":"DEMO: captured OSRM geometry; illustrative travel times"}
    providers=SimpleNamespace(routing=SimpleNamespace(leg=leg),traffic=SimpleNamespace(status=lambda:"SIMULATED"))
    return {**base,"network":{**base["network"],"nodes":nodes,"edges":{}},"providers":providers,"operations":operations,"holidays":{},"transfer":{},"hub_delays":{},"is_demo":True}
