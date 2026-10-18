from copy import deepcopy
from datetime import datetime,timedelta,timezone

from app.dispatch import connection_warnings
from app.dispatch import action_comparison, attention
from types import SimpleNamespace
from test_combined import client
from app.shipments import _advance_time_status


def test_missed_connection_is_relative_to_approved_departure():
    service={"from":"A","to":"B","departure":"2026-10-20T18:00:00Z","buffer_minutes":10}
    baseline={"scheduled_services":[service]}
    assert connection_warnings(baseline)[0]["status"]=="TIGHT"
    revised={"scheduled_services":[{**service,"departure":"2026-10-21T18:00:00Z","buffer_minutes":600}]}
    result=connection_warnings(revised,baseline)[0]
    assert result["status"]=="MISSED" and result["connection_delay_minutes"]==1440
    assert baseline["scheduled_services"][0]==service


def test_clock_does_not_confirm_delivery_and_hold_remains_paused():
    now=datetime.now(timezone.utc)
    ship={"status":"IN TRANSIT","current_eta":(now-timedelta(minutes=1)).isoformat()}
    assert _advance_time_status(ship,now) and ship["status"]=="ARRIVAL EXPECTED"
    assert not _advance_time_status(ship,now)
    ship["delivery_confirmation"]={"at":now.isoformat(),"source":"DRIVER REPORTED"}
    assert _advance_time_status(ship,now) and ship["status"]=="DELIVERED"
    held={**ship,"status":"ON HOLD"}
    assert not _advance_time_status(held,now+timedelta(days=10))


def test_no_clear_route_produces_no_approvable_action():
    option={"route_id":"A-B:normal","path":["A","B"],"avoidance_status":"IMPACTED",
            "eta":"2026-10-20T12:00:00Z","risk":{"deadline_ok":False},
            "cost":{"distance_km":100,"transport_eur":200,"fuel_l":30}}
    rows=action_comparison({"route":["A","B"],"accepted_plan":option,"options":[option]})
    assert not any(r["available"] for r in rows)
    assert rows[0]["option_index"]==0
    assert rows[1]["eta"] is None and rows[2]["delta"] is None


def test_attention_explains_connection_exposure_without_mutating_plan():
    now=datetime(2026,10,20,8,tzinfo=timezone.utc)
    service={"from":"A","to":"B","departure":"2026-10-20T10:00:00Z",
             "ready_at":"2026-10-20T09:00:00Z","cutoff_at":"2026-10-20T09:30:00Z"}
    ship={"status":"SCHEDULED","current_eta":"2026-10-20T12:00:00Z","accepted_plan":{"scheduled_services":[service]}}
    previous=deepcopy(ship)
    result=attention(ship,SimpleNamespace(data={}),pending_minutes=45,at=now)
    assert result["priority"]=="CRITICAL"
    assert result["connections"][0]["projected_buffer_minutes"]==-15
    assert ship==previous


def test_bounded_wait_on_a_via_hub_itinerary_can_be_reviewed_and_approved(client,monkeypatch):
    from app import eta
    from app.weather_routes import _point_at,_route_length
    monkeypatch.setattr(eta,"closest_clear_detour",lambda *args,**kwargs:None)
    departure=datetime(2026,10,20,6,tzinfo=timezone.utc)
    ship=client.post("/api/shipments",json={"origin":"R16","destination":"R21","planned_departure":departure.isoformat(),"weight_kg":8000}).json()
    index=next(i for i,o in enumerate(ship["options"]) if len(o["path"])==3)
    option=ship["options"][index]
    approved=client.post("/api/decisions",json={"shipment_id":ship["id"],"action":"accept","option":index,"revision":option["revision"],"quote_id":option["quote_id"],"reason":"Approve via hub itinerary","acknowledge_deadline":True})
    assert approved.status_code==200,approved.text
    lon,lat=_point_at(option["geometry"],_route_length(option["geometry"])*.3)
    zone=client.post("/api/weather-zones",json={"kind":"tornado","lat":lat,"lon":lon,"radius_km":8,"start":departure.isoformat(),"end":(departure+timedelta(hours=12)).isoformat()})
    assert zone.status_code==200,zone.text
    reviewed=client.post(f"/api/shipments/{ship['id']}/replan")
    assert reviewed.status_code==200,reviewed.text
    rows=reviewed.json();wait_index=next(i for i,o in enumerate(rows["options"]) if o.get("dispatch_action")=="wait")
    wait=rows["options"][wait_index]
    assert len(wait["path"])==3 and wait["avoidance_status"]=="NO_ZONE"
    assert wait["steps"][0]["type"]=="manager_wait"
    assert wait["comparison"]["baseline"].startswith("Current itinerary")
    result=client.post("/api/decisions",json={"shipment_id":ship["id"],"action":"accept","option":wait_index,"revision":wait["revision"],"quote_id":wait["quote_id"],"reason":"Wait until weather zone expires","acknowledge_deadline":True})
    assert result.status_code==200,result.text


def test_ui_review_can_reschedule_a_missed_unstarted_departure(client):
    past=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
    ship=client.post("/api/shipments",json={"origin":"R16","destination":"R21","planned_departure":past,"weight_kg":8000}).json()
    reviewed=client.post(f"/api/shipments/{ship['id']}/replan?from_now=true")
    assert reviewed.status_code==200,reviewed.text
    row=reviewed.json()
    assert datetime.fromisoformat(row["planned_departure"])>datetime.now(timezone.utc)
    assert row["accepted_plan"]==ship["accepted_plan"]
    assert row["status"]=="PLANNED"
