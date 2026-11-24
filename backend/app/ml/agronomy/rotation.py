"""Crop rotation advice (Italian).

Return intervals and forbidden successions come from the Emilia-Romagna integrated-production rules
(Disciplinari di Produzione Integrata 2023, Norme generali, Allegato 1): they are the binding minimum for
farms in that scheme and a good reference elsewhere in Italy. Nutrient demand, crop groups and the extra
waiting time after soil-borne diseases are common agronomic practice and are shown as advice, not law.
"""
from __future__ import annotations

from dataclasses import dataclass, field

SRC = {
    "er_dpi": {"title": "Regione Emilia-Romagna – Disciplinari di Produzione Integrata 2023, Norme generali, "
                        "Allegato 1 «Norme di avvicendamento specifiche di coltura»",
               "url": "https://agricoltura.regione.emilia-romagna.it/produzioni-agroalimentari/temi/bio-agro-climambiente/"
                      "agricoltura-integrata/Collezione-dpi/dpi_2023/norme/norme_generali-2023.pdf"},
    "piemonte": {"title": "Regione Piemonte – Norme generali di produzione integrata: avvicendamento quinquennale "
                          "con almeno 3 colture e al massimo un ristoppio",
                 "url": "https://www.regione.piemonte.it/web/sites/default/files/media/documenti/2020-06/NG%20pratiche%20agronomiche.pdf"},
    "gaec7": {"title": "Reg. (UE) 2024/1468 – BCAA 7: rotazione delle colture nei seminativi (PAC)",
              "url": "https://eur-lex.europa.eu/eli/reg/2024/1468/oj"},
    "fao_ca": {"title": "FAO – Agricoltura conservativa: rotazioni e colture di copertura",
               "url": "https://www.fao.org/conservation-agriculture/en/"},
}

FAMILIES = {
    "solanacee": "Solanacee (pomodoro, patata, melanzana, peperone)",
    "cucurbitacee": "Cucurbitacee (zucchino, melone, anguria, cetriolo, zucca)",
    "crucifere": "Crucifere (cavoli, broccolo, rapa, ravanello, rucola, colza)",
    "leguminose": "Leguminose (fagiolo, pisello, fava, cece, soia, erba medica)",
    "liliacee": "Liliacee (cipolla, aglio, porro, scalogno, asparago)",
    "ombrellifere": "Ombrellifere (carota, finocchio, sedano, prezzemolo)",
    "composite": "Composite (lattuga, cicoria, radicchio, girasole, carciofo)",
    "chenopodiacee": "Chenopodiacee (bietola, spinacio, barbabietola)",
    "graminacee": "Cereali (frumento, orzo, mais, sorgo, riso)",
    "rosacee": "Rosacee (fragola)",
    "lamiacee": "Lamiacee (basilico)",
}
GROUPS = {"frutto": "da frutto", "foglia": "da foglia", "radice": "da radice o bulbo", "legume": "legumi",
          "cereale": "cereali"}


@dataclass(frozen=True)
class RCrop:
    key: str
    name: str
    family: str
    gap: int                      # years of OTHER crops required before it returns (Emilia-Romagna DPI 2023)
    demand: str                   # alta | media | bassa | miglioratrice (nitrogen and soil demand)
    group: str                    # frutto | foglia | radice | legume | cereale
    season: str = "estate"        # estate | inverno | tutto l'anno | pluriennale
    one_repeat: bool = False      # the same crop may follow itself once in five years ("ristoppio")
    not_next_to: tuple[str, ...] = ()   # crops that must not precede or follow it
    not_after: tuple[str, ...] = ()     # crops that must not precede it
    family_free_neighbours: bool = True  # previous / next crop must not be of the same family
    note: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)


