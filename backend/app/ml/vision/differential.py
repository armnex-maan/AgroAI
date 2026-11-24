"""Differential diagnosis: weigh every plausible cause against what is actually seen.

The vision model describes the symptoms with fixed fields (which organ, where on the fruit, texture,
colour, shape, mould, leaves/stems, sun exposure…) and proposes causes. This module re-scores each
cause with a symptom profile per cause: features that fit raise the score, features that contradict it
lower it (e.g. blossom-end rot with lesions next to the stalk). Farmer answers to follow-up questions
override the photo and count more. A single photo is never treated as certain: scores are capped and
reported as "compatibility with what is seen", in three tiers: probable / possible / unlikely.
"""
from __future__ import annotations

import math

from app.ml.vision.causes import CAUSES

# ---------------- observable features ----------------
FEATURES: dict[str, dict[str, str]] = {
    "fruit_location": {
        "stem_end": "lesioni sulla parte alta del frutto, vicino al picciolo",
        "blossom_end": "lesioni all'estremità del frutto opposta al picciolo",
        "sun_side": "lesioni solo sul lato del frutto esposto al sole",
        "scattered": "macchie sparse su tutto il frutto",
    },
    "texture": {
        "dry_leathery": "lesioni secche e dure, come cuoio",
        "firm_greasy": "chiazze sode, come unte",
        "soft_wet": "tessuto molle e acquoso",
        "papery_pale": "tessuto chiaro e secco come carta",
        "sunken": "macchie infossate",
    },
    "colour": {
        "dark_brown_black": "colore marrone scuro o nero",
        "olive_brown_marbled": "chiazze brune o verde-oliva marmorizzate",
        "pale_white_yellow": "zone chiare, biancastre o giallastre",
        "grey": "colore grigio",
        "yellow": "ingiallimento",
        "orange_rust": "pustole arancioni o color ruggine",
    },
    "shape": {
        "concentric_rings": "macchie con anelli concentrici",
        "circular_sunken": "macchie rotonde e infossate",
        "large_irregular": "chiazze grandi e irregolari",
        "small_spots": "macchie piccole e numerose",
        "cracks": "crepe o spaccature",
        "holes_chewed": "buchi o parti mangiate",
        "interveinal": "giallo tra le nervature",
        "margins": "bordi delle foglie secchi",
        "uniform": "colore alterato in modo uniforme",
    },
    "leaves": {"affected": "anche le foglie sono colpite", "healthy": "le foglie sono sane"},
    "stems": {"affected": "anche i fusti hanno lesioni scure", "healthy": "i fusti sono sani"},
    "sun_exposed": {"yes": "i frutti colpiti sono esposti direttamente al sole", "no": "i frutti colpiti sono all'ombra"},
    "mould": {
        "none": "nessuna muffa visibile",
        "white_downy": "muffetta bianca sottile",
        "white_powder": "polvere bianca che si toglie con un dito",
        "grey_fuzzy": "muffa grigia polverosa",
        "dark_velvety": "muffetta nera vellutata",
        "pink_orange": "massa rosata o arancione",
    },
    "wilting": {"yes": "la pianta è appassita", "no": "la pianta non è appassita"},
    "weather": {"humid_rainy": "tempo piovoso o notti umide nei giorni scorsi",
                "hot_sunny": "giorni caldi con sole forte", "dry_mild": "tempo asciutto e mite"},
    "irrigation": {"irregular": "irrigazione irregolare (secco e poi molta acqua)", "regular": "irrigazione regolare"},
    "spread": {"fast": "si è diffuso in pochi giorni su molte piante", "slow": "si diffonde lentamente"},
}
ORGANS = {"leaf": "foglie", "fruit": "frutti", "stem": "fusti"}

