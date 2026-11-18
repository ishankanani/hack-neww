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

type LngLat = [number, number];
const KM_PER_DEGREE = 111.32;
const INCIDENT_RADIUS_KM = 1;
const gridIndex = (degrees: number) => Math.floor(degrees / 0.02);

/** Index a road once, then check only nearby segments for each incident coordinate. */
export function createRouteIncidentMatcher(route: number[][]) {
  const grid = new Map<string, number[]>();
  const longSegments: number[] = [];
  for (let i = 1; i < route.length; i++) {
    const a = route[i - 1], b = route[i];
    const west = gridIndex(Math.min(a[0], b[0])), east = gridIndex(Math.max(a[0], b[0]));
    const south = gridIndex(Math.min(a[1], b[1])), north = gridIndex(Math.max(a[1], b[1]));
    // An approximate road can contain a very long straight leg.
    if ((east - west + 1) * (north - south + 1) > 16) {
      longSegments.push(i);
      continue;
    }
    for (let x = west; x <= east; x++) {
      for (let y = south; y <= north; y++) {
        const key = `${x}:${y}`;
        const cell = grid.get(key);
        if (cell) cell.push(i);
        else grid.set(key, [i]);
      }
    }
  }

  return (incident: Incident): LngLat | null => {
    let bestDistance = Infinity;
    let bestPoint: LngLat | null = null;
    function visit(value: unknown) {
      if (!Array.isArray(value)) return;
      const [lon, lat] = value;
      if (typeof lon !== "number" || typeof lat !== "number") {
        value.forEach(visit);
        return;
      }
      if (!Number.isFinite(lon) || !Number.isFinite(lat) || Math.abs(lat) > 85) return;
      const scaleX = KM_PER_DEGREE * Math.cos((lat * Math.PI) / 180);
      const lonRadius = INCIDENT_RADIUS_KM / scaleX, latRadius = INCIDENT_RADIUS_KM / KM_PER_DEGREE;
      const candidates = new Set(longSegments);
      for (let x = gridIndex(lon - lonRadius); x <= gridIndex(lon + lonRadius); x++) {
        for (let y = gridIndex(lat - latRadius); y <= gridIndex(lat + latRadius); y++) {
          grid.get(`${x}:${y}`)?.forEach(index => candidates.add(index));
        }
      }
      for (const index of candidates) {
        const a = route[index - 1], b = route[index];
        const dx = (b[0] - a[0]) * scaleX, dy = (b[1] - a[1]) * KM_PER_DEGREE;
        const px = (lon - a[0]) * scaleX, py = (lat - a[1]) * KM_PER_DEGREE;
        const t = Math.max(0, Math.min(1, (px * dx + py * dy) / (dx * dx + dy * dy || 1)));
        const distance = (px - t * dx) ** 2 + (py - t * dy) ** 2;
        if (distance <= INCIDENT_RADIUS_KM ** 2 && distance < bestDistance) {
          bestDistance = distance;
          bestPoint = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
        }
      }
    }
    visit(incident.geometry.coordinates);
    return bestPoint;
  };
}

