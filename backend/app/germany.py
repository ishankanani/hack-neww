"""Approximate German border, used to keep weather detours inside Germany.

The outline is simplified (about 10 km accuracy), so checks allow a tolerance:
roads that run along the border stay valid, while detours that cross into a
neighbouring country are rejected. Coordinates are (lon, lat).
"""
import math

BORDER = [
    (8.60, 54.91), (9.45, 54.83), (10.05, 54.75), (11.10, 54.55), (12.35, 54.62), (13.40, 54.80),
    (14.25, 54.10), (14.22, 53.90), (14.42, 53.28), (14.13, 52.85), (14.63, 52.57), (14.55, 52.32),
    (14.72, 51.95), (14.73, 51.55), (15.04, 51.25), (14.82, 50.87), (14.60, 50.92), (14.30, 51.00),
    (14.15, 50.90), (13.75, 50.73), (13.30, 50.58), (12.97, 50.41), (12.47, 50.35), (12.20, 50.32),
    (12.10, 50.25), (12.20, 50.10), (12.50, 49.95), (12.47, 49.70), (12.65, 49.43), (12.95, 49.33),
    (13.40, 49.05), (13.84, 48.77), (13.45, 48.56), (13.03, 48.29), (12.80, 48.14), (12.98, 47.82),
    (13.05, 47.48), (12.75, 47.68), (12.20, 47.61), (11.60, 47.58), (11.27, 47.40), (10.98, 47.40),
    (10.70, 47.55), (10.45, 47.55), (10.18, 47.27), (9.97, 47.54), (9.70, 47.55), (9.55, 47.53),
    (9.20, 47.67), (8.85, 47.70), (8.65, 47.80), (8.40, 47.62), (8.20, 47.62), (7.59, 47.58),
    (7.52, 47.70), (7.58, 48.10), (7.80, 48.58), (8.23, 48.97), (7.95, 49.05), (7.45, 49.17),
    (7.05, 49.12), (6.73, 49.17), (6.55, 49.45), (6.37, 49.47), (6.50, 49.75), (6.13, 50.13),
    (6.40, 50.32), (6.17, 50.55), (6.03, 50.73), (5.97, 50.80), (6.08, 50.92), (5.90, 51.05),
    (6.07, 51.22), (6.22, 51.38), (5.95, 51.75), (6.20, 51.87), (6.83, 51.97), (6.73, 52.08),
    (7.07, 52.24), (6.70, 52.48), (7.05, 52.65), (7.20, 53.25), (6.90, 53.65), (8.00, 53.95),
    (8.40, 54.40), (8.20, 54.90),
]


def _inside(lon, lat):
    inside = False
    j = len(BORDER) - 1
    for i in range(len(BORDER)):
        xi, yi = BORDER[i]
        xj, yj = BORDER[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _segment_km(lon, lat, a, b):
    scale = math.cos(math.radians(lat))
    def xy(p): return ((p[0] - lon) * 111.32 * scale, (p[1] - lat) * 111.32)
    (x, y), (u, v) = xy(a), xy(b)
    dx, dy = u - x, v - y
    t = max(0.0, min(1.0, -(x * dx + y * dy) / (dx * dx + dy * dy or 1)))
    return math.hypot(x + t * dx, y + t * dy)


def outside_km(lon, lat):
    """0 inside Germany, otherwise the approximate distance to the border in km."""
    if _inside(lon, lat):
        return 0.0
    return min(_segment_km(lon, lat, a, b) for a, b in zip(BORDER, BORDER[1:] + BORDER[:1]))


def leaves_germany(line, tolerance_km=10.0):
    """True if a road line ([lon, lat] points) goes more than tolerance_km outside Germany."""
    if not line:
        return False
    step = max(1, len(line) // 300)
    return any(outside_km(p[0], p[1]) > tolerance_km for p in line[::step] + [line[-1]])
