"""Explain dispatch consequences using stored or freshly computed itineraries."""
from datetime import datetime, timedelta, timezone

from .operations import parse


def connection_warnings(option, approved=None):
    """The ETA engine selects departures; this layer explains its decisions."""
    previous={(s["from"],s["to"]):s for s in (approved or {}).get("scheduled_services",[])}
    result=[]
    for service in option.get("scheduled_services",[]):
        row=dict(service)
        old=previous.get((service["from"],service["to"]))
        missed=bool(old and parse(service["departure"])>parse(old["departure"]))
        row.update({"status":"MISSED" if missed else "TIGHT" if service.get("buffer_minutes",9999)<30 else "ON TRACK",
                    "previous_departure":old["departure"] if missed else None,
                    "connection_delay_minutes":round((parse(service["departure"])-parse(old["departure"])).total_seconds()/60) if missed else 0})
        result.append(row)
    return result


def deadline_delta(option, required):
    return round((parse(required)-parse(option["eta"])).total_seconds()/60) if required else None


def remaining_connections(approved, at=None):
    at=at or datetime.now(timezone.utc)
    return [s for s in (approved or {}).get("scheduled_services",[]) if parse(s["departure"])>=at]
