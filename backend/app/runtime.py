"""Hosting defaults. Local records are never copied into a hosted demo."""
import os
import tempfile
from pathlib import Path


def configure_runtime():
    if os.environ.get("VERCEL")=="1":
        root=Path(tempfile.gettempdir())/"dachser-transit-demo"
        os.environ.setdefault("STORE_DIR",str(root/"store"))
        os.environ.setdefault("MAP_TILE_CACHE_DIR",str(root/"map-tiles"))
        os.environ.setdefault("SEED_DEMO_SHIPMENTS","0")


def deployment_info():
    cloud=os.environ.get("VERCEL")=="1"
    return {"hosting":"vercel" if cloud else "local","storage":"ephemeral" if cloud else "local",
            "message":"Temporary hosted demo: saved journeys and scenarios may reset or differ across server instances. Use local storage for persistent prototype records." if cloud else None}
