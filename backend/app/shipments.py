"""
Shipment lifecycle + persistence. The provided data is aggregate daily operations,
not per-shipment records, so managers CREATE shipments here; each is planned,
costed, risk-scored and scheduled with a real feasibility check. Persisted to a
JSON store (STORE_DIR) so it survives restarts.
"""
from __future__ import annotations

import json
import os
import re
import uuid
import hashlib
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from .review import change_summary
from datetime import datetime, timedelta, timezone

from .cost import journey_cost, cost_per_kg
from .eta import compute_journey
from .risk import assess
from .operations import parse
from .live import DEFAULT_TRUCK
from . import persistence

STORE_DIR = os.environ.get("STORE_DIR", os.path.join(os.getcwd(), "store"))
STORE = os.path.join(STORE_DIR, "shipments.json")
KG_PER_LDM = 1750.0


def shipment_visits_hub_during(ship, event, pending_only=False):
    """Check the approved itinerary, without changing its saved ETA or route."""
    node=event.get("node")
    plan=ship.get("accepted_plan")
    if (not node or not plan or node not in plan.get("path",[]) or
            ship.get("status")=="DELIVERED" or ship.get("demo_session")):
        return False
    if pending_only and event.get("updated_at") and plan.get("evaluated_at") and (
            parse(event["updated_at"])<=parse(plan["evaluated_at"])):
        return False
    steps=plan.get("steps",[])
    event_start,event_end=parse(event["start"]),parse(event["end"])
    for handling in (s for s in steps if s["type"]=="handling" and s["location"]==node):
        arrival=parse(handling["start"])
        departure=next((parse(s["start"]) for s in steps if s["type"]=="drive" and
                        s["location"]==node and parse(s["start"])>=arrival),parse(handling["end"]))
        if event_start<max(departure,arrival+timedelta(minutes=1)) and event_end>arrival:
            return True
    if plan["path"][-1]==node:
        drives=[s for s in steps if s["type"]=="drive"]
        if drives:
            arrival=parse(drives[-1]["end"])
            completion=max(parse(plan["eta"]),arrival+timedelta(minutes=1))
            return event_start<completion and event_end>arrival
    return False


def shipment_traffic_exposure_minutes(ship, event, pending_only=False):
    """Return a trip-level traffic delay when a saved drive overlaps the event."""
    plan=ship.get("accepted_plan")
    if not plan or ship.get("status") not in {"SCHEDULED","IN TRANSIT","DELAYED"} or ship.get("demo_session"):
        return 0
    if pending_only and event.get("updated_at") and plan.get("evaluated_at") and (
            parse(event["updated_at"])<=parse(plan["evaluated_at"])):
        return 0
    path=plan.get("path",[])
    origin,destination=event.get("origin"),event.get("destination")
    global_event=not origin and not destination
    if not global_event and not any(a==origin and b==destination for a,b in zip(path,path[1:])):
        return 0
    start,end=parse(event["start"]),parse(event["end"])
    for step in plan.get("steps",[]):
        if step.get("type")!="drive":continue
        if not global_event and step.get("location")!=origin:continue
        if parse(step["start"])<end and parse(step["end"])>start:
            return max(0,int(event.get("minutes",0)))
    return 0


def _load():
    baseline={}
    try:
        with open(STORE, encoding="utf-8") as fh:
            baseline=json.load(fh)
    except Exception:
        pass
    return persistence.load("shipments.json",baseline,force=True) if persistence.configured() else baseline


def _save(d):
    if persistence.save("shipments.json",d):return
    os.makedirs(STORE_DIR, exist_ok=True)
    temporary = STORE + ".tmp"
    with open(temporary, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=2, default=str)
    os.replace(temporary, STORE)


def _ldm(weight_kg):
    return max(0.5, round((weight_kg or 0) / KG_PER_LDM, 1))