CROPS: list[RCrop] = [
    # ---------- ortaggi da frutto
    RCrop("tomato", "Pomodoro", "solanacee", 2, "alta", "frutto", one_repeat=True, aliases=("pomodor",),
          note="In pieno campo è ammesso un solo ristoppio in 5 anni, poi 2 anni senza solanacee."),
    RCrop("potato", "Patata", "solanacee", 2, "alta", "radice", aliases=("patat",)),
    RCrop("eggplant", "Melanzana", "solanacee", 2, "alta", "frutto", aliases=("melanzan",),
          note="Con piante innestate l'intervallo scende a 1 anno."),
    RCrop("pepper", "Peperone", "solanacee", 2, "alta", "frutto", aliases=("peperon",),
          note="Con piante innestate l'intervallo scende a 1 anno."),
    RCrop("zucchini", "Zucchino", "cucurbitacee", 1, "alta", "frutto", aliases=("zucchin",)),
    RCrop("cucumber", "Cetriolo", "cucurbitacee", 2, "alta", "frutto", aliases=("cetriol",)),
    RCrop("melon", "Melone", "cucurbitacee", 2, "alta", "frutto", aliases=("melon",),
          note="Con piante innestate o varietà resistenti a Fusarium le regole sono più flessibili."),
    RCrop("watermelon", "Anguria", "cucurbitacee", 2, "alta", "frutto", aliases=("anguri", "cocomer")),
    RCrop("pumpkin", "Zucca", "cucurbitacee", 2, "alta", "frutto", aliases=("zucca",)),
    RCrop("strawberry", "Fragola", "rosacee", 2, "media", "frutto", aliases=("fragol",)),
    # ---------- ortaggi da foglia
    RCrop("cabbage", "Cavoli (cavolfiore, broccolo, verza, cappuccio)", "crucifere", 2, "alta", "foglia",
          aliases=("cavol", "broccol", "verza", "cappuccio", "cime di rapa")),
    RCrop("rocket", "Rucola", "crucifere", 0, "bassa", "foglia", season="tutto l'anno", aliases=("rucol",),
          note="Più cicli nello stesso anno contano come un anno; tra due cicli bastano 60 giorni o un'altra famiglia."),
    RCrop("lettuce", "Lattuga", "composite", 1, "bassa", "foglia", season="tutto l'anno", aliases=("lattug", "insalat")),
    RCrop("chicory", "Cicoria e radicchio", "composite", 1, "media", "foglia", aliases=("cicori", "radicchi", "indivi")),
    RCrop("spinach", "Spinacio", "chenopodiacee", 1, "media", "foglia", season="inverno", aliases=("spinac",)),
    RCrop("chard", "Bietola da costa o da foglia", "chenopodiacee", 1, "media", "foglia", aliases=("bietol", "coste")),
    RCrop("basil", "Basilico", "lamiacee", 1, "media", "foglia", aliases=("basilic",)),
    RCrop("celery", "Sedano", "ombrellifere", 1, "alta", "foglia", aliases=("sedan",)),
    RCrop("parsley", "Prezzemolo", "ombrellifere", 2, "media", "foglia", aliases=("prezzemol",)),
    RCrop("fennel", "Finocchio", "ombrellifere", 1, "media", "radice", aliases=("finocchi",)),
    # ---------- radici e bulbi
    RCrop("carrot", "Carota", "ombrellifere", 3, "media", "radice", aliases=("carot",),
          note="L'intervallo può scendere a 2 anni se l'analisi del terreno esclude i nematodi."),
    RCrop("radish", "Ravanello", "crucifere", 1, "bassa", "radice", aliases=("ravanell",)),
    RCrop("turnip", "Rapa", "crucifere", 2, "media", "radice", aliases=("rapa", "rape")),
    RCrop("onion", "Cipolla", "liliacee", 1, "media", "radice", aliases=("cipoll",)),
    RCrop("garlic", "Aglio", "liliacee", 3, "bassa", "radice", season="inverno", aliases=("aglio",)),
    RCrop("leek", "Porro", "liliacee", 1, "alta", "radice", aliases=("porr",)),
    RCrop("shallot", "Scalogno", "liliacee", 5, "bassa", "radice", aliases=("scalogn",)),
    RCrop("asparagus", "Asparago", "liliacee", 5, "media", "radice", season="pluriennale", aliases=("asparag",),
          not_after=("potato", "alfalfa", "carrot", "sugar_beet"),
          note="Non dopo patata, erba medica, carota o barbabietola: rischio di mal vinato (Rhizoctonia)."),
    # ---------- legumi
    RCrop("bean", "Fagiolo", "leguminose", 1, "miglioratrice", "legume", aliases=("fagiol",),
          not_next_to=("rapeseed", "soybean", "sunflower"),
          note="Sensibile a Sclerotinia come colza, soia e girasole: non metterli prima o dopo."),
    RCrop("green_bean", "Fagiolino", "leguminose", 1, "miglioratrice", "legume", aliases=("fagiolin",)),
    RCrop("pea", "Pisello", "leguminose", 1, "miglioratrice", "legume", season="inverno", aliases=("pisell",)),
    RCrop("faba", "Fava e favino", "leguminose", 1, "miglioratrice", "legume", season="inverno", aliases=("fava", "favin")),
    RCrop("chickpea", "Cece", "leguminose", 1, "miglioratrice", "legume", season="inverno", aliases=("cece", "ceci")),
    RCrop("soybean", "Soia", "leguminose", 1, "miglioratrice", "legume", aliases=("soia",),
          not_next_to=("rapeseed", "sunflower", "bean")),
    RCrop("alfalfa", "Erba medica", "leguminose", 1, "miglioratrice", "legume", season="pluriennale",
          aliases=("erba medica", "medica"), note="Prima di un nuovo medicaio serve un anno senza leguminose."),
    # ---------- colture di pieno campo
    RCrop("wheat", "Frumento (tenero o duro)", "graminacee", 0, "media", "cereale", season="inverno", one_repeat=True,
          aliases=("frument", "grano", "farro"), family_free_neighbours=False,
          note="Il ristoppio (frumento dopo un altro cereale a paglia) è ammesso una sola volta in 5 anni; "
               "per il frumento duro non è ammesso."),
    RCrop("barley", "Orzo", "graminacee", 0, "media", "cereale", season="inverno", one_repeat=True,
          aliases=("orzo",), family_free_neighbours=False),
    RCrop("maize", "Mais", "graminacee", 0, "alta", "cereale", one_repeat=True, aliases=("mais", "granturco"),
          family_free_neighbours=False),
    RCrop("sorghum", "Sorgo", "graminacee", 0, "media", "cereale", one_repeat=True, aliases=("sorgo",),
          family_free_neighbours=False),
    RCrop("sunflower", "Girasole", "composite", 1, "media", "cereale", aliases=("girasol",),
          not_next_to=("rapeseed", "soybean", "bean")),
    RCrop("rapeseed", "Colza", "crucifere", 1, "media", "cereale", season="inverno", aliases=("colza",),
          not_next_to=("sugar_beet", "soybean", "bean", "sunflower")),
    RCrop("sugar_beet", "Barbabietola da zucchero", "chenopodiacee", 3, "media", "radice",
          aliases=("barbabietol",), not_next_to=("rapeseed",),
          note="Prima e dopo non vanno chenopodiacee né crucifere: condividono il nematode della bietola."),
]
BY_KEY = {c.key: c for c in CROPS}
REST = "rest"  # field left fallow / no crop

