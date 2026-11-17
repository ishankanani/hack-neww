"""Customer business policy, separate from the existing holiday calendar.

No truck moves or delivers from Saturday 15:00 to Monday 05:00 (Europe/Berlin).
A truck never waits on the road: if a leg would overlap that window, it waits at
the hub it is at (origin or intermediate) and leaves on Monday at 05:00.
"""
from datetime import timedelta, timezone
from .restrictions import BERLIN

WINDOW_START = (5, 15)  # Saturday 15:00
WINDOW_END = (0, 5)     # Monday 05:00
HOLD_TEXT = "Weekend rest at hub · no movement or delivery Saturday 15:00 – Monday 05:00"


def weekend_window(instant):
    """(start, end) in UTC of the window containing `instant`, or the next one after it."""
    local = instant.astimezone(BERLIN)
    saturday = (local - timedelta(days=(local.weekday() - WINDOW_START[0]) % 7)).replace(hour=WINDOW_START[1], minute=0, second=0, microsecond=0)
    for start in (saturday - timedelta(days=7), saturday, saturday + timedelta(days=7)):
        end = (start + timedelta(days=2)).replace(hour=WINDOW_END[1], minute=0, second=0, microsecond=0)
        if end.astimezone(timezone.utc) > instant:
            return start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    raise AssertionError("unreachable")


def hub_release(arrival, ready, intermediate=True):
    """Earliest time a truck that is ready at `ready` may leave a hub."""
    start, end = weekend_window(ready)
    return end if start <= ready < end else ready


def leg_start(ready, leg_minutes_at):
    """Earliest departure so the whole leg (ending at leg_minutes_at(departure)) avoids the window."""
    start, end = weekend_window(ready)
    if ready >= start or leg_minutes_at(ready) > start:
        return end
    return ready
