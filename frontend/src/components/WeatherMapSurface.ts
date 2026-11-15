import type { WeatherZone } from "../api/types";

/** Weather tools use geographic coordinates, independently of the basemap. */
export interface WeatherMapSurface {
  readonly rendersWeatherEffects?: boolean;
  project(position: [number, number]): { x: number; y: number } | null;
  unproject(point: [number, number]): { lng: number; lat: number } | null;
  subscribe(listener: () => void): () => void;
  focus(position: [number, number]): void;
  drawWeather(zones: WeatherZone[], onSelect: (zone: WeatherZone) => void,
    onMove?: (zone: WeatherZone, position: { lng: number; lat: number }) => Promise<boolean>): () => void;
}