def plan(ctx, origin, destination, depart_utc, weight_kg, required_delivery, value_eur, optimization="fastest", truck=None, required_paths=None, only_paths=None, wait_until=None):
    from .hub_selection import select_hubs, ll
    from .operations import parse
    net=ctx["network"]; operations=ctx["operations"]; ldm=_ldm(weight_kg)
    if ldm>13.6: raise ValueError("Shipment exceeds the prototype single-trailer capacity (13.6 loading metres). Split the shipment.")
    road=ctx["providers"].routing.leg(ll(net["nodes"][origin]),ll(net["nodes"][destination]))
    blocked={e["node"] for e in operations.data.get("events",[]) if e["kind"]=="closure" and e.get("node") and operations.overlaps(e,depart_utc,depart_utc+timedelta(days=7))}
    selected=select_hubs(net["nodes"][origin],net["nodes"][destination],net["nodes"].values(),road,ctx["providers"].routing,{"blocked":blocked,"ldm":ldm})
    paths=[([origin,destination],None)]+[([origin,h["hub"],destination],h) for h in selected]
    for path in required_paths or []:
        if all(n in net["nodes"] for n in path) and path not in [p for p,_ in paths]:
            paths.append((path,None))
    if only_paths is not None: paths=[(path,None) for path in only_paths]
    def build_option(path,hub,avoid=False,road_override=None,road_id=None):
        actual_departure=parse(wait_until) if wait_until else depart_utc
        jr=compute_journey(net,ctx["holidays"],ctx["transfer"],ctx["hub_delays"],ctx["providers"],origin,destination,actual_departure,path,operations,truck,avoid_zones=avoid,skip_origin_handling=ctx.get("skip_origin_handling",False),road_overrides={(origin,destination):road_override} if road_override else None,planning_rules=ctx.get("planning_rules"))
        if wait_until:
            minutes=max(0,round((actual_departure-depart_utc).total_seconds()/60))
            jr["depart_at"]=depart_utc.isoformat();jr["total_minutes"]+=minutes
            jr["components"]["manager_wait"]=minutes
            jr["steps"].insert(0,{"type":"manager_wait","location":origin,"location_name":net["nodes"][origin]["name"],"start":depart_utc.isoformat(),"end":actual_departure.isoformat(),"minutes":minutes,"detail":"Wait at departure facility, then re-evaluate loading and service eligibility","source":"MANAGER WAIT COMPARISON"})
            jr["dispatch_action"]="wait";jr["dispatch_wait_until"]=wait_until
        # Use the SAME road distances for fuel, cost and map/ETA.
        cost_net={**net,"edges":dict(net["edges"])}
        for leg in jr["road_legs"]:
            key=leg["from"]+"-"+leg["to"]
            edge=cost_net["edges"].get(key,{"cost_eur":round(leg["km"]*2.6),"capacity_ldm":13.6})
            cost_net["edges"][key]={**edge,"km":leg["km"]}
        c=journey_cost(cost_net,path,ldm)
        known=all(a+"-"+b in net["edges"] for a,b in zip(path,path[1:]))
        surcharge=round(jr["detour_km"]*2.6*min(1,max(.15,ldm/13.6))) if avoid and known else 0
        c["transport_eur"]+=surcharge
        # Only attach lane histories for actual dataset edges, not unrelated endpoint histories.
        relations={net["edges"][a+"-"+b]["relation"] for a,b in zip(path,path[1:]) if a+"-"+b in net["edges"]}
        hist=[ctx["history"][r] for r in relations if r in ctx["history"]]
        risk=assess(jr,required_delivery,value_eur,hist)
        if jr["weather_alerts"]:
            risk["reasons"].append("Weather alert adds a modelled delay")
            risk["score"]+=25
        if jr["zone_impacts"]:
            risk["reasons"].append("Road crosses a manually simulated weather zone; assumed delay included")
            risk["score"]+=35
        if avoid:
            risk["reasons"].append("Provider road geometry verified outside every active simulated zone (+2 km margin)")
        if jr["components"]["hub_delay"] or jr["components"]["traffic"]:
            risk["reasons"].append("Active operational events included in ETA")
            risk["score"]+=20
        risk["level"]="HIGH" if risk["score"]>=55 else "MEDIUM" if risk["score"]>=25 else "LOW"
        return {**jr,"route_id":"-".join(path)+(f":road-{road_id}" if road_id else "")+(":clear" if avoid else ":normal"),"label":(f"Via {hub['name']} · clear detour" if hub else "Weather-safe road detour") if avoid else f"Via {hub['name']}" if hub else "Alternative road" if road_id else "Direct road estimate","kind":"dataset_lane" if known else "estimate",
                        "intermediate_hub":hub,"recommendation_note":"User-entered timetable applied; capacity is unverified." if jr.get("scheduled_services") else "Next eligible movement estimate — departure availability unverified.",
                        "is_demo":ctx.get("is_demo",False), "vehicle_constraints":"Truck profile requested" if "TomTom" in jr["data_sources"]["transport"] else "Vehicle restrictions unverified by fallback routing",
                        "cost":{"transport_eur":c["transport_eur"],"fuel_l":c["fuel_l"],"fuel_eur":c["fuel_eur"],"distance_km":round(c["km"],1),"cost_per_kg":cost_per_kg(c["transport_eur"],weight_kg),"detour_surcharge_eur":surcharge},
                        "risk":risk,"ldm":ldm,"historical":_hist_summary(hist),"revision":operations.data["revision"]}
    def evaluate_path(item):
        path,hub=item
        options=[build_option(path,hub)]
        if options[0]["zone_impacts"]:
            try: options.append(build_option(path,hub,True))
            except ValueError: options[0]["avoidance_status"]="NO_CLEAR_DETOUR"
        return options
    # Each itinerary is independent; preserve deterministic ordering while
    # overlapping provider waits. Every candidate still checks all weather zones.
    with ThreadPoolExecutor(max_workers=min(4,len(paths))) as pool:
        options=[option for group in pool.map(evaluate_path,paths) for option in group]
    # Ask for real road alternatives, rather than treating a transfer stop as a
    # different road. Each is costed and checked by the same journey engine.
    if only_paths is None and not wait_until:
        direct=next(o for o in options if o["path"]==[origin,destination] and not o["weather_detours"])
        departure=parse(direct["road_legs"][0]["departure"])
        providers=ctx["providers"];tomtom=getattr(providers,"tomtom",None)
        choices=tomtom.alternatives(ll(net["nodes"][origin]),ll(net["nodes"][destination]),departure,truck or DEFAULT_TRUCK) if tomtom and hasattr(tomtom,"alternatives") else []
        if not choices and hasattr(providers.routing,"alternatives"):
            choices=providers.routing.alternatives(ll(net["nodes"][origin]),ll(net["nodes"][destination]))
        def signature(geometry):
            cells=[]
            for point in geometry or []:
                cell=(round(point[0],2),round(point[1],2))
                if not cells or cells[-1]!=cell:cells.append(cell)
            return hashlib.sha1(json.dumps(cells).encode()).hexdigest()[:12]
        seen={signature(o.get("geometry")) for o in options}
        extra=[]
        for road_choice in choices:
            key=signature(road_choice.get("geometry"))
            if not road_choice.get("geometry") or key in seen:continue
            seen.add(key);extra.append((road_choice,key))
        with ThreadPoolExecutor(max_workers=2) as pool:
            additions=list(pool.map(lambda pair:build_option([origin,destination],None,road_override=pair[0],road_id=pair[1]),extra[:2]))
        for i,option in enumerate(additions,1):option["label"]=f"Alternative road {i}"
        options.extend(additions)
    from .optimization import decorate
    from .capacity import evaluate as evaluate_capacity
    from .manager_routes import add_route_constraints
    for option in options:
        if len(option["path"])>2 and not option.get("intermediate_hub"):
            option["label"]="Via "+" → ".join(net["nodes"][n]["name"] for n in option["path"][1:-1])+(" · clear detour" if option["avoidance_status"]=="CLEAR" else "")
        option["capacity"]=evaluate_capacity(option,ctx,ldm)
        add_route_constraints(option,net)
    from .reliability import arrival_evidence
    for option in options:option["arrival_evidence"]=arrival_evidence(ctx.get("capacity_shipments",[]),ctx.get("original_origin",origin),destination,option["eta"],ctx.get("skip_origin_handling",False))
    from .dispatch import connection_warnings
    options=decorate(options,ctx,origin,destination,ldm,optimization)
    for option in options:
        option["connections"]=connection_warnings(option)
        if wait_until:
            option["route_id"]+=":wait";option["label"]="Wait at departure facility"
    return options


