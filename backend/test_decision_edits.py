from copy import deepcopy
from test_combined import client
from test_manager_routes import shipment


def initial_decision(client):
    s=shipment(client)
    o=s["options"][s.get("selected_option",0)]
    body={"shipment_id":s["id"],"action":"defer","option":s.get("selected_option",0),"revision":o["revision"],"quote_id":o["quote_id"],"reason":"Awaiting loading confirmation"}
    r=client.post("/api/decisions",json=body)
    assert r.status_code==200,r.text
    return s,r.json(),body


def test_note_edit_preserves_previous_text_and_does_not_change_route(client):
    s,d,_=initial_decision(client)
    before=deepcopy(client.get(f"/api/shipments/{s['id']}").json()["accepted_plan"])
    r=client.patch(f"/api/decisions/{d['id']}",json={"reason":"Waiting for the warehouse team","expected_updated_at":d["updated_at"]})
    assert r.status_code==200,r.text
    edited=r.json()
    assert edited["id"]==d["id"] and edited["action"]==d["action"]
    assert edited["reason_edits"][0]["previous_reason"]==d["reason"]
    assert edited["created_at"]==d["created_at"]
    assert client.get(f"/api/shipments/{s['id']}").json()["accepted_plan"]==before
    stale=client.patch(f"/api/decisions/{d['id']}",json={"reason":"Conflicting old browser edit","expected_updated_at":d["updated_at"]})
    assert stale.status_code==409


def test_replacement_applies_hold_and_links_both_decisions(client):
    s,d,body=initial_decision(client)
    replacement=client.post("/api/decisions",json={**body,"action":"hold","reason":"Hold until loading is confirmed","supersedes_decision_id":d["id"],"supersedes_updated_at":d["updated_at"]})
    assert replacement.status_code==200,replacement.text
    new=replacement.json()
    history=client.get("/api/operations").json()["decisions"]
    original=next(x for x in history if x["id"]==d["id"])
    assert original["action"]=="defer" and original["reason"]==d["reason"]
    assert original["superseded_by"]==new["id"] and new["supersedes_decision_id"]==d["id"]
    assert client.get(f"/api/shipments/{s['id']}").json()["hold"]["reason"]==new["reason"]
    duplicate=client.post("/api/decisions",json={**body,"supersedes_decision_id":d["id"],"supersedes_updated_at":d["updated_at"]})
    assert duplicate.status_code==409


def test_stale_or_unrelated_replacement_has_no_operational_effect(client):
    s,d,body=initial_decision(client)
    stale=client.post("/api/decisions",json={**body,"action":"hold","supersedes_decision_id":d["id"],"supersedes_updated_at":"outdated"})
    assert stale.status_code==409
    assert not client.get(f"/api/shipments/{s['id']}").json().get("hold")
    other=shipment(client)
    unrelated=client.post("/api/decisions",json={**body,"shipment_id":other["id"],"supersedes_decision_id":d["id"],"supersedes_updated_at":d["updated_at"]})
    assert unrelated.status_code==404


def test_replacement_cannot_approve_an_unavailable_requested_hub(client):
    from app import main
    s,d,body=initial_decision(client)
    main.S["network"]["nodes"]["R29"]["transfer_enabled"]=False
    proposed=client.post(f"/api/shipments/{s['id']}/route-proposal",json={"via_hubs":["R29"]}).json()
    i=next(i for i,o in enumerate(proposed["options"]) if o.get("manager_requested"))
    o=proposed["options"][i]
    refused=client.post("/api/decisions",json={**body,"action":"accept","option":i,"revision":o["revision"],"quote_id":o["quote_id"],"supersedes_decision_id":d["id"],"supersedes_updated_at":d["updated_at"]})
    assert refused.status_code in {409,422}
    original=next(x for x in client.get("/api/operations").json()["decisions"] if x["id"]==d["id"])
    assert not original.get("superseded_by")
    assert client.get(f"/api/shipments/{s['id']}").json()["route"]==s["route"]