# soil-borne problems from the questions: families to keep away for longer, and what helps
PROBLEMS = {
    "wilt": {"label": "piante che appassiscono e muoiono", "avoid": {"solanacee": 4, "cucurbitacee": 4},
             "why": "funghi o batteri dei vasi (fusariosi, verticillosi, avvizzimento batterico) restano nel terreno per anni",
             "help": "usa piante innestate o varietà resistenti e inserisci cereali o crucifere."},
    "nematodes": {"label": "radici con palline o nodi", "avoid": {"solanacee": 3, "cucurbitacee": 3, "ombrellifere": 3,
                                                                   "composite": 2},
                  "why": "i nematodi galligeni attaccano molti ortaggi",
                  "help": "metti cereali o un sovescio biocida (senape o rafano), che riduce i nematodi."},
    "clubroot": {"label": "cavoli con radici gonfie e deformate", "avoid": {"crucifere": 5},
                 "why": "l'ernia del cavolo sopravvive molti anni nel terreno",
                 "help": "aspetta almeno 5 anni con le crucifere e correggi i terreni acidi con calce."},
    "white_rot": {"label": "cipolle o agli con muffa bianca alla base", "avoid": {"liliacee": 6},
                  "why": "il marciume bianco forma piccoli corpi neri che restano vivi nel terreno per molti anni",
                  "help": "tieni lontane cipolle, agli e porri il più a lungo possibile."},
    "root_rot": {"label": "radici o colletto marci", "avoid": {},
                 "why": "di solito c'entrano ristagni d'acqua e funghi del terreno",
                 "help": "migliora il drenaggio, evita di irrigare troppo e allunga la rotazione."},
}
SOIL_STATE = {
    "good": "fertile e soffice", "normal": "normale", "tired": "stanco: le piante crescono poco",
    "hard": "duro e compatto",
}