def _hist_summary(lane_hist):
    if not lane_hist:
        return None
    n = len(lane_hist)
    return {
        "avg_cost_eur": round(sum(h["avg_daily_cost_eur"] for h in lane_hist) / n),
        "avg_fuel_l": round(sum(h["avg_daily_fuel_l"] for h in lane_hist) / n),
        "reliability_pct": round(sum(h["reliability_pct"] for h in lane_hist) / n, 1),
        "samples": sum(h["samples"] for h in lane_hist),
    }


def savings_vs_baseline(recommended, baseline):
    """Estimated savings of recommended vs a baseline option (not guaranteed)."""
    return {
        "money_eur": baseline["cost"]["transport_eur"] - recommended["cost"]["transport_eur"],
        "fuel_l": baseline["cost"]["fuel_l"] - recommended["cost"]["fuel_l"],
        "time_min": baseline["total_minutes"] - recommended["total_minutes"],
        "note": "Estimated, not guaranteed — based on tariffs (relationen.csv) and current plan.",
    }


def review_options(ctx, ship):
    """One reproducible option set for review and approval, including a bounded wait."""
    from .dispatch import connection_warnings
    from .progress import dispatched,position_context,attach_completed,VEHICLE_NODE
    remaining=dispatched(ship)
    if remaining:ctx=position_context(ctx,ship)
    ctx={**ctx,"original_origin":ship["origin"],"planning_rules":ship.get("planning_rules")}
    origin=VEHICLE_NODE if remaining else ship["origin"]
    destination=ship["destination"]
    path=ship["vehicle_position"]["remaining_path"] if remaining else ship["route"]
    args=(ctx,origin,ship["destination"],datetime.now(timezone.utc) if remaining else parse(ship["planned_departure"]),ship["weight_kg"],
          ship.get("required_delivery"),ship.get("value_eur",0),ship.get("optimization","fastest"),ship.get("truck"))
    reported_delay=ship.get("reported_delay")
    if reported_delay and parse(reported_delay["until"])>args[3]:
        minutes=max(0,round((parse(reported_delay["until"])-args[3]).total_seconds()/60))
        ctx["hub_delays"]={**ctx["hub_delays"],origin:{"minutes":minutes+ctx["hub_delays"].get(origin,{}).get("minutes",0),"reason":"Driver report: "+reported_delay["reason"]}}
    request=ship.get("manager_route_request")
    requested_path=None
    if request:
        from .manager_routes import validate_path
        requested_path=validate_path(ctx["network"],origin,destination,request["via_hubs"])
        if request.get("depart_at") and not remaining:
            args=(*args[:3],parse(request["depart_at"]),*args[4:])
    options=plan(*args,required_paths=[path]+([requested_path] if requested_path else []))
    if requested_path:
        for option in options:option["manager_requested"]=option["path"]==requested_path
    current=next((o for o in options if o["path"]==path and o.get("avoidance_status")!="CLEAR"),None)
    departure=parse(ship["planned_departure"])
    if current and not ship.get("vehicle_position"):
        zone_ids={z["id"] for z in current.get("zone_impacts",[])}
        ends=[parse(z["end"]) for z in ctx["operations"].data.get("weather_zones",[]) if z["id"] in zone_ids]
        ends.extend(parse(e["end"]) for e in ctx["operations"].data.get("events",[]) if e["kind"]=="closure" and e.get("node") in ship["route"] and parse(e["start"])<parse(current["eta"]) and parse(e["end"])>departure)
        if ends:
            release=max(ends)+timedelta(minutes=1)
            if departure<release<=departure+timedelta(hours=24):
                try: options.extend(plan(*args,only_paths=[ship["route"]],wait_until=release.isoformat()))
                except ValueError: pass
    for option in options:
        option["connections"]=connection_warnings(option,ship.get("accepted_plan"))
        if current and option.get("dispatch_action")=="wait":
            option["comparison"]={"baseline":"Current itinerary without waiting, under the same conditions","money_saved_eur":current["cost"]["transport_eur"]-option["cost"]["transport_eur"],"minutes_saved":current["total_minutes"]-option["total_minutes"],"fuel_saved_l":current["cost"]["fuel_l"]-option["cost"]["fuel_l"]}
            option["baseline_snapshot"]={k:deepcopy(current[k]) for k in ("path","depart_at","eta","total_minutes","cost","revision")}
    if remaining:
        for option in options:option["baseline_snapshot"]=deepcopy(option.get("baseline_snapshot",{}))
        for option in options:
            attach_completed(option,ship["vehicle_position"])
            option["cost"]["cost_per_kg"]=cost_per_kg(option["cost"]["transport_eur"],ship["weight_kg"])
    from .dispatch import approvable
    objective=ship.get("optimization","fastest")
    def rank(option):
        value=option["cost"]["transport_eur"] if objective=="cost" else option["cost"]["transport_eur"]+option["total_minutes"]*50/60 if objective=="balanced" else option["total_minutes"]
        return (not approvable(option),not option["risk"]["deadline_ok"],value,option["total_minutes"])
    options.sort(key=rank)
    eligible=[o for o in options if approvable(o)]
    eligible=[o for o in eligible if o["risk"]["deadline_ok"]] or eligible
    choices=[("Fastest",min(eligible,key=lambda o:o["total_minutes"])),("Lowest cost",min(eligible,key=lambda o:o["cost"]["transport_eur"])),("Balanced",min(eligible,key=lambda o:o["cost"]["transport_eur"]+o["total_minutes"]*50/60))] if eligible else []
    for option in options:option["badges"]=[label for label,choice in choices if option is choice]
    return options


