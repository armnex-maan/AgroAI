"""Species names and local plausibility via the iNaturalist public API.

- Italian common name and animal group for a scientific name.
- Whether the species has research-grade observations near the farm: a species never
  observed within RADIUS_KM is downgraded, because it is probably a misidentification.
Results are cached on disk; without internet the lookup returns None and nothing is filtered.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from app.config import settings

log = logging.getLogger("agroai.taxonomy")
API = "https://api.inaturalist.org/v1"
RADIUS_KM = 250
UA = {"User-Agent": "AGROAI/0.1 (agricultural monitoring; species name lookup)"}

GROUP = {"Aves": ("bird", "Uccello"), "Amphibia": ("amphibian", "Anfibio"), "Insecta": ("insect", "Insetto"),
         "Mammalia": ("mammal", "Mammifero"), "Reptilia": ("reptile", "Rettile"), "Arachnida": ("arachnid", "Aracnide"),
         "Mollusca": ("mollusc", "Mollusco")}

_lock = threading.Lock()
_cache: dict | None = None
_last_call = 0.0


def _path() -> Path:
    p = settings.media_path / "models" / "perch_v2"
    p.mkdir(parents=True, exist_ok=True)
    return p / "taxa_cache.json"


def _load_cache() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _cache = {"taxa": {}, "nearby": {}}
    return _cache


def _save() -> None:
    _path().write_text(json.dumps(_cache, ensure_ascii=False), encoding="utf-8")


def _get(path: str, params: dict) -> dict | None:
    global _last_call
    wait = 1.0 - (time.time() - _last_call)  # iNaturalist asks for ≤ ~1 request/second
    if wait > 0:
        time.sleep(wait)
    _last_call = time.time()
    try:
        url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
        return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15))
    except Exception as exc:
        log.info("iNaturalist lookup failed: %s", exc)
        return None


def taxon(scientific: str) -> dict | None:
    with _lock:
        c = _load_cache()
        if scientific in c["taxa"]:
            return c["taxa"][scientific]
        d = _get("taxa", {"q": scientific, "rank": "species,subspecies", "locale": "it", "per_page": 5})
        if d is None:
            return None
        hit = next((t for t in d.get("results", []) if t.get("name", "").lower() == scientific.lower()), None)
        hit = hit or (d.get("results") or [None])[0]
        info = None
        if hit:
            g, g_it = GROUP.get(hit.get("iconic_taxon_name") or "", ("other", "Altro"))
            info = {"id": hit["id"], "common_name": hit.get("preferred_common_name"), "group": g, "group_it": g_it}
        c["taxa"][scientific] = info
        _save()
        return info


# Sound-producing groups worth listing: birds, amphibians, mammals, reptiles, crickets &
# grasshoppers (Orthoptera), cicadas (Cicadidae), bees & wasps (Apoidea), mosquitoes (Culicidae).
LOCAL_TAXA = {3: "Aves", 20978: "Amphibia", 40151: "Mammalia", 26036: "Reptilia",
              47651: "Orthoptera", 50190: "Cicadidae", 47222: "Apoidea", 52134: "Culicidae"}


def local_species(lat: float, lon: float) -> dict | None:
    """Species with research-grade iNaturalist observations within RADIUS_KM of the farm.
    Returns {scientific name: {common_name, group, group_it, observations}} or None when offline."""
    key = f"{lat:.1f}:{lon:.1f}"
    with _lock:
        c = _load_cache()
        cached = c.setdefault("local", {}).get(key)
        if cached is not None:
            return cached
    out: dict = {}
    for taxon_id in LOCAL_TAXA:
        for page in (1, 2, 3):
            d = _get("observations/species_counts", {
                "lat": lat, "lng": lon, "radius": RADIUS_KM, "taxon_id": taxon_id, "quality_grade": "research",
                "locale": "it", "per_page": 500, "page": page})
            if d is None:
                return None  # offline: do not cache a partial list
            for r in d.get("results", []):
                t = r.get("taxon") or {}
                g, g_it = GROUP.get(t.get("iconic_taxon_name") or "", ("other", "Altro"))
                out[t.get("name", "")] = {"common_name": t.get("preferred_common_name"), "group": g,
                                          "group_it": g_it, "observations": r.get("count", 0), "id": t.get("id")}
            if len(d.get("results", [])) < 500:
                break
    with _lock:
        c = _load_cache()
        c["local"][key] = out
        for name, info in out.items():
            c["taxa"].setdefault(name, {"id": info["id"], "common_name": info["common_name"],
                                        "group": info["group"], "group_it": info["group_it"]})
        _save()
    return out


def seen_nearby(taxon_id: int, lat: float, lon: float) -> int | None:
    key = f"{taxon_id}:{lat:.1f}:{lon:.1f}"
    with _lock:
        c = _load_cache()
        if key in c["nearby"]:
            return c["nearby"][key]
        d = _get("observations", {"taxon_id": taxon_id, "lat": lat, "lng": lon, "radius": RADIUS_KM,
                                  "quality_grade": "research", "per_page": 0})
        if d is None:
            return None
        n = int(d.get("total_results", 0))
        c["nearby"][key] = n
        _save()
        return n