def find(name: str | None) -> RCrop | None:
    """Italian or English crop name -> crop (longest alias wins)."""
    if not name:
        return None
    n = name.strip().lower()
    if n in BY_KEY:
        return BY_KEY[n]
    hits = [(len(a), c) for c in CROPS for a in (c.aliases + (c.name.lower(),)) if a in n]
    return max(hits, key=lambda h: h[0])[1] if hits else None


def _season(entry) -> list[RCrop]:
    """A season can hold one crop key, several (list), or nothing (None / rest / unknown)."""
    if not entry:
        return []
    keys = entry if isinstance(entry, (list, tuple, set)) else [entry]
    return [BY_KEY[k] for k in keys if k in BY_KEY]


def _years_since(history: list, pred) -> int | None:
    """history[0] = last season, history[1] = the one before... -> how many seasons ago pred matched."""
    for i, entry in enumerate(history):
        if any(pred(c) for c in _season(entry)):
            return i  # 0 = last season
    return None


def short(c: RCrop) -> str:
    return c.name.split(" (")[0]


def _constraints(crop: RCrop, region: str | None) -> dict:
    """The rule that applies to `crop`: legacy (no region) = Emilia-Romagna values stored on the crop."""
    if region is None:
        return {"gap": crop.gap, "once": crop.one_repeat, "family_free": crop.family_free_neighbours,
                "not_after": set(crop.not_after), "not_next_to": set(crop.not_next_to), "advise_not_after": set(),
                "level": "disciplinare", "source": None, "label": ""}
    from app.ml.agronomy import rotation_rules as rr
    r, level = rr.rule_for(crop.key, region)
    d = rr.DOCS[r["doc"]]
    label = (f"{rr.REGIONS.get(d['region'], '')} {d['year']}" if level == "disciplinare"
             else f"riferimento Emilia-Romagna {d['year']}, non vincolante nella tua regione")
    return {"gap": r.get("gap", 0), "once": r.get("repeat") == "once", "family_free": bool(r.get("family_free")),
            "not_after": set(r.get("not_after", [])), "not_next_to": set(r.get("not_next_to", [])),
            "advise_not_after": set(r.get("advise_not_after", [])),
            "level": "disciplinare" if level == "disciplinare" else "buona_pratica", "source": rr.doc(r["doc"]),
            "label": label}