# where each cause shows symptoms
CAUSE_ORGANS: dict[str, set[str]] = {
    "blossom_end_rot": {"fruit"}, "fruit_cracking": {"fruit"}, "anthracnose": {"fruit"},
    "late_blight": {"leaf", "fruit", "stem"}, "early_blight": {"leaf", "fruit", "stem"},
    "grey_mould": {"leaf", "fruit", "stem"}, "heat_sunscald": {"leaf", "fruit"},
    "chewing_insects": {"leaf", "fruit"}, "sucking_insects": {"leaf", "stem"},
    "viral_disease": {"leaf", "fruit"}, "mechanical_damage": {"leaf", "fruit", "stem"},
    "chemical_damage": {"leaf"}, "water_stress": {"leaf", "stem"}, "bacterial_wilt": {"leaf", "stem"}, "waterlogging": {"leaf", "stem"},
}
LEAF_ONLY = {"nitrogen_deficiency", "iron_chlorosis", "magnesium_deficiency", "potassium_deficiency",
             "fungal_leaf_spot", "powdery_mildew", "downy_mildew", "rust", "natural_senescence"}
FRUIT_DIFFERENTIAL = ["late_blight", "blossom_end_rot", "heat_sunscald", "anthracnose", "early_blight",
                      "grey_mould", "fruit_cracking"]

