"""Explain dispatch consequences using stored or freshly computed itineraries."""
from datetime import datetime, timedelta, timezone

from .operations import parse
from .weather_routes import active_zones, crossed_zones, CLEARANCE_KM


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


def attention(ship, operations, pending_minutes=0, closures=(), at=None):
    """Cheap fleet screening. Approval still requires the full ETA engine."""
    at=at or datetime.now(timezone.utc)
    plan=ship.get("accepted_plan") or {}
    reasons=[]; score=0; decision_by=None; connections=[]
    if ship["status"]=="DELIVERED":
        return {"priority":"COMPLETE","score":0,"reasons":["Delivery confirmed"],"connections":[],"weather_zone_ids":[],"decision_by":None}
    if ship.get("hold"):
        score=95;reasons.append("Shipment held; release requires a clear approved route")
    if ship.get("stop_request",{}).get("status")=="REQUESTED":
        score=max(score,98);reasons.append("Safe-stop request awaiting driver acknowledgement")
    zones=[]
    if plan.get("geometry") and ship.get("status")!="ARRIVAL EXPECTED":
        start=max(at,parse(plan["depart_at"]))
        end=max(start+timedelta(minutes=1),parse(plan["eta"]))
        geometry=plan["geometry"]
        if ship.get("vehicle_position"):
            from .progress import snap
            position=ship["vehicle_position"]
            _,index,point,_=snap(geometry,[position["lon"],position["lat"]])
            geometry=[point,*geometry[index+1:]]
        zones=crossed_zones(geometry,active_zones(operations,start,end),CLEARANCE_KM)
    if zones:
        score=max(score,100);reasons.append(f"{'Approved' if ship.get('approved_at') else 'Saved'} road intersects {len(zones)} active weather zone(s); refresh clearance")
    if closures:
        score=max(score,95);reasons.append("Closure affects a pending facility visit")
    for service in remaining_connections(plan,at):
        if not service.get("ready_at") or not service.get("cutoff_at"):continue
        # A screening upper-bound, not a recomputed ETA. The full review resolves
        # which events fall before each connection and any cascading waits.
        ready=parse(service["ready_at"])+timedelta(minutes=pending_minutes)
        buffer=round((parse(service["cutoff_at"])-ready).total_seconds()/60)
        row={**service,"projected_buffer_minutes":buffer,"screening":True}
        if buffer<0:
            score=max(score,90);reasons.append(f"Connection cutoff at {service['from']} may be missed ({abs(buffer)}m short)")
        elif buffer<30:
            score=max(score,65);reasons.append(f"Only {buffer}m buffer before a connection cutoff")
        if buffer<30:
            connections.append(row)
            decision_by=min(decision_by,service["cutoff_at"]) if decision_by else service["cutoff_at"]
    eta=parse(ship["current_eta"])+timedelta(minutes=pending_minutes)
    deadline=parse(ship["required_delivery"]) if ship.get("required_delivery") else None
    if deadline and eta>deadline:
        score=max(score,80);reasons.append(f"Delivery estimate exceeds deadline by {round((eta-deadline).total_seconds()/60)}m")
    elif deadline and (deadline-eta).total_seconds()<3600:
        score=max(score,55);reasons.append("Less than one hour of delivery buffer")
    if pending_minutes:
        score=max(score,60);reasons.append(f"{pending_minutes}m of newly reported delay needs recalculation")
    if ship["status"]=="ARRIVAL EXPECTED":
        score=max(score,50);reasons.append("Arrival estimate has passed; delivery confirmation outstanding")
    if ship["status"]=="PLANNED" and not ship.get("approved_at"):
        score=max(score,35);reasons.append("Proposal awaiting manager approval")
    return {"priority":"CRITICAL" if score>=90 else "HIGH" if score>=65 else "REVIEW" if score>=35 else "MONITOR",
            "score":score,"reasons":reasons or ["No urgent change detected in stored itinerary"],
            "connections":connections,"weather_zone_ids":[z["id"] for z in zones],"decision_by":decision_by,
            "note":"Screening of stored plans and pending inputs; refresh the journey before deciding."}


def action_comparison(ship):
    options=ship.get("options",[]); approved=ship.get("accepted_plan") or {}
    current_path=ship.get("vehicle_position",{}).get("remaining_path",ship["route"])
    current=next((i for i,o in enumerate(options) if o.get("dispatch_action")!="wait" and o.get("route_id")==approved.get("route_id")),None)
    if current is None:
        current=next((i for i,o in enumerate(options) if o.get("dispatch_action")!="wait" and o["path"]==current_path and o.get("avoidance_status")!="CLEAR"),None)
    reroute=next((i for i,o in enumerate(options) if i!=current and o.get("dispatch_action")!="wait" and approvable(o)),None)
    wait=next((i for i,o in enumerate(options) if o.get("dispatch_action")=="wait" and approvable(o)),None)
    baseline=options[current] if current is not None else None
    rows=[]
    for action,index in (("continue",current),("reroute",reroute),("wait",wait)):
        opt=options[index] if index is not None else None
        clear=bool(opt and approvable(opt))
        rows.append({"action":action,"option_index":index,"available":clear,
                     "reason":("Delay departure, then recheck the full itinerary" if action=="wait" else "Fresh evaluation of the current itinerary" if action=="continue" else "Clear alternative checked against current conditions") if clear else
                              "Route affected or capacity unavailable" if opt else "No comparable alternative found" if action=="reroute" else "No bounded wait can be verified from the current inputs" if action=="wait" else "Current itinerary could not be reproduced",
                     "eta":opt["eta"] if opt else None,"deadline_ok":opt["risk"]["deadline_ok"] if opt else None,
                     "distance_km":opt["cost"]["distance_km"] if opt else None,"transport_eur":opt["cost"]["transport_eur"] if opt else None,
                     "fuel_l":opt["cost"]["fuel_l"] if opt else None,"wait_until":opt.get("dispatch_wait_until") if opt else None,
                     "delta":{ "km":round(opt["cost"]["distance_km"]-baseline["cost"]["distance_km"],1),
                               "transport_eur":round(opt["cost"]["transport_eur"]-baseline["cost"]["transport_eur"],2),
                               "fuel_l":round(opt["cost"]["fuel_l"]-baseline["cost"]["fuel_l"],1),
                               "arrival_minutes":round((parse(opt["eta"])-parse(baseline["eta"])).total_seconds()/60)} if opt and baseline else None})
    return rows


def approvable(option):
    return option.get("avoidance_status") in {"CLEAR","NO_ZONE"} and option.get("capacity",{}).get("feasible",True)
