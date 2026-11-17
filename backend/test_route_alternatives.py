from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.providers import RoutingProvider
from app.live import TomTom, DEFAULT_TRUCK
from app.journey_examples import request_for, example
from test_combined import client


def test_osrm_alternatives_are_cached_without_losing_the_main_leg():
    calls = []
    road = {"duration": 3600, "distance": 70000, "geometry": {"coordinates": [[8, 49], [9, 49]]}}
    alternative = {**road, "distance": 80000, "geometry": {"coordinates": [[8, 49], [8.5, 49.2], [9, 49]]}}
    def get(url, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"routes": [road, alternative]})
    provider = RoutingProvider()
    provider.client.close()
    provider.client = SimpleNamespace(get=get)
    choices = provider.alternatives((49, 8), (49, 9))
    assert len(choices) == 2 and calls[0]["params"]["alternatives"] == 2
    assert provider.leg((49, 8), (49, 9)) == choices[0]
    assert provider.alternatives((49, 8), (49, 9)) == choices
    assert len(calls) == 1


def test_tomtom_alternatives_keep_truck_profile_and_each_roads_metrics():
    provider=TomTom()
    provider.client.close()
    provider.key="unit-test-placeholder"
    calls=[]
    def get(url, params):
        calls.append(params)
        return {"routes":[{"summary":{"travelTimeInSeconds":seconds,"lengthInMeters":metres,"trafficDelayInSeconds":120},
            "legs":[{"points":[{"longitude":8,"latitude":49},{"longitude":lon,"latitude":50}]}]}
            for seconds,metres,lon in [(3600,70000,9),(4200,85000,10)]]}
    provider.get=get
    roads=provider.alternatives((49,8),(50,10),datetime.now(timezone.utc)+timedelta(hours=1),DEFAULT_TRUCK)
    assert calls[0]["maxAlternatives"]==2 and calls[0]["alternativeType"]=="anyRoute"
    assert calls[0]["travelMode"]=="truck" and calls[0]["vehicleWeight"]==DEFAULT_TRUCK["gross_weight_kg"]
    assert len(roads)==2 and roads[0]["distance_km"]==70 and roads[1]["distance_km"]==85
    assert roads[1]["duration_minutes"]==70 and roads[1]["traffic_minutes"]==2
    assert roads[0]["geometry"]!=roads[1]["geometry"]


def test_distinct_roads_are_ranked_and_the_selected_road_can_be_saved(client, monkeypatch):
    from app import main
    routing = main.S["providers"].routing
    def alternatives(a, b):
        direct = routing.leg(a, b)
        return [direct, {**direct, "geometry": [direct["geometry"][0], [(a[1]+b[1])/2, (a[0]+b[0])/2+.25], direct["geometry"][-1]],
                         "distance_km": direct["distance_km"]*1.1,
                         "duration_minutes": round(direct["distance_km"]*1.1/80*60),
                         "source": "TomTom test truck route"}]
    monkeypatch.setattr(routing, "alternatives", alternatives, raising=False)
    departure=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
    body = {"origin": "R16", "destination": "R21", "depart_at": departure, "weight_kg": 12000}
    fastest = client.post("/api/route", json=body)
    assert fastest.status_code == 200, fastest.text
    roads = [o for o in fastest.json()["options"] if ":road-" in o["route_id"]]
    baseline=next(o for o in fastest.json()["options"] if o["route_id"]=="R16-R21:normal")
    assert roads and roads[0]["geometry"] != baseline["geometry"]
    assert fastest.json()["options"][0]["route_id"] == roads[0]["route_id"]
    cheapest = client.post("/api/route", json={**body, "optimization": "cost"}).json()
    assert cheapest["options"][0]["cost"]["transport_eur"] <= roads[0]["cost"]["transport_eur"]
    saved = client.post("/api/shipments", json={**body, "planned_departure": body["depart_at"], "selected_route_id": roads[0]["route_id"]})
    assert saved.status_code == 200, saved.text
    assert saved.json()["accepted_plan"]["route_id"] == roads[0]["route_id"]
    assert saved.json()["accepted_plan"]["geometry"] == roads[0]["geometry"]
    shipment=saved.json()
    index=next(i for i,o in enumerate(shipment["options"]) if o["route_id"]==roads[0]["route_id"])
    quoted=shipment["options"][index]
    approved=client.post("/api/decisions",json={"shipment_id":shipment["id"],"action":"accept","option":index,
        "revision":quoted["revision"],"quote_id":quoted["quote_id"],"reason":"Review native road alternative","acknowledge_deadline":True})
    assert approved.status_code==200,approved.text
    assert client.get(f"/api/shipments/{shipment['id']}").json()["accepted_plan"]["geometry"]==roads[0]["geometry"]


def test_sample_catalog_and_weather_preview_do_not_change_shared_data(client, monkeypatch):
    from app import main
    monkeypatch.setattr(main.S["providers"].routing, "via", lambda *args: {"geometry": None}, raising=False)
    catalog = client.get("/api/journey-examples")
    assert catalog.status_code == 200, catalog.text
    assert len(catalog.json()["examples"]) == 5
    sample = next(row for row in catalog.json()["examples"] if row["id"] == "J2-snow-reroute")
    operations = deepcopy(main.S["operations"].data)
    shipments = deepcopy(main.S["ships"].data)
    response = client.post("/api/route", json={**sample["request"], "sample_id": sample["id"], "sample_weather": True})
    assert response.status_code == 200, response.text
    assert response.json()["sample"]["weather_applied"] is True
    assert response.json()["weather_zones"][0]["kind"] == "snow"
    assert any(option["zone_impacts"] for option in response.json()["options"])
    assert main.S["operations"].data == operations
    assert main.S["ships"].data == shipments


def test_saturday_example_uses_berlin_time_and_a_future_monday_deadline():
    request = request_for(example("J3-high-value-weekend"), datetime(2026, 10, 23, 10, tzinfo=timezone.utc))
    departure = datetime.fromisoformat(request["depart_at"])
    deadline = datetime.fromisoformat(request["required_delivery"])
    assert departure.isoweekday() == 6 and departure.hour == 18
    assert deadline.isoweekday() == 1 and deadline.hour == 9
    assert departure.utcoffset().total_seconds() == 7200
    assert deadline.utcoffset().total_seconds() == 3600