# symptom profiles: feature -> value -> weight (+ fits, - contradicts; ±3 = decisive)
P = dict[str, dict[str, float]]
PROFILES: dict[str, P] = {
    "blossom_end_rot": {
        "fruit_location": {"blossom_end": 3, "stem_end": -3, "sun_side": -1.5, "scattered": -2},
        "texture": {"dry_leathery": 1, "sunken": 1, "firm_greasy": -1.5, "soft_wet": -0.5, "papery_pale": -1},
        "colour": {"dark_brown_black": 1, "olive_brown_marbled": -1, "pale_white_yellow": -1},
        "shape": {"concentric_rings": -1, "circular_sunken": 0.5, "cracks": -1},
        "leaves": {"affected": -2, "healthy": 1},
        "stems": {"affected": -2},
        "mould": {"white_downy": -1.5, "grey_fuzzy": -1, "pink_orange": -1.5},
        "irrigation": {"irregular": 1.5, "regular": -0.5},
        "spread": {"fast": -1},
    },
    "late_blight": {
        "fruit_location": {"stem_end": 2, "scattered": 0.5, "blossom_end": -1, "sun_side": -0.5},
        "texture": {"firm_greasy": 2.5, "dry_leathery": 0.5, "papery_pale": -2, "soft_wet": -0.5},
        "colour": {"olive_brown_marbled": 2.5, "dark_brown_black": 1, "pale_white_yellow": -2},
        "shape": {"large_irregular": 1.5, "concentric_rings": -1, "circular_sunken": -1, "cracks": -1},
        "leaves": {"affected": 2, "healthy": -2},
        "stems": {"affected": 2},
        "mould": {"white_downy": 2.5, "grey_fuzzy": -1, "pink_orange": -1.5, "white_powder": -1},
        "weather": {"humid_rainy": 1.5, "hot_sunny": -1, "dry_mild": -1},
        "spread": {"fast": 1.5, "slow": -0.5},
    },
    "early_blight": {
        "fruit_location": {"stem_end": 1, "blossom_end": -1},
        "shape": {"concentric_rings": 3, "large_irregular": -2, "circular_sunken": 0.5, "uniform": -1},
        "colour": {"dark_brown_black": 1, "olive_brown_marbled": -0.5},
        "texture": {"sunken": 0.5, "dry_leathery": 0.5, "firm_greasy": -1},
        "leaves": {"affected": 1.5, "healthy": -1.5},
        "mould": {"dark_velvety": 2, "white_downy": -2.5},
        "weather": {"humid_rainy": 0.5},
    },
    "anthracnose": {
        "shape": {"circular_sunken": 2.5, "concentric_rings": 1, "large_irregular": -1},
        "texture": {"sunken": 1.5, "soft_wet": 1, "firm_greasy": -1},
        "mould": {"pink_orange": 2.5, "white_downy": -1},
        "fruit_location": {"scattered": 1, "blossom_end": -0.5},
        "leaves": {"affected": -0.5, "healthy": 0.5},
        "stems": {"affected": -1},
        "weather": {"humid_rainy": 1},
    },
    "heat_sunscald": {
        "sun_exposed": {"yes": 2, "no": -3},
        "fruit_location": {"sun_side": 3, "stem_end": 0.5, "blossom_end": -1, "scattered": -1.5},
        "texture": {"papery_pale": 3, "firm_greasy": -2, "soft_wet": -1},
        "colour": {"pale_white_yellow": 2.5, "olive_brown_marbled": -2, "dark_brown_black": -1.5},
        "stems": {"affected": -1.5},
        "mould": {"white_downy": -1.5},
        "weather": {"hot_sunny": 2, "humid_rainy": -1},
    },
    "grey_mould": {
        "mould": {"grey_fuzzy": 3, "none": -1, "white_downy": -0.5},
        "texture": {"soft_wet": 2, "firm_greasy": -1.5, "dry_leathery": -1, "papery_pale": -1},
        "colour": {"grey": 1.5},
        "weather": {"humid_rainy": 1.5, "hot_sunny": -1},
    },
    "fruit_cracking": {
        "shape": {"cracks": 3, "large_irregular": -1, "circular_sunken": -1},
        "irrigation": {"irregular": 1.5},
        "leaves": {"affected": -0.5},
    },
    "bacterial_wilt": {"wilting": {"yes": 2.5, "no": -2}, "stems": {"affected": 1.5}, "leaves": {"affected": 0.5},
                       "weather": {"hot_sunny": 0.5}, "mould": {"white_downy": -1, "grey_fuzzy": -1}},
    "water_stress": {"wilting": {"yes": 2, "no": -1}, "shape": {"margins": 0.5, "uniform": 0.5},
                     "irrigation": {"irregular": 0.5}},
    "waterlogging": {"wilting": {"yes": 1}, "colour": {"yellow": 0.5}},
    "nitrogen_deficiency": {"shape": {"uniform": 1.5, "interveinal": -1}, "colour": {"yellow": 1.5}},
    "iron_chlorosis": {"shape": {"interveinal": 2.5, "uniform": -1}, "colour": {"yellow": 1}},
    "magnesium_deficiency": {"shape": {"interveinal": 2, "uniform": -1}, "colour": {"yellow": 1}},
    "potassium_deficiency": {"shape": {"margins": 2.5}},
    "fungal_leaf_spot": {"shape": {"small_spots": 1.5, "concentric_rings": 1}, "weather": {"humid_rainy": 1}},
    "powdery_mildew": {"mould": {"white_powder": 3, "white_downy": -0.5, "none": -1.5}},
    "downy_mildew": {"mould": {"white_downy": 2}, "colour": {"yellow": 0.5}, "weather": {"humid_rainy": 1.5}},
    "rust": {"colour": {"orange_rust": 3}},
    "chewing_insects": {"shape": {"holes_chewed": 3}},
    "sucking_insects": {"shape": {"small_spots": 0.5}},
    "mechanical_damage": {"shape": {"cracks": 0.5, "holes_chewed": 0.5}},
}
# decisive explanations shown to the farmer when a key feature rules a cause in or out
KEY_NOTES: dict[tuple[str, str, str], str] = {
    ("blossom_end_rot", "fruit_location", "stem_end"):
        "il marciume apicale colpisce l'estremità opposta al picciolo, non la parte vicina al calice",
    ("blossom_end_rot", "fruit_location", "blossom_end"): "la posizione è quella tipica del marciume apicale",
    ("blossom_end_rot", "leaves", "affected"): "il marciume apicale riguarda solo i frutti, non foglie e fusti",
    ("blossom_end_rot", "stems", "affected"): "il marciume apicale non causa lesioni sui fusti",
    ("late_blight", "leaves", "affected"): "foglie e frutti colpiti insieme sono tipici della peronospora",
    ("late_blight", "stems", "affected"): "le lesioni scure sui fusti sono tipiche della peronospora",
    ("late_blight", "texture", "firm_greasy"): "chiazze sode e come unte sono tipiche della peronospora sui frutti",
    ("late_blight", "colour", "olive_brown_marbled"): "le chiazze brune marmorizzate sono tipiche della peronospora",
    ("heat_sunscald", "colour", "olive_brown_marbled"):
        "la scottatura dà zone chiare e secche, non chiazze brune marmorizzate",
    ("heat_sunscald", "sun_exposed", "no"): "i frutti all'ombra non prendono la scottatura",
    ("heat_sunscald", "texture", "papery_pale"): "il tessuto chiaro e cartaceo è tipico della scottatura",
    ("early_blight", "mould", "white_downy"):
        "la muffetta bianca sottile è tipica della peronospora, non dell'alternariosi",
    ("early_blight", "shape", "concentric_rings"): "gli anelli concentrici sono il segno tipico dell'alternariosi",
    ("early_blight", "shape", "large_irregular"):
        "chiazze grandi e irregolari, senza gli anelli concentrici tipici dell'alternariosi",
    ("anthracnose", "shape", "circular_sunken"): "macchie rotonde e infossate sono tipiche dell'antracnosi",
    ("anthracnose", "mould", "pink_orange"): "la massa rosata di spore è tipica dell'antracnosi",
    ("grey_mould", "mould", "grey_fuzzy"): "la muffa grigia polverosa è il segno della botrite",
    ("powdery_mildew", "mould", "white_powder"): "la polvere bianca che si toglie è tipica dell'oidio",
}

