import type { Components, OptCost, RouteOption } from "../api/types";
import { eur, hm } from "../lib";
import "../route-tradeoff.css";

const timeGroups: {label: string; keys: (keyof Components)[]}[] = [
  {label: "Driving", keys: ["transport"]},
  {label: "Traffic", keys: ["traffic"]},
  {label: "Handling and hub delays", keys: ["transfer", "hub_delay"]},
  {label: "Waiting for departure", keys: ["schedule_wait", "manager_wait"]},
  {label: "Weekend and holiday holds", keys: ["weekend_hold", "legal_wait"]},
  {label: "Driver breaks and rest", keys: ["driver_break", "driver_rest", "weekly_rest"]},
  {label: "Weather", keys: ["weather"]},
];
const sum = (values: Components, keys: (keyof Components)[]) => keys.reduce((acc, key) => acc + (values[key] ?? 0), 0);
const km = (value: number) => `${value.toLocaleString("en-GB", {maximumFractionDigits: 1})} km`;
const litres = (value: number) => `${value.toLocaleString("en-GB", {maximumFractionDigits: 1})} L`;
const difference = (delta: number, format: (value: number) => string, less = "less", more = "more") =>
  delta === 0 ? "Same" : `${format(Math.abs(delta))} ${delta > 0 ? less : more}`;

function LegCosts({cost, title, name}: {cost?: OptCost; title: string; name: (id: string) => string}) {
  return <div>
    <h4>{title}</h4>
    {cost?.legs?.length ? <ul>
      {cost.legs.map((leg, index) => <li key={`${leg.from}-${leg.to}-${index}`}>
        <strong>{name(leg.from)} → {name(leg.to)}</strong>
        <span>{eur(leg.transport_eur)} · {Math.round(leg.ldm_share * 100)}% of {eur(leg.tariff_eur)} {leg.basis === "lane_tariff" ? "lane tariff" : "distance estimate"}</span>
      </li>)}
      {!!cost.detour_surcharge_eur && <li><strong>Weather detour</strong><span>{eur(cost.detour_surcharge_eur)} extra</span></li>}
    </ul> : <p>Leg prices are unavailable for this quote.</p>}
  </div>;
}

export function RouteTradeoff({option, hasSafe, name}: {option: RouteOption; hasSafe: boolean; name: (id: string) => string}) {
  const comparison = option.comparison;
  const baseline = option.baseline_snapshot;
  const baselineComponents = baseline?.components;
  const reference = option.dispatch_action === "wait" ? "current itinerary" : "direct";
  const timeChanges = baselineComponents ? timeGroups.map(group => ({
    label: group.label,
    delta: sum(baselineComponents, group.keys) - sum(option.components, group.keys),
  })).filter(row => row.delta !== 0).sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta)) : [];
  const objective = option.optimization === "cost" ? "Lowest cost within deadline"
    : option.optimization === "balanced" ? "Balanced · €50 per transit hour" : "Fastest arrival";
  const lanes = option.cost.legs?.filter(leg => leg.basis === "lane_tariff").length;
  const estimated = option.cost.legs?.filter(leg => leg.basis === "distance_estimate").length;
  const basis = [
    lanes ? `${lanes} lane tariff${lanes === 1 ? "" : "s"}` : "",
    estimated ? `${estimated} distance estimate${estimated === 1 ? "" : "s"}` : "",
  ].filter(Boolean).join(" and ");

  return <section className="optimization-insight route-tradeoff" aria-label="Optimization result">
    <header>
      <div><span className="eyebrow">OPTIMIZATION RESULT</span><h3>{option.label}</h3></div>
      <span>{objective}{!hasSafe ? " · Manager review required" : !option.risk.deadline_ok ? " · Deadline missed" : ""}</span>
    </header>
    {comparison && <div className="route-tradeoff-metrics">
      <div>
        <h4>Cost vs {reference}</h4>
        <b>{difference(comparison.money_saved_eur, eur)}</b>
        <p>{eur(option.cost.transport_eur)} selected · {eur(baseline?.cost?.transport_eur ?? option.cost.transport_eur + comparison.money_saved_eur)} {reference}</p>
        {basis && <p>Uses {basis}, allocated to this shipment’s share of the trailer.</p>}
      </div>
      <div>
        <h4>Time vs {reference}</h4>
        <b>{difference(comparison.minutes_saved, hm, "faster", "slower")}</b>
        <p>{hm(option.total_minutes)} selected · {hm(baseline?.total_minutes ?? option.total_minutes + comparison.minutes_saved)} {reference}</p>
        {!!timeChanges.length && <p>{timeChanges.slice(0, 2).map(row => `${row.label}: ${difference(row.delta, hm)}`).join(" · ")}</p>}
      </div>
      <div>
        <h4>Fuel vs {reference}</h4>
        <b>{difference(comparison.fuel_saved_l, litres)}</b>
        <p>{litres(option.cost.fuel_l)} selected · {litres(baseline?.cost?.fuel_l ?? option.cost.fuel_l + comparison.fuel_saved_l)} {reference}</p>
        {baseline?.cost && <p>{km(option.cost.distance_km)} selected · {km(baseline.cost.distance_km)} {reference}. Estimated at 30 L per 100 km.</p>}
      </div>
    </div>}
    {comparison && (option.cost.legs?.length || baseline?.cost?.legs?.length || timeChanges.length) ? <details className="route-tradeoff-details">
      <summary>See how this comparison was calculated</summary>
      <div className="route-tradeoff-costs">
        <LegCosts cost={option.cost} title="Selected route costs" name={name}/>
        <LegCosts cost={baseline?.cost} title={reference === "direct" ? "Direct route costs" : "Current itinerary costs"} name={name}/>
      </div>
      {option.remaining_only && <p>Totals include the completed distance. Leg prices cover the remaining journey.</p>}
      {!!timeChanges.length && <ul className="route-tradeoff-times">{timeChanges.map(row => <li key={row.label}>
        <strong>{row.label}</strong><span>{difference(row.delta, hm)}</span>
      </li>)}</ul>}
      <p>Fuel is a distance estimate, rounded per leg. It is shown separately from transport cost.</p>
    </details> : null}
  </section>;
}
