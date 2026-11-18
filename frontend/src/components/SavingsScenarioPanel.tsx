import { Loader2 } from "lucide-react";
import type { SavingsScenarioKind, SavingsScenarioObjective, SavingsScenarios } from "../api/types";
import { eur } from "../lib";
import "../savings-scenarios.css";

export const scenarioLabels: Record<SavingsScenarioKind, string> = {
  efficient: "Efficient day",
  special_trips: "Most special trips",
  freight_backlog: "Most freight deferred",
  surplus_trailers: "Most surplus trailers",
};

const ldm = (value: number) => `${value.toLocaleString("en-GB", {maximumFractionDigits: 1})} LDM`;
const dateLabel = (date: string) => new Intl.DateTimeFormat("en-GB", {
  dateStyle: "medium", timeZone: "UTC",
}).format(new Date(date));

interface Props {
  data: SavingsScenarios | null;
  lane: string;
  reserve: number;
  objective: SavingsScenarioObjective;
  loading: boolean;
  error: string;
  onLane: (value: string) => void;
  onReserve: (value: number) => void;
  onObjective: (value: SavingsScenarioObjective) => void;
}

export function SavingsScenarioPanel({
  data, lane, reserve, objective, loading, error, onLane, onReserve, onObjective,
}: Props) {
  const results = data?.lane === lane && data.reserve === reserve && data.objective === objective
    ? data
    : null;
  const summary = results?.lane_summary;

  return <section aria-label="CSV dispatch scenarios" className="csv-savings">
    <div className="card csv-savings-controls">
      <div>
        <h2>Compare dispatch plans</h2>
        <p>Compare estimated dispatch costs for the same day's recorded freight demand. All results are simulations.</p>
      </div>
      <div className="csv-savings-fields">
        <label>Destination lane<select value={lane} onChange={e => onLane(e.target.value)}>
          {(data?.lanes ?? [{id: "R01", name: "Hamburg"}]).map(item => <option value={item.id} key={item.id}>{item.name} · {item.id}</option>)}
        </select></label>
        <label>Extra regular trailers available<select value={reserve} onChange={e => onReserve(Number(e.target.value))}>
          {[0, 1, 2, 3, 4].map(value => <option key={value} value={value}>{value === 0 ? "None" : `Up to ${value}`}</option>)}
        </select></label>
        <label>Dispatch goal<select value={objective} onChange={e => onObjective(e.target.value as SavingsScenarioObjective)}>
          <option value="match_dispatch">Match recorded dispatch</option>
          <option value="clear_demand">Send as much as possible today</option>
        </select></label>
      </div>
    </div>

    {loading && <div className="card empty" role="status"><Loader2 size={18} className="spin"/> Calculating scenarios…</div>}
    {!loading && !error && results && <>
      {summary && <section className="savings-headline" aria-label="Estimated lane savings">
        <div className="savings-headline-main">
          <span className="eyebrow">SIMULATED DISPATCH SAVINGS</span>
          <strong>{summary.saving_eur > 0 ? "+" : summary.saving_eur < 0 ? "−" : ""}{eur(Math.abs(summary.saving_eur))}</strong>
          <small>{summary.days.toLocaleString("en-GB")} days · {dateLabel(summary.first_date)} – {dateLabel(summary.last_date)}</small>
          <small className="csv-headline-freight">
            {summary.additional_dispatch_ldm > 0
              ? `${ldm(summary.additional_dispatch_ldm)} more freight sent across those days`
              : "Same amount of freight sent each day"}
          </small>
        </div>
        <div className="savings-breakdown">
          <span><small>Recorded plan estimate</small><b>{eur(summary.recorded_cost_eur)}</b></span>
          <span><small>Simulated plan estimate</small><b>{eur(summary.simulated_cost_eur)}</b></span>
        </div>
      </section>}
      <div className="csv-savings-source">
        <span>{summary
          ? `${summary.cheaper_days} lower cost · ${summary.equal_days} same cost · ${summary.costlier_days} higher cost`
          : `${results.rows_scanned} days analysed`}{results.rows_excluded > 0 ? ` · ${results.rows_excluded} inconsistent rows excluded` : ""}</span>
        <span>{eur(results.regular_rate_eur)} regular · {eur(results.special_rate_eur)} special trip</span>
      </div>
      <div className="csv-savings-grid">
        {results.scenarios.map(scenario => {
          const original = scenario.historical;
          const revised = scenario.simulation;
          const difference = scenario.difference_eur;
          const currency = eur(Math.abs(difference));
          const extra = scenario.additional_dispatch_ldm;
          return <article className="card csv-savings-case" key={scenario.kind}>
            <header>
              <div><h3>{scenarioLabels[scenario.kind]}</h3><small>{dateLabel(scenario.date)} · {ldm(scenario.demand_ldm)} demand</small></div>
              <span className={`csv-savings-delta ${difference < 0 ? "is-extra" : difference === 0 ? "is-flat" : ""}`}>
                {difference > 0 ? `${currency} saved` : difference < 0 ? `${currency} extra` : "Same cost"}
              </span>
            </header>
            <table><thead><tr><th scope="col">Measure</th><th scope="col">Recorded plan</th><th scope="col">Simulated plan</th></tr></thead>
              <tbody>
                <tr><th scope="row">Regular trailers</th><td>{original.regular}</td><td>{revised.regular}</td></tr>
                <tr><th scope="row">Special trips</th><td>{original.special}</td><td>{revised.special}</td></tr>
                <tr><th scope="row">Sent that day</th><td>{ldm(original.dispatched_ldm)}</td><td>{ldm(revised.dispatched_ldm)}</td></tr>
                <tr><th scope="row">Deferred freight</th><td>{ldm(original.deferred_ldm)}</td><td>{ldm(revised.deferred_ldm)}</td></tr>
                <tr><th scope="row">Estimated dispatch cost</th><td>{eur(original.cost_eur)}</td><td><b>{eur(revised.cost_eur)}</b></td></tr>
              </tbody>
            </table>
            <footer>
              {extra > 0 ? `${ldm(extra)} more sent that day` : "Same freight sent that day"}
              {revised.deferred_ldm > 0 && ` · ${ldm(revised.deferred_ldm)} still deferred`}
              {extra > 0 && difference < 0 && <small>{`€${(-difference / extra).toFixed(2)} extra per additional loading metre sent`}</small>}
            </footer>
          </article>;
        })}
      </div>
      {results.scenarios.length === 0 && <div className="card empty">No eligible scenario records for this lane.</div>}
      <details className="card savings-explainer csv-savings-method">
        <summary>How the simulation works</summary>
        <p>The cases come from <i>disposition.csv</i>. We select the highest utilisation day with no extras or deferrals, the most special trips, the largest deferred load, and the most surplus trailers on days without extras or deferrals. A category appears when the selected lane has a matching day.</p>
        <p>Both plans use the tariffs in <i>relationen.csv</i>. The model uses {ldm(results.target_capacity_ldm)} per trailer as the planning target, allowing the recorded average load when higher, up to the {ldm(results.rated_capacity_ldm)} trailer limit. It assumes the day's demand is known in advance and that the selected reserve can be booked at the regular tariff. It can cancel recorded surplus trailers and use up to the recorded number of special trips.</p>
        <p>The lane total sums every eligible day. The model calculates each day independently using the selected reserve and dispatch goal. Later dispatch costs, cancellation fees, delivery times and revenue are outside this comparison. LDM means loading metres.</p>
      </details>
    </>}
  </section>;
}
