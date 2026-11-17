from copy import deepcopy
from datetime import datetime,timedelta,timezone
from test_combined import client


def shipment(client):
    departure=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
    r=client.post("/api/shipments",json={"origin":"R16","destination":"R21","planned_departure":departure,"weight_kg":8000})
    assert r.status_code==200,r.text
    return r.json()


def test_manager_connects_wurzburg_and_only_approval_changes_saved_route(client):
    from app import main
    s=shipment(client);saved=deepcopy(s["accepted_plan"])
    hub=next(n["id"] for n in main.S["network"]["nodes"].values() if n["name"]=="Würzburg")
    r=client.post(f"/api/shipments/{s['id']}/route-proposal",json={"via_hubs":[hub]})
    assert r.status_code==200,r.text
    proposal=r.json();assert proposal["accepted_plan"]==saved
    index=next(i for i,o in enumerate(proposal["options"]) if o.get("manager_requested") and o["route_feasible"])
    option=proposal["options"][index]
    assert option["path"]==["R16",hub,"R21"] and option["total_minutes"]>0 and option["cost"]["transport_eur"]>0
    accepted=client.post("/api/decisions",json={"shipment_id":s["id"],"action":"accept","option":index,"revision":option["revision"],"quote_id":option["quote_id"],"reason":"Transfer through Würzburg","acknowledge_deadline":True})
    assert accepted.status_code==200,accepted.text
    assert client.get(f"/api/shipments/{s['id']}").json()["route"]==option["path"]
    assert any(row["id"]==s["id"] for row in client.get("/api/shipments").json()["shipments"])


def test_unavailable_hub_explains_failure_and_keeps_available_alternatives(client):
    from app import main
    s=shipment(client);hub="R29"
    main.S["network"]["nodes"][hub]["transfer_enabled"]=False
    r=client.post(f"/api/shipments/{s['id']}/route-proposal",json={"via_hubs":[hub]})
    assert r.status_code==200,r.text
    options=r.json()["options"];index=next(i for i,o in enumerate(options) if o.get("manager_requested"))
    requested=options[index]
    assert requested["route_feasible"] is False
    assert any("does not accept transfers" in reason for reason in requested["unavailable_reasons"])
    assert any(o["route_feasible"] and not o.get("manager_requested") for o in options)
    assert requested["total_minutes"]>0 and requested["eta"]
    refused=client.post("/api/decisions",json={"shipment_id":s["id"],"action":"accept","option":index,"revision":requested["revision"],"quote_id":requested["quote_id"],"reason":"Unavailable connection check","acknowledge_deadline":True})
    assert refused.status_code in {409,422}
    assert client.get(f"/api/shipments/{s['id']}").json()["route"]==s["route"]


def test_duplicate_hub_request_is_rejected(client):
    s=shipment(client)
    r=client.post(f"/api/shipments/{s['id']}/route-proposal",json={"via_hubs":["R29","R29"]})
    assert r.status_code==422 and "once" in r.json()["detail"]
