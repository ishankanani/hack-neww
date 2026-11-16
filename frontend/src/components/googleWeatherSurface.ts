import type { WeatherMapSurface } from "./WeatherMapSurface";
import type { WeatherZone } from "../api/types";
import { weatherViewportClip } from "./weatherViewport";

export const googlePosition = (p: number[]): google.maps.LatLngLiteral => ({ lat: p[1], lng: p[0] });
export const googlePath = (coords: number[][]) => coords.filter(p => Number.isFinite(p[0]) && Number.isFinite(p[1])).map(googlePosition);

export function googleMarker(maps: typeof google.maps, map: google.maps.Map, point: google.maps.LatLngLiteral,
  element: HTMLElement, title: string, draggable = false) {
  const marker = new maps.marker.AdvancedMarkerElement({ map, position: point, title, gmpDraggable: draggable, anchorTop: "-50%", anchorLeft: "-50%" });
  marker.append(element);
  return marker;
}

export function googleWeatherSurface(maps: typeof google.maps, map: google.maps.Map, onReady: () => void) {
  const listeners = new Set<() => void>();
  const overlay = new maps.OverlayView();
  const root = document.createElement("div"); root.className = "google-weather-effects";
  const effects = new Map<string, { zone: WeatherZone; element: HTMLDivElement }>();
  let disposed = false, frame = 0;
  function attachRoot() {
    const pane = overlay.getPanes()?.overlayLayer;
    if (pane && root.parentElement !== pane) pane.append(root);
  }
  function positionEffects() {
    if (disposed) return;
    attachRoot();
    const projection = overlay.getProjection(); if (!projection) return;
    const width = map.getDiv().clientWidth, height = map.getDiv().clientHeight;
    if (width <= 0 || height <= 0) return;
    // Container pixels locate the viewport; div pixels account for Google's pane translation.
    const corner = projection.fromContainerPixelToLatLng(new maps.Point(0, 0), true);
    const origin = corner && projection.fromLatLngToDivPixel(corner);
    if (!origin || !Number.isFinite(origin.x) || !Number.isFinite(origin.y)) return;
    root.style.left = `${origin.x}px`; root.style.top = `${origin.y}px`;
    root.style.width = `${width}px`; root.style.height = `${height}px`;
    effects.forEach(({ zone, element }) => {
      const center = projection.fromLatLngToContainerPixel(new maps.LatLng(zone.lat, zone.lon));
      const lonKm = 111.32 * Math.max(.1, Math.cos(zone.lat * Math.PI / 180));
      const edge = projection.fromLatLngToContainerPixel(new maps.LatLng(zone.lat, zone.lon + zone.radius_km / lonKm));
      if (!center || !edge) return;
      const r = Math.abs(center.x - edge.x);
      // Ignore a transient invalid projection rather than losing the last good frame.
      if (!Number.isFinite(center.x) || !Number.isFinite(center.y) || !Number.isFinite(r) || r <= 0) return;
      const clip = weatherViewportClip(center.x, center.y, r, width, height);
      element.hidden = !clip;
      if (!clip) return;
      element.style.left = `${clip.left}px`; element.style.top = `${clip.top}px`;
      element.style.width = `${clip.width}px`; element.style.height = `${clip.height}px`;
      element.style.clipPath = `circle(${clip.radius}px at ${clip.centerX}px ${clip.centerY}px)`;
      element.style.setProperty("--zone-center-x", `${clip.centerX}px`);
      element.style.setProperty("--zone-center-y", `${clip.centerY}px`);
      element.style.setProperty("--zone-radius", `${clip.radius}px`);
      element.style.setProperty("--tornado-size", `${Math.max(32, Math.min(160, clip.radius))}px`);
      element.style.setProperty("--zone-diameter", `${clip.height + 60}px`);
    });
  }
  function scheduleDraw() {
    if (disposed || frame) return;
    frame = requestAnimationFrame(() => { frame = 0; positionEffects(); listeners.forEach(listener => listener()); });
  }
  let notified = false;
  overlay.onAdd = () => { attachRoot(); scheduleDraw(); };
  overlay.onRemove = () => { root.remove(); };
  overlay.draw = () => {
    if (!notified) { notified = true; onReady(); }
    scheduleDraw();
  };
  overlay.setMap(map);
  const changes = ["bounds_changed", "zoom_changed", "idle", "projection_changed", "maptypeid_changed", "resize"]
    .map(event => map.addListener(event, scheduleDraw));

  const surface: WeatherMapSurface = {
    rendersWeatherEffects: true,
    project(point) {
      const projection = overlay.getProjection();
      return projection?.fromLatLngToContainerPixel(new maps.LatLng(point[1], point[0])) ?? null;
    },
    unproject(point) {
      const value = overlay.getProjection()?.fromContainerPixelToLatLng(new maps.Point(point[0], point[1]));
      return value ? { lat: value.lat(), lng: value.lng() } : null;
    },
    subscribe(listener) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    focus(point) { map.panTo(googlePosition(point)); if ((map.getZoom() ?? 5) < 7) map.setZoom(7); },
    drawWeather(zones, onSelect, onMove) {
      const shapes = zones.map(zone => {
        const element = document.createElement("div"); element.className = `sim-weather-effect sim-weather-effect--${zone.kind}`; element.setAttribute("aria-hidden", "true"); element.dataset.weatherZone = zone.id;
        for (let i = 0; i < (zone.kind === "tornado" ? 9 : 16); i++) {
          const particle = document.createElement("span"); particle.className = "sim-weather-particle"; particle.style.left = `${(i * 37) % 100}%`; if (zone.kind === "tornado") particle.style.top = `${12 + (i * 29) % 72}%`; particle.style.animationDelay = `-${(i % 7) * .43}s`; particle.textContent = zone.kind === "snow" ? "❄" : zone.kind === "rain" ? "╱" : "·"; element.append(particle);
        }
        if (zone.kind === "tornado") { const core = document.createElement("i"); core.className = "sim-tornado-core"; element.append(core); }
        root.append(element); effects.set(zone.id, { zone, element });
        const color = zone.kind === "snow" ? "#3888ca" : zone.kind === "rain" ? "#294c9d" : "#c23563";
        const circle = new maps.Circle({ map, center: { lat: zone.lat, lng: zone.lon }, radius: zone.radius_km * 1000,
          fillColor: color, fillOpacity: 0.22, strokeColor: color, strokeOpacity: 0.8, strokeWeight: 2, clickable: false, zIndex: 1 });
        const button = document.createElement("button");
        button.className = `sim-zone-marker sim-zone-marker--${zone.kind}`;
        button.textContent = zone.kind === "snow" ? "❄" : zone.kind === "rain" ? "☔" : "🌪";
        const title = `Simulated ${zone.kind} · ${zone.radius_km} km radius${onMove ? " · drag to move" : ""}`;
        button.title = title; button.setAttribute("aria-label", title);
        const marker = googleMarker(maps, map, { lat: zone.lat, lng: zone.lon }, button, title, !!onMove);
        marker.collisionBehavior = maps.CollisionBehavior.REQUIRED;
        marker.zIndex = 50;
        button.addEventListener("click", () => onSelect(zone));
        const moving = marker.addListener("drag", () => {
          const p = marker.position; if (!p) return;
          const center = p instanceof maps.LatLng ? { lat: p.lat(), lng: p.lng() } : { lat: p.lat, lng: p.lng };
          circle.setCenter(center);
          effects.set(zone.id, { zone: { ...zone, lon: center.lng, lat: center.lat }, element }); positionEffects();
        });
        const dragged = marker.addListener("dragend", () => {
          const point = marker.position;
          if (!point || !onMove) return;
          const position = point instanceof maps.LatLng ? { lat: point.lat(), lng: point.lng() } : { lat: point.lat, lng: point.lng };
          const rollback = () => {
            if (marker.map !== map) return;
            const original = { lat: zone.lat, lng: zone.lon }; circle.setCenter(original); marker.position = original;
            effects.set(zone.id, { zone, element }); positionEffects();
          };
          void onMove(zone, position).then(ok => { if (!ok) rollback(); }, rollback);
        });
        return { zone, element, circle, marker, dragged, moving };
      });
      positionEffects();
      return () => shapes.forEach(({ zone, element, circle, marker, dragged, moving }) => { effects.delete(zone.id); element.remove(); moving.remove(); dragged.remove(); circle.setMap(null); marker.map = null; });
    },
  };
  return { surface, dispose() { disposed = true; cancelAnimationFrame(frame); changes.forEach(change => change.remove()); effects.clear(); listeners.clear(); overlay.setMap(null); } };
}