QUESTIONS: dict[str, dict] = {
    "fruit_location": {"text": "Dove sono le macchie sul frutto?", "options": [
        ("stem_end", "In alto, vicino al picciolo"), ("blossom_end", "In basso, all'estremità opposta al picciolo"),
        ("sun_side", "Solo sul lato al sole"), ("scattered", "Sparse su tutto il frutto")]},
    "sun_exposed": {"text": "I frutti colpiti sono esposti direttamente al sole?", "options": [
        ("yes", "Sì, sono scoperti"), ("no", "No, sono all'ombra delle foglie")]},
    "texture": {"text": "Toccando le macchie, come sono?", "options": [
        ("dry_leathery", "Dure e secche, come cuoio"), ("firm_greasy", "Sode ma come unte"),
        ("soft_wet", "Molli e acquose"), ("papery_pale", "Chiare e secche come carta")]},
    "leaves": {"text": "Anche foglie e fusti hanno macchie o seccumi?", "options": [
        ("affected", "Sì, anche foglie o fusti"), ("healthy", "No, solo i frutti")]},
    "mould": {"text": "Al mattino, si vede una muffa sulle macchie?", "options": [
        ("none", "Nessuna muffa"), ("white_downy", "Muffetta bianca sottile"), ("grey_fuzzy", "Muffa grigia polverosa"),
        ("pink_orange", "Massa rosata o arancione"), ("dark_velvety", "Muffetta nera vellutata")]},
    "weather": {"text": "Com'è stato il tempo negli ultimi 7–10 giorni?", "options": [
        ("humid_rainy", "Piovoso o con notti umide"), ("hot_sunny", "Caldo con sole forte"), ("dry_mild", "Asciutto e mite")]},
    "irrigation": {"text": "L'irrigazione è stata regolare?", "options": [
        ("regular", "Sì, regolare"), ("irregular", "No: periodi secchi e poi molta acqua")]},
    "spread": {"text": "Quanto in fretta si è diffuso?", "options": [
        ("fast", "In pochi giorni su molte piante"), ("slow", "Lentamente, su poche piante")]},
}
QUESTION_FEATURE = {"leaves": ("leaves", "stems")}  # one answer sets both features
PHOTO_UNRELIABLE = {"mould", "texture"}

PRIOR = {"high": 0.6, "medium": 0.4, "low": 0.2}
PRIOR_ENGINE = 0.12        # cause not proposed by the vision model
PRIOR_MODEL = 0.3          # cause proposed only by the trained image model
PHOTO_WEIGHT = 0.6         # what the model reads from a photo counts less than a farmer's answer
ANSWER_WEIGHT = 1.0
SLOPE = 0.6
CAP_PHOTO, CAP_ANSWERS = 0.85, 0.92
TIERS = (("probable", 0.6), ("possible", 0.3), ("unlikely", 0.0))
TIER_TO_LIKELIHOOD = {"probable": "high", "possible": "medium", "unlikely": "low"}


