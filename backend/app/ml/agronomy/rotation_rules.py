"""Crop-rotation rules by region, each with its source, year and type.

Rule types (always shown to the farmer, never mixed up):
  obbligatoria   – law for everyone in its scope (EU CAP conditionality, BCAA 7, for CAP beneficiaries)
  disciplinare   – regional integrated-production guidelines: binding only for farms that join the
                   scheme (PSR/CSR, SQNPI, OCM), good reference for everyone else
  buona_pratica  – common agronomic practice, or a value from ANOTHER region shown only as a reference
  suggerimento   – choices made by AGROAI's planner (ranking, area split): never a rule

Only documents actually read are encoded. A region without documents gets no regional rule: the
farmer sees good practice only, clearly labelled. Rules of one region are never applied to another.
"""
from __future__ import annotations

from app.ml.agronomy import rotation as base

DOCS: dict[str, dict] = {
    "er_2023": {"region": "emilia_romagna", "year": 2023, "type": "disciplinare",
                "title": "Emilia-Romagna – Disciplinari di Produzione Integrata 2023, Norme generali, Allegato 1",
                "url": base.SRC["er_dpi"]["url"]},
    "pie_2020_ng": {"region": "piemonte", "year": 2020, "type": "disciplinare",
                    "title": "Piemonte – Disciplinari di Produzione Integrata 2020, Norme generali, punto 7 (avvicendamento)",
                    "url": "https://www.regione.piemonte.it/web/sites/default/files/media/documenti/2020-06/NG%20pratiche%20agronomiche.pdf"},
    "pie_2020_schede": {"region": "piemonte", "year": 2020, "type": "disciplinare",
                        "title": "Piemonte – Disciplinari di Produzione Integrata 2020, schede di coltura",
                        "url": "https://www.regione.piemonte.it/web/sites/default/files/media/documenti/2020-06/PA%20schede%20di%20coltura.pdf"},
    "lazio_2020": {"region": "lazio", "year": 2020, "type": "disciplinare",
                   "title": "Lazio – Disciplinare di produzione integrata 2020, Allegato 1 (DD G01782 del 24/02/2020)",
                   "url": "https://regione.lazio.it/sites/default/files/documentazione/AGC_DD_G01782_24_02_2020_Allegato1.pdf"},
    "marche_2026": {"region": "marche", "year": 2026, "type": "disciplinare",
                    "title": "Marche – Disciplinare di produzione integrata, parte generale (Allegato A alla DGR 2026)",
                    "url": "https://meteo.regione.marche.it/assets/pi/doc/tecnicheagronomiche/parte-generale.pdf"},
    "marche_2026_pom": {"region": "marche", "year": 2026, "type": "disciplinare",
                        "title": "Marche – Disciplinare di produzione integrata, pomodoro da mensa (Allegato A alla DGR 2026)",
                        "url": "https://meteo.regione.marche.it/assets/pi/colture/ortive/pomodoro-da-mensa_tecniche.pdf"},
    "toscana_2007": {"region": "toscana", "year": 2007, "type": "disciplinare",
                     "title": "Toscana – Principi generali di produzione integrata, Allegato 2 (documento del 2007: "
                              "verifica la versione in vigore)",
                     "url": "https://www.regione.toscana.it/documents/10180/70126/Allegato_2_principi%20generali%20di%20produzione%20integrata"},
    "eu_gaec7": {"region": "*", "year": 2024, "type": "obbligatoria",
                 "title": "Reg. (UE) 2024/1468 che modifica il Reg. (UE) 2021/2115 – BCAA 7, rotazione nei seminativi",
                 "url": "https://eur-lex.europa.eu/eli/reg/2024/1468/oj"},
    "fao_ca": {"region": "*", "year": None, "type": "buona_pratica",
               "title": "FAO – Agricoltura conservativa: rotazioni e colture di copertura", "url": base.SRC["fao_ca"]["url"]},
}

REGIONS: dict[str, str] = {
    "abruzzo": "Abruzzo", "basilicata": "Basilicata", "calabria": "Calabria", "campania": "Campania",
    "emilia_romagna": "Emilia-Romagna", "friuli_venezia_giulia": "Friuli Venezia Giulia", "lazio": "Lazio",
    "liguria": "Liguria", "lombardia": "Lombardia", "marche": "Marche", "molise": "Molise", "piemonte": "Piemonte",
    "puglia": "Puglia", "sardegna": "Sardegna", "sicilia": "Sicilia", "toscana": "Toscana",
    "trentino_alto_adige": "Trentino-Alto Adige", "umbria": "Umbria", "valle_d_aosta": "Valle d'Aosta", "veneto": "Veneto",
}

