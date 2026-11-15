import { useEffect, useMemo, useRef, useState } from "react";
import type { RefObject } from "react";
import { ExternalLink, Navigation, ScanEye, X } from "lucide-react";
import maplibregl from "maplibre-gl";
import type { SimView } from "./JourneySimulator";
import { inspectionFraction, inspectionRoute, inspectionTarget, streetViewEmbed, streetViewLink } from "./streetView";
import type { StreetViewTarget } from "./streetView";
import "../streetview.css";

const EMBED_KEY = (import.meta.env.VITE_GOOGLE_MAPS_EMBED_API_KEY ?? "").trim();

export function StreetViewInspector({ coords, mapRef, ready, styleVersion, simulation, routeLabel, onClose }: {
  coords: number[][]; mapRef: RefObject<maplibregl.Map | null>; ready: boolean; styleVersion: number;
  simulation?: SimView; routeLabel: string; onClose: () => void;
}) {
  const route = useMemo(() => inspectionRoute(coords), [coords]);
  const [fraction, setFraction] = useState(0.5);
  const [loadedTarget, setLoadedTarget] = useState<StreetViewTarget | null>(null);
  const [loading, setLoading] = useState(false);
  const target = useMemo(() => inspectionTarget(route.points, route.cumulative, fraction), [route, fraction]);
  const initialPosition = useRef(target.position);
  const marker = useRef<maplibregl.Marker | null>(null);
  const totalKm = route.cumulative[route.cumulative.length - 1] ?? 0;
  const link = streetViewLink(target);
  const embed = loadedTarget ? streetViewEmbed(loadedTarget, EMBED_KEY) : null;
  const changed = !!loadedTarget && (loadedTarget.position[0] !== target.position[0] || loadedTarget.position[1] !== target.position[1]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const element = document.createElement("div");
    element.className = "streetview-pin";
    element.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M2 8V4a2 2 0 0 1 2-2h4m8 0h4a2 2 0 0 1 2 2v4M2 16v4a2 2 0 0 0 2 2h4m8 0h4a2 2 0 0 0 2-2v-4"/></svg>';
    const pin = new maplibregl.Marker({ element }).setLngLat(initialPosition.current).addTo(map);
    element.setAttribute("role", "img"); element.setAttribute("aria-label", "Street View inspection point"); element.title = "Street View inspection point";
    marker.current = pin;
    return () => { pin.remove(); if (marker.current === pin) marker.current = null; };
  }, [mapRef, ready, styleVersion]);

  useEffect(() => { marker.current?.setLngLat(target.position); }, [target, ready, styleVersion]);

  function useTruck() {
    const truck = simulation?.sampleTruck();
    if (truck) setFraction(inspectionFraction(route.points, route.cumulative, truck.position));
  }

  function loadPanorama() { setLoading(true); setLoadedTarget({ ...target, position: [...target.position] }); }

  return <section className="streetview-inspector" aria-label="Google Street View road inspection">
    <div className="streetview-heading"><div><h3><ScanEye size={18} /> Google Street View</h3><p>{routeLabel}</p></div><button className="icon-button" aria-label="Close Street View" onClick={onClose}><X size={17} /></button></div>
    <div className="streetview-selector">
      <div className="streetview-presets" role="group" aria-label="Street View route position">{[[0, "Start"], [0.5, "Midpoint"], [1, "End"]].map(([f, label]) => <button key={label} aria-pressed={Math.abs(fraction - Number(f)) < 0.001} onClick={() => setFraction(Number(f))}>{label}</button>)}{simulation?.engaged && <button className="streetview-truck" onClick={useTruck}><Navigation size={13} />Truck position</button>}</div>
      <label className="streetview-distance"><span>Road inspection point <b>{Math.round(target.distanceKm)} km along route</b></span><input type="range" min={0} max={100} step={1} value={fraction * 100} onChange={e => setFraction(Number(e.target.value) / 100)} aria-label="Street View position along route" aria-valuetext={`${Math.round(target.distanceKm)} of ${Math.round(totalKm)} kilometres`} /><span className="streetview-range-labels"><span>Start</span><span>{Math.round(totalKm)} km · End</span></span></label>
    </div>
    {embed ? <><div className="streetview-frame">{loading && <span className="streetview-loading" role="status">Loading Google Street View…</span>}<iframe title="Google Street View panorama" src={embed} width="100%" height="340" allowFullScreen referrerPolicy="strict-origin-when-cross-origin" onLoad={() => setLoading(false)} /></div><div className="streetview-footer"><span>{changed ? "Point changed. Update the panorama to inspect it." : "Recorded imagery · Coverage varies"}</span><button className="btn btn--sm btn--ghost" disabled={!changed} onClick={loadPanorama}>Update panorama</button><a href={link} target="_blank" rel="noopener noreferrer">Open Google Maps <ExternalLink size={12} /></a></div></> : <div className="streetview-launch"><span className="streetview-launch-icon"><ScanEye size={27} /></span><div><h4>Inspect this road at street level</h4><p>Choose a point on the route, then look around in Google Street View.</p></div><div className="streetview-launch-actions">{EMBED_KEY && <button className="btn btn--sm" onClick={loadPanorama}>Load panorama</button>}<a className={`btn btn--sm ${EMBED_KEY ? "btn--ghost" : ""}`} href={link} target="_blank" rel="noopener noreferrer" aria-label="Open Street View in Google Maps (opens a new tab)">Open Street View <ExternalLink size={14} /></a></div></div>}
    <p className="streetview-note">Recorded imagery, where available. Google may show the nearest panorama. Road conditions and simulated weather are shown on the route map.</p>
  </section>;
}