def _logit(p: float) -> float:
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def tier(p: float) -> str:
    return next(name for name, lo in TIERS if p >= lo)


def merge_observations(observations: dict | None, answers: dict | None) -> dict[str, tuple[str, str]]:
    """feature -> (value, origin) with origin 'photo' or 'answer'. Answers win."""
    obs: dict[str, tuple[str, str]] = {}
    for k, v in (observations or {}).items():
        if k in FEATURES and isinstance(v, str) and v in FEATURES[k]:
            obs[k] = (v, "photo")
    for k, v in (answers or {}).items():
        for feat in QUESTION_FEATURE.get(k, (k,)):
            if feat in FEATURES and v in FEATURES[feat]:
                obs[feat] = (v, "answer")
    return obs


def _evidence(cause_id: str, obs: dict[str, tuple[str, str]], organs: set[str]) -> tuple[float, list[dict]]:
    total, ev = 0.0, []
    for feat, weights in PROFILES.get(cause_id, {}).items():
        if feat not in obs:
            continue
        value, origin = obs[feat]
        w = weights.get(value)
        if not w:
            continue
        w_eff = w * (ANSWER_WEIGHT if origin == "answer" else PHOTO_WEIGHT)
        total += w_eff
        text = KEY_NOTES.get((cause_id, feat, value)) or FEATURES[feat][value]
        ev.append({"text": text[0].upper() + text[1:], "effect": "supports" if w > 0 else "weakens",
                   "strength": "forte" if abs(w) >= 2.5 else "media" if abs(w) >= 1.5 else "debole",
                   "origin": "tua risposta" if origin == "answer" else "foto", "weight": round(w_eff, 2)})
    allowed = CAUSE_ORGANS.get(cause_id) or ({"leaf"} if cause_id in LEAF_ONLY else None)
    if organs and allowed and not (organs & allowed):
        total -= 2.0
        seen = ", ".join(ORGANS[o] for o in sorted(organs))
        where = ", ".join(ORGANS[o] for o in sorted(allowed))
        ev.append({"text": f"Si vedono sintomi su {seen}, mentre questa causa colpisce {where}",
                   "effect": "weakens", "strength": "forte", "origin": "foto", "weight": -2.0})
    return total, ev


def _sensor_evidence(cause_id: str, soil: dict | None, ctx: dict) -> tuple[float, list[dict]]:
    total, ev = 0.0, []
    if soil and cause_id in ("water_stress", "waterlogging", "blossom_end_rot"):
        if not soil.get("usable"):
            ev.append({"text": f"Umidità del terreno {soil['value']:.1f}%: dato di prova, non considerato",
                       "effect": "neutral", "strength": "nessuna", "origin": "sensore", "weight": 0})
        else:
            k = {"alta": 1.5, "media": 1.0, "bassa": 0.5}.get(soil.get("reliability"), 0.5)
            st = soil["status"]
            w = 0.0
            if cause_id == "water_stress":
                w = {"very_dry": 2, "dry": 1.5, "adequate": -1.5, "wet": -2, "very_wet": -2}.get(st, 0)
            elif cause_id == "waterlogging":
                w = {"very_wet": 2, "wet": 0.5, "adequate": -1, "dry": -2, "very_dry": -2}.get(st, 0)
            if w:
                total += w * k
                ev.append({"text": f"Terreno: {soil['status_label']} ({soil['value']:.1f}%, affidabilità {soil['reliability']})",
                           "effect": "supports" if w > 0 else "weakens", "strength": "media" if k >= 1 else "debole",
                           "origin": "sensore", "weight": round(w * k, 2)})
            elif cause_id == "blossom_end_rot":
                ev.append({"text": "Una sola lettura del terreno non dice se l'irrigazione è stata irregolare",
                           "effect": "neutral", "strength": "nessuna", "origin": "sensore", "weight": 0})
    rh, src = ctx.get("air_humidity"), (ctx.get("sources") or {}).get("air_humidity")
    if rh is not None and cause_id in ("late_blight", "downy_mildew", "grey_mould", "fungal_leaf_spot") and src != "simulation":
        if rh >= 85:
            total += 0.5
            ev.append({"text": f"Umidità dell'aria alta ora ({rh:.0f}%)", "effect": "supports", "strength": "debole",
                       "origin": "sensore", "weight": 0.5})
    return total, ev


