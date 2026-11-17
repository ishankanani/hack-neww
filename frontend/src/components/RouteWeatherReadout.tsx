import { useMemo } from "react";
import { CloudRain, CloudSnow, CloudSun, Wind } from "lucide-react";
import type { LiveWeather } from "../api/types";
import { dt } from "../lib";
import "../route-map-organization.css";

export function RouteWeatherReadout({ forecasts }: { forecasts: LiveWeather[] }) {
  const points = useMemo(() => {
    const unique = new Map<string, LiveWeather>();
    for (const point of forecasts) {
      const key = `${point.lat}:${point.lon}:${point.valid_at}:${point.status}`;
      if (!unique.has(key)) unique.set(key, point);
    }
    return [...unique.values()].sort((a,b) => Date.parse(a.valid_at) - Date.parse(b.valid_at));
  }, [forecasts]);
  return <details className="route-weather-panel" open>
    <summary><CloudSun size={17}/><strong>Weather along the route</strong><span>{points.filter(p=>p.status==="FORECAST").length} forecast points</span></summary>
    {points.length ? <ul className="route-weather-grid">{points.map((point,index) => {
      const Icon = /snow/i.test(point.condition??"") ? CloudSnow : /rain|storm/i.test(point.condition??"") ? CloudRain : CloudSun;
      const location = point.name && !/^Route sample \d+$/i.test(point.name) ? point.name : (index===0 ? "Route start" : index===points.length-1 ? "Route end" : `Checkpoint ${index+1}`);
      const unavailable = !point.condition && point.temperature_c == null;
      return <li className={`route-weather-card ${unavailable?"is-unavailable":""}`} key={`${point.id}-${point.valid_at}-${index}`}>
        <div className="route-weather-point"><b>{location}</b><time dateTime={point.valid_at}>{dt(point.valid_at)}</time></div>
        <div className="route-weather-condition"><span className="route-weather-icon"><Icon size={22}/></span><div><b>{point.condition || "Forecast unavailable"}</b><span>{point.temperature_c == null ? "—" : `${point.temperature_c}°C`}</span></div></div>
        <div className="route-weather-wind"><Wind size={13}/><span>{point.wind_kmh == null ? "Wind unavailable" : `${point.wind_kmh} km/h wind`}</span>{point.rain_mm != null && <span>{point.rain_mm} mm rain</span>}</div>
      </li>;
    })}</ul> : <p className="route-weather-empty">No forecast is available for this journey yet.</p>}
  </details>;
}