def judge(crop: RCrop, history: list, problems: set[str], soil: str | None,
          region: str | None = None, integrated: bool | None = None) -> dict:
    """Is `crop` a good choice for next season after `history`? Returns verdict, score and reasons.

    region=None keeps the original behaviour (Emilia-Romagna rules for everyone). With a region, only that
    region's documented rules are binding; other regions' values are shown as non-binding references.
    integrated=False (farm not in the integrated-production scheme) turns guideline breaches into warnings.
    Every reason carries its level: disciplinare | buona_pratica, and the source when there is one."""
    reasons: list[dict] = []
    score = 0.0
    blocked = False
    k = _constraints(crop, region)

    def add(effect: str, text: str, w: float, level: str = "buona_pratica", source: dict | None = None):
        nonlocal score
        score += w
        reasons.append({"effect": effect, "text": text, "rule": level in ("disciplinare", "obbligatoria"),
                        "level": level, "source": source})

    def breach(text: str, w: float):
        """A regional-guideline breach: blocking for farms in the scheme, a strong warning otherwise."""
        nonlocal blocked
        if k["level"] == "disciplinare" and integrated is not False:
            add("bad", text + (f" [{k['label']}]" if k["label"] else ""), w, "disciplinare", k["source"])
            blocked = True
        elif k["level"] == "disciplinare":
            add("warn", text + f" [{k['label']}: obbligatorio solo per chi aderisce alla produzione integrata]",
                w / 2, "disciplinare", k["source"])
        else:
            add("warn", text + f" [{k['label']}]", -1.5, "buona_pratica", k["source"])

    prevs = _season(history[0]) if history else []
    # 1) same crop too recently
    same = _years_since(history, lambda c: c.key == crop.key)
    if same is not None and same < k["gap"]:
        second = len(history) > 1 and any(c.key == crop.key for c in _season(history[1]))
        if k["once"] and same == 0 and not second:
            add("warn", f"{short(crop)} dopo {short(crop).lower()}: il ristoppio è ammesso una sola volta in 5 anni.",
                -1.5, k["level"], k["source"])
        else:
            wait = k["gap"] - same
            when = "l'anno scorso" if same == 0 else f"{same + 1} anni fa"
            breach(f"{short(crop)} c'era {when}: deve passare un intervallo di {k['gap']} "
                   f"{'anno' if k['gap'] == 1 else 'anni'} (ancora {wait} {'anno' if wait == 1 else 'anni'}).", -4)
    elif same == 0 and k["gap"] == 0 and k["once"]:
        add("warn", f"Ristoppio di {short(crop).lower()}: ammesso una sola volta in 5 anni.", -1, k["level"], k["source"])
    # 2) same family right before
    fam_prev = next((p for p in prevs if p.family == crop.family and p.key != crop.key), None)
    fam = _years_since(history, lambda c: c.family == crop.family and c.key != crop.key)
    if fam_prev and k["family_free"]:
        breach(f"Viene dopo {short(fam_prev).lower()}, della stessa famiglia ({crop.family}): stessi parassiti e "
               f"malattie del terreno.", -3)
    elif fam_prev and crop.family != "graminacee":
        add("warn", f"Viene dopo {short(fam_prev).lower()}, della stessa famiglia ({crop.family}): di solito è meglio "
                    f"cambiare famiglia.", -1.5, "buona_pratica", _fao())
    elif fam is not None and 0 < fam < max(k["gap"], 1):
        add("warn", f"La stessa famiglia ({crop.family}) c'era {fam + 1} anni fa: meglio aspettare ancora.", -1)
    # 3) forbidden or discouraged neighbours
    for p in prevs:
        other = _constraints(p, region)
        if p.key in k["not_next_to"] or crop.key in other["not_next_to"]:
            breach(f"Non va dopo {short(p).lower()}: condividono malattie o parassiti.", -3)
        if p.key in k["not_after"]:
            breach(f"Non va dopo {short(p).lower()}.", -3)
        if p.key in k["advise_not_after"]:
            add("warn", f"Sconsigliato dopo {short(p).lower()} [{k['label']}].", -1, "disciplinare", k["source"])
    # 4) soil-borne problems seen on the farm (advice)
    for pr in problems:
        spec = PROBLEMS.get(pr)
        if not spec:
            continue
        need = spec["avoid"].get(crop.family)
        if need:
            seen = _years_since(history, lambda c: c.family == crop.family)
            if seen is not None and seen < need:
                add("bad", f"Hai visto «{spec['label']}»: {spec['why']}. Tieni lontane le {crop.family} per "
                           f"almeno {need} anni.", -2.5)
                blocked = True
            elif seen is None:
                add("warn", f"Hai visto «{spec['label']}»: le {crop.family} sono sensibili. Se il problema era in "
                            f"questo campo, scegli varietà resistenti o piante innestate.", -1.5)
    # 5) nutrients and soil (advice)
    prev = prevs[0] if prevs else None
    if prev:
        if prev.demand == "miglioratrice" and crop.demand == "alta":
            add("good", f"Dopo {short(prev).lower()} (leguminosa) il terreno ha più azoto: ottimo per una coltura esigente.", 2)
        elif prev.demand == "alta" and crop.demand == "alta":
            add("warn", f"Due colture esigenti di fila ({short(prev).lower()} e {short(crop).lower()}): "
                        f"servirà più concime o compost.", -1)
        elif prev.demand == "alta" and crop.demand in ("miglioratrice", "bassa"):
            add("good", "Dopo una coltura esigente, una coltura leggera fa riposare il terreno.", 1)
        if prev.group == "cereale" and crop.group in ("frutto", "legume", "radice"):
            add("good", "Dopo un cereale si interrompe il ciclo di molti parassiti degli ortaggi.", 0.5)
        if prev.group != crop.group and prev.group != "cereale":
            add("good", f"Cambia tipo di coltura ({GROUPS[prev.group]} → {GROUPS[crop.group]}).", 0.5)
    if soil == "tired":
        if crop.demand == "miglioratrice":
            add("good", "Il terreno è stanco: una leguminosa lo arricchisce di azoto.", 1.5)
        elif crop.demand == "alta":
            add("warn", "Il terreno è stanco: una coltura esigente rischia di produrre poco.", -1)
    if soil == "hard" and crop.group == "radice":
        add("warn", "Il terreno è compatto: radici e tuberi crescono deformi.", -1)
    if not blocked and not any(r["effect"] in ("good", "bad", "warn") for r in reasons):
        add("good", "Nessun conflitto con le colture degli anni scorsi.", 0.5)
    verdict = "no" if blocked or score <= -3.5 else "care" if score < 0 else "ok"
    return {"key": crop.key, "name": crop.name, "family": crop.family, "verdict": verdict, "score": round(score, 1),
            "reasons": reasons, "note": crop.note, "demand": crop.demand, "group": crop.group}


