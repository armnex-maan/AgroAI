"""Fusion of all acoustic engines into one explainable identification (Italian text).

Rules:
- a candidate is "probable" or "possible" only by thresholds on model scores;
  thresholds are configurable and are NOT calibrated probabilities
- the underground pattern detector can never exceed "possible" and never names a species
- strong wind / water / machinery context is reported, because it explains many false alarms
- with no candidate above threshold the verdict is "unknown"
"""
from __future__ import annotations

GROUP_INFO = {
    "bird": ("Uccello", "Controlla a vista o con una fototrappola; se BirdNET è attivo, verifica la specie ascoltando o con una foto."),
    "poultry_waterfowl": ("Pollame / uccelli acquatici", "Controlla se ci sono anatre, oche o galline nelle vicinanze."),
    "insect": ("Insetti", "Ispeziona le foglie e usa trappole adesive o a feromoni per capire quale insetto è."),
    "amphibian": ("Rana / rospo", "Di solito utili (mangiano insetti). Controlla se c'è acqua ferma."),
    "rodent": ("Roditore", "Cerca tane, camminamenti e rosicchiature; metti una fototrappola vicino al sensore."),
    "dog_canid": ("Cane / volpe", "Controlla recinzioni e impronte; le volpi cacciano anche i roditori."),
    "cat_feline": ("Gatto", "Di solito un gatto domestico: nessun intervento sulle colture."),
    "livestock": ("Bestiame", "Controlla se degli animali sono entrati nel campo."),
    "wild_animal": ("Animale selvatico (non identificato)", "Usa una fototrappola per capire di che animale si tratta."),
    "farm_animal": ("Animale da cortile o da allevamento", "Controlla se ci sono animali dell'azienda o dei vicini nei paraggi."),
    "underground_pattern": ("Attività ripetuta nel sottosuolo (bassa frequenza)",
                            "Cerca cumuli di terra freschi o gallerie entro pochi metri dal sensore e ripeti la "
                            "registrazione nello stesso punto in un altro orario. Etichetta il risultato per addestrare "
                            "il modello della tua azienda: questo rilevatore da solo non sa dire che animale è."),
}

CONTEXT_INFO = {
    "crackle_impact": "Si sentono crepitii, sfregamenti o rumori di attrezzi",
    "water_irrigation": "Si sente acqua / irrigazione",
    "hiss_noise": "Si sente un fruscio continuo (spruzzo d'acqua, vapore o vento sul microfono)",
    "snake_rattle": "Si sente un sibilo ritmico (spruzzo d'acqua o insetti)",
    "wind_vegetation": "Si sente vento o fruscio di foglie",
    "machinery_vehicle": "Si sentono macchine o veicoli",
    "human": "Si sentono voci o attività umane",
}
# Short names for the headline when the main sound is not an animal.
CONTEXT_SHORT = {
    "water_irrigation": "acqua o irrigazione", "hiss_noise": "fruscio continuo (spruzzo d'acqua, vapore o vento)",
    "wind_vegetation": "vento o foglie", "machinery_vehicle": "macchine o motori",
    "crackle_impact": "crepitii o attrezzi", "human": "voci o persone",
    "snake_rattle": "fruscio ritmico (spruzzo d'acqua o insetti)",
}
NOISE_GROUPS = ("machinery_vehicle", "water_irrigation", "wind_vegetation", "crackle_impact", "hiss_noise")

LEVEL_IT = {"probable": "Probabile", "possible": "Possibile"}


def _level(score: float, probable: float, possible: float) -> str | None:
    if score >= probable:
        return "probable"
    if score >= possible:
        return "possible"
    return None


YAM_TAXON = {"bird": "bird", "poultry_waterfowl": "bird", "insect": "insect", "amphibian": "amphibian",
             "dog_canid": "mammal", "cat_feline": "mammal", "livestock": "mammal", "rodent": "mammal"}


