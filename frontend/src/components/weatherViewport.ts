export interface WeatherViewportClip {
  left: number; top: number; width: number; height: number;
  centerX: number; centerY: number; radius: number;
}

/** Keep animated DOM layers within the viewport, even at street-level zoom. */
export function weatherViewportClip(x: number, y: number, radius: number, width: number, height: number): WeatherViewportClip | null {
  if (![x, y, radius, width, height].every(Number.isFinite) || radius <= 0 || width <= 0 || height <= 0) return null;
  const nearestX = Math.max(0, Math.min(width, x));
  const nearestY = Math.max(0, Math.min(height, y));
  if (Math.hypot(nearestX - x, nearestY - y) >= radius) return null;
  const left = Math.max(0, x - radius), top = Math.max(0, y - radius);
  const right = Math.min(width, x + radius), bottom = Math.min(height, y + radius);
  if (right <= left || bottom <= top) return null;
  return { left, top, width: right - left, height: bottom - top, centerX: x - left, centerY: y - top, radius };
}
