import { useEffect, useState } from "react";
import { CalendarClock, Plus, Trash2 } from "lucide-react";
import { api } from "../api/client";
import type { NetNode, Service } from "../api/types";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function ServiceSettings({ nodes, onChange }: { nodes: NetNode[]; onChange: () => void }) {
  const [rows, setRows] = useState<Service[]>([]);
  const [origin, setOrigin] = useState("R16");
  const [destination, setDestination] = useState("R21");
  const [days, setDays] = useState([0, 1, 2, 3, 4]);
  const [time, setTime] = useState("18:00");
  const [cutoff, setCutoff] = useState("30");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const name = (id: string) => nodes.find(n => n.id === id)?.name ?? id;
  const validConnection = nodes.some(n => n.id === origin) && nodes.some(n => n.id === destination) && origin !== destination;

  useEffect(() => {
    let alive = true;
    api.services().then(r => { if (alive) setRows(r.services); }).catch(e => { if (alive) setError(String(e)); });
    return () => { alive = false; };
  }, []);

  async function save() {
    if (!validConnection || !days.length || cutoff.trim() === "" || !Number.isInteger(Number(cutoff)) || Number(cutoff) < 0 || Number(cutoff) > 1440) return;
    setBusy(true); setError("");
    try {
      await api.saveService({ origin, destination, weekdays: [...days].sort(), departure_time: time, timezone: "Europe/Berlin", cutoff_minutes: Number(cutoff) });
      setRows((await api.services()).services); onChange();
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  async function remove(id: string) {
    setBusy(true); setError("");
    try { await api.deleteService(id); setRows(r => r.filter(s => s.id !== id)); onChange(); }
    catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  return <details className="card departure-schedules" open>
    <summary className="section-summary"><span><CalendarClock size={19} /> Departure schedules</span><span className="count-badge">{rows.length} scheduled</span></summary>
    <div className="schedule-body">
      {error && <div role="alert" className="notice notice--warn">{error}</div>}
      <form onSubmit={e => { e.preventDefault(); void save(); }}>
        <fieldset disabled={busy} className="schedule-fields">
          <label>From<select value={origin} onChange={e => setOrigin(e.target.value)}>{nodes.map(n => <option key={n.id} value={n.id}>{n.name}</option>)}</select></label>
          <label>To<select value={destination} onChange={e => setDestination(e.target.value)}>{nodes.map(n => <option key={n.id} value={n.id}>{n.name}</option>)}</select></label>
          <label>Departure · Berlin time<input type="time" required value={time} onChange={e => setTime(e.target.value)} /></label>
          <label>Ready before departure · minutes<input type="number" required min={0} max={1440} step={1} value={cutoff} onChange={e => setCutoff(e.target.value)} /></label>
        </fieldset>
        {origin === destination && <p className="field-error" role="alert">Choose two different facilities.</p>}
        <div className="schedule-bottom"><div className="day-picker" role="group" aria-label="Operating days">{DAYS.map((d, i) => <button key={d} type="button" disabled={busy} aria-pressed={days.includes(i)} onClick={() => setDays(v => v.includes(i) ? v.filter(x => x !== i) : [...v, i])}>{d}</button>)}</div><button className="btn btn--sm" disabled={busy || !days.length || !validConnection}><Plus size={15} />{busy ? "Saving…" : "Add departure"}</button></div>
        {!days.length && <p className="field-error" role="alert">Select at least one operating day.</p>}
      </form>
      <div className="schedule-list">{rows.map(r => <article className="schedule-item" key={r.id}>
        <div className="schedule-time">{r.departure_time}<small>Berlin time</small></div>
        <div className="schedule-connection"><b>{name(r.origin)} → {name(r.destination)}</b><small>{r.weekdays.slice().sort().map(d => DAYS[d]).join(" · ")}</small></div>
        <span className="schedule-cutoff">Ready {r.cutoff_minutes} min before</span>
        <button className="icon-button" disabled={busy} aria-label={`Remove ${name(r.origin)} to ${name(r.destination)} departure at ${r.departure_time}`} onClick={() => void remove(r.id)}><Trash2 size={16} /></button>
      </article>)}</div>
    </div>
  </details>;
}