# general five-year rule, as written in each regional document
GENERAL = {
    "emilia_romagna": ("er_2023", "In 5 anni almeno 3 colture principali diverse e al massimo un ristoppio per coltura."),
    "piemonte": ("pie_2020_ng", "Avvicendamento quinquennale con almeno 3 colture e al massimo un ristoppio per coltura "
                                "(vincolante solo per le aziende che aderiscono alla Produzione Integrata del PSR)."),
    "lazio": ("lazio_2020", "Avvicendamento quinquennale con almeno 3 colture e al massimo un ristoppio per coltura; "
                            "per le colture da seme il ristoppio non è ammesso."),
    "marche": ("marche_2026", "Avvicendamento quinquennale con almeno 3 colture principali e al massimo un ristoppio per coltura."),
    "toscana": ("toscana_2007", "Niente monosuccessioni; alternare colture con caratteristiche opposte (radici profonde e "
                                "superficiali, azotofissatrici e sfruttatrici, semine autunnali e primaverili)."),
}

# crop-specific rules read in the regional documents (Emilia-Romagna is built from rotation.CROPS)
# keys: gap = years of other crops before it returns; repeat = "once" (one ristoppio in 5 years) | "no";
# family_free = previous/next crop must not be of the same family; not_after / not_next_to = crop keys;
# advise_not_after = discouraged (not forbidden) previous crops
REGIONAL_CROP_RULES: dict[str, dict[str, dict]] = {
    "piemonte": {
        "garlic": {"doc": "pie_2020_schede", "gap": 2, "text": "Rotazione almeno triennale: torna dopo almeno due colture "
                   "annuali (oppure 2 cicli e poi 4 anni senza aglio). Sconsigliate in precessione liliacee e prato."},
        "asparagus": {"doc": "pie_2020_schede", "gap": 4, "not_after": ["potato", "alfalfa", "carrot", "sugar_beet"],
                      "text": "Non torna prima di 4 anni; non dopo patata, erba medica, carota e barbabietola (mal vinato)."},
        "onion": {"doc": "pie_2020_schede", "gap": 2, "text": "Rotazione almeno triennale: torna dopo 2 anni di altre colture."},
        "potato": {"doc": "pie_2020_schede", "gap": 2, "family_free": True,
                   "text": "Rotazione almeno triennale: torna dopo 2 anni; non può seguire un'altra solanacea."},
        "tomato": {"doc": "pie_2020_schede", "gap": 1, "repeat": "no", "family_free": True,
                   "text": "Ristoppio non consentito (oppure dopo 2 cicli almeno 3 anni senza pomodoro); non dopo altre solanacee."},
        "pumpkin": {"doc": "pie_2020_schede", "gap": 2, "family_free": True,
                    "text": "Torna dopo almeno 2 anni; prima e dopo niente cucurbitacee."},
        "zucchini": {"doc": "pie_2020_schede", "gap": 1, "repeat": "no", "family_free": True,
                     "not_after": ["tomato", "eggplant", "pepper", "bean"],
                     "text": "Ristoppio non consentito; torna dopo almeno un anno senza cucurbitacee; vietato dopo "
                             "pomodoro, melanzana, peperone e fagiolo."},
        "wheat": {"doc": "pie_2020_schede", "gap": 0, "repeat": "once",
                  "text": "Un solo ristoppio in 5 anni; i cereali autunno-vernini contano come la stessa coltura.",
                  "advise_not_after": ["sorghum"]},
        "barley": {"doc": "pie_2020_schede", "gap": 0, "repeat": "once",
                   "text": "Un solo ristoppio in 5 anni; i cereali autunno-vernini contano come la stessa coltura."},
        "maize": {"doc": "pie_2020_schede", "gap": 0, "repeat": "once",
                  "text": "Un solo ristoppio in 5 anni (importante anche contro la Diabrotica)."},
        "rapeseed": {"doc": "pie_2020_schede", "gap": 1, "repeat": "no", "not_after": ["sugar_beet"],
                     "advise_not_after": ["soybean", "bean", "sunflower"],
                     "text": "Ristoppio non ammesso; non dopo barbabietola (nematode); sconsigliato dopo soia, fagiolo, girasole."},
        "sunflower": {"doc": "pie_2020_schede", "gap": 1, "repeat": "no",
                      "advise_not_after": ["soybean", "bean", "rapeseed"],
                      "text": "Ristoppio non ammesso; sconsigliato dopo soia, fagiolo e colza (Sclerotinia)."},
    },
    "marche": {
        "tomato": {"doc": "marche_2026_pom", "gap": 2, "repeat": "once", "not_next_to": ["eggplant", "potato", "pepper"],
                   "text": "Un solo ristoppio in 5 anni, poi almeno 2 anni senza solanacee; con un solo ciclo, prima e "
                           "dopo non vanno melanzana, patata e peperone."},
    },
    "toscana": {
        "wheat": {"doc": "toscana_2007", "gap": 0, "repeat": "once", "text": "Cereali autunno-vernini: al massimo 2 annate di fila."},
        "barley": {"doc": "toscana_2007", "gap": 0, "repeat": "once", "text": "Cereali autunno-vernini: al massimo 2 annate di fila."},
        "maize": {"doc": "toscana_2007", "gap": 0, "repeat": "once", "text": "Mais: al massimo 2 annate di fila."},
        "sorghum": {"doc": "toscana_2007", "gap": 2, "text": "Sorgo: intervallo di due annate."},
    },
}


