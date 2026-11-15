import { useState } from "react";
import { FlaskConical, Car, Factory, Ban, Check, Cone, Clock3, Plus, CalendarDays } from "lucide-react";
import { api } from "../api/client";
import type { NetNode, Operations } from "../api/types";
import { dt, localInput } from "../lib";

const EVENT_TYPES = [
  { kind: "hub_delay", label: "Hub delay", icon: Factory, hint: "Loading or handling backlog" },
  { kind: "closure", label: "Hub closure", icon: Ban, hint: "Facility unavailable" },
  { kind: "traffic", label: "Heavy traffic", icon: Car, hint: "Delay across all routes" },
  { kind: "roadwork", label: "Roadwork", icon: Cone, hint: "Delay across all routes" },
] as const;
type EventKind = typeof EVENT_TYPES[number]["kind"];

export function ScenarioStudio({ nodes, ops, onChange }: {
  nodes: NetNode[]; ops: Operations | null; onChange: () => Promise<void>;
}) {
  const [node, setNode] = useState("HN");
  const [minutes, setMinutes] = useState(120);
  const [start, setStart] = useState(() => localInput(new Date()));
  const [end, setEnd] = useState(() => localInput(new Date(Date.now() + 24 * 3600000)));
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [kind, setKind] = useState<EventKind>("hub_delay");
  const [filter, setFilter] = useState<"current" | "past">("current");
  const isHub = kind === "hub_delay" || kind === "closure";
  const name = (id: string) => nodes.find(n => n.id === id)?.name ?? id;
  const now = Date.now();
  const current = (ops?.events ?? []).filter(e => Date.parse(e.end) > now).sort((a, b) => Date.parse(a.start) - Date.parse(b.start));
  const past = (ops?.events ?? []).filter(e => Date.parse(e.end) <= now).sort((a, b) => Date.parse(b.end) - Date.parse(a.end));
  const events = filter === "current" ? current : past;

  async function apply() {
    if (!start || !end || !Number.isFinite(Date.parse(start)) || !Number.isFinite(Date.parse(end)) || Date.parse(end) <= Date.parse(start)) {
      setErr("Choose an effective end after the start."); return;
    }
    if (Date.parse(end) <= Date.now()) { setErr("The event must end in the future."); return; }
    if (isHub && !nodes.some(n => n.id === node)) { setErr("Select a facility for this event."); return; }
    setBusy(true); setErr("");
    try {
      const defaultReason =
        kind === "traffic" ? "Heavy traffic · all routes" :
        kind === "roadwork" ? "Roadwork · all routes" :
        kind === "closure" ? "Manager-reported facility closure" :
        "Manager-reported hub congestion";
      await api.addEvent({
        kind: kind === "roadwork" ? "traffic" : kind,
        node: kind === "hub_delay" || kind === "closure" ? node : undefined,
        start: new Date(start).toISOString(),
        end: new Date(end).toISOString(),
        minutes: kind === "closure" ? 0 : minutes,
        reason: reason.trim() || defaultReason,
      });
      await onChange();
      setReason(""); setFilter("current");
    } catch (e) { setErr(String(e)); }
    finally { setBusy(false); }
  }

  async function resolve(id: string) {
    setBusy(true); setErr("");
    try { await api.resolveEvent(id); await onChange(); }
    catch (e) { setErr(String(e)); }
    finally { setBusy(false); }
  }

  return <section className="card scenario-workspace">
    <div className="section-summary"><h2><FlaskConical size={19} /> Scenario Studio</h2><span className="count-badge">{current.length} current</span></div>
    <div className="scenario-create">
      <div className="scenario-type-picker" role="group" aria-label="Event type">{EVENT_TYPES.map(type => <button key={type.kind} type="button" disabled={busy} aria-pressed={kind === type.kind} onClick={() => { setKind(type.kind); setErr(""); }}><type.icon size={20} /><span>{type.label}<small>{type.hint}</small></span>{kind === type.kind && <Check size={15} className="type-check" />}</button>)}</div>
      <form onSubmit={e => { e.preventDefault(); void apply(); }}>
        <fieldset disabled={busy} className="scenario-form-grid">
          {isHub && <label>Facility<select required aria-label="Scenario target facility" value={node} onChange={e => setNode(e.target.value)}>{nodes.map(n => <option key={n.id} value={n.id}>{n.name}</option>)}</select></label>}
          {kind !== "closure" && <label>Added delay<select aria-label="Scenario delay duration" value={minutes} onChange={e => setMinutes(Number(e.target.value))}>{[30,60,90,120,180,240].map(n => <option key={n} value={n}>{n} minutes</option>)}</select></label>}
          <label>From · local time<input required aria-label="Scenario effective from" type="datetime-local" value={start} onChange={e => setStart(e.target.value)} /></label>
          <label>Until · local time<input required aria-label="Scenario effective until" type="datetime-local" min={start} value={end} onChange={e => setEnd(e.target.value)} /></label>
          <label className="scenario-reason">Reason · optional<input aria-label="Scenario manager reason" maxLength={500} placeholder="Add a short note for your team" value={reason} onChange={e => setReason(e.target.value)} /></label>
        </fieldset>
        {err && <div role="alert" className="notice notice--warn">{err}</div>}
        <div className="scenario-submit"><p>{isHub ? `Applies to journeys visiting ${name(node)} during this period.` : "Applies to all journeys driving during this period."} Approved plans require your review.</p><button className="btn btn--sm" disabled={busy || !nodes.length}><Plus size={15} />{busy ? "Adding…" : "Add event"}</button></div>
      </form>
    </div>
    <div className="scenario-register">
      <div className="register-heading"><h3><Clock3 size={16} /> Events</h3><div className="event-filters" role="group" aria-label="Event list"><button type="button" aria-pressed={filter === "current"} onClick={() => setFilter("current")}>Current <span>{current.length}</span></button><button type="button" aria-pressed={filter === "past"} onClick={() => setFilter("past")}>Past <span>{past.length}</span></button></div></div>
      {!events.length && <div className="events-empty"><CalendarDays size={24} /><div><b>{filter === "current" ? "No current events" : "No past events"}</b><p>{filter === "current" ? "Add a condition above when your team needs to plan around it." : "Events appear here after their effective period ends."}</p></div></div>}
      <div className="event-list">{events.map(e => {
        const expired = Date.parse(e.end) <= now;
        const upcoming = Date.parse(e.start) > now;
        const type = EVENT_TYPES.find(t => t.kind === (e.kind === "traffic" && /roadwork/i.test(e.reason) ? "roadwork" : e.kind));
        const Icon = type?.icon ?? Car;
        const scope = e.node ? name(e.node) : e.origin && e.destination ? `${name(e.origin)} → ${name(e.destination)}` : "All routes";
        return <article className={`event-card ${expired ? "event-card--past" : ""}`} key={e.id}>
          <div className={`event-kind-icon ${e.kind === "closure" ? "event-kind-icon--closure" : ""}`}><Icon size={19} /></div>
          <div className="event-content"><div className="event-title"><b>{type?.label ?? "Operational event"}</b><span className={`event-state ${expired ? "ended" : upcoming ? "upcoming" : "active"}`}>{expired ? "Ended" : upcoming ? "Scheduled" : "Active"}</span></div><strong className="event-scope">{scope}{e.kind !== "closure" && <span>+{e.minutes} min</span>}</strong><p>{e.reason}</p><div className="event-meta"><span><CalendarDays size={13} /><time dateTime={e.start}>{dt(e.start)}</time><span>→</span><time dateTime={e.end}>{dt(e.end)}</time></span>{!expired && <span>{e.affected_count ?? 0} journeys affected</span>}</div></div>
          {!expired && <button type="button" className="event-resolve" aria-label={`Resolve ${e.reason}`} disabled={busy} onClick={() => void resolve(e.id)}><Check size={15} />Resolve</button>}
        </article>;
      })}</div>
    </div>
  </section>;
}
