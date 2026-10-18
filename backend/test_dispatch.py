from copy import deepcopy
from datetime import datetime,timedelta,timezone

from app.dispatch import connection_warnings
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
