import type { WeatherMapSurface } from "./WeatherMapSurface";
import type { WeatherZone } from "../api/types";

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
  function positionEffects() {
    const projection = overlay.getProjection(); if (!projection) return;
    effects.forEach(({ zone, element }) => {
      const center = projection.fromLatLngToDivPixel(new maps.LatLng(zone.lat, zone.lon));
      const lonKm = 111.32 * Math.max(.1, Math.cos(zone.lat * Math.PI / 180));
      const edge = projection.fromLatLngToDivPixel(new maps.LatLng(zone.lat, zone.lon + zone.radius_km / lonKm));
      if (!center || !edge) return;
      const r = Math.max(1, Math.abs(center.x - edge.x));
      element.style.left = `${center.x - r}px`; element.style.top = `${center.y - r}px`;
      element.style.width = element.style.height = `${r * 2}px`; element.style.setProperty("--zone-diameter", `${r * 2}px`);
    });
  }
  let notified = false;
  overlay.onAdd = () => { overlay.getPanes()?.overlayLayer.append(root); };
  overlay.onRemove = () => { root.remove(); };
  overlay.draw = () => {
    if (!notified) { notified = true; onReady(); }
    positionEffects();
    listeners.forEach(listener => listener());
  };
  overlay.setMap(map);
  const change = map.addListener("bounds_changed", () => listeners.forEach(listener => listener()));

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
        const element = document.createElement("div"); element.className = `sim-weather-effect sim-weather-effect--${zone.kind}`; element.setAttribute("aria-hidden", "true");
        for (let i = 0; i < (zone.kind === "tornado" ? 9 : 16); i++) {
          const particle = document.createElement("span"); particle.className = "sim-weather-particle"; particle.style.left = `${(i * 37) % 100}%`; particle.style.animationDelay = `-${(i % 7) * .43}s`; particle.textContent = zone.kind === "snow" ? "❄" : zone.kind === "rain" ? "╱" : "·"; element.append(particle);
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
  return { surface, dispose() { change.remove(); effects.clear(); listeners.clear(); overlay.setMap(null); } };
}
