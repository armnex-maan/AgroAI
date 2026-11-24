"""DEV ONLY - demo farm for the Visual Planner 3D (local SQLite dev database).

Creates «Azienda Agricola Rossi» through the public API, like a farmer would: 5 traced plots (2.5 ha),
2026 crop history, a saved 2027 plan checked by the rotation engine, and farm elements (farmhouse,
glass greenhouse, tank, orchard, roads, hedges, sprinklers).

It REPLACES the plots and farm elements of the dev farm. Never run it against a real database.
Usage (API running on :8000):  .venv\\Scripts\\python.exe scripts\\seed_demo_planner.py
"""
import math
import sys

import httpx

API = "http://localhost:8000/api/v1"
LAT0, LON0 = 43.0425, 11.5735            # Val d'Orcia (Toscana), open farmland: north-west corner of the farm
KY = 110574.0
KX = 111320.0 * math.cos(math.radians(LAT0))


def ll(x: float, z: float) -> list[float]:
    """Farm metres (x east, z south) -> [lon, lat]."""
    return [round(LON0 + x / KX, 8), round(LAT0 - z / KY, 8)]


def rect(x0: float, z0: float, x1: float, z1: float) -> list[list[float]]:
    return [ll(x0, z0), ll(x1, z0), ll(x1, z1), ll(x0, z1)]


# name, rect (x0, z0, x1, z1), crop 2026 (history), crop 2027 (plan), row spacing m, plant spacing m, row dir, irrigation
PLOTS = [
    ("Campo del Grano", (0, 0, 100, 70), "chickpea", "wheat", 0.17, 0.05, "x", "none"),
    ("Orto dei Pomodori", (40, 140, 120, 200), "bean", "tomato", 0.8, 0.45, "x", "drip"),
    ("Campo delle Insalate", (132, 140, 242, 200), "carrot", "lettuce", 0.45, 0.35, "x", "sprinkler"),
    ("Orto dei Cavoli", (105, 76, 165, 136), "potato", "cabbage", 0.6, 0.5, "x", "drip"),
    ("Orto delle Melanzane", (176, 72, 236, 122), "onion", "eggplant", 0.9, 0.5, "x", "drip"),
]