def _fao() -> dict:
    return {"id": "fao_ca", "title": SRC["fao_ca"]["title"], "url": SRC["fao_ca"]["url"], "year": None,
            "type": "buona_pratica", "region": "—"}


def plan(history: list[str | None], wanted: list[str], problems: set[str], soil: str | None,
         years: int = 4, candidates: list[str] | None = None) -> list[dict]:
    """Greedy multi-year plan: each year the best allowed crop, preferring the farmer's wishes."""
    pool = [BY_KEY[k] for k in (candidates or BY_KEY) if k in BY_KEY]
    hist = list(history)
    out = []
    used_families: list[str] = []
    for y in range(years):
        best = None
        for c in pool:
            j = judge(c, hist, problems, soil if y == 0 else None)
            if j["verdict"] == "no":
                continue
            s = j["score"] + (3 if c.key in wanted and c.key not in [o["key"] for o in out] else 0)
            s -= 1.5 * used_families.count(c.family)  # spread families across the plan
            if c.season == "pluriennale":
                s -= 2  # perennials are a separate decision
            if c.demand == "miglioratrice" and "leguminose" not in used_families and y >= 1:
                s += 1.5  # a good plan includes a legume that gives nitrogen back to the soil
            if best is None or s > best[0]:
                best = (s, c, j)
        if best is None:
            out.append({"year": y + 1, "key": REST, "name": "Riposo o sovescio", "family": "",
                        "reasons": [{"effect": "warn", "text": "Nessuna coltura adatta: semina un sovescio.", "rule": False}]})
            hist.insert(0, None)
            continue
        _, c, j = best
        out.append({"year": y + 1, **j})
        used_families.append(c.family)
        hist.insert(0, c.key)
    return out


def cover_crop(next_crop: RCrop | None, problems: set[str], soil: str | None) -> dict:
    """What to sow in the gap before the next crop (sovescio / coltura di copertura)."""
    if "nematodes" in problems:
        return {"name": "Senape o rafano biocida", "why": "liberano sostanze che riducono i nematodi quando vengono interrati",
                "when": "fine estate–autunno, interrati a fioritura"}
    if next_crop and next_crop.demand == "alta" or soil == "tired":
        return {"name": "Favino, veccia e avena (miscuglio)", "why": "le leguminose fissano azoto, l'avena aggiunge sostanza organica",
                "when": "semina in autunno, interramento in primavera 3–4 settimane prima del trapianto"}
    if soil == "hard":
        return {"name": "Rafano o ravanello da foraggio", "why": "le radici a fittone rompono gli strati compatti",
                "when": "fine estate, lasciato gelare o trinciato in inverno"}
    return {"name": "Trifoglio o veccia", "why": "proteggono il terreno d'inverno e lasciano azoto",
            "when": "dopo il raccolto, interramento in primavera"}


