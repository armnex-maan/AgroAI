"""Plot boundaries drawn on the satellite map: real area on the Earth and conversion to the local
metre grid used by the visual field planner (x to the east, y to the south, origin at the north-west corner)."""
from __future__ import annotations

import math

R = 6378137.0  # WGS84 equatorial radius, as used by web maps and Turf.js


def clean_ring(ring: list[list[float]]) -> list[list[float]]:
    """[[lon, lat], ...] without the closing point and without repeated consecutive points."""
    pts: list[list[float]] = []
    for p in ring:
        lon, lat = float(p[0]), float(p[1])
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError("Coordinate fuori scala.")
        if not pts or (abs(pts[-1][0] - lon) > 1e-9 or abs(pts[-1][1] - lat) > 1e-9):
            pts.append([lon, lat])
    if len(pts) > 1 and abs(pts[0][0] - pts[-1][0]) < 1e-9 and abs(pts[0][1] - pts[-1][1]) < 1e-9:
        pts.pop()
    if len(pts) < 3:
        raise ValueError("Servono almeno 3 punti.")
    return pts


def area_m2(ring: list[list[float]]) -> float:
    """Area of a lon/lat ring on the sphere (Chamberlain & Duquette 2007, same method as Turf.js area)."""
    pts = clean_ring(ring)
    total = 0.0
    n = len(pts)
    for i in range(n):
        lo1, la1 = pts[i]
        lo2, la2 = pts[(i + 1) % n]
        total += math.radians(lo2 - lo1) * (2 + math.sin(math.radians(la1)) + math.sin(math.radians(la2)))
    return abs(total * R * R / 2.0)


def to_local(ring: list[list[float]]) -> dict:
    """Project the ring to metres around its own latitude (accurate to well under 1% for farm-sized plots)."""
    pts = clean_ring(ring)
    lon0 = min(p[0] for p in pts)
    lat0 = max(p[1] for p in pts)
    lat_m = sum(p[1] for p in pts) / len(pts)
    ky = math.pi * R / 180.0
    kx = ky * math.cos(math.radians(lat_m))
    outline = [[round((lon - lon0) * kx, 2), round((lat0 - lat) * ky, 2)] for lon, lat in pts]
    return {"outline": outline, "width_m": round(max(p[0] for p in outline), 2) or 0.1,
            "length_m": round(max(p[1] for p in outline), 2) or 0.1,
            "origin": [lon0, lat0], "k": [kx, ky],
            "centroid": [sum(p[0] for p in pts) / len(pts), lat_m]}


def from_local(outline: list[list[float]], origin: list[float], k: list[float]) -> list[list[float]]:
    """Inverse of to_local: metre points of the field editor back to [lon, lat]."""
    lon0, lat0 = origin
    kx, ky = k
    return [[round(lon0 + x / kx, 8), round(lat0 - y / ky, 8)] for x, y in outline]


def perimeter_m(ring: list[list[float]]) -> float:
    pts = clean_ring(ring)
    tot = 0.0
    for i in range(len(pts)):
        lo1, la1 = map(math.radians, pts[i])
        lo2, la2 = map(math.radians, pts[(i + 1) % len(pts)])
        a = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
        tot += 2 * R * math.asin(math.sqrt(a))
    return tot


# ---------------- local metre geometry (field editor) ----------------
def poly_area(pts: list[list[float]]) -> float:
    a = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2


def clip_to_rect(poly: list[list[float]], x0: float, y0: float, x1: float, y1: float) -> list[list[float]]:
    """Sutherland-Hodgman with an axis-aligned rectangle as clip window: correct for any simple polygon."""
    out = [list(p) for p in poly]
    for axis, lim, keep_ge in ((0, x0, True), (0, x1, False), (1, y0, True), (1, y1, False)):
        inp, out = out, []
        if not inp:
            break
        ins = (lambda p: p[axis] >= lim) if keep_ge else (lambda p: p[axis] <= lim)
        for j, cur in enumerate(inp):
            prev = inp[j - 1]
            if ins(cur) != ins(prev):
                t = (lim - prev[axis]) / (cur[axis] - prev[axis])
                out.append([prev[0] + (cur[0] - prev[0]) * t, prev[1] + (cur[1] - prev[1]) * t])
            if ins(cur):
                out.append(cur)
    return out


def area_in(outline: list[list[float]] | None, x: float, y: float, w: float, h: float) -> float:
    """Area of the rectangle (x, y, w, h) that really falls inside the plot outline."""
    if not outline or len(outline) < 3:
        return w * h
    return poly_area(clip_to_rect(outline, x, y, x + w, y + h))


def split_strips(outline: list[list[float]] | None, width: float, length: float, parts: int, path: float) -> list[dict]:
    """Cut the plot into `parts` strips along its longer side, separated by paths, each with the same real
    area inside the outline (an irregular plot gets strips of different widths)."""
    along_x = length >= width            # strips run north-south, cut along x
    span, other = (width, length) if along_x else (length, width)

    def strip_area(a: float, b: float) -> float:
        return area_in(outline, a, 0, b - a, other) if along_x else area_in(outline, 0, a, other, b - a)

    total = strip_area(0, span)
    usable = max(0.0, total - path * other * (parts - 1))
    target = usable / parts
    cuts: list[tuple[float, float]] = []
    for _ in range(6):  # paths take a share that depends on the cuts: iterate to equal areas
        cuts, a = [], 0.0
        for i in range(parts):
            if i == parts - 1:
                cuts.append((a, span))
                break
            lo, hi = a, span
            for _ in range(50):
                mid = (lo + hi) / 2
                if strip_area(a, mid) < target:
                    lo = mid
                else:
                    hi = mid
            b = min(hi, span)
            cuts.append((a, b))
            a = min(span, b + path)
        areas = [strip_area(a, b) for a, b in cuts]
        target = sum(areas) / parts
    out = []
    for a, b in cuts:
        w = max(0.1, b - a)
        out.append({"x": a, "y": 0, "w": w, "h": other} if along_x else {"x": 0, "y": a, "w": other, "h": w})
    paths = []
    for (a1, b1), (a2, _) in zip(cuts, cuts[1:]):
        if a2 - b1 > 0.05:
            paths.append({"x": b1, "y": 0, "w": a2 - b1, "h": other} if along_x else {"x": 0, "y": b1, "w": other, "h": a2 - b1})
    return [{"kind": "bed", **r} for r in out] + [{"kind": "path", **r} for r in paths]