def main() -> None:
    c = httpx.Client(base_url=API, timeout=60)
    farm = c.get("/rotation/farm").json()
    c.put("/rotation/farm", json={"name": "Azienda Agricola Rossi", "region": "toscana", "province": "Siena",
                                  "municipality": "San Quirico d'Orcia", "latitude": LAT0, "longitude": LON0}).raise_for_status()
    reuse = []   # plots that cannot be deleted (sensor zones of the dev seed point to them) are reused
    for p in farm["plots"]:
        if c.delete(f"/rotation/plots/{p['id']}").status_code >= 400:
            reuse.append(p)
    for f in c.get("/rotation/features").json()["features"]:
        c.delete(f"/rotation/features/{f['id']}").raise_for_status()

    for name, (x0, z0, x1, z1), before, crop, rs, ps, rdir, irr in PLOTS:
        w, h = x1 - x0, z1 - z0
        profile = {"irrigation": irr, "texture": "mixed", "fertility": "normal", "water": "normal", "purpose": "commercial"}
        body = {"name": name, "shape": "rectangle", "width_m": w, "length_m": h, "profile": profile}
        if reuse:
            old = reuse.pop(0)
            pid = old["id"]
            c.put(f"/rotation/plots/{pid}", json=body).raise_for_status()
            for y in {h_["year"] for h_ in old.get("history", [])} - {2026}:
                c.put(f"/rotation/plots/{pid}/history", json={"year": y, "status": "unknown"})
            for y in range(2027, 2031):
                c.delete(f"/rotation/plots/{pid}/plans/{y}")
        else:
            pid = c.post("/rotation/plots", json=body).json()["id"]
        c.put(f"/rotation/plots/{pid}/boundary", json={"ring": rect(x0, z0, x1, z1)}).raise_for_status()
        plot = c.get("/rotation/farm").json()["plots"]
        plot = next(q for q in plot if q["id"] == pid)
        W, L = plot["width_m"], plot["length_m"]
        lay = {"width_m": W, "length_m": L, "shape": plot["shape"], "outline": plot["outline"], "orientation_deg": 0,
               "sections": [{"name": "Aiuola 1", "kind": "bed", "x": 1.0, "y": 1.0, "w": round(W - 2, 1), "h": round(L - 2, 1),
                             "row_spacing_m": rs, "plant_spacing_m": ps, "row_dir": rdir}]}
        plot = c.put(f"/rotation/plots/{pid}/layout", json=lay).json()
        sid = plot["sections"][0]["id"]
        c.put(f"/rotation/plots/{pid}/history", json={"year": 2026, "status": "crop",
                                                     "crops": [{"crop": before, "section_id": sid}]}).raise_for_status()
        j = c.post(f"/rotation/plots/{pid}/check", json={"section_id": sid, "crop": crop, "year": 2027, "planned": {}}).json()
        ass = [{"section_id": sid, "section": "Aiuola 1", "crop": crop, "name": j["name"], "family": j["family"],
                "verdict": j["verdict"], "reasons": j["reasons"], "manual": True}]
        c.put(f"/rotation/plots/{pid}/plans/2027", json={"assignments": ass}).raise_for_status()
        print(f"  {name}: {W:.0f} x {L:.0f} m, 2026 {before} -> 2027 {crop} ({j['verdict']})")

    feats = [
        ("building", "Casale", {"type": "Point", "coordinates": ll(128, 26)},
         {"type": "casale", "width_m": 14, "length_m": 26, "floors": 2, "rotation_deg": 90}),
        ("building", "Fienile", {"type": "Point", "coordinates": ll(112, 46)},
         {"type": "fienile", "width_m": 9, "length_m": 14, "floors": 1, "rotation_deg": 0}),
        ("greenhouse", "Serra in vetro", {"type": "Polygon", "coordinates": [rect(146, 18, 196, 52) + [ll(146, 18)]]},
         {"type": "vetro", "height_m": 4.5, "heated": False}),
        ("tank", "Cisterna", {"type": "Point", "coordinates": ll(203, 50)}, {"diameter_m": 4, "height_m": 6, "capacity_l": 75000}),
        ("orchard", "Frutteto di peschi", {"type": "Polygon", "coordinates": [rect(-44, 78, -6, 200) + [ll(-44, 78)]]},
         {"species": "peach", "row_spacing_m": 5, "tree_spacing_m": 4, "planted_year": 2016}),
        ("orchard", "Meleto", {"type": "Polygon", "coordinates": [rect(4, 76, 96, 132) + [ll(4, 76)]]},
         {"species": "apple", "row_spacing_m": 4.5, "tree_spacing_m": 3.5, "planted_year": 2018}),
        ("road", "Strada poderale", {"type": "LineString", "coordinates": [ll(126, 240), ll(126, 138), ll(126, 60), ll(140, 40)]},
         {"width_m": 4, "surface": "sterrato"}),
        ("road", "Capezzagna", {"type": "LineString", "coordinates": [ll(-50, 137), ll(250, 137)]}, {"width_m": 3, "surface": "sterrato"}),
        ("road", "Viale del casale", {"type": "LineString", "coordinates": [ll(100, 72), ll(250, 66)]}, {"width_m": 3, "surface": "ghiaia"}),
        # farm tracks (capezzagne) between the plots
        ("road", "Capezzagna sud", {"type": "LineString", "coordinates": [ll(34, 205), ll(248, 205)]}, {"width_m": 3.5, "surface": "sterrato"}),
        ("road", "Capezzagna ovest", {"type": "LineString", "coordinates": [ll(35, 137), ll(35, 205)]}, {"width_m": 3, "surface": "sterrato"}),
        ("road", "Capezzagna est", {"type": "LineString", "coordinates": [ll(247, 66), ll(247, 205)]}, {"width_m": 3, "surface": "sterrato"}),
        ("road", "Passaggio dei cavoli", {"type": "LineString", "coordinates": [ll(100, 73), ll(100, 137)]}, {"width_m": 3, "surface": "sterrato"}),
        ("road", "Passaggio delle melanzane", {"type": "LineString", "coordinates": [ll(170, 68), ll(170, 137)]}, {"width_m": 3, "surface": "sterrato"}),
        ("road", "Capezzagna del grano", {"type": "LineString", "coordinates": [ll(-3, -4), ll(105, -4), ll(105, 70)]}, {"width_m": 3, "surface": "sterrato"}),
        ("fence", "Staccionata dell'aia", {"type": "LineString", "coordinates": [ll(121, 63), ll(108, 63), ll(108, 6), ll(212, 6), ll(212, 63), ll(131, 63)]},
         {"type": "staccionata", "height_m": 1.2}),
        ("hedge", "Siepe nord", {"type": "LineString", "coordinates": [ll(-50, -10), ll(250, -10)]}, {"height_m": 6, "species": "acero campestre"}),
        ("hedge", "Siepe est", {"type": "LineString", "coordinates": [ll(252, -10), ll(252, 205)]}, {"height_m": 5, "species": "biancospino"}),
    ]
    for i, (x, z) in enumerate([(160, 160), (190, 160), (220, 160), (160, 185), (190, 185), (220, 185)]):
        feats.append(("sprinkler", f"Irrigatore {i + 1}", {"type": "Point", "coordinates": ll(x, z)},
                      {"type": "a_impulsi", "radius_m": 14, "flow_l_h": 1200}))
    for kind, name, geom, props in feats:
        r = c.post("/rotation/features", json={"kind": kind, "name": name, "geometry": geom, "props": props})
        if r.status_code >= 400:
            print("  !!", kind, name, r.text, file=sys.stderr)
        else:
            print(f"  + {name}")
    print("demo farm ready")


if __name__ == "__main__":
    main()
