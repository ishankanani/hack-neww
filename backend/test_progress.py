from copy import deepcopy
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace

import pytest
from app.progress import position_report,position_context,attach_completed
from app.eta import compute_journey
from test_combined import Providers,client
from test_weather_hold import saved


def record():
    at=datetime.now(timezone.utc)
    plan={"quote_id":"approved","path":["A","H","B"],"geometry":[[8,49],[9,49],[10,49]],
          "cost":{"distance_km":150,"transport_eur":300,"fuel_l":45,"fuel_eur":70}}
    ship={"approved_at":at.isoformat(),"status":"IN TRANSIT","accepted_plan":plan,"route":plan["path"],"destination":"B"}
    net={"nodes":{"H":{"lat":49,"lon":9}}}
    return ship,net,at


def test_progress_retains_completed_prefix_and_only_future_hubs():
    ship,net,at=record()
    position=position_report(ship,net,progress_percent=60,at=at)
    assert position["source"]=="SIMULATION"
    assert position["remaining_path"]==["@vehicle","B"]
    assert position["completed_geometry"][0]==[8,49]
    assert position["lon"]==pytest.approx(9.2,abs=.01)
    assert position["completed_estimates"]["transport_eur"]==pytest.approx(180,abs=1)
    ship["vehicle_position"]=position
    with pytest.raises(ValueError,match="backwards"):
        position_report(ship,net,progress_percent=20,at=at+timedelta(minutes=1))
    with pytest.raises(ValueError,match="expired"):
        position_context({"network":net},ship,at+timedelta(minutes=16))


def test_report_rejects_off_route_stale_and_future_locations():
    ship,net,at=record()
    with pytest.raises(ValueError,match="3 km"):position_report(ship,net,lat=51,lon=9,at=at)
    with pytest.raises(ValueError,match="older"):position_report(ship,net,lat=49,lon=9,reported_at=(at-timedelta(minutes=16)).isoformat(),at=at)
    with pytest.raises(ValueError,match="future"):position_report(ship,net,lat=49,lon=9,reported_at=(at+timedelta(minutes=1)).isoformat(),at=at)


def test_remaining_eta_engine_skips_original_loading_and_preserves_hub_handling():
    nodes={i:{"id":i,"name":i,"lat":49,"lon":lon} for i,lon in [("@vehicle",9),("H",9.5),("B",10)]}
    net={"nodes":nodes,"edges":{}}
    ops=SimpleNamespace(data={"events":[],"weather":[],"weather_zones":[],"schedules":[]})
    journey=compute_journey(net,{}, {},{},Providers(),"@vehicle","B",datetime(2026,10,20,8,tzinfo=timezone.utc),["@vehicle","H","B"],ops,skip_origin_handling=True)
    assert journey["steps"][0]["type"]=="drive"
    assert [(s["location"],s["minutes"]) for s in journey["steps"] if s["type"]=="handling"]==[("H",120)]


def test_in_transit_hold_requests_stop_without_asserting_stopped(saved):
    ships,ops,option=saved
    ships.data["S1"]["status"]="IN TRANSIT"
    ships.hold("S1",0,"Weather ahead; find safe parking")
    assert ships.data["S1"]["status"]=="IN TRANSIT"
    assert ships.data["S1"]["stop_request"]["status"]=="REQUESTED"
    assert "hold" not in ships.data["S1"]


def test_remaining_review_and_approval_keep_completed_road(client):
    ship=client.post("/api/shipments",json={"origin":"R16","destination":"R21","planned_departure":(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat(),"weight_kg":8000}).json()
    sid=ship["id"];opt=ship["options"][0]
    assert client.post("/api/decisions",json={"shipment_id":sid,"action":"accept","option":0,"revision":opt["revision"],"quote_id":opt["quote_id"],"reason":"Approve initial route","acknowledge_deadline":True}).status_code==200
    report=client.post(f"/api/shipments/{sid}/position",json={"progress_percent":50,"source":"SIMULATION"})
    assert report.status_code==200,report.text
    position=report.json()["vehicle_position"]
    reviewed=client.post(f"/api/shipments/{sid}/replan")
    assert reviewed.status_code==200,reviewed.text
    option=reviewed.json()["options"][0]
    assert option["remaining_only"] and option["path"][0]=="@vehicle"
    assert option["geometry"][0]==pytest.approx([position["lon"],position["lat"]])
    assert option["completed_geometry"][0]==ship["accepted_plan"]["geometry"][0]
    assert not any(s["type"]=="handling" and s["location"]=="@vehicle" for s in option["steps"])
    result=client.post("/api/decisions",json={"shipment_id":sid,"action":"accept","option":0,"revision":option["revision"],"quote_id":option["quote_id"],"reason":"Approve remaining road","acknowledge_deadline":True})
    assert result.status_code==200,result.text
    saved=client.get(f"/api/shipments/{sid}").json()
    assert saved["status"]=="IN TRANSIT"
    assert saved["accepted_plan"]["completed_geometry"]==position["completed_geometry"]
    assert saved["accepted_plan"]["is_demo"]