def _model_evidence(cid: str, model: dict | None) -> tuple[float, list[dict]]:
    """Evidence from AGROAI's image model trained on public datasets, weighted by its measured accuracy
    on real photos. Not used when the model does not know this crop or organ."""
    if not model or not model.get("applicable"):
        return 0.0, []
    mass = model["by_cause"].get(cid)
    if mass is None:
        return 0.0, []
    acc = model.get("cause_accuracy") or model.get("real_photo_accuracy") or 0.5
    best = next((t for t in model["top"] if t["cause"] == cid), None)
    name = best["name"] if best else cid
    known = set(model.get("known_causes") or [])
    # On fruit, the usual look-alikes (late blight, blossom-end rot, sunscald...) may be missing from the model:
    # a closed-set model then picks the most similar disease it knows, so its "yes" is only a weak hint.
    unknown_alikes = [c for c in FRUIT_DIFFERENTIAL if c not in known] if "fruit" in (model.get("organs_used") or []) else []
    if mass >= 0.5:
        w = 3.0 * acc * mass
        text = f"Il modello addestrato sui dataset riconosce «{name}» ({mass:.0%})"
        if unknown_alikes:
            w = min(w, 0.8)
            text += ", ma sui frutti non conosce ancora malattie simili (es. " +                 ", ".join(CAUSES[c]["name"].split(" (")[0].lower() for c in unknown_alikes[:2]) + ")"
        return w, [{"text": text, "effect": "supports",
                    "strength": "media" if w >= 1.5 else "debole", "origin": "modello addestrato", "weight": round(w, 2)}]
    if mass >= 0.2:
        w = 1.0 * acc * mass
        return w, [{"text": f"Il modello addestrato vede qualche somiglianza con «{name}» ({mass:.0%})",
                    "effect": "supports", "strength": "debole", "origin": "modello addestrato", "weight": round(w, 2)}]
    confident = max((t["score"] for t in model.get("top", [])), default=0) >= 0.5
    # only a confident model, trained to recognise this cause on these organs, can speak against it
    if mass < 0.05 and confident and (not known or cid in known):
        w = -0.8 * acc
        return w, [{"text": f"Il modello addestrato non riconosce questa causa ({mass:.0%})", "effect": "weakens",
                    "strength": "debole", "origin": "modello addestrato", "weight": round(w, 2)}]
    return 0.0, []


