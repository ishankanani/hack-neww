"""Descriptive arrival evidence from matched user-reported delivery outcomes."""
import math
from datetime import datetime,timedelta,timezone

from .operations import parse
from .savings import is_demo

MINIMUM_WINDOW_SAMPLES=20
LOOKBACK_DAYS=180


def quantile(values,q):
    position=(len(values)-1)*q
    lo=math.floor(position);hi=math.ceil(position)
    return values[lo]+(values[hi]-values[lo])*(position-lo)


def arrival_evidence(ships,origin,destination,eta,remaining=False,at=None):
    at=at or datetime.now(timezone.utc);errors=[]
    for ship in ships:
        if ship.get("origin")!=origin or ship.get("destination")!=destination or is_demo(ship) or not ship.get("approved_at"):continue
        actual=ship.get("actual") or {};plan=ship.get("accepted_plan") or {}
        if not actual.get("accepted_quote_id") or actual["accepted_quote_id"]!=plan.get("quote_id"):continue
        if bool(plan.get("remaining_only"))!=remaining:continue
        try:
            arrival=parse(actual["actual_arrival"]);departure=parse(actual["actual_departure"])
            if not at-timedelta(days=LOOKBACK_DAYS)<=arrival<=at or arrival<departure:continue
            errors.append((arrival-parse(plan["eta"])).total_seconds()/60)
        except (KeyError,TypeError,ValueError):continue
    errors.sort();enough=len(errors)>=MINIMUM_WINDOW_SAMPLES
    low=quantile(errors,.1) if enough else None;high=quantile(errors,.9) if enough else None
    return {"samples":len(errors),"minimum_samples":MINIMUM_WINDOW_SAMPLES,"lookback_days":LOOKBACK_DAYS,
            "status":"EMPIRICAL" if enough else "INSUFFICIENT_DATA","remaining_only":remaining,
            "median_error_minutes":round(quantile(errors,.5),1) if enough else None,
            "arrival_mae_minutes":round(sum(abs(e) for e in errors)/len(errors),1) if enough else None,
            "lower_error_minutes":round(low,1) if enough else None,"upper_error_minutes":round(high,1) if enough else None,
            "window_start":(parse(eta)+timedelta(minutes=low)).isoformat() if enough else None,
            "window_end":(parse(eta)+timedelta(minutes=high)).isoformat() if enough else None,
            "source":"Same origin/destination and planning stage, last 180 days; approved quotes matched to reported actuals. Demo and simulated-progress approvals excluded.",
            "note":"Descriptive middle 80% of observed arrival errors, not an 80% prediction guarantee. Aggregate daily CSV records have no measured shipment arrival times."}
