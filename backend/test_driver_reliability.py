from copy import deepcopy
from datetime import datetime,timedelta,timezone

from app.reliability import arrival_evidence
from test_combined import client


def test_arrival_window_needs_matched_actuals_and_excludes_simulation():
    at=datetime(2026,10,18,12,tzinfo=timezone.utc)
    eta=at-timedelta(days=2)
    rows=[]
    for i in range(20):
        actual=(eta+timedelta(minutes=i-10)).isoformat()
        rows.append({"id":str(i),"origin":"A","destination":"B","approved_at":(eta-timedelta(days=1)).isoformat(),
                     "accepted_plan":{"quote_id":str(i),"eta":eta.isoformat()},
                     "actual":{"accepted_quote_id":str(i),"actual_arrival":actual,"actual_departure":(eta-timedelta(hours=5)).isoformat()}})
    future_eta=(at+timedelta(days=1)).isoformat()
    insufficient=arrival_evidence(rows[:19],"A","B",future_eta,at=at)
    assert insufficient["samples"]==19 and insufficient["window_start"] is None
    result=arrival_evidence(rows,"A","B",future_eta,at=at)
    assert result["status"]=="EMPIRICAL" and result["lower_error_minutes"]==-8.1 and result["upper_error_minutes"]==7.1
    rows[0]["accepted_plan"]["is_demo"]=True
    rows[1]["actual"]["accepted_quote_id"]="unmatched"
    assert arrival_evidence(rows,"A","B",future_eta,at=at)["samples"]==18
    assert arrival_evidence(rows,"A","C",future_eta,at=at)["samples"]==0
    assert arrival_evidence(rows,"A","B",future_eta,remaining=True,at=at)["samples"]==0


def approved(client):
    ship=client.post("/api/shipments",json={"origin":"R16","destination":"R21","planned_departure":(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),"weight_kg":8000}).json()
    option=ship["options"][0]
    result=client.post("/api/decisions",json={"shipment_id":ship["id"],"action":"accept","option":0,"revision":option["revision"],"quote_id":option["quote_id"],"reason":"Initial dispatch approval","acknowledge_deadline":True})
    assert result.status_code==200,result.text
    return client.get(f"/api/shipments/{ship['id']}").json()


def test_driver_confirmation_records_actuals_and_no_clock_proof(client):
    ship=approved(client);sid=ship["id"]
    departure=client.post(f"/api/shipments/{sid}/driver-update",json={"kind":"departed"})
    assert departure.status_code==200,departure.text
    assert client.post(f"/api/shipments/{sid}/driver-update",json={"kind":"arrived"}).status_code==422
    bad=client.post(f"/api/shipments/{sid}/driver-update",json={"kind":"arrived","at":(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat(),"reference":"POD-42"})
    assert bad.status_code==422
    assert client.get(f"/api/shipments/{sid}").json()["status"]!="DELIVERED"
    result=client.post(f"/api/shipments/{sid}/driver-update",json={"kind":"arrived","reference":"POD-42","actual_cost_eur":500})
    assert result.status_code==200,result.text
    confirmed=result.json()
    assert confirmed["status"]=="DELIVERED"
    assert confirmed["delivery_confirmation"]["reference"]=="POD-42"
    assert confirmed["actual"]["accepted_quote_id"]==confirmed["accepted_plan"]["quote_id"]
    assert client.get("/api/performance").json()["samples"]==1


def test_safe_stop_requires_fresh_stopped_location_then_clear_release(client):
    ship=approved(client);sid=ship["id"]
    client.post(f"/api/shipments/{sid}/driver-update",json={"kind":"departed"})
    assert client.post(f"/api/shipments/{sid}/stop-request",json={"reason":"Severe weather ahead"}).status_code==200
    assert client.post(f"/api/shipments/{sid}/driver-update",json={"kind":"safe_stop","reference":"A6 rest area"}).status_code==422
    lon,lat=ship["accepted_plan"]["geometry"][0]
    position=client.post(f"/api/shipments/{sid}/position",json={"lat":lat,"lon":lon,"source":"DRIVER REPORTED","movement_state":"STOPPED"})
    assert position.status_code==200,position.text
    stopped=client.post(f"/api/shipments/{sid}/driver-update",json={"kind":"safe_stop","reference":"A6 rest area"})
    assert stopped.status_code==200,stopped.text
    assert stopped.json()["status"]=="ON HOLD"
    assert stopped.json()["stop_request"]["status"]=="ACKNOWLEDGED"
    assert client.post(f"/api/shipments/{sid}/driver-update",json={"kind":"arrived","reference":"POD-42"}).status_code==422
    updated=client.post(f"/api/shipments/{sid}/replan").json();option=updated["options"][0]
    released=client.post("/api/decisions",json={"shipment_id":sid,"action":"accept","option":0,"revision":option["revision"],"quote_id":option["quote_id"],"reason":"Clear remaining road verified","acknowledge_deadline":True})
    assert released.status_code==200,released.text
    assert "hold" not in client.get(f"/api/shipments/{sid}").json()


def test_simulated_position_cannot_leak_into_actual_metrics_without_approval(client):
    ship=approved(client);sid=ship["id"]
    assert client.post(f"/api/shipments/{sid}/position",json={"progress_percent":40,"source":"SIMULATION"}).status_code==200
    client.post(f"/api/shipments/{sid}/driver-update",json={"kind":"departed"})
    result=client.post(f"/api/shipments/{sid}/driver-update",json={"kind":"arrived","reference":"SIMULATED-POD","actual_cost_eur":500})
    assert result.status_code==200,result.text
    assert result.json()["actual"]["source"]=="DEMO OUTCOME"
    assert client.get("/api/performance").json()["samples"]==0
