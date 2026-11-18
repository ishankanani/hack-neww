from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.driver_hours import DriverClock, drive_with_driver_rules
from app.transport_calendar import holidays, month_calendar, ban_dates, easter
from app.restrictions import BERLIN
from app.eta import compute_journey
from test_combined import client, Road, Traffic


def utc(value):
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def test_break_is_due_after_4_and_half_hours_not_8_hours():
    start=utc("2026-11-17T06:00:00+01:00")
    clock=DriverClock(start)
    result=drive_with_driver_rules(start,271,{},clock)
    assert result["arrival"] == start+timedelta(minutes=316)
    pause=result["pauses"][0]
    assert pause["kind"]=="driver_break" and pause["minutes"]==45
    assert pause["start"]==start+timedelta(minutes=270)


def test_no_break_is_added_after_the_journey_has_finished():
    start=utc("2026-11-17T06:00:00+01:00")
    result=drive_with_driver_rules(start,270,{},DriverClock(start))
    assert result["arrival"]==start+timedelta(minutes=270)
    assert not result["pauses"]


def test_daily_limit_uses_regular_11_hour_rest():
    start=utc("2026-11-17T06:00:00+01:00")
    result=drive_with_driver_rules(start,541,{},DriverClock(start))
    assert [p["kind"] for p in result["pauses"]]==["driver_break","driver_rest"]
    assert [p["minutes"] for p in result["pauses"]]==[45,660]
    assert result["arrival"]==start+timedelta(minutes=541+45+660)


def test_hub_handling_does_not_reset_driving_clock():
    start=utc("2026-11-17T06:00:00+01:00")
    clock=DriverClock(start)
    first=drive_with_driver_rules(start,180,{},clock)
    second_start=first["arrival"]+timedelta(hours=2)
    second=drive_with_driver_rules(second_start,180,{},clock)
    assert second["pauses"][0]["start"]==second_start+timedelta(minutes=90)
    assert second["pauses"][0]["minutes"]==45


def test_legal_sunday_ban_ends_at_22_while_company_policy_can_hold_until_monday():
    start=utc("2026-11-22T21:30:00+01:00")
    legal=drive_with_driver_rules(start,60,{},DriverClock(start))
    company=drive_with_driver_rules(start,60,{},DriverClock(start),True)
    assert legal["arrival"].astimezone(BERLIN).isoformat()=="2026-11-22T23:00:00+01:00"
    assert company["arrival"].astimezone(BERLIN).isoformat()=="2026-11-23T01:00:00+01:00"


def test_non_banned_light_vehicle_is_not_held_on_sunday():
    start=utc("2026-11-22T12:00:00+01:00")
    result=drive_with_driver_rules(start,60,{},DriverClock(start),False,False)
    assert result["arrival"]==start+timedelta(hours=1)


def test_rest_is_planned_inside_long_sunday_wait_without_double_counting():
    start=utc("2026-11-21T23:00:00+01:00")
    clock=DriverClock(start)
    result=drive_with_driver_rules(start,120,{},clock)
    assert result["arrival"].astimezone(BERLIN).isoformat()=="2026-11-22T23:00:00+01:00"
    assert clock.rest_minutes==660
    assert len(result["pauses"])==1 and "includes 660" in result["pauses"][0]["reason"]


def test_public_holiday_is_not_automatically_a_truck_ban():
    bw=holidays(2027,"DE-BW")
    assert bw["2027-01-06"]["name"]=="Epiphany"
    assert bw["2027-01-06"]["truck_ban"] is False
    assert "2027-01-06" not in ban_dates(2027,2027,"DE-BW")


def test_regional_holidays_and_future_years():
    assert easter(2026).isoformat()=="2026-04-05"
    assert easter(2027).isoformat()=="2027-03-28"
    assert holidays(2026,"DE-BW")["2026-06-04"]["truck_ban"]
    assert "2026-06-04" not in holidays(2026,"DE-NI")
    assert holidays(2026,"DE-HH")["2026-10-31"]["truck_ban"]
    assert "2026-10-31" not in holidays(2026,"DE-BW")
    assert holidays(2027,"DE-BW")["2027-12-25"]["truck_ban"]


