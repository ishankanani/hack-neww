"""Validated planning examples from the supplied JSON, isolated from fleet data."""
import json
from copy import copy
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo
from .eta import _haversine_km

DATASET = Path(__file__).resolve().parents[2] / "data" / "journeys" / "journeys.json"


@lru_cache(maxsize=1)
def dataset():
    document = json.loads(DATASET.read_text(encoding="utf-8"))
    if document.get("version") != 1: raise ValueError("Unsupported journey dataset version")
    ids = set()
    for journey in document["journeys"]:
        if journey["id"] in ids: raise ValueError("Duplicate example journey id")
        ids.add(journey["id"])
        shipment = journey["shipment"]
        if shipment["origin"] == shipment["destination"]: raise ValueError("Example endpoints must differ")
        if not 1 <= shipment["weight_kg"] <= 23800: raise ValueError("Invalid example weight")
        if not 0 <= shipment["value_eur"] <= 100_000_000: raise ValueError("Invalid example value")
        if shipment["optimization"] not in {"fastest", "cost", "balanced"}: raise ValueError("Invalid objective")
        for zone in journey.get("weather_zones", []):
            if zone["kind"] not in {"snow", "rain", "tornado"} or not 3 <= zone["radius_km"] <= 80:
                raise ValueError("Invalid example weather zone")
            if not 0 <= zone.get("place_at_route_fraction", .5) <= 1: raise ValueError("Invalid route fraction")
            if not -85 <= zone.get("lat", 0) <= 85 or not -180 <= zone.get("lon", 0) <= 180:
                raise ValueError("Invalid example coordinates")
    return document


def example(example_id):
    row = next((row for row in dataset()["journeys"] if row["id"] == example_id), None)
    if row is None: raise ValueError("Unknown sample journey")
    return row


def request_for(row, now=None):
    spec = row["shipment"]
    now = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo("Europe/Berlin"))
    if "depart_next_weekday" in spec:
        departure = (now + timedelta(days=1)).replace(hour=spec.get("depart_at_local_hour", 8), minute=0, second=0, microsecond=0)
        while departure.isoweekday() != spec["depart_next_weekday"]: departure += timedelta(days=1)
        deadline = (departure + timedelta(days=1)).replace(hour=spec.get("deliver_at_local_hour", 9))
        while deadline.isoweekday() != spec["deliver_next_weekday"]: deadline += timedelta(days=1)
    else:
        departure = now + timedelta(minutes=spec.get("depart_in_minutes", 20))
        deadline = departure + timedelta(hours=spec.get("deliver_in_hours", 24))
    return {**{k: spec[k] for k in ("origin", "destination", "weight_kg", "value_eur", "optimization")},
            "depart_at": departure.isoformat(), "required_delivery": deadline.isoformat()}


def catalog(nodes):
    rows = dataset()["journeys"]
    if any(row["shipment"][key] not in nodes for row in rows for key in ("origin", "destination")):
        raise ValueError("Journey dataset references an unknown facility")
    return {"examples": [{"id": row["id"], "title": row["title"], "description": row["what_it_proves"],
                          "weather_zone_count": len(row.get("weather_zones", [])), "request": request_for(row)} for row in rows]}


def isolated_context(ctx):
    operations = copy(ctx["operations"])
    operations.data = {"revision": ctx["operations"].data["revision"],
                       **{key: [] for key in ("events", "weather", "weather_zones", "schedules", "capacity_records", "decisions")}}
    return {**ctx, "operations": operations, "hub_delays": {}, "capacity_shipments": []}


def weather_for(row, geometry, departure):
    distances = [_haversine_km((a[1], a[0]), (b[1], b[0])) for a, b in zip(geometry or [], (geometry or [])[1:])]
    zones = []
    for index, spec in enumerate(row.get("weather_zones", [])):
        if "lat" in spec and "lon" in spec: lon, lat = spec["lon"], spec["lat"]
        else:
            if not distances: raise ValueError("Road geometry is needed to place this example's weather. Try calculating again.")
            target, walked = sum(distances) * spec.get("place_at_route_fraction", .6), 0
            lon, lat = geometry[-1]
            for a, b, distance in zip(geometry, geometry[1:], distances):
                if walked + distance >= target:
                    ratio = (target - walked) / distance if distance else 0
                    lon, lat = a[0] + (b[0] - a[0]) * ratio, a[1] + (b[1] - a[1]) * ratio
                    break
                walked += distance
        zones.append({"id": f"example-{row['id']}-{index}", "kind": spec["kind"], "lon": lon, "lat": lat,
                      "radius_km": spec["radius_km"], "source": "SAMPLE SIMULATION",
                      "start": (departure + timedelta(minutes=spec.get("from_minutes", -60))).isoformat(),
                      "end": (departure + timedelta(minutes=spec.get("to_minutes", 720))).isoformat()})
    return zones
