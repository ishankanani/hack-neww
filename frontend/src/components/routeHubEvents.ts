import type { NetNode, RouteOption, ScenarioEvent } from "../api/types";

export interface HubRouteNotice {
  node: NetNode;
  events: ScenarioEvent[];
  kind: "closure" | "delay" | "information";
  title: string;
  impact: string;
  visitStart: string;
  visitEnd: string;
  delayMinutes: number;
  affectsVisit: boolean;
}

const waitingTime = (minutes:number) => minutes < 60 ? `${minutes} min` : `${Math.floor(minutes/60)}h${minutes%60 ? ` ${minutes%60}m` : ""}`;

/** Match operational notices to actual hub visits, not to roads passing nearby. */
export function routeHubEvents(option: RouteOption | undefined, nodes: NetNode[], events: ScenarioEvent[], revision?: number, now = Date.now()): HubRouteNotice[] {
  if (!option || option.is_demo) return [];
  const legs = option.road_legs ?? [];
  return option.path.flatMap<HubRouteNotice>((id, index) => {
    const node = nodes.find(n => n.id === id);
    if (!node) return [];
    const steps = option.steps.filter(s => s.location === id && s.type !== "drive" && s.type !== "legal_wait" && s.type !== "weekend_hold");
    const visitStart = index === 0 ? option.depart_at : legs.find(l => l.to === id)?.arrival ?? steps[0]?.start ?? option.eta;
    const visitEnd = index === option.path.length - 1 ? option.eta : legs.find(l => l.from === id)?.departure ?? steps[steps.length - 1]?.end ?? visitStart;
    const start = Date.parse(visitStart), end = Math.max(start + 60000, Date.parse(visitEnd));
    if (!Number.isFinite(start) || !Number.isFinite(end)) return [];
    const overlaps = (e: ScenarioEvent) => Date.parse(e.start) < end && Date.parse(e.end) > start;
    const relevant = events.filter(e => e.node === id && ["hub_delay", "closure"].includes(e.kind) &&
      (overlaps(e) || Date.parse(e.start) <= now && now < Date.parse(e.end)));
    if (!relevant.length) return [];
    const affecting = relevant.filter(overlaps);
    const closure = affecting.some(e => e.kind === "closure");
    const pending = revision !== undefined && option.revision !== revision;
    const affectsVisit = affecting.length > 0;
    // These are the engine's recorded hub waits, not another delay added by the map.
    const delayMinutes = pending || !affectsVisit ? 0 : option.steps.filter(s => s.location === id && s.type === "hub_delay" &&
      ["MANAGER HUB EVENT", "MANAGER CLOSURE"].includes(s.source)).reduce((total, s) => total + s.minutes, 0);
    return [{ node, events: relevant, kind: affectsVisit ? closure ? "closure" : "delay" : "information",
      title: affectsVisit ? closure ? "Hub closure" : "Hub delay" : "Current hub notice",
      visitStart, visitEnd, affectsVisit, delayMinutes,
      impact: !affectsVisit ? "Does not overlap the planned hub visit." : pending ? "Manager update received. Recalculate the route to update ETA." :
        delayMinutes > 0 ? `${waitingTime(delayMinutes)} hub waiting included in ETA.` : "Overlaps the planned visit. Check hub availability before dispatch.",
    }];
  });
}

export function hubNoticeDetails(notice: HubRouteNotice, formatTime: (value:string) => string): string[] {
  return [...notice.events.flatMap(event => [
    `${event.kind === "closure" ? "Closure" : `Delay +${event.minutes} min`}: ${event.reason}`,
    `${formatTime(event.start)} – ${formatTime(event.end)}`,
  ]), notice.impact, `Planned hub visit: ${formatTime(notice.visitStart)} – ${formatTime(notice.visitEnd)}`, "Reported by your traffic manager"];
}

export function hubNoticeMarker(notice: HubRouteNotice) {
  const button = document.createElement("button");
  button.className = `hub-event-marker hub-event-marker--${notice.kind}`;
  const label = `${notice.node.name}: ${notice.title}`;
  button.setAttribute("aria-label", label); button.title = label;
  button.textContent = `${notice.kind === "closure" ? "⛔" : "◷"} ${notice.title}${notice.delayMinutes > 0 ? ` · +${waitingTime(notice.delayMinutes)}` : ""}`;
  return button;
}
