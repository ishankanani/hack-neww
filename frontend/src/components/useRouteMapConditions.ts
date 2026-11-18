import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { MapConditions } from "../api/types";

interface CachedConditions {
  data: MapConditions;
  tick: number;
  loadedAt: number;
}

export function useRouteMapConditions(road: number[][], offset: number, tick: number, enabled: boolean) {
  const cache = useRef(new WeakMap<number[][], Map<number, CachedConditions>>());
  const [result, setResult] = useState<{road: number[][]; offset: number; tick: number; error: string} | null>(null);
  const eligible = enabled && road.length >= 2;
  const cached = eligible ? cache.current.get(road)?.get(offset) : undefined;
  const error = eligible && result?.road === road && result.offset === offset && result.tick === tick ? result.error : "";

  useEffect(() => {
    if (!eligible) return;
    const previous = cache.current.get(road)?.get(offset);
    if (previous?.tick === tick && Date.now() - previous.loadedAt < 120_000) return;
    const controller = new AbortController();
    // Coalesce rapid clicks and give the route and card time to paint first.
    const timer = window.setTimeout(() => {
      setResult(null);
      const at = new Date(Date.now() + Math.max(0, offset) * 3600000).toISOString();
      api.mapConditions(road, at, controller.signal).then(data => {
        if (controller.signal.aborted) return;
        const entries = cache.current.get(road) ?? new Map<number, CachedConditions>();
        entries.set(offset, {data, tick, loadedAt: Date.now()});
        cache.current.set(road, entries);
        setResult({road, offset, tick, error: ""});
      }).catch(error => {
        if (!controller.signal.aborted) setResult({road, offset, tick, error: String(error)});
      });
    }, 120);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [road, offset, tick, eligible]);

  const fresh = cached?.tick === tick && Date.now() - cached.loadedAt < 120_000;
  return {data: cached?.data ?? null, loading: eligible && !fresh && !error, error};
}