class Shipments:
    def __init__(self, ctx):
        self.ctx = ctx
        self.data = _load()
        migrated = False
        for ship in self.data.values():
            if ship.get("status")=="DELIVERED" and not ship.get("actual") and not ship.get("delivery_confirmation"):
                ship["status"]="ARRIVAL EXPECTED" if ship.get("approved_at") else "PLANNED"
                migrated=True
            if "accepted_plan" not in ship:
                ship["accepted_plan"] = next((o for o in ship.get("options",[]) if o["path"] == ship["route"]), None)
            if not ship.get("data_kind"):
                # Plans saved before data_kind existed. Seeded sample rows carry a
                # customer segment and a generated container reference; nothing the
                # planner creates ever does, so the signature is unambiguous.
                seeded = bool(ship.get("customer_segment")) and bool(
                    re.fullmatch(r"C[0-9A-F]{5}", str(ship.get("container") or "")))
                ship["data_kind"] = "demo" if seeded else "user"
                migrated = True
        if migrated:
            _save(self.data)

    def repair_comparisons(self):
        """Give older saved plans a baseline comparison from their own stored options.

        Nothing is re-planned and no provider is called, so historical plans keep
        the numbers they were approved on. Returns how many plans were repaired.
        """
        from .savings import comparison_for, BASIS_LEGACY
        repaired = 0
        for ship in self.data.values():
            plan = ship.get("accepted_plan")
            if not plan or plan.get("comparison"):
                continue
            comparison, basis = comparison_for(ship)
            if comparison and basis != BASIS_LEGACY:
                plan["comparison"] = comparison
                plan.setdefault("comparison_basis", basis)
                repaired += 1
        if repaired:
            _save(self.data)
        return repaired

    def seed_if_empty(self):
        if self.data:
            return
        net = self.ctx["network"]
        base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        samples = [
            ("R01", "R11", 8200, 42000, base + timedelta(hours=2), base + timedelta(days=2, hours=9), "Top"),
            ("R11", "R24", 15400, 180000, base + timedelta(hours=6), base + timedelta(days=2), "Top"),
            ("R08", "R03", 3100, 12000, base + timedelta(days=1), base + timedelta(days=3), "Standard"),
            ("R16", "R21", 21000, 810000, _next_friday(base, 16), _next_monday(_next_friday(base, 16), 9), "Top"),
        ]
        for o, d, w, v, dep, req, seg in samples:
            self.create({"origin": o, "destination": d, "weight_kg": w, "value_eur": v,
                         "planned_departure": dep.isoformat(), "required_delivery": req.isoformat(),
                         "data_kind":"demo", "customer_segment": seg, "container": f"C{uuid.uuid4().hex[:5].upper()}"})

    def context_for(self, ship):
        ctx=self.ctx
        if ship.get("demo_session"):
            from .demo import context
            ctx=context(self.ctx,ship["demo_session"])
        return {**ctx,"capacity_shipments":list(self.data.values()),"exclude_shipment_id":ship.get("id")}

    def create(self, p):
        sid = "SHP-" + uuid.uuid4().hex[:6].upper()
        if p.get("selected_path"):
            from .manager_routes import validate_path
            selected=p["selected_path"]
            if len(selected)<2 or selected[0]!=p["origin"] or selected[-1]!=p["destination"]:
                raise ValueError("Selected route must start at the shipment origin and end at its destination")
            validate_path(self.ctx["network"],p["origin"],p["destination"],selected[1:-1])
        dep = datetime.fromisoformat(p["planned_departure"].replace("Z", "+00:00")).astimezone(timezone.utc)
        opts = plan({**self.context_for(p),"planning_rules":p.get("planning_rules")}, p["origin"], p["destination"], dep, p.get("weight_kg", 0),
                    p.get("required_delivery"), p.get("value_eur", 0), p.get("optimization","fastest"),p.get("truck"),required_paths=[p["selected_path"]] if p.get("selected_path") else None)
        chosen = next((i for i,o in enumerate(opts) if o.get("route_id") == p.get("selected_route_id")), -1) if p.get("selected_route_id") else -1
        if chosen<0: chosen = next((i for i,o in enumerate(opts) if o["path"] == p.get("selected_path")), 0)
        if p.get("selected_route_id") and opts[chosen].get("route_id") != p["selected_route_id"]: raise ValueError("Selected road detour is no longer available. Recalculate first.")
        if p.get("selected_path") and opts[chosen]["path"] != p["selected_path"]: raise ValueError("Selected route is no longer available. Recalculate first.")
        rec = opts[chosen]
        ship = {
            "data_kind":"demo" if p.get("demo_session") or p.get("data_kind")=="demo" else "user", "demo_session":p.get("demo_session"),
            "optimization": p.get("optimization","fastest"), "truck": p.get("truck"), "planning_rules":p.get("planning_rules"),
            "id": sid, "origin": p["origin"], "destination": p["destination"],
            "current_location": p["origin"], "route": rec["path"],
            "next_hub": rec["path"][1] if len(rec["path"]) > 1 else None,
            "status": "PLANNED",
            "planned_departure": p["planned_departure"], "scheduled_departure": None,
            "current_eta": rec["eta"], "required_delivery": p.get("required_delivery"),
            "distance_km": rec["cost"]["distance_km"], "weight_kg": p.get("weight_kg", 0),
            "container": p.get("container"), "value_eur": p.get("value_eur", 0),
            "est_cost_eur": rec["cost"]["transport_eur"], "est_fuel_l": rec["cost"]["fuel_l"],
            "cost_per_kg": rec["cost"]["cost_per_kg"], "risk_level": rec["risk"]["level"],
            "customer_segment": p.get("customer_segment"),
            "alert": None if rec["risk"]["deadline_ok"] else "Delivery deadline at risk",
            "options": opts, "selected_option": chosen, "accepted_plan": deepcopy(rec), "created_at": datetime.now(timezone.utc).isoformat(),
        }
        ship["delay_minutes"] = _delay(rec["eta"], p.get("required_delivery"))
        self.data[sid] = ship
        _save(self.data)
        return ship

    def schedule(self, sid, option_index=0, force=False, quote_id=None, decision_reason=None):
        s = self.data.get(sid)
        if not s:
            return None, "unknown shipment"
        from .progress import dispatched,position_context
        if s["status"]=="DELIVERED":raise ValueError("Delivery is already confirmed")
        moving=dispatched(s)
        if moving:
            position_context(self.context_for(s),s)
        if not 0 <= option_index < len(s["options"]): raise ValueError("Invalid route option")
        opt = s["options"][option_index]
        if not opt.get("route_feasible",True):raise ValueError("; ".join(opt.get("unavailable_reasons",[])) or "Requested road connection is unavailable")
        if moving and opt.get("position_id")!=s["vehicle_position"]["id"]:raise ValueError("Vehicle position changed. Recalculate remaining route before approval")
        if not opt.get("capacity",{}).get("feasible",True):raise ValueError("Insufficient hub or service capacity. Choose another option or wait")
        if opt.get("avoidance_status") in {"IMPACTED", "NO_CLEAR_DETOUR"}:
            raise ValueError("Route crosses an active simulated weather zone. Hold the shipment or choose a clear route.")
        if quote_id is not None and quote_id!=opt.get("quote_id"): raise ValueError("This quote was replaced. Recalculate and review again.")
        ctx=self.context_for(s)
        if s.get("hold") and not moving and parse(s["planned_departure"])<datetime.now(timezone.utc):
            raise ValueError("The held departure is in the past. Recalculate before releasing the hold.")
        if opt.get("revision", -1) != ctx["operations"].data["revision"]: raise ValueError("Conditions changed. Recalculate the shipment before scheduling.")
        fresh=review_options(ctx,s)
        candidate=next((o for o in fresh if o.get("route_id")==opt.get("route_id")),None)
        if candidate and not candidate.get("capacity",{}).get("feasible",True):raise ValueError("Capacity changed during approval. Recalculate and choose an available option")
        if candidate and moving and not candidate.get("geometry"):raise ValueError("Remaining road geometry is unavailable; a reroute cannot be approved")
        if candidate and candidate.get("avoidance_status") in {"IMPACTED", "NO_CLEAR_DETOUR"}:
            raise ValueError("Weather conditions changed. Hold the shipment and recalculate a clear route.")
        if candidate is None or change_summary(opt,candidate)["material"]:
            s["options"]=fresh
            s["plan_change"]=change_summary(s.get("accepted_plan"),fresh[0])
            _save(self.data)
            raise ValueError("Live conditions changed during approval. Recalculate and review the updated options; saved plan was retained.")
        # The freshly checked quote is the plan we actually approve and persist.
        approved = candidate
        approved_index = fresh.index(candidate)
        if not approved["risk"]["deadline_ok"] and not force:
            # feasibility warning BEFORE committing
            return s, f"WARNING: selected route misses delivery window (ETA {approved['eta']}). Schedule anyway or pick another route."
        # What would have happened had we kept the previously approved path? The
        # counterfactual is that same path re-evaluated under the CURRENT
        # conditions, which is exactly what this option set already contains.
        previous_plan=s.get("accepted_plan") or {}
        previous=previous_plan.get("path")
        # An initial proposal is not an approved counterfactual. Each approval
        # replaces the attribution instead of carrying stale benefits forward.
        s.pop("disruption_savings",None)
        if s.get("approved_at") and previous and previous_plan.get("route_id")!=approved.get("route_id"):
            stayed = next((o for o in fresh if o.get("route_id")==previous_plan.get("route_id")), None)
            if stayed:
                rescued = bool(approved["risk"]["deadline_ok"]) and not stayed["risk"]["deadline_ok"]
                s["disruption_savings"] = {
                    "approved_quote_id":approved.get("quote_id"),
                    "minutes_avoided": round(stayed["total_minutes"] - approved["total_minutes"]),
                    "cost_delta_eur": round(approved["cost"]["transport_eur"] - stayed["cost"]["transport_eur"], 2),
                    "fuel_delta_l": round(approved["cost"]["fuel_l"] - stayed["cost"]["fuel_l"], 1),
                    "deadline_rescued": rescued,
                    "exposure_avoided_eur": round(stayed["risk"]["exposure_eur"], 2) if rescued else 0,
                    "previous_path": previous, "new_path": approved["path"],
                    "counterfactual_eta": stayed["eta"], "approved_eta": approved["eta"],
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "basis": "Previously approved path re-evaluated under the conditions in force at approval",
                }
        s["options"] = fresh
        from .capacity import reservations
        s["capacity_reservations"]=reservations(approved)
        s.setdefault("approval_history",[]).append({"quote_id":previous_plan.get("quote_id"),"path":previous_plan.get("path"),"eta":previous_plan.get("eta"),"at":s.get("approved_at"),"reason":s.get("approval_reason")})
        s.pop("hold",None)
        request=s.pop("manager_route_request",None)
        if request and request.get("depart_at") and not moving:s["planned_departure"]=approved["depart_at"]
        if moving:s.pop("stop_request",None)
        s.update({"status": "IN TRANSIT" if moving else "SCHEDULED", "approval_reason":decision_reason, "scheduled_departure": s.get("scheduled_departure") if moving else next((step["start"] for step in approved["steps"] if step["type"]=="drive"),s["planned_departure"]),
                  "route": approved["path"], "current_eta": approved["eta"],
                  "est_cost_eur": approved["cost"]["transport_eur"], "est_fuel_l": approved["cost"]["fuel_l"],
                  "risk_level": approved["risk"]["level"], "selected_option": approved_index, "accepted_plan": deepcopy(approved), "approved_at":datetime.now(timezone.utc).isoformat(), "plan_change":None,
                  "next_hub": approved["path"][1], "distance_km": approved["cost"]["distance_km"], "cost_per_kg": approved["cost"]["cost_per_kg"],
                  "delay_minutes": _delay(approved["eta"],s.get("required_delivery")), "alert": None if approved["risk"]["deadline_ok"] else "Delivery deadline at risk"})
        _save(self.data)
        return s, None

    def hold(self, sid, option_index, reason):
        s=self.data[sid]
        from .progress import dispatched
        if s["status"]=="DELIVERED":raise ValueError("Delivery is already confirmed")
        if not reason.strip() or len(reason.strip())<3: raise ValueError("Enter a reason for the hold")
        if not 0<=option_index<len(s["options"]): raise ValueError("Invalid route option")
        opt=s["options"][option_index]
        if dispatched(s) and not s.get("hold"):
            s["stop_request"]={"status":"REQUESTED","reason":reason.strip(),"at":datetime.now(timezone.utc).isoformat(),"path":list(opt["path"])}
            s["alert"]="Safe-stop request awaiting driver acknowledgement"
            _save(self.data)
            return s
        # Store the exact reviewed route separately. A hold does not approve an
        # unsafe plan or overwrite an earlier approved route/ETA.
        s["hold"]={"reason":reason.strip(),"at":datetime.now(timezone.utc).isoformat(),
                   "previous_status":s.get("hold",{}).get("previous_status",s["status"]),
                   "route_id":opt.get("route_id"),"path":list(opt["path"]),"plan":deepcopy(opt)}
        s["status"]="ON HOLD"
        s["alert"]="Manager hold — "+reason.strip()
        s["scheduled_departure"]=None
        _save(self.data)
        return s

    def replan(self, sid, from_now=False):
        s=self.data[sid]
        from .progress import dispatched
        if s["status"]=="DELIVERED":raise ValueError("Delivery is already confirmed")
        if (s.get("hold") or from_now) and not dispatched(s) and not s.get("demo_session") and parse(s["planned_departure"])<datetime.now(timezone.utc):
            # A resumed shipment cannot use its missed departure. The old
            # accepted plan remains intact for the manager's comparison.
            s["planned_departure"]=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat()
        s["options"]=review_options(self.context_for(s),s)
        from .dispatch import connection_warnings
        for option in s["options"]: option["connections"]=connection_warnings(option,s.get("accepted_plan"))
        s["plan_change"]=change_summary(s.get("accepted_plan"),s["options"][0])
        _save(self.data)
        return s

    def update_position(self,sid,report):
        from .progress import position_report
        s=self.data[sid]
        position=position_report(s,self.ctx["network"],**report)
        s["vehicle_position"]=position
        s["simulation_used"]=s.get("simulation_used",False) or position["source"]=="SIMULATION"
        s.setdefault("movement_started_at",s.get("scheduled_departure") or datetime.now(timezone.utc).isoformat())
        s.setdefault("driver_updates",[]).append({"kind":"position","reported_at":position["reported_at"],"source":position["source"],"lat":position["lat"],"lon":position["lon"],"movement_state":position["movement_state"]})
        if not s.get("hold"):s["status"]="IN TRANSIT"
        _save(self.data)
        return s

    def driver_event(self,sid,event):
        s=self.data[sid]
        if not s.get("approved_at"):raise ValueError("Approve the shipment before driver updates")
        if s["status"]=="DELIVERED":raise ValueError("Delivery is already confirmed")
        now=datetime.now(timezone.utc)
        when=parse(event["at"]) if event.get("at") else now
        if when>now:raise ValueError("Reported event time cannot be in the future")
        from .savings import is_demo
        kind=event["kind"];source="SIMULATION" if is_demo(s) else "DRIVER REPORTED"
        reference=event.get("reference","").strip()
        if kind=="departed":
            if s.get("hold"):raise ValueError("Release the manager hold before departure")
            if s.get("actual_departure"):raise ValueError("Departure already recorded")
            s["actual_departure"]=when.isoformat();s["movement_started_at"]=when.isoformat();s["status"]="IN TRANSIT"
        elif kind=="delay":
            if not 1<=(event.get("minutes") or 0)<=1440 or len(reference)<3:raise ValueError("Enter a delay of 1–1440 minutes and a reason")
            s["reported_delay"]={"minutes":event["minutes"],"reason":reference,"at":when.isoformat(),"reported_at":now.isoformat(),"until":(when+timedelta(minutes=event["minutes"])).isoformat(),"source":source}
            s["alert"]="Driver delay: "+reference
        elif kind=="safe_stop":
            if not s.get("stop_request") or s["stop_request"]["status"]!="REQUESTED":raise ValueError("No pending safe-stop request")
            from .progress import position_context
            position_context(self.context_for(s),s)
            if s["vehicle_position"]["movement_state"]!="STOPPED":raise ValueError("Record a fresh stopped position first")
            if len(reference)<3:raise ValueError("Identify the safe stopping location")
            request=s["stop_request"]
            s["hold"]={"reason":request["reason"],"at":when.isoformat(),"previous_status":s["status"],"route_id":s["accepted_plan"].get("route_id"),"path":list(s["route"]),"plan":deepcopy(s["accepted_plan"]),"stop_reference":reference}
            request.update({"status":"ACKNOWLEDGED","reference":reference,"acknowledged_at":when.isoformat()})
            s["status"]="ON HOLD";s["alert"]="Stopped at reported location: "+reference
        elif kind=="arrived":
            if s.get("hold"):raise ValueError("Shipment is held; release it before confirming destination arrival")
            if len(reference)<3:raise ValueError("Enter a delivery or recipient reference")
            if s.get("actual_departure") and when<parse(s["actual_departure"]):raise ValueError("Arrival must follow reported departure")
            if event.get("actual_cost_eur") is not None and not s.get("actual_departure"):raise ValueError("Record the actual departure before adding actual cost; arrival can be confirmed without a cost")
            s["delivery_confirmation"]={"at":when.isoformat(),"source":source,"reference":reference}
            s["status"]="DELIVERED";s["alert"]=None;s.pop("stop_request",None)
            if event.get("actual_cost_eur") is not None:
                self.record_outcome(sid,{"actual_departure":s["actual_departure"],"actual_arrival":when.isoformat(),"actual_cost_eur":event["actual_cost_eur"],"delivery_reference":reference})
        else:raise ValueError("Unknown driver event")
        s.setdefault("driver_updates",[]).append({"kind":kind,"reported_at":now.isoformat(),"at":when.isoformat(),"reference":reference,"source":source,"minutes":event.get("minutes")})
        _save(self.data)
        return s

    def set_status(self, sid, status):
        if status not in {"PLANNED","SCHEDULED","IN TRANSIT","DELAYED","DELIVERED"}: raise ValueError("Invalid shipment status")
        s = self.data.get(sid)
        if s:
            if s.get("status")=="DELIVERED" and status!="DELIVERED":raise ValueError("Delivery is confirmed. Create a new journey instead of reopening this record")
            if s.get("hold"): raise ValueError("Shipment is on hold. Recalculate and approve a clear route in the control room to release it.")
            if status in {"SCHEDULED","IN TRANSIT"} and not s.get("approved_at"): raise ValueError("A manager must approve a plan first")
            if status=="DELIVERED":
                if not s.get("approved_at"): raise ValueError("Approve the shipment before confirming delivery")
                s["delivery_confirmation"]={"at":datetime.now(timezone.utc).isoformat(),"source":"MANAGER REPORTED","reference":None}
            s["status"] = status; _save(self.data)
        return s

    def record_outcome(self, sid, outcome):
        s=self.data[sid]
        if not s.get("approved_at"): raise ValueError("Actual comparison requires a manager-approved plan")
        if s.get("hold"): raise ValueError("Release the hold and confirm movement before recording delivery")
        baseline=s["accepted_plan"]
        departure=datetime.fromisoformat(outcome["actual_departure"])
        arrival=datetime.fromisoformat(outcome["actual_arrival"])
        if arrival<departure: raise ValueError("Actual arrival must follow actual departure")
        if s.get("data_kind")!="demo" and arrival>datetime.now(timezone.utc): raise ValueError("Actual arrival cannot be in the future")
        error=round((arrival-datetime.fromisoformat(baseline["eta"])).total_seconds()/60)
        actual={**outcome,"recorded_at":datetime.now(timezone.utc).isoformat(),"arrival_error_minutes":error,"cost_error_eur":round(outcome["actual_cost_eur"]-baseline["cost"]["transport_eur"],2),"on_time":arrival<=datetime.fromisoformat(s["required_delivery"]) if s.get("required_delivery") else None,"source":"DEMO OUTCOME" if s.get("simulation_used") or s.get("data_kind")=="demo" or baseline.get("is_demo") else "USER-REPORTED ACTUAL","accepted_quote_id":baseline.get("quote_id")}
        s.setdefault("outcome_history",[]).append(deepcopy(actual))
        s["actual"]=actual
        s["status"]="DELIVERED"
        s["delivery_confirmation"]={"at":outcome["actual_arrival"],"source":actual["source"],"reference":outcome.get("delivery_reference")}
        _save(self.data)
        return s

    def list(self):
        changed = False
        for ship in self.data.values():
            if _advance_time_status(ship):
                changed = True
        if changed and (not persistence.configured() or persistence.writing()):
            _save(self.data)
        return sorted(self.data.values(), key=lambda x: x["created_at"], reverse=True)

    def get(self, sid):
        ship = self.data.get(sid)
        if ship and _advance_time_status(ship) and (not persistence.configured() or persistence.writing()):
            _save(self.data)
        return ship


