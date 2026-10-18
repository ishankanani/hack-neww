"""Reported vehicle progress, kept separate from simulated GPS and proof of delivery."""
import math
import uuid
from datetime import datetime, timedelta, timezone

from .operations import parse
from .weather_routes import _distance_km, _point_at, _route_length, _xy

VEHICLE_NODE="@vehicle"
MAX_POSITION_AGE=timedelta(minutes=15)


def dispatched(ship):
    return bool(ship.get("movement_started_at")) or ship.get("status") in {"IN TRANSIT","DELAYED","ARRIVAL EXPECTED"}


def snap(geometry, point):
    if not geometry or len(geometry)<2: raise ValueError("Approved road geometry is unavailable; record a new road plan first")
    best=None;walked=0
    for index,(a,b) in enumerate(zip(geometry,geometry[1:])):
        ax,ay=_xy(a,point);bx,by=_xy(b,point);dx,dy=bx-ax,by-ay
        fraction=max(0,min(1,-(ax*dx+ay*dy)/(dx*dx+dy*dy))) if dx*dx+dy*dy else 0
        distance=math.hypot(ax+fraction*dx,ay+fraction*dy)
        length=_distance_km(a,b)
        candidate=(distance,index,[a[0]+fraction*(b[0]-a[0]),a[1]+fraction*(b[1]-a[1])],walked+fraction*length)
        if best is None or candidate[0]<best[0]:best=candidate
        walked+=length
    return best


def position_report(ship, network, lat=None, lon=None, source="DRIVER REPORTED", reported_at=None, progress_percent=None, movement_state="MOVING", at=None):
    at=at or datetime.now(timezone.utc)
    if not ship.get("approved_at"):raise ValueError("A manager must approve a route before vehicle updates")
    if ship.get("status")=="DELIVERED":raise ValueError("Delivery is already confirmed")
    if ship.get("hold") and movement_state!="STOPPED":raise ValueError("Manager hold remains active; record a stopped position until a clear route is approved")
    reported=parse(reported_at) if reported_at else at
    if reported>at+timedelta(seconds=30):raise ValueError("Vehicle report cannot be in the future")
    if at-reported>MAX_POSITION_AGE:raise ValueError("Vehicle position is older than 15 minutes; request a fresh update")
    previous=ship.get("vehicle_position")
    if previous and reported<=parse(previous["reported_at"]):raise ValueError("A newer vehicle report already exists; refresh before reporting")
    approved=ship.get("accepted_plan") or {};geometry=approved.get("geometry")
    if progress_percent is not None:
        if not 0<=progress_percent<=100:raise ValueError("Simulation progress must be between 0 and 100")
        if not geometry:raise ValueError("No approved road geometry to simulate")
        lon,lat=_point_at(geometry,_route_length(geometry)*progress_percent/100)
        source="SIMULATION"
    if lat is None or lon is None:raise ValueError("Provide latitude and longitude, or simulation progress")
    distance,index,point,offset=snap(geometry,[lon,lat])
    if distance>3:raise ValueError("Position is more than 3 km from the approved road. Review the location before rerouting")
    if previous and previous.get("base_quote_id")==approved.get("quote_id") and offset+0.5<previous["offset_km"]:
        raise ValueError("Position goes backwards along the approved route; check the report")
    path=approved.get("path",ship["route"])
    remaining=[]
    for node in path[1:-1]:
        coords=network["nodes"].get(node)
        if coords and snap(geometry,[coords["lon"],coords["lat"]])[3]>offset+0.2:remaining.append(node)
    remaining.append(ship["destination"])
    ratio=min(1,offset/max(.001,_route_length(geometry)))
    spent=approved.get("completed_estimates",{})
    remaining_cost=approved.get("remaining_cost",approved["cost"])
    completed={key:round(spent.get(key,0)+remaining_cost[key]*ratio,2) for key in ("distance_km","transport_eur","fuel_l","fuel_eur")}
    prefix=[*approved.get("completed_geometry",[]),*geometry[:index+1],point]
    return {"id":uuid.uuid4().hex[:12],"lat":point[1],"lon":point[0],"reported_lat":lat,"reported_lon":lon,
            "reported_at":reported.isoformat(),"source":source,"movement_state":movement_state,
            "base_quote_id":approved.get("quote_id"),"offset_km":round(offset,3),"completed_geometry":prefix,
            "remaining_path":[VEHICLE_NODE,*remaining],"completed_estimates":completed,
            "note":"Position snapped to approved road; completed cost and fuel are proportional model allocations, not measured spend."}


def position_context(ctx, ship, at=None):
    at=at or datetime.now(timezone.utc)
    position=ship.get("vehicle_position")
    if not position:raise ValueError("Record a fresh vehicle position before reviewing an in-transit journey")
    if at-parse(position["reported_at"])>MAX_POSITION_AGE:raise ValueError("Vehicle position expired after 15 minutes. Record a fresh report before rerouting")
    nodes=dict(ctx["network"]["nodes"])
    nodes[VEHICLE_NODE]={"id":VEHICLE_NODE,"name":"Reported vehicle position","lat":position["lat"],"lon":position["lon"],"type":"branch","source":position["source"],"transfer_enabled":False}
    return {**ctx,"network":{**ctx["network"],"nodes":nodes},"skip_origin_handling":True,
            "is_demo":ctx.get("is_demo",False) or position["source"]=="SIMULATION"}


def attach_completed(option, position):
    option["remaining_only"]=True;option["position_id"]=position["id"]
    option["vehicle_start"]={k:position[k] for k in ("lat","lon","reported_at","source")}
    option["completed_geometry"]=position["completed_geometry"]
    option["completed_estimates"]=position["completed_estimates"]
    option["remaining_cost"]=dict(option["cost"])
    for key,value in position["completed_estimates"].items():option["cost"][key]=round(option["cost"][key]+value,2)
    baseline=option.get("baseline_snapshot",{}).get("cost")
    if baseline:
        # decorate() shares the direct snapshot object between options. Replace
        # rather than mutating it so the completed prefix is allocated once.
        option["baseline_snapshot"]={**option["baseline_snapshot"],"cost":{**baseline,**{k:round(baseline[k]+v,2) for k,v in position["completed_estimates"].items()}}}
    return option
