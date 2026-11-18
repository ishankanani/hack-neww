"""Offline German holiday calendar, with StVO 30(4) freight bans distinguished."""
from calendar import monthrange
from datetime import date, timedelta

SOURCE = "https://www.gesetze-im-internet.de/stvo_2013/__30.html"
REGIONS = {
    "DE-BW": "Baden-Württemberg", "DE-BY": "Bavaria", "DE-BE": "Berlin",
    "DE-BB": "Brandenburg", "DE-HB": "Bremen", "DE-HH": "Hamburg",
    "DE-HE": "Hesse", "DE-MV": "Mecklenburg-Vorpommern", "DE-NI": "Lower Saxony",
    "DE-NW": "North Rhine-Westphalia", "DE-RP": "Rhineland-Palatinate",
    "DE-SL": "Saarland", "DE-SN": "Saxony", "DE-ST": "Saxony-Anhalt",
    "DE-SH": "Schleswig-Holstein", "DE-TH": "Thuringia",
}
CORPUS = {"DE-BW", "DE-BY", "DE-HE", "DE-NW", "DE-RP", "DE-SL"}
REFORMATION = {"DE-BB", "DE-HB", "DE-HH", "DE-MV", "DE-NI", "DE-SN", "DE-ST", "DE-SH", "DE-TH"}
ALL_SAINTS = {"DE-BW", "DE-BY", "DE-NW", "DE-RP", "DE-SL"}


def easter(year):
    """Gregorian computus, valid for the supported planning years."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19*a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2*e + 2*i - h - k) % 7
    m = (a + 11*h + 22*l) // 451
    month, day = divmod(h + l - 7*m + 114, 31)
    return date(year, month, day + 1)


def holidays(year, region="DE-BW"):
    if region not in REGIONS:
        raise ValueError("Choose a German federal state")
    if not 1900 <= year <= 2100:
        raise ValueError("Calendar supports years 1900–2100")
    result = {}

    def add(day, name, ban=False, note=None):
        result[day.isoformat()] = {"name": name, "truck_ban": ban, "note": note}

    for month, day, name in [(1, 1, "New Year's Day"), (5, 1, "Labour Day"),
                             (10, 3, "German Unity Day"), (12, 25, "Christmas Day"),
                             (12, 26, "Second Christmas Day")]:
        add(date(year, month, day), name, True)
    e = easter(year)
    for delta, name in [(-2, "Good Friday"), (1, "Easter Monday"),
                        (39, "Ascension Day"), (50, "Whit Monday")]:
        add(e + timedelta(days=delta), name, True)
    if region in CORPUS:
        add(e + timedelta(days=60), "Corpus Christi", True)
    if region in REFORMATION:
        add(date(year, 10, 31), "Reformation Day", True)
    if region in ALL_SAINTS:
        add(date(year, 11, 1), "All Saints' Day", True)
    if region in {"DE-BW", "DE-BY", "DE-ST"}:
        add(date(year, 1, 6), "Epiphany")
    if region in {"DE-BE", "DE-MV"}:
        add(date(year, 3, 8), "International Women's Day")
    if region == "DE-SL":
        add(date(year, 8, 15), "Assumption Day")
    if region == "DE-TH":
        add(date(year, 9, 20), "World Children's Day")
    if region == "DE-SN":
        before = date(year, 11, 22)
        add(before - timedelta(days=(before.weekday()-2) % 7), "Repentance and Prayer Day")
    return result


def ban_dates(first_year, last_year, region):
    return {day: row["name"] for year in range(first_year, last_year + 1)
            for day, row in holidays(year, region).items() if row["truck_ban"]}


def month_calendar(year, month, region="DE-BW", company_sunday_hold=False):
    if not 1 <= month <= 12:
        raise ValueError("Choose a month from 1 to 12")
    public = holidays(year, region)
    days = []
    for n in range(1, monthrange(year, month)[1] + 1):
        day = date(year, month, n)
        holiday = public.get(day.isoformat())
        sunday = day.weekday() == 6
        ban = sunday or bool(holiday and holiday["truck_ban"])
        days.append({"date": day.isoformat(), "weekday": day.weekday(), "sunday": sunday,
                     "holiday": holiday["name"] if holiday else None,
                     "truck_ban": ban, "ban_start": "00:00" if ban else None,
                     "ban_end": "22:00" if ban else None,
                     "company_hold": company_sunday_hold and day.weekday() in {5, 6, 0},
                     "summer_route_review": month in {7, 8} and day.weekday() == 5})
    return {"year": year, "month": month, "region": region, "region_name": REGIONS[region],
            "timezone": "Europe/Berlin", "days": days, "source": SOURCE,
            "regions": [{"id": k, "name": v} for k, v in REGIONS.items()],
            "reviewed_at":"2026-11-17",
            "scope": "Selected federal state only. Confirm all states crossed on a multi-state journey.",
            "notes": ["A public holiday is not automatically a StVO truck-ban holiday.",
                      "Municipal holidays and individual exemptions require manager review.",
                      "Summer Saturdays: additional 07:00–20:00 bans apply on specified roads; road-specific review is required."]}
