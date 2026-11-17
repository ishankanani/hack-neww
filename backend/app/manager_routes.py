"""Manager-requested hub connections, evaluated without changing an approved plan."""
from datetime import datetime, timezone
from .operations import parse
from .progress import dispatched, position_context


def validate_path(network, origin, destination, via_hubs):
    path = [origin, *via_hubs, destination]
    if len(via_hubs) > 6: raise ValueError("Choose no more than six intermediate hubs")
    if len(set(path)) != len(path): raise ValueError("Choose each hub once; origin and destination cannot be intermediate stops")
    for node in path:
        if node not in network["nodes"]: raise ValueError("Unknown facility in the requested route")
    return path


def add_route_constraints(option, network):
    reasons = []
    if not option.get("geometry"):
        reasons.append("No road connection could be verified by the routing provider. The displayed time and distance are estimates.")
    for node in option["path"][1:-1]:
        hub = network["nodes"][node]
        if not hub.get("operational", True): reasons.append(f"{hub['name']} is not operational.")
        if not hub.get("transfer_enabled", True): reasons.append(f"{hub['name']} does not accept transfers.")
    option["route_feasible"] = not reasons
    if option.get("zone_impacts"):
        kinds = ", ".join(sorted({z["kind"] for z in option["zone_impacts"]}))
        reasons.append(f"This road crosses an active {kinds} zone. Choose a clear alternative or hold the shipment.")
    if option.get("capacity", {}).get("feasible") is False:
        reasons.append("The requested hub or departure service has insufficient capacity.")
    if not option["risk"]["deadline_ok"]:
        # Same local time and format the planner shows, so the reason and the
        # metrics beside it never appear to disagree by the UTC offset.
        from zoneinfo import ZoneInfo
        arrival = parse(option["eta"]).astimezone(ZoneInfo("Europe/Berlin")).strftime("%a %d %b, %H:%M")
        reasons.append(f"Arrival {arrival} misses the delivery deadline. Review the alternative arrival times.")
    option["unavailable_reasons"] = reasons


def propose(store, sid, via_hubs, depart_at=None):
    ship = store.get(sid)
    if ship is None: raise ValueError("Unknown shipment")
    if ship["status"] == "DELIVERED": raise ValueError("A delivered journey cannot be changed")
    ctx = store.context_for(ship)
    moving = dispatched(ship)
    if moving:
        current = position_context(ctx, ship)
        origin = "@vehicle"
        network = current["network"]
        if depart_at: raise ValueError("A moving journey is recalculated from its current reported position")
    else:
        origin, network = ship["origin"], ctx["network"]
        if depart_at and parse(depart_at) < datetime.now(timezone.utc):
            raise ValueError("Choose a future departure for this proposal")
    path = validate_path(network, origin, ship["destination"], via_hubs)
    # Only the proposal changes here. The saved itinerary stays in effect until approval.
    previous = ship.get("manager_route_request")
    ship["manager_route_request"] = {"via_hubs": list(via_hubs), "path": path, "depart_at": depart_at,
        "requested_at": datetime.now(timezone.utc).isoformat(), "source": "MANAGER ROUTE REQUEST"}
    try: return store.replan(sid, from_now=True)
    except Exception:
        if previous is None: ship.pop("manager_route_request", None)
        else: ship["manager_route_request"] = previous
        raise
