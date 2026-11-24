"""Species-level identification.

Perch 2.0 decides WHICH species, YAMNet decides WHETHER an animal is there at all.
On ESC-50 Perch alone turned chainsaws into sheep and trains into sandpipers; YAMNet's
animal/machine classes are reliable, so a species is accepted only when:
  1. YAMNet hears an animal clearly, and louder than machines / water / wind;
  2. the species belongs to the animal group YAMNet (or Perch's cricket/frog classes) heard;
  3. for clearly domestic sounds (dog, cat, livestock, poultry) the species is of that family.
"""
from __future__ import annotations

import math

from app.ml.audio import taxonomy

YAM_TO_GROUP = {"bird": "bird", "poultry_waterfowl": "bird", "insect": "insect", "amphibian": "amphibian",
                "dog_canid": "mammal", "cat_feline": "mammal", "livestock": "mammal", "rodent": "mammal",
                "wild_animal": "animal", "farm_animal": "animal"}
ANIMAL_YAM = set(YAM_TO_GROUP)
NOISE_YAM = {"machinery_vehicle", "water_irrigation", "wind_vegetation", "crackle_impact", "hiss_noise"}
# Domestic sound families: when YAMNet clearly hears one, the species must be from these genera.
FAMILY_GENERA = {
    "dog_canid": {"Canis", "Vulpes", "Nyctereutes"},
    "cat_feline": {"Felis"},
    "livestock": {"Bos", "Ovis", "Capra", "Sus", "Equus"},
    "poultry_waterfowl": {"Gallus", "Anas", "Anser", "Meleagris", "Numida", "Cairina", "Phasianus", "Pavo"},
}
GROUP_IT = {"bird": "uccello", "insect": "insetto", "amphibian": "anfibio", "mammal": "mammifero",
            "reptile": "rettile", "arachnid": "aracnide", "other": "animale"}
MOLE = "Talpa europaea"
MIN_ANIMAL = 0.3


INSECT_CONFIRM = 0.15  # Perch "Cricket/Insect" evidence that turns an ambiguous "Snake" hiss into an insect


def _yam_scores(yam: dict | None, perch_res: dict | None = None) -> dict[str, float]:
    if not yam or not yam.get("available"):
        return {}
    s = {g["group"]: g["score"] for g in yam.get("groups", [])}
    rattle = s.pop("snake_rattle", 0.0)
    if rattle:
        insect_ev = ((perch_res or {}).get("group_evidence") or {}).get("insect", 0.0)
        key = "insect" if insect_ev >= INSECT_CONFIRM else "hiss_noise"
        s[key] = max(s.get(key, 0.0), rattle)
    return s


def animal_presence(yam: dict | None, perch_res: dict | None = None) -> tuple[float, float]:
    s = _yam_scores(yam, perch_res)
    animal = max([v for k, v in s.items() if k in ANIMAL_YAM] or [0.0])
    noise = max([v for k, v in s.items() if k in NOISE_YAM] or [0.0])
    return animal, noise


def group_support(group: str, yam: dict | None, perch_res: dict | None) -> float:
    s = _yam_scores(yam, perch_res)
    yam_g = max([v for k, v in s.items() if YAM_TO_GROUP.get(k) == group] or [0.0])
    pev = (perch_res or {}).get("group_evidence") or {}
    # Perch's own "Cricket/Insect" and "Frog" classes are reliable; its bird/mammal classes are not.
    if group in ("insect", "amphibian"):
        yam_g = max(yam_g, pev.get(group, 0.0))
    return yam_g


def candidates(perch_res: dict | None, yam: dict | None, local: dict | None,
               probable: float, possible: float) -> tuple[list[dict], list[dict], dict]:
    if not perch_res or not perch_res.get("available"):
        return [], [], {}
    animal, noise = animal_presence(yam, perch_res)
    s = _yam_scores(yam, perch_res)
    generic = max(s.get("wild_animal", 0.0), s.get("farm_animal", 0.0))
    strong_family = {k: v for k, v in s.items() if k in FAMILY_GENERA and v >= 0.5}
    gate = {"animal": round(animal, 3), "noise": round(noise, 3), "yamnet": bool(s)}
    accepted, rejected = [], []

    for d in perch_res.get("species", []):
        name = d["scientific_name"]
        info = (local or {}).get(name) or taxonomy.taxon(name) or {}
        group = info.get("group", "other")
        common = info.get("common_name")
        label = f"{common} ({name})" if common else name

        def reject(reason: str):
            rejected.append({"label": label, "score": d["score"], "group": group, "reason": reason})

        if s and (animal < MIN_ANIMAL or animal < 0.8 * noise):
            reject("non si sente chiaramente un animale (prevalgono macchine, acqua o vento)")
            continue
        support = group_support(group, yam, perch_res)
        if strong_family:
            genus = name.split()[0]
            fams = [f for f in strong_family if genus in FAMILY_GENERA[f]]
            if not fams and group in ("mammal", "bird") and any(YAM_TO_GROUP[f] == group for f in strong_family):
                reject("il suono è chiaramente di un animale domestico di un'altra famiglia")
                continue
        confirm = max(support, 0.6 * generic) if s else 0.5
        eff = math.sqrt(d["score"] * confirm)
        if eff < possible:
            reject(f"non si sente un suono tipico di {GROUP_IT.get(group, 'animale')}")
            continue
        level = "probable" if eff >= probable and support >= possible and s else "possible"
        note = ""
        if name == MOLE:
            level = "possible"
            note = (" Esistono pochissime registrazioni di talpa per addestrare i modelli: verifica sempre "
                    "con cumuli di terra freschi e gallerie.")
        accepted.append({
            "label": label, "group": f"species_{group}", "source": "Perch 2.0", "score": round(eff, 3),
            "level": level, "scientific_name": name, "common_name": common, "taxon_group": group,
            "taxon_group_it": GROUP_IT.get(group, "animale"),
            "evidence": (f"Specie indicata da Perch 2.0 tra {d['start_s']} e {d['end_s']} s; il riconoscimento "
                         f"generale conferma un suono di {GROUP_IT.get(group, 'animale')} "
                         f"(punteggio {max(support, generic):.2f}).{note}"),
            "verification": _verify_text(group, common or name),
            "inat_observations": info.get("observations"),
        })
    accepted.sort(key=lambda c: (c["level"] == "probable", c["score"]), reverse=True)
    return accepted[:4], rejected[:6], gate


def _verify_text(group: str, name: str) -> str:
    return {
        "bird": f"Ascolta il confronto su xeno-canto.org cercando «{name}», oppure cercalo con il binocolo all'alba.",
        "insect": f"Di sera cerca «{name}» nell'erba vicino al microfono; confronta il canto con una registrazione di riferimento.",
        "amphibian": "Controlla fossi e canali vicini di sera: le rane cantano soprattutto dopo il tramonto in primavera.",
        "mammal": "Cerca impronte, escrementi, tane o usa una fototrappola vicino al microfono.",
    }.get(group, "Verifica sul campo con una fototrappola o un'osservazione diretta.")
