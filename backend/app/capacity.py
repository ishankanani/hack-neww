"""Manager-entered availability and reservations inside this prototype only."""
from datetime import timedelta

from .operations import parse
from .savings import is_demo


def resources(option):
    rows=[]
    for service in option.get("scheduled_services",[]):
        departure=parse(service["departure"])
        rows.append({"kind":"service","resource":service["service_id"],"from":service["from"],"to":service["to"],
                     "start":departure.isoformat(),"end":(departure+timedelta(minutes=1)).isoformat(),"departure":service["departure"]})
    for step in option.get("steps",[]):
        if step["type"]=="handling" and step["location"] in option["path"][1:-1]:
            rows.append({"kind":"hub","resource":step["location"],"start":step["start"],"end":step["end"]})
    return rows


def overlaps(a,b):
    return parse(a["start"])<parse(b["end"]) and parse(a["end"])>parse(b["start"])


def evaluate(option,ctx,ldm):
    records=ctx["operations"].data.get("capacity_records",[])
    checked=[];unverified=[]
    for resource in resources(option):
        matching=[r for r in records if r["kind"]==resource["kind"] and
                  (r.get("service_id") if r["kind"]=="service" else r.get("node"))==resource["resource"] and overlaps(r,resource)]
        if not matching:
            unverified.append(resource);continue
        reserved=0
        for ship in ctx.get("capacity_shipments",[]):
            if ship["id"]==ctx.get("exclude_shipment_id") or not ship.get("approved_at") or ship.get("status")=="DELIVERED":continue
            if ctx.get("is_demo") or is_demo(ship):continue
            for booking in ship.get("capacity_reservations",[]):
                if booking["kind"]==resource["kind"] and booking["resource"]==resource["resource"] and overlaps(booking,resource):
                    reserved+=booking["ldm"]
                    break
        # Overlapping records are conservative limits; managers remove an old
        # record when replacing it with a larger allowance.
        record=min(matching,key=lambda r:r["available_ldm"])
        free=max(0,round(record["available_ldm"]-reserved,2))
        checked.append({**resource,"record_id":record["id"],"available_ldm":free,"reserved_ldm":round(reserved,2),
                        "requested_ldm":ldm,"feasible":free>=ldm,"source":"MANAGER ENTERED / prototype reservations","reason":record["reason"]})
    feasible=all(r["feasible"] for r in checked)
    return {"feasible":feasible,"status":"INSUFFICIENT" if not feasible else "PARTIAL" if checked and unverified else "CHECKED" if checked else "UNVERIFIED",
            "requested_ldm":ldm,"checks":checked,"unverified_resources":unverified,
            "source":"Manager-entered limits, before this prototype's reservations. Loading metres are estimated from weight; carrier booking capacity is unverified."}


def reservations(option):
    # Reserve all identifiable resources, including ones without a limit yet;
    # a limit added later must see already-approved prototype commitments.
    return [{**r,"ldm":option["ldm"]} for r in resources(option)]
