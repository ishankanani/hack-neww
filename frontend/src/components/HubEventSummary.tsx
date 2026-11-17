import { Ban, Clock3 } from "lucide-react";
import type { HubRouteNotice } from "./routeHubEvents";
import { dt } from "../lib";
import "../hub-events.css";

export function HubEventSummary({notices}: {notices: HubRouteNotice[]}) {
  if (!notices.length) return null;
  return <section className="hub-event-summary" aria-label="Manager notices on this route">
    {notices.map(notice => <article key={notice.node.id} className={`hub-event-card hub-event-card--${notice.kind}`}>
      {notice.kind === "closure" ? <Ban size={18}/> : <Clock3 size={18}/>}
      <div><h4>{notice.node.name} <span>{notice.title}</span></h4>
        {notice.events.map(event => <p key={event.id}><b>{event.reason}</b><small>{event.kind === "closure" ? "Closure" : `Delay +${event.minutes} min`} · {dt(event.start)} – {dt(event.end)}</small></p>)}
        <p className="hub-event-impact">{notice.impact}</p>
        <small>Planned hub visit · {dt(notice.visitStart)}{notice.visitEnd !== notice.visitStart ? ` – ${dt(notice.visitEnd)}` : ""}</small>
      </div>
    </article>)}
  </section>;
}