def fuse(yam: dict | None, bird: dict | None, custom: dict | None, underground: dict,
         probable: float, possible: float, species: list[dict] | None = None,
         rejected: list[dict] | None = None, perch_info: dict | None = None) -> dict:
    candidates: list[dict] = []
    context: list[dict] = []

    if yam and yam.get("available"):
        noise = max([g["score"] for g in yam.get("groups", []) if g["group"] in NOISE_GROUPS] or [0.0])
        for g in yam.get("groups", []):
            lvl = _level(g["score"], probable, possible)
            if not lvl:
                continue
            if g["kind"] == "animal" and g["score"] < 0.8 * noise:
                continue  # an engine or running water louder than the "animal": classic false alarm
            if g["kind"] == "animal":
                name, verify = GROUP_INFO.get(g["group"], (g["group"], "Verifica sul campo."))
                candidates.append({"label": name, "group": g["group"], "source": "YAMNet",
                                   "taxon_group": YAM_TAXON.get(g["group"]),
                                   "score": g["score"], "level": lvl,
                                   "evidence": f"Il modello YAMNet ha riconosciuto «{g['best_class']}» "
                                               f"(punteggio {g['score']:.2f})",
                                   "verification": verify})
            elif g["group"] in CONTEXT_INFO:
                context.append({"group": g["group"], "description": CONTEXT_INFO[g["group"]],
                                "score": g["score"], "best_class": g["best_class"]})

    specific = {c["group"] for c in candidates if c["group"] != "wild_animal"}
    if specific - {"farm_animal"} or species:
        # "Animal" / "Wild animals" / "Livestock" are AudioSet parent classes that fire with any specific animal.
        candidates = [c for c in candidates if c["group"] not in ("wild_animal", "farm_animal")]
    if species:
        # A named species replaces the generic group it belongs to ("Merlo" instead of "Uccello").
        named_groups = {s["taxon_group"] for s in species}
        candidates = [c for c in candidates if c.get("taxon_group") not in named_groups] + list(species)

    if bird and bird.get("available"):
        for d in bird.get("detections", [])[:3]:
            lvl = _level(d["confidence"], probable, possible)
            if lvl:
                candidates.append({
                    "label": f"{d['common_name']} ({d['scientific_name']})", "group": "bird_species",
                    "source": "BirdNET", "score": d["confidence"], "level": lvl,
                    "evidence": f"BirdNET tra {d['start_s']} e {d['end_s']} s, punteggio {d['confidence']:.2f}",
                    "verification": "Conferma vedendolo o confrontando con registrazioni di riferimento (es. xeno-canto).",
                })

    if custom and custom.get("label") not in (None, "unknown"):
        lvl = _level(custom["confidence"], probable, possible)
        if lvl:
            candidates.append({
                "label": custom["label"], "group": "farm_model", "source": f"modello della tua azienda v{custom.get('version')}",
                "score": custom["confidence"], "level": lvl,
                "evidence": "Riconosciuto dal modello addestrato sulle tue registrazioni; il suono è simile agli "
                            "esempi che hai etichettato.",
                "verification": "Conferma sul campo, poi etichetta questa registrazione per rendere il modello più preciso.",
            })

    if underground.get("category") == "repetitive_low_freq_pattern":
        noisy = [c for c in context if c["group"] in ("water_irrigation", "machinery_vehicle", "wind_vegetation")]
        score = float(underground.get("confidence", 0.0))
        if noisy:
            score *= 0.5
        lvl = "possible" if score >= possible else None
        if lvl:
            name, verify = GROUP_INFO["underground_pattern"]
            ev = underground.get("evidence", {})
            period = ev.get("periodicity", {}).get("period_s")
            note = f"{ev.get('envelope_peaks')} colpi ripetuti, circa ogni {period} s"
            if noisy:
                note += "; affidabilità dimezzata perché " + ", ".join(c["description"].lower() for c in noisy)
            candidates.append({"label": name, "group": "underground_pattern", "source": "rilevatore sottosuolo (sperimentale)",
                               "score": round(score, 3), "level": lvl, "evidence": note,
                               "verification": verify})

    candidates.sort(key=lambda c: (c["level"] == "probable", c["score"]), reverse=True)
    context.sort(key=lambda c: c["score"], reverse=True)
    main_sound = None
    c0 = next((c for c in context if c["group"] in CONTEXT_SHORT), None)
    if c0:
        main_sound = {"group": c0["group"], "label": CONTEXT_SHORT[c0["group"]],
                      "level": _level(c0["score"], probable, possible), "score": c0["score"],
                      "best_class": c0["best_class"]}
    if candidates:
        top = candidates[0]
        verdict = top["level"]
        summary = f"{LEVEL_IT[top['level']]}: {top['label']}"
    elif main_sound:
        # No animal, but we do know what the sound is: say it plainly instead of "unknown".
        verdict = "other_sound"
        summary = f"Nessun animale. {LEVEL_IT[main_sound['level']]}: {main_sound['label']}"
    else:
        verdict = "unknown"
        summary = "Non riconosciuto: nessun modello ha trovato prove sufficienti."

    return {
        "verdict": verdict,
        "summary": summary,
        "candidates": candidates,
        "main_sound": main_sound,
        "rejected": rejected or [],
        "species_model": perch_info or {},
        "context": context,
        "thresholds": {"probable": probable, "possible": possible,
                       "note": "punteggi dei modelli, non vere probabilità"},
        "engines": {
            "perch": bool(perch_info and perch_info.get("available")),
            "yamnet": bool(yam and yam.get("available")),
            "birdnet": bool(bird and bird.get("available")),
            "farm_model": bool(custom),
            "underground_experimental": True,
        },
    }
