import { useState } from "react";
import { Check, Clock3, History, Pause } from "lucide-react";
import type { Decision, NetNode } from "../api/types";
import { dt } from "../lib";

export function DecisionHistory({ decisions, nodes }: { decisions: Decision[]; nodes: NetNode[] }) {
  const [expanded, setExpanded] = useState(false);
  const ordered = decisions.slice().sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at));
  const visible = expanded ? ordered : ordered.slice(0, 5);
  const name = (id: string) => nodes.find(n => n.id === id)?.name ?? id;
  const labels: Record<string, string> = { accept: "Route approved", hold: "Hold / stop requested", keep: "Current plan retained", defer: "Review deferred" };

  return <section className="card manager-history">
    <div className="section-summary"><h2><History size={19} /> Decision history</h2><span className="count-badge">{decisions.length} decisions</span></div>
    {!visible.length && <div className="events-empty"><History size={24} /><div><b>No decisions yet</b><p>Approvals and hold decisions appear here with your reason.</p></div></div>}
    <ol className="decision-list">{visible.map(d => {
      const Icon = d.action === "accept" ? Check : d.action === "hold" ? Pause : Clock3;
      return <li className={`decision-entry decision-entry--${d.action}`} key={d.id}>
        <span className="decision-symbol"><Icon size={17} /></span>
        <div className="decision-content"><div className="decision-entry-heading"><b>{labels[d.action] ?? d.action}</b><span className="shipment-reference">{d.shipment_id}</span></div><p>{d.reason}</p><small>{(d.action === "hold" ? d.reviewed_path ?? d.path : d.path).map(name).join(" → ")}</small></div>
        <time dateTime={d.updated_at}>{dt(d.updated_at)}</time>
      </li>;
    })}</ol>
    {ordered.length > 5 && <button className="history-expand" type="button" aria-expanded={expanded} onClick={() => setExpanded(v => !v)}>{expanded ? "Show recent decisions" : `Show all ${ordered.length} decisions`}</button>}
  </section>;
}
