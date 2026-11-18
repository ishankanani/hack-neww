from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

from app.capacity import evaluate
from test_combined import client


def test_reservations_reduce_capacity_and_own_booking_is_excluded():
    service={"service_id":"S","from":"A","to":"B","departure":"2026-10-20T12:00:00Z"}
    option={"path":["A","B"],"scheduled_services":[service],"steps":[]}
    reservation={"kind":"service","resource":"S","start":service["departure"],"end":"2026-10-20T12:01:00Z","ldm":4}
    record={"id":"cap","kind":"service","service_id":"S","start":"2026-10-20T00:00:00Z","end":"2026-10-21T00:00:00Z","available_ldm":6,"reason":"Limited trailer space"}
    ctx={"operations":SimpleNamespace(data={"capacity_records":[record]}),"capacity_shipments":[{"id":"one","approved_at":"2026-10-19T00:00:00Z","status":"SCHEDULED","capacity_reservations":[reservation]}]}
    assert not evaluate(option,ctx,4)["feasible"]
    assert evaluate(option,ctx,4)["checks"][0]["available_ldm"]==2
    ctx["exclude_shipment_id"]="one"
    assert evaluate(option,ctx,4)["checks"][0]["available_ldm"]==6
    assert evaluate(option,ctx,4)["feasible"]
    ctx["operations"].data["capacity_records"]=[]
    assert evaluate(option,ctx,4)["status"]=="UNVERIFIED"


def test_capacity_rechecked_before_approval_prevents_overbooking(client):
    departure=datetime.now(timezone.utc).replace(hour=6,minute=0,second=0,microsecond=0)+timedelta(days=7)
    departure+=timedelta(days=(1-departure.weekday())%7)
    service=client.post("/api/services",json={"origin":"R16","destination":"R21","weekdays":[0,1,2,3,4],"departure_time":"12:00","cutoff_minutes":0}).json()
    cap=client.post("/api/capacity",json={"kind":"service","service_id":service["id"],"start":departure.isoformat(),"end":(departure+timedelta(days=7)).isoformat(),"available_ldm":5,"reason":"One shipment slot available"})
    assert cap.status_code==200,cap.text
    body={"origin":"R16","destination":"R21","planned_departure":departure.isoformat(),"weight_kg":8000}
    first=client.post("/api/shipments",json=body).json()
    second=client.post("/api/shipments",json=body).json()
    def approve(ship):
        index=next(i for i,o in enumerate(ship["options"]) if len(o["path"])==2)
        option=ship["options"][index]
        return client.post("/api/decisions",json={"shipment_id":ship["id"],"action":"accept","option":index,"revision":option["revision"],"quote_id":option["quote_id"],"reason":"Allocate remaining service space","acknowledge_deadline":True})
    assert approve(first).status_code==200
    rejected=approve(second)
    assert rejected.status_code==422 and "Capacity changed" in rejected.text
    # Reapproving our own slot does not count it twice.
    reviewed=client.post(f"/api/shipments/{first['id']}/replan").json()
    assert approve(reviewed).status_code==200
