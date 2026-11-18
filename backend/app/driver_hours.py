"""Driver planning with a driver change at every hub.

DACHSER runs relay driving: a fresh driver takes over at each hub, so only the
driving time between two hubs counts. Within one hub-to-hub leg the driver takes
a 45-minute break only once more than 8 hours of driving have been done. Daily (11 h) and weekly rests
are not planned, because several drivers are available. Handling is never a break.
This is a prospective estimate, not a tachograph validator.
"""
from datetime import timedelta
from .restrictions import BERLIN, restriction_at, _next_restriction_start

BREAK_AFTER = 480  # 8 hours of driving within one hub-to-hub leg
BREAK = 45


class DriverClock:
    """Tracks one driver's driving since the last break; reset at every hub."""
    def __init__(self, start):
        self.since_break = 0
        self.leg_drive = 0
        self.break_minutes = 0
        self.rest_minutes = 0
        self.legs = 0
        self.review = []
        self.credited_until = start

    def new_leg(self):
        """A rested driver takes over at the hub: the break clock starts again."""
        self.since_break = 0
        self.leg_drive = 0
        self.legs += 1

    def credit_wait(self, start, end):
        """A parked wait of 45 min or more counts as the driver's break, once only."""
        if start < self.credited_until:
            return 0
        minutes = (end-start).total_seconds()/60
        if minutes >= BREAK:
            self.since_break = 0
            self.break_minutes += BREAK
            self.credited_until = end
            return BREAK
        return 0

    def drive(self, start, seconds):
        self.since_break += seconds
        self.leg_drive += seconds

    def available(self, at):
        return BREAK_AFTER*60 - self.since_break

    def pause(self, start, minutes, kind):
        end = start + timedelta(minutes=minutes)
        self.since_break = 0
        self.break_minutes += minutes
        return end

    def required_pause(self, at):
        if self.since_break >= BREAK_AFTER*60:
            return BREAK, "driver_break", "Driving break · 45 minutes after 8 hours of driving"
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
        if restricted:
            # Deliberately plan rest during parked restriction time; annotate it,
            # rather than adding the same rest again after the ban ends.
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
        take = min(remaining, clock.available(cur), (next_midnight-cur).total_seconds())
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
