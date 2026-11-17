import { useCallback, useEffect, useRef, useState } from "react";
import { useVisibleRows } from "./useVisibleRows";
import { Save, RefreshCw, ArrowUpRight, CircleCheck, CircleDashed } from "lucide-react";
import { api } from "../api/client";
import type { NetNode, Shipment } from "../api/types";
import { dt, eur, riskCls } from "../lib";

/**
 * The saved-journey queue, shown right under the planner so a manager can see a
 * save land instead of trusting a one-line confirmation. Read-only: approving a
 * plan still happens in the control room.
 */
export function SavedJourneys({ nodes, refreshKey, onReview }: { nodes: NetNode[]; refreshKey: number; onReview: (id?:string) => void }) {
  const [ships, setShips] = useState<Shipment[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try { const r = await api.shipments(); setShips(r.shipments); setError(""); }
    catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }, []);

  useEffect(() => { void load(); }, [load, refreshKey]);

  const name = (id: string) => nodes.find((n) => n.id === id)?.name ?? id;
  const mine = (ships ?? []).filter((s) => s.data_kind !== "demo");
  const listRef = useRef<HTMLDivElement>(null);
  const listStyle = useVisibleRows(listRef, 4, [mine.length, ships]);

  return (
    <details className="card saved-journeys" open>
      <summary className="card__h saved-journeys-summary">
        <div>
          <h2><Save size={15} className="h-ic" /> Saved journeys <span className="mini">{mine.length}</span></h2>
        </div>
        <button className="icon-button" aria-label="Refresh saved journeys" onClick={(e) => { e.preventDefault(); void load(); }}>
          <RefreshCw size={14} className={busy ? "spin" : ""} />
        </button>
      </summary>

      {error && <div role="alert" className="notice notice--warn">{error}</div>}

      {ships && mine.length === 0 && (
        <div className="empty">Nothing saved yet. Calculate a route and choose “Save plan for review”.</div>
      )}

      <div className="saved-list" ref={listRef} style={listStyle} tabIndex={mine.length > 4 ? 0 : undefined} aria-label={mine.length > 4 ? "Saved journeys, scroll for more" : undefined}>
        {[...mine].sort((a,b)=>Date.parse(b.created_at)-Date.parse(a.created_at)).map((s) => (
          <div className="saved-row" key={s.id}>
            <span className="saved-id">
              <b>{s.id}</b>
              <small>{dt(s.created_at)}</small>
            </span>
            <span className="saved-route">
              <b>{s.route.map(name).join(" → ")}</b>
              <small>{s.weight_kg.toLocaleString("en-GB")} kg · {eur(s.value_eur)} · {s.distance_km} km</small>
            </span>
            <span className="saved-eta">
              <small>Saved ETA</small>
              <b>{dt(s.current_eta)}</b>
            </span>
            <span className={`saved-state ${s.approved_at ? "is-approved" : ""}`}>
              {s.approved_at ? <CircleCheck size={13} /> : <CircleDashed size={13} />}
              {s.status.replace(/_/g, " ")}
            </span>
            <span className={riskCls(s.risk_level)}>{s.risk_level}</span>
            <span className="saved-row-actions">{s.disruption_savings && (
              <span className="saved-flag" title={s.disruption_savings.basis}>
                re-routed · {Math.abs(s.disruption_savings.minutes_avoided)}m avoided
              </span>
            )}
            <button className="linkbtn saved-review-button" aria-label={`Review ${s.id} in control room`} onClick={()=>onReview(s.id)}>Review <ArrowUpRight size={13}/></button></span>
          </div>
        ))}
      </div>

      {mine.length > 0 && (
        <div className="saved-foot">
          <span>Saved plans are proposals. A shipment’s route changes only when a manager approves it.</span>
          <button className="linkbtn" onClick={()=>onReview()}>Open control room <ArrowUpRight size={13} /></button>
        </div>
      )}
    </details>
  );
}