def er_rule(c: base.RCrop) -> dict:
    """Emilia-Romagna 2023 values already stored in rotation.CROPS, as a rule record."""
    return {"doc": "er_2023", "gap": c.gap, "repeat": "once" if c.one_repeat else ("no" if c.gap >= 1 else "allowed"),
            "family_free": c.family_free_neighbours, "not_after": list(c.not_after),
            "not_next_to": list(c.not_next_to),
            "text": f"Intervallo di {c.gap} {'anno' if c.gap == 1 else 'anni'} di altre colture" +
                    ("; ristoppio ammesso una sola volta in 5 anni" if c.one_repeat else "") +
                    ("; prima e dopo niente della stessa famiglia" if c.family_free_neighbours else "") +
                    (f". {c.note}" if c.note else ".")}


def rule_for(crop_key: str, region: str | None) -> tuple[dict | None, str]:
    """(rule, level). level = 'disciplinare' when the farm's region has a rule for this crop,
    'riferimento' when only another region's value exists (shown as non-binding good practice)."""
    c = base.BY_KEY[crop_key]
    if region == "emilia_romagna":
        return er_rule(c), "disciplinare"
    own = REGIONAL_CROP_RULES.get(region or "", {}).get(crop_key)
    if own:
        return own, "disciplinare"
    return er_rule(c), "riferimento"


def doc(doc_id: str) -> dict:
    d = DOCS[doc_id]
    return {"id": doc_id, "title": d["title"], "url": d["url"], "year": d["year"], "type": d["type"],
            "region": REGIONS.get(d["region"], "Tutta l'UE" if d["region"] == "*" else d["region"])}


def coverage(region: str | None) -> dict:
    """What AGROAI knows for this region: shown to the farmer before any advice."""
    if not region or region not in REGIONS:
        return {"region": None, "level": "none", "text": "Regione non indicata: valgono solo le buone pratiche agronomiche."}
    name = REGIONS[region]
    crops = 41 if region == "emilia_romagna" else len(REGIONAL_CROP_RULES.get(region, {}))
    gen = GENERAL.get(region)
    if region == "emilia_romagna" or crops:
        level, text = "crops", f"{name}: regola generale e intervalli per {crops} colture dal disciplinare regionale."
    elif gen:
        level, text = "general", (f"{name}: abbiamo solo la regola generale del disciplinare. Per gli intervalli delle "
                                  f"singole colture mostriamo i valori dell'Emilia-Romagna come riferimento NON vincolante.")
    else:
        level, text = "none", (f"{name}: non abbiamo ancora letto il disciplinare regionale. Mostriamo solo buone pratiche "
                               f"e, come riferimento non vincolante, i valori dell'Emilia-Romagna. Verifica il disciplinare "
                               f"di produzione integrata della tua Regione.")
    docs = sorted({d for d in [gen[0] if gen else None] + [r["doc"] for r in REGIONAL_CROP_RULES.get(region, {}).values()]
                   + (["er_2023"] if region == "emilia_romagna" else []) if d})
    return {"region": region, "name": name, "level": level, "text": text, "documents": [doc(d) for d in docs],
            "general_rule": {"text": gen[1], "source": doc(gen[0])} if gen else None}


def all_rules(region: str | None) -> list[dict]:
    """Flat list of every rule that applies (or is shown as reference) for a region, with its source."""
    out = [{"type": "obbligatoria", "region": "Tutta l'UE", "year": 2024, "crop": None,
            "text": "Per chi riceve i pagamenti PAC: sui seminativi la rotazione è richiesta dalla BCAA 7 (cambio di "
                    "coltura a livello di parcella, con le eccezioni e le alternative, come la diversificazione, previste "
                    "dal Piano strategico nazionale). Verifica i dettagli con il tuo CAA.",
            "interval": None, "source": doc("eu_gaec7")}]
    gen = GENERAL.get(region or "")
    if gen:
        out.append({"type": "disciplinare", "region": REGIONS[region], "year": DOCS[gen[0]]["year"], "crop": None,
                    "text": gen[1], "interval": None, "source": doc(gen[0])})
    for c in base.CROPS:
        r, level = rule_for(c.key, region)
        out.append({"type": "disciplinare" if level == "disciplinare" else "buona_pratica",
                    "region": REGIONS.get(DOCS[r["doc"]]["region"], ""), "year": DOCS[r["doc"]]["year"],
                    "crop": c.key, "crop_name": c.name, "family": c.family, "interval": r.get("gap"),
                    "text": r["text"] if level == "disciplinare" else f"Riferimento di un'altra regione: {r['text']}",
                    "source": doc(r["doc"])})
    return out
