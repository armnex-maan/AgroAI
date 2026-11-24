"""AI Farm Layout Generator: alternative layouts of one plot (parts, paths, greenhouse, water point).

Pure geometry, no database. Every choice carries its reason; numbers that are not agronomic data (path width,
number of parts) are labelled as AgroAI choices the farmer can change. Crops are NOT chosen here: each layout is
handed to the rotation engine (rotation_planner), the only source of crop choices and verdicts.
Local frame: metres, x east, y south, origin at the north-west corner of the plot bounding box.
"""
from __future__ import annotations

from app.ml.agronomy.geo import area_in

MIN_BED = 1.0          # m: narrower strips are not offered (they could not be worked)


def strips(outline, region: tuple[float, float, float, float], parts: int, path: float, along_x: bool) -> list[dict]:
    """Cut the rectangle region (x0, y0, x1, y1) into `parts` strips of equal REAL area (inside the outline),
    separated by paths. along_x: cuts follow x (strips run north-south)."""
    x0, y0, x1, y1 = region
    span0, span1 = (x0, x1) if along_x else (y0, y1)
    o0, o1 = (y0, y1) if along_x else (x0, x1)

    def a(lo: float, hi: float) -> float:
        return area_in(outline, lo, o0, hi - lo, o1 - o0) if along_x else area_in(outline, o0, lo, o1 - o0, hi - lo)

    target = max(0.0, a(span0, span1) - path * (o1 - o0) * (parts - 1)) / parts
    cuts: list[tuple[float, float]] = []
    for _ in range(6):
        cuts, s = [], span0
        for i in range(parts):
            if i == parts - 1:
                cuts.append((s, span1))
                break
            lo, hi = s, span1
            for _ in range(50):
                mid = (lo + hi) / 2
                lo, hi = (mid, hi) if a(s, mid) < target else (lo, mid)
            cuts.append((s, min(hi, span1)))
            s = min(span1, hi + path)
        target = sum(a(p, q) for p, q in cuts) / parts
    rect = (lambda p, q: {"x": p, "y": o0, "w": q - p, "h": o1 - o0}) if along_x else (lambda p, q: {"x": o0, "y": p, "w": o1 - o0, "h": q - p})
    out = [{"kind": "bed", **rect(p, q)} for p, q in cuts]
    out += [{"kind": "path", **rect(q1, p2)} for (_, q1), (p2, _) in zip(cuts, cuts[1:]) if p2 - q1 > 0.05]
    return out


def default_parts(wanted: dict) -> int:
    return min(8, max(3, len(wanted) + 2))


def default_path(area: float) -> float:
    return 0.6 if area < 2000 else 3.0


def _named(secs: list[dict], garden: bool, tag: str) -> list[dict]:
    n = {"bed": 0, "path": 0, "greenhouse": 0, "water": 0}
    out = []
    for s in sorted(secs, key=lambda s: ({"greenhouse": 0, "bed": 1, "path": 2, "water": 3}[s["kind"]], s["y"], s["x"])):
        n[s["kind"]] += 1
        name = {"bed": f"{'Aiuola' if garden else 'Parte'} {n['bed']}", "path": "Sentiero" if garden else "Capezzagna",
                "greenhouse": f"Serra {n['greenhouse']}", "water": "Punto d'acqua"}[s["kind"]]
        out.append({**{k: round(v, 2) if isinstance(v, float) else v for k, v in s.items()}, "id": f"tmp-{tag}-{len(out) + 1}", "name": name})
    return out


def variants(outline, width: float, length: float, area: float, wanted: dict, *, parts: int | None = None,
             path_m: float | None = None, greenhouse_m2: float | None = None, water_point: bool = False) -> list[dict]:
    """Up to three alternatives. Returns [{key, title, sections, why: [..], params}]."""
    garden = area < 2000
    n = parts or default_parts(wanted)
    path = default_path(area) if path_m is None else path_m
    why_parts = (f"{n} parti indicate da te." if parts else
                 f"{n} parti: almeno 3 per poter alternare le famiglie negli anni; con {len(wanted)} colture richieste "
                 f"AgroAI usa le colture richieste + 2 (massimo 8). È una scelta modificabile, non una norma.")
    why_path = (f"Passaggi da {path:g} m indicati da te." if path_m is not None else
                f"Passaggi da {path:g} m: valore indicativo per {'un orto (a piedi)' if garden else 'un campo (passaggio dei mezzi)'}, "
                "da adattare alla larghezza dei tuoi attrezzi.")
    long_x = width >= length
    out: list[dict] = []

    def add(key, title, secs, why):
        beds = [s for s in secs if s["kind"] in ("bed", "greenhouse")]
        if not beds or min(min(s["w"], s["h"]) for s in beds) < MIN_BED:
            return
        out.append({"key": key, "title": title, "sections": _named(secs, garden, key), "why": [why_parts, why_path, *why],
                    "params": {"parts": n, "path_m": path}})

    full = (0.0, 0.0, width, length)
    add("lungo", "Strisce lungo il lato lungo", strips(outline, full, n, path, along_x=not long_x),
        ["Parti a strisce di uguale superficie reale lungo il lato più lungo: meno svolte in testata e passaggi più corti."])
    add("corto", "Strisce lungo il lato corto", strips(outline, full, n, path, along_x=long_x),
        ["Alternativa: strisce perpendicolari, più corte. Utile se l'accesso è sul lato lungo o per lavorare a mano."])

    if greenhouse_m2 and greenhouse_m2 > 0:
        depth = min(length * 0.5, greenhouse_m2 / max(1.0, width))
        if depth >= 3:
            gh = {"kind": "greenhouse", "x": 0.0, "y": 0.0, "w": width, "h": depth}
            rest = (0.0, depth + path, width, length)
            secs = [gh, {"kind": "path", "x": 0.0, "y": depth, "w": width, "h": path}] + strips(outline, rest, max(2, n - 1), path, along_x=not long_x)
            real = area_in(outline, 0, 0, width, depth)
            add("serra", "Serra a nord e strisce", secs, [
                f"Serra di circa {real:.0f} m² sul lato nord: la sua ombra cade verso nord, quindi non toglie sole alle "
                "altre parti (emisfero nord).",
                "La serra conta come una parte della rotazione: anche lì le colture vengono controllate con le regole."])
    if water_point and out:
        for v in out:
            paths = [s for s in v["sections"] if s["kind"] == "path"]
            if paths:
                p = paths[len(paths) // 2]
                size = min(1.5, p["w"], p["h"])
                if size >= 0.5:
                    v["sections"].append({"id": f"tmp-{v['key']}-w", "name": "Punto d'acqua", "kind": "water",
                                          "x": round(p["x"] + (p["w"] - size) / 2, 2), "y": round(p["y"], 2), "w": size, "h": size})
                    v["why"].append("Punto d'acqua all'inizio del passaggio centrale: è raggiungibile da tutte le parti.")
                    continue
            v["why"].append("Punto d'acqua non inserito: i passaggi sono troppo stretti. Aggiungilo a mano dove ce l'hai.")
    return out