def _delay(eta, required):
    if not required:
        return 0
    e = datetime.fromisoformat(eta); r = datetime.fromisoformat(required.replace("Z", "+00:00"))
    return max(0, int((e - r).total_seconds() // 60))


def _advance_time_status(ship, at=None):
    """Advance approved shipments using the plan clock; this is not GPS proof."""
    if ship.get("status") not in {"SCHEDULED", "IN TRANSIT", "DELAYED", "ARRIVAL EXPECTED"}:
        return False
    at = at or datetime.now(timezone.utc)
    try:
        eta = parse(ship["current_eta"])
    except (KeyError, TypeError, ValueError):
        return False
    if eta <= at:
        next_status = "DELIVERED" if ship.get("delivery_confirmation") or ship.get("actual") else "ARRIVAL EXPECTED"
    else:
        try:
            deadline = parse(ship["required_delivery"]) if ship.get("required_delivery") else None
        except (TypeError, ValueError):
            deadline = None
        if deadline and deadline <= at:
            next_status = "DELAYED"
        elif ship.get("status") == "SCHEDULED":
            try:
                departure = parse(ship.get("scheduled_departure") or ship["planned_departure"])
            except (KeyError, TypeError, ValueError):
                departure = None
            next_status = "IN TRANSIT" if departure and departure <= at else "SCHEDULED"
        else:
            next_status = ship["status"]
    if next_status == ship["status"]:
        return False
    ship["status"] = next_status
    return True


def _next_friday(base, hour):
    d = base
    while d.isoweekday() != 5:
        d += timedelta(days=1)
    return d.replace(hour=hour)


def _next_monday(base, hour):
    d = base + timedelta(days=1)
    while d.isoweekday() != 1:
        d += timedelta(days=1)
    return d.replace(hour=hour)
