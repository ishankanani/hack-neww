import type { Incident } from "../api/types";

export const ALTERNATIVE_COLORS = ["#5268b9", "#9a62ae", "#b48b35", "#397d9c", "#7a698e", "#ad7261"];
export const alternativeColor = (index: number) => ALTERNATIVE_COLORS[index % ALTERNATIVE_COLORS.length];

/** Put the option label near its largest road separation, rather than a shared endpoint. */
export function alternativeLabelPoint(road: number[][], selected: number[][]): number[] | null {
  if (road.length < 2) return null;
  let best = road[Math.floor(road.length / 2)], separation = -1;
  const stride = Math.max(1, Math.floor(road.length / 80));
  const referenceStride = Math.max(1, Math.floor(selected.length / 160));
  for (let i = Math.floor(road.length * .15); i < road.length * .85; i += stride) {
    const p = road[i], scale = Math.cos(p[1] * Math.PI / 180);
    let distance = Infinity;
    for (let j = 0; j < selected.length - 1; j += referenceStride) {
      const a = selected[j], b = selected[Math.min(j + referenceStride, selected.length - 1)];
      const dx = (b[0] - a[0]) * scale, dy = b[1] - a[1];
      const x = (p[0] - a[0]) * scale, y = p[1] - a[1];
      const t = Math.max(0, Math.min(1, (x * dx + y * dy) / (dx * dx + dy * dy || 1)));
      distance = Math.min(distance, Math.hypot(x - t * dx, y - t * dy));
    }
    if (distance > separation) { separation = distance; best = p; }
  }
  return best;
}

export function routePointForIncident(incident: Incident, route: number[][]): [number, number] | null {
  if (route.length < 2) return null;
  const incidentPoints: [number, number][] = [];
  const collect = (value: unknown) => {
    if (!Array.isArray(value)) return;
    if (value.length >= 2 && typeof value[0] === "number" && typeof value[1] === "number") {
      incidentPoints.push([value[0], value[1]]);
      return;
    }
    value.forEach(collect);
  };
  collect(incident.geometry.coordinates);
  let bestDistance = Infinity;
  let bestPoint: [number, number] | null = null;
  for (const [lon, lat] of incidentPoints) {
    const scaleX = 111.32 * Math.cos((lat * Math.PI) / 180);
    for (let i = 1; i < route.length; i++) {
      const a = route[i - 1], b = route[i];
      const dx = (b[0] - a[0]) * scaleX, dy = (b[1] - a[1]) * 111.32;
      const px = (lon - a[0]) * scaleX, py = (lat - a[1]) * 111.32;
      const t = Math.max(0, Math.min(1, (px * dx + py * dy) / (dx * dx + dy * dy || 1)));
      const x = a[0] + (b[0] - a[0]) * t, y = a[1] + (b[1] - a[1]) * t;
      const distance = Math.hypot((lon - x) * scaleX, (lat - y) * 111.32);
      if (distance < bestDistance) { bestDistance = distance; bestPoint = [x, y]; }
    }
  }
  // TomTom queries a corridor around the road; only display incidents within 1 km of this route.
  return bestDistance <= 1 ? bestPoint : null;
}

