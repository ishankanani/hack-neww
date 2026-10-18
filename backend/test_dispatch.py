from copy import deepcopy
from datetime import datetime,timedelta,timezone

from app.dispatch import connection_warnings
from app.dispatch import action_comparison, attention
from types import SimpleNamespace
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
