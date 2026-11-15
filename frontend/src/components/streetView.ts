import { cumulativeKm, haversineKm, pointAtKm } from "./simulation";
import type { LngLat } from "./simulation";

export interface StreetViewTarget { position: LngLat; bearing: number; distanceKm: number; }

export function inspectionRoute(coords: number[][]) {
  const points = coords.filter(p => p.length >= 2 && Number.isFinite(p[0]) && Number.isFinite(p[1]) && Math.abs(p[0]) <= 180 && Math.abs(p[1]) <= 90).map(p => [p[0], p[1]] as LngLat);
  return { points, cumulative: cumulativeKm(points) };
}

/** Distance-based selection keeps the control useful on densely sampled roads. */
export function inspectionTarget(points: LngLat[], cumulative: number[], fraction: number): StreetViewTarget {
  const total = cumulative[cumulative.length - 1] ?? 0;
  const distanceKm = total * Math.min(1, Math.max(0, fraction));
  const { position } = pointAtKm(points, cumulative, distanceKm);
  const behind = pointAtKm(points, cumulative, Math.max(0, distanceKm - 0.02)).position;
  const ahead = pointAtKm(points, cumulative, Math.min(total, distanceKm + 0.02)).position;
  const rad = Math.PI / 180;
  const dLon = (ahead[0] - behind[0]) * rad;
  const a = behind[1] * rad, b = ahead[1] * rad;
  const bearing = (Math.atan2(Math.sin(dLon) * Math.cos(b), Math.cos(a) * Math.sin(b) - Math.sin(a) * Math.cos(b) * Math.cos(dLon)) / rad + 360) % 360;
  return { position, bearing, distanceKm };
}

/** Project a sampled truck position onto its route, keeping the slider in sync. */
export function inspectionFraction(points: LngLat[], cumulative: number[], position: LngLat) {
  let best = Infinity, distance = 0;
  const scale = Math.cos(position[1] * Math.PI / 180);
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1], b = points[i];
    const dx = (b[0] - a[0]) * scale, dy = b[1] - a[1];
    const len = dx * dx + dy * dy;
    const f = len ? Math.max(0, Math.min(1, (((position[0] - a[0]) * scale) * dx + (position[1] - a[1]) * dy) / len)) : 0;
    const nearest: LngLat = [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
    const gap = haversineKm(position, nearest);
    if (gap < best) { best = gap; distance = cumulative[i - 1] + (cumulative[i] - cumulative[i - 1]) * f; }
  }
  return distance / Math.max(0.000001, cumulative[cumulative.length - 1] ?? 0);
}

function locationParams(target: StreetViewTarget) {
  const [lon, lat] = target.position;
  if (!Number.isFinite(lon) || !Number.isFinite(lat) || Math.abs(lon) > 180 || Math.abs(lat) > 90) throw new Error("Choose a valid road location.");
  return { location: `${lat.toFixed(6)},${lon.toFixed(6)}`, heading: String(Math.round((target.bearing % 360 + 360) % 360)), pitch: "0", fov: "85" };
}

export function streetViewLink(target: StreetViewTarget) {
  const { location, ...camera } = locationParams(target);
  const params = new URLSearchParams({ api: "1", map_action: "pano", viewpoint: location, ...camera });
  return `https://www.google.com/maps/@?${params}`;
}

export function streetViewEmbed(target: StreetViewTarget, key: string) {
  if (!key.trim()) return null;
  const params = new URLSearchParams({ key: key.trim(), ...locationParams(target) });
  return `https://www.google.com/maps/embed/v1/streetview?${params}`;
}