def diagnose(ai: dict | None, colour_fallback: list[dict], soil: dict | None, ctx: dict,
             answers: dict | None = None, model: dict | None = None) -> dict:
    observations = (ai or {}).get("observations") or {}
    obs = merge_observations(observations, answers)
    organs = {o for o in (observations.get("organs") or []) if o in ORGANS}
    if (answers or {}).get("leaves") == "affected":
        organs |= {"leaf"}
    proposed = {c["id"]: c for c in ((ai or {}).get("causes") or [])}
    if not proposed:
        proposed = {c["id"]: c for c in colour_fallback}

    candidates = set(proposed)
    fruit_lesions = "fruit" in organs or any(f in obs for f in ("fruit_location",))
    if fruit_lesions:
        candidates |= set(FRUIT_DIFFERENTIAL)
    for cid in PROFILES:  # the engine can add a cause the model missed if the symptoms fit strongly
        score, _ = _evidence(cid, obs, organs)
        if score >= 2.5:
            candidates.add(cid)
    by_model: set[str] = set()
    model_alts: set[str] = set()
    if model and model.get("applicable"):  # ...or if the trained image model is fairly sure
        by_model = {cid for cid, m in model["by_cause"].items() if m >= 0.5 and cid in CAUSES}
        # the model's runner-up alternatives are compared too, so questions can tell them apart
        model_alts = {cid for cid, m in model["by_cause"].items() if m >= 0.1 and cid in CAUSES}
        candidates |= by_model | model_alts
    if any(o == "answer" for _, o in obs.values()):
        cap = CAP_ANSWERS
    else:
        cap = CAP_PHOTO

    results = []
    for cid in candidates:
        if cid not in CAUSES:
            continue
        p0 = (PRIOR.get(proposed[cid]["likelihood"], 0.2) if cid in proposed
              else PRIOR_MODEL if cid in by_model else PRIOR_ENGINE)
        s_obs, ev = _evidence(cid, obs, organs)
        s_sen, ev_s = _sensor_evidence(cid, soil, ctx)
        s_mod, ev_m = _model_evidence(cid, model)
        s_sen += s_mod
        ev_s = ev_s + ev_m
        if cid == "healthy" and obs:
            lesion_feats = {"fruit_location", "texture", "shape", "mould"}
            if lesion_feats & set(obs):
                s_obs -= 3
                ev.append({"text": "Ci sono lesioni o macchie visibili", "effect": "weakens", "strength": "forte",
                           "origin": "foto", "weight": -3})
        p = _sigmoid(_logit(p0) + SLOPE * (s_obs + s_sen))
        p = max(0.02, min(cap, p))
        # "probable" means the symptoms fit well: a clear contradiction keeps a cause at most "possible"
        if any(e["effect"] == "weakens" and e["strength"] in ("forte", "media") for e in ev + ev_s):
            p = min(p, 0.59)
        results.append({"id": cid, "probability": round(p, 2), "tier": tier(p),
                        "model_view": proposed[cid]["why"] if cid in proposed else None,
                        "model_likelihood": proposed[cid]["likelihood"] if cid in proposed else None,
                        "evidence": ev + ev_s})
    results.sort(key=lambda r: -r["probability"])

    keep = [r for r in results if r["tier"] != "unlikely"]
    # unlikely causes stay visible when the model proposed them, when a decisive sign rules them out, or when
    # they belong to the usual look-alikes for fruit lesions (so the farmer sees why they were excluded)
    unlikely = [r for r in results if r["tier"] == "unlikely"
                and (r["id"] in proposed or r["id"] in by_model or r["id"] in model_alts
                     or any(e["strength"] == "forte" for e in r["evidence"])
                     or (fruit_lesions and r["id"] in FRUIT_DIFFERENTIAL[:4]))]
    unlikely.sort(key=lambda r: (r["id"] not in proposed and r["id"] not in by_model, -len(r["evidence"])))
    shown = keep[:5] + unlikely[:3]
    return {"causes": shown, "observations": {k: {"value": v, "origin": o, "label": FEATURES[k][v]}
                                              for k, (v, o) in obs.items()},
            "organs": sorted(organs), "questions": questions(results, obs, answers or {}, fruit_lesions),
            "cap": cap}


def questions(results: list[dict], obs: dict, answers: dict, fruit: bool, limit: int = 4) -> list[dict]:
    """Ask what would most change the ranking among the leading causes."""
    top = [r for r in results if r["probability"] >= 0.1][:5]
    if len(top) < 2:
        return []
    gap = top[0]["probability"] - top[1]["probability"]
    scored = []
    for q, spec in QUESTIONS.items():
        feats = QUESTION_FEATURE.get(q, (q,))
        if q in answers:
            continue
        if q in ("fruit_location", "sun_exposed") and not fruit:
            continue
        # mould grows under the leaf and texture must be touched: a photo cannot rule them out
        seen_in_photo = any(f in obs and obs[f][1] == "photo" for f in feats) and q not in PHOTO_UNRELIABLE
        if seen_in_photo and gap >= 0.25:
            continue  # the photo already answers it and the ranking is clear
        power = 0.0
        for value, _ in spec["options"]:
            ws = [PROFILES.get(r["id"], {}).get(feats[0], {}).get(value, 0.0) for r in top]
            power += (max(ws) - min(ws)) * (0.5 if seen_in_photo else 1)
        if power >= 2:
            scored.append((power, q))
    scored.sort(reverse=True)
    return [{"id": q, "text": QUESTIONS[q]["text"],
             "options": [{"value": v, "label": label} for v, label in QUESTIONS[q]["options"]]}
            for _, q in scored[:limit]]
