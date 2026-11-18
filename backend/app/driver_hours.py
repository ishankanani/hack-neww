"""Conservative single-driver planning; no shortened rests or 10-hour extensions.

This is a prospective driving-time estimate for a fully rested driver. It is not
a tachograph validator. Handling is never treated as a driving break.
"""
from datetime import timedelta
from .restrictions import BERLIN, restriction_at, _next_restriction_start

BREAK_AFTER = 270
BREAK = 45
DAILY_DRIVE = 540
DAILY_REST = 660


class DriverClock:
    def __init__(self, start):
        self.since_break = 0
        self.daily_drive = 0
        self.daily_rest_end = start
        self.weekly_rest_end = start
        self.by_week = {}
        self.break_minutes = 0
        self.rest_minutes = 0
        self.review = []
        self.credited_until = start

    def credit_wait(self, start, end):
        """Assign prospective off-duty rest inside a parked wait, once only."""
        if start < self.credited_until:
            return 0
        minutes=(end-start).total_seconds()/60
        credited=0
        if minutes >= 45*60:
            self.weekly_rest_end=end
            self.daily_rest_end=end
            self.since_break=self.daily_drive=0
            credited=45*60;self.rest_minutes+=credited
        elif minutes >= DAILY_REST:
            self.daily_rest_end=end
            self.since_break=self.daily_drive=0
            credited=DAILY_REST;self.rest_minutes+=credited
        elif minutes >= BREAK:
            self.since_break=0
            credited=BREAK;self.break_minutes+=credited
        if credited:self.credited_until=end
        return credited

    def week(self, at):
        local = at.astimezone(BERLIN).date()
        return (local - timedelta(days=local.weekday())).isoformat()

    def drive(self, start, seconds):
        self.since_break += seconds
        self.daily_drive += seconds
        key = self.week(start)
        self.by_week[key] = self.by_week.get(key, 0) + seconds

    def available(self, at):
        key = self.week(at)
        current = self.by_week.get(key, 0)
        previous = (at.astimezone(BERLIN).date() - timedelta(days=at.astimezone(BERLIN).weekday()+7)).isoformat()
        return min(BREAK_AFTER*60-self.since_break, DAILY_DRIVE*60-self.daily_drive,
                   56*3600-current, 90*3600-current-self.by_week.get(previous, 0))

    def pause(self, start, minutes, kind):
        end = start + timedelta(minutes=minutes)
        if kind == "driver_break":
            self.since_break = 0
            self.break_minutes += minutes
        else:
            self.since_break = self.daily_drive = 0
            self.daily_rest_end = end
            self.rest_minutes += minutes
            if kind == "weekly_rest":
                self.weekly_rest_end = end
        return end

    def required_pause(self, at):
        if at >= self.weekly_rest_end + timedelta(days=6):
            return 45*60, "weekly_rest", "Regular weekly rest · 45 hours before continuing"
        key = self.week(at)
        local = at.astimezone(BERLIN).date()
        previous = (local-timedelta(days=local.weekday()+7)).isoformat()
        if self.by_week.get(key, 0) >= 56*3600 or self.by_week.get(key, 0)+self.by_week.get(previous, 0) >= 90*3600:
            # A weekly rest does not reset calendar-week or fortnight totals.
            monday = (at.astimezone(BERLIN)+timedelta(days=7-at.astimezone(BERLIN).weekday())).replace(hour=0,minute=0,second=0,microsecond=0).astimezone(at.tzinfo)
            minutes = max(45*60, int((monday-at).total_seconds()/60))
            return minutes, "weekly_rest", "Weekly / fortnightly driving limit · regular weekly rest and wait for the next eligible week"
        if self.daily_drive >= DAILY_DRIVE*60 or at >= self.daily_rest_end + timedelta(hours=13):
            return DAILY_REST, "driver_rest", "Regular daily rest · 11 hours (9-hour daily driving plan)"
        if self.since_break >= BREAK_AFTER*60:
            return BREAK, "driver_break", "Driving break · 45 minutes after 4½ hours of driving"
        return None


def drive_with_driver_rules(depart, minutes, holidays, clock, company_sunday_hold=False, truck_ban_applies=True):
    cur = depart
    remaining = max(0, int(minutes))*60
    pauses = []
    drive_segments = []
    for _ in range(2000):
        if remaining <= 0:
            break
        restricted, reason, until = restriction_at(cur, holidays, company_sunday_hold=company_sunday_hold) if truck_ban_applies else (False, None, None)
        required = clock.required_pause(cur)
        if required and required[1] == "weekly_rest":
            duration, kind, reason = required
            end = clock.pause(cur, duration, kind)
            pauses.append({"start":cur,"end":end,"minutes":duration,"kind":kind,"reason":reason})
            cur = end
            continue
        if restricted:
            # Deliberately plan rest during parked restriction time; annotate it,
            # rather than adding the same rest again after the ban ends.
            until = min(until, clock.weekly_rest_end + timedelta(days=6))
            duration = (until-cur).total_seconds()/60
            included = clock.credit_wait(cur,until)
            pauses.append({"start":cur,"end":until,"minutes":round(duration),"kind":"weekend_hold" if company_sunday_hold and cur.astimezone(BERLIN).weekday()==6 else "legal_wait",
                           "reason":reason + (f" · includes {included} min planned driver rest" if included else "")})
            cur = until
            continue
        if required:
            duration, kind, reason = required
            end = clock.pause(cur, duration, kind)
            pauses.append({"start":cur,"end":end,"minutes":duration,"kind":kind,"reason":reason})
            cur = end
            continue
        next_ban = _next_restriction_start(cur, holidays) if truck_ban_applies else None
        next_midnight = (cur.astimezone(BERLIN) + timedelta(days=1)).replace(hour=0,minute=0,second=0,microsecond=0).astimezone(cur.tzinfo)
        duty_available = max(0, (clock.daily_rest_end + timedelta(hours=13)-cur).total_seconds())
        weekly_rest_due = max(0, (clock.weekly_rest_end + timedelta(days=6)-cur).total_seconds())
        take = min(remaining, clock.available(cur), duty_available, weekly_rest_due, (next_midnight-cur).total_seconds())
        if next_ban:
            take = min(take, (next_ban-cur).total_seconds())
        if take <= 0:
            raise ValueError("Driver limits leave no eligible driving window; manager review is required")
        end = cur + timedelta(seconds=take)
        drive_segments.append({"start":cur,"end":end})
        clock.drive(cur, take)
        cur = end
        remaining -= take
    if remaining > 0:
        raise ValueError("Journey exceeds the driver-planning horizon")
    return {"arrival":cur,"pauses":pauses,"segments":drive_segments}