def advise(history: list[str | None], wanted: list[str], problems: set[str], soil: str | None,
           manure: str | None = None, cover_ok: str | None = None) -> dict:
    next_options = [judge(c, history, problems, soil) for c in CROPS if c.season != "pluriennale"]
    next_options.sort(key=lambda j: -j["score"])
    wished = [judge(BY_KEY[k], history, problems, soil) for k in wanted if k in BY_KEY]
    best, fams = [], set()
    for j in next_options:  # one suggestion per family, so the list shows real alternatives
        if j["verdict"] == "ok" and j["family"] not in fams:
            best.append(j)
            fams.add(j["family"])
        if len(best) == 6:
            break
    p = plan(history, wanted, problems, soil)
    first = BY_KEY.get(p[0]["key"]) if p and p[0]["key"] != REST else None
    tips = []
    if manure == "no" or soil == "tired":
        tips.append("Porta sostanza organica: letame maturo o compost ogni 1–2 anni migliorano struttura e fertilità.")
    if soil == "hard":
        tips.append("Non lavorare il terreno quando è bagnato e prova colture o sovesci con radici profonde.")
    for pr in problems:
        if pr in PROBLEMS:
            tips.append(f"Per «{PROBLEMS[pr]['label']}»: {PROBLEMS[pr]['help']}")
    tips.append("Regola generale dei disciplinari: in 5 anni almeno 3 colture diverse e al massimo un ristoppio.")
    return {
        "wished": wished, "best_next": best, "plan": p,
        "cover_crop": cover_crop(first, problems, soil) if cover_ok != "no" else None,
        "tips": tips,
        "families": FAMILIES,
        "sources": [SRC["er_dpi"], SRC["piemonte"], SRC["fao_ca"], SRC["gaec7"]],
        "legal_note": "Gli intervalli sono quelli dei disciplinari di produzione integrata dell'Emilia-Romagna (2023): "
                      "obbligatori per chi aderisce, buona pratica per tutti. Se ricevi i contributi PAC, la rotazione "
                      "dei seminativi è richiesta anche dalla BCAA 7: verifica i dettagli con il tuo CAA.",
    }


def catalog() -> list[dict]:
    from app.ml.agronomy import crop_heights
    return [{"key": c.key, "name": c.name, "family": c.family, "group": c.group, "gap": c.gap, "season": c.season,
             "height_m": crop_heights.height(c.key)} for c in CROPS]


QUESTIONS = [
    {"id": "last", "type": "crop", "text": "Cosa hai coltivato in questo campo nell'ultima stagione?",
     "hint": "Se c'erano più colture, scegli quella principale."},
    {"id": "before", "type": "crop", "text": "E la stagione prima?", "hint": "Se non lo ricordi, salta."},
    {"id": "wanted", "type": "crops", "text": "Cosa vorresti coltivare la prossima stagione?",
     "hint": "Puoi sceglierne più di una, oppure lasciar scegliere ad AGROAI."},
    {"id": "problems", "type": "multi", "text": "Negli ultimi anni hai visto uno di questi problemi?",
     "options": [{"value": k, "label": v["label"]} for k, v in PROBLEMS.items()] + [{"value": "none", "label": "Nessuno"}]},
    {"id": "soil", "type": "single", "text": "Com'è il terreno di questo campo?",
     "options": [{"value": k, "label": v} for k, v in SOIL_STATE.items()]},
    {"id": "manure", "type": "single", "text": "Usi letame o compost?",
     "options": [{"value": "yes", "label": "Sì, ogni anno"}, {"value": "some", "label": "Ogni tanto"},
                 {"value": "no", "label": "No"}]},
    {"id": "cover", "type": "single", "text": "Puoi seminare qualcosa tra un raccolto e l'altro (sovescio)?",
     "options": [{"value": "yes", "label": "Sì"}, {"value": "maybe", "label": "Forse"}, {"value": "no", "label": "No"}]},
]