def test_calendar_marks_regional_sundays_and_summer_review():
    doc=month_calendar(2027,7,"DE-BW")
    saturday=next(d for d in doc["days"] if d["weekday"]==5)
    sunday=next(d for d in doc["days"] if d["weekday"]==6)
    assert saturday["summer_route_review"] and not saturday["truck_ban"]
    assert sunday["truck_ban"] and sunday["ban_end"]=="22:00"


def test_calendar_endpoint_does_not_need_a_dataset_holiday(client):
    r=client.get("/api/transport-calendar?year=2027&month=12&region=DE-BW")
    assert r.status_code==200,r.text
    assert next(d for d in r.json()["days"] if d["date"]=="2027-12-25")["truck_ban"]
    assert client.get("/api/transport-calendar?year=2027&month=13").status_code==422
    assert client.get("/api/transport-calendar?year=2027&month=1&region=XX").status_code==422


def test_real_journey_emits_break_steps_and_shared_minutes():
    start=utc("2026-11-17T06:00:00+01:00")
    class LongRoad(Road):
        def leg(self,a,b):
            result=super().leg(a,b)
            return {**result,"duration_minutes":180,"distance_km":195}
    providers=SimpleNamespace(routing=LongRoad(),traffic=Traffic())
    nodes={x:{"id":x,"name":x,"lat":49,"lon":9+i,"type":"branch"} for i,x in enumerate(["A","B","C"])}
    journey=compute_journey({"nodes":nodes,"edges":{}},{},{},{},providers,"A","C",start,["A","B","C"],planning_rules={"region":"DE-BW","company_sunday_hold":False,"trailer_attached":True})
    breaks=[s for s in journey["steps"] if s["type"]=="driver_break"]
    assert len(breaks)==1 and breaks[0]["minutes"]==45
    assert journey["components"]["driver_break"]==45
    assert sum(s["minutes"] for s in journey["steps"])==journey["total_minutes"]
    assert journey["planning_rules"]["region"]=="DE-BW"


def test_saved_journey_keeps_calendar_rules_during_manager_replanning(client):
    start=datetime.now(timezone.utc)+timedelta(days=2)
    rules={"region":"DE-HH","company_sunday_hold":False,"trailer_attached":True}
    response=client.post("/api/shipments",json={"origin":"R16","destination":"R21","planned_departure":start.isoformat(),"weight_kg":8000,"planning_rules":rules})
    assert response.status_code==200,response.text
    ship=response.json()
    assert ship["planning_rules"]==rules
    assert ship["accepted_plan"]["planning_rules"]==rules
    replan=client.post(f"/api/shipments/{ship['id']}/route-proposal",json={"via_hubs":["R29"]})
    assert replan.status_code==200,replan.text
    requested=next(o for o in replan.json()["options"] if o.get("manager_requested"))
    assert requested["planning_rules"]==rules
    assert requested["driver_plan"] and "fully rested" in requested["driver_plan"]["assumption"]


def test_daily_and_weekly_limits_are_never_reset_by_midnight():
    start=utc("2026-11-16T23:00:00+01:00")
    clock=DriverClock(start)
    result=drive_with_driver_rules(start,600,{},clock)
    assert any(p["kind"]=="driver_rest" for p in result["pauses"])
    assert clock.by_week[clock.week(start)]==600*60


def test_dst_sunday_uses_berlin_wall_clock_22_not_a_fixed_22_hour_wait():
    start=utc("2026-10-25T00:00:00+02:00")
    result=drive_with_driver_rules(start,60,{},DriverClock(start))
    assert result["pauses"][0]["minutes"]==23*60
    assert result["arrival"].astimezone(BERLIN).isoformat()=="2026-10-25T23:00:00+01:00"
