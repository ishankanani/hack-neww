"""Replay daily lane demand with a bounded dispatch plan and published tariffs."""
from collections import defaultdict
import csv
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


def loading_tenths(value):
    return int((Decimal(value) * 10).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class Lane:
    name: str
    regular_rate: int
    special_rate: int
    capacity: int
    target_capacity: int


@dataclass(frozen=True)
class LaneDay:
    date: str
    regular: int
    special: int
    surplus: int
    demand: int
    deferred: int
    utilisation: float

    @property
    def dispatched(self):
        return self.demand - self.deferred


class SavingsScenarios:
    def __init__(self, data_dir):
        root = Path(data_dir)
        self.lanes = {}
        self.days = defaultdict(list)
        self.excluded = defaultdict(int)
        with (root / "relationen.csv").open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                capacity = Decimal(row["kapazitaet_ldm"])
                self.lanes[row["relation"]] = Lane(
                    row["ziel_niederlassung"], int(row["kosten_linientrailer_eur"]),
                    int(row["kosten_sonderfahrt_eur"]), loading_tenths(capacity),
                    loading_tenths(capacity * Decimal(row["ziel_ldm_auslastung"])),
                )
        with (root / "disposition.csv").open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                lane_id = row["relation"]
                lane = self.lanes[lane_id]
                day = LaneDay(
                    row["datum"], int(row["trailer_linie_gefahren"]), int(row["sonderfahrten"]),
                    int(row["trailer_ueberzaehlig"]), loading_tenths(row["lademeter_aufkommen"]),
                    loading_tenths(row["lademeter_verschoben_auf_folgetag"]), float(row["auslastung_pct"]),
                )
                if not 0 <= day.dispatched <= (day.regular + day.special) * lane.capacity:
                    self.excluded[lane_id] += 1
                    continue
                self.days[lane_id].append(day)

    def compare(self, lane_id, reserve, objective):
        lane = self.lanes[lane_id]
        days = self.days[lane_id]
        efficient = max(
            (d for d in days if not (d.special or d.deferred or d.surplus)),
            key=lambda d: (d.utilisation, d.demand, d.date), default=None,
        )
        costly = max(
            (d for d in days if d.special),
            key=lambda d: (d.special, -d.deferred, d.demand, d.date), default=None,
        )
        backlog = max(
            (d for d in days if d.deferred),
            key=lambda d: (d.deferred, d.special, d.demand, d.date), default=None,
        )
        surplus = max(
            (d for d in days if d.surplus and not (d.special or d.deferred)),
            key=lambda d: (d.surplus, -d.utilisation, d.date), default=None,
        )
        cases = (
            ("efficient", efficient), ("special_trips", costly),
            ("freight_backlog", backlog), ("surplus_trailers", surplus),
        )
        return {
            "lane": lane_id,
            "lanes": [{"id": key, "name": item.name} for key, item in self.lanes.items()],
            "reserve": reserve, "objective": objective,
            "rated_capacity_ldm": lane.capacity / 10,
            "target_capacity_ldm": lane.target_capacity / 10,
            "regular_rate_eur": lane.regular_rate, "special_rate_eur": lane.special_rate,
            "rows_scanned": len(days) + self.excluded.get(lane_id, 0),
            "rows_excluded": self.excluded.get(lane_id, 0),
            "scenarios": [compare_day(kind, day, lane, reserve, objective) for kind, day in cases if day],
        }


def compare_day(kind, day, lane, reserve, objective):
    target = day.demand if objective == "clear_demand" else day.dispatched
    # Keep existing regular departures except recorded surplus. Reserve departures
    # are hypothetical. We never assume more special trips than already ran.
    minimum_regular = max(0, day.regular - day.surplus)
    # Honor actual dispatch evidence if recorded loading exceeded the planning target.
    trips = day.regular + day.special
    historical_load = (day.dispatched + trips - 1) // trips if trips else 0
    capacity = max(lane.target_capacity, historical_load)
    choices = (
        (regular, special, min(target, (regular + special) * capacity))
        for regular in range(minimum_regular, day.regular + reserve + 1)
        for special in range(day.special + 1)
    )

    def cost(regular, special):
        return regular * lane.regular_rate + special * lane.special_rate

    # Maximise dispatch up to the target, then minimise modeled transport cost.
    regular, special, dispatched = min(
        choices, key=lambda c: (-c[2], cost(c[0], c[1]), c[0] + c[1], c[1]),
    )
    baseline_cost = cost(day.regular, day.special)
    simulated_cost = cost(regular, special)
    return {
        "kind": kind, "date": day.date, "demand_ldm": day.demand / 10,
        "target_dispatch_ldm": target / 10, "capacity_used_ldm": capacity / 10,
        "historical_utilisation_pct": day.utilisation, "recorded_surplus": day.surplus,
        "historical": {
            "regular": day.regular, "special": day.special, "dispatched_ldm": day.dispatched / 10,
            "deferred_ldm": day.deferred / 10, "cost_eur": baseline_cost,
        },
        "simulation": {
            "regular": regular, "special": special, "dispatched_ldm": dispatched / 10,
            "deferred_ldm": (day.demand - dispatched) / 10, "cost_eur": simulated_cost,
        },
        "difference_eur": baseline_cost - simulated_cost,
        "additional_dispatch_ldm": (dispatched - day.dispatched) / 10,
    }
