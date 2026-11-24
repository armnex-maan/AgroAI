"""Integrated systems ("ecosistemi") a farmer can build around the rotation: fish with vegetables,
fish in rice, wildlife ponds, hedges and flower strips, animals after harvest.

Every figure comes from a document that was read (FAO 2014 aquaponics manual, FAO 2004 rice-fish,
Freshwater Habitats Trust pond toolkit, EU pollinators page, FAO 10 elements of agroecology).
Nothing here is a legal obligation: suggestions are "buona_pratica"; where animals are kept, the farmer
is told to check registration with the local veterinary service (EU Animal Health Law)."""
from __future__ import annotations

SOURCES = {
    "fao_aquaponics": {"title": "FAO (2014) – Small-scale aquaponic food production. Fisheries and Aquaculture "
                                "Technical Paper 589", "year": 2014,
                       "url": "https://openknowledge.fao.org/handle/20.500.14283/i4021e"},
    "fao_ricefish": {"title": "FAO, WorldFish (2004) – Culture of fish in rice fields", "year": 2004,
                     "url": "https://openknowledge.fao.org/handle/20.500.14283/a0823e"},
    "fht_ponds": {"title": "Freshwater Habitats Trust – Pond Creation Toolkit (Million Ponds Project)", "year": 2011,
                  "url": "https://freshwaterhabitats.org.uk/advice-resources/pond-creation-hub/pond-creation-toolkit/"},
    "eu_pollinators": {"title": "Commissione europea – Impollinatori (EU Pollinators Initiative)", "year": None,
                       "url": "https://environment.ec.europa.eu/topics/nature-and-biodiversity/pollinators_en"},
    "fao_10el": {"title": "FAO (2018) – The 10 elements of agroecology", "year": 2018,
                 "url": "https://openknowledge.fao.org/handle/20.500.14283/i9037en"},
    "eu_ahl": {"title": "Regolamento (UE) 2016/429 – Normativa in materia di sanità animale", "year": 2016,
               "url": "https://eur-lex.europa.eu/eli/reg/2016/429/oj"},
}

VET_CHECK = ("Prima di tenere animali (pesci, galline, anatre) chiedi al servizio veterinario della tua ASL: la "
             "normativa europea sulla sanità animale prevede la registrazione degli allevamenti, con alcune eccezioni.")

# fish for aquaponics, FAO 2014 chapter 7.4 (temperatures as written there)
FISH = [
    {"key": "carp", "name": "Carpa", "temp": "sopravvive da 4 a 34 °C, cresce meglio tra 25 e 30 °C",
     "fit": "La più adatta al clima italiano: resiste al freddo invernale.", "source": "fao_aquaponics"},
    {"key": "trout", "name": "Trota", "temp": "10–18 °C, ottimo 15 °C; sopra 21 °C cresce male",
     "fit": "Adatta all'inverno o a zone fresche; d'estate serve acqua fredda.", "source": "fao_aquaponics"},
    {"key": "tilapia", "name": "Tilapia", "temp": "non mangia e non cresce sotto 17 °C",
     "fit": "Solo in serra o con acqua riscaldata in inverno. Specie esotica: mai in acque libere.",
     "source": "fao_aquaponics"},
]

ECOSYSTEMS = [
    {
        "key": "aquaponics", "icon": "fish", "title": "Pesci + ortaggi (acquaponica)",
        "summary": "Le deiezioni dei pesci nutrono gli ortaggi; le piante puliscono l'acqua che torna ai pesci.",
        "pairs": ["Pesci: carpa (la più adatta da noi), trota d'inverno, tilapia solo in serra riscaldata",
                  "Piante più facili: insalate, erbe aromatiche (basilico, prezzemolo), bietola",
                  "Piante da frutto (pomodoro, peperone) solo con impianto ben avviato"],
        "where": "Vicino a casa o in serra: servono corrente per la pompa e un posto riparato.",
        "needs": {"water": ["plenty", "limited"]},
        "benefits": ["Ortaggi e pesce dallo stesso impianto", "Pochissima acqua: si ricircola"],
        "cautions": ["Non superare 20 kg di pesce ogni 1000 litri d'acqua.",
                     "I pesci mangiano l'1–2% del loro peso al giorno: il mangime decide quante piante puoi nutrire.",
                     VET_CHECK],
        "sources": ["fao_aquaponics", "eu_ahl"], "calculator": True,
    },
    {
        "key": "rice_fish", "icon": "grain", "title": "Pesci in risaia",
        "summary": "Nella risaia allagata i pesci mangiano erbe e insetti e concimano l'acqua.",
        "pairs": ["Pesce più usato: carpa comune", "Anatre in risaia: mangiano anche le chiocciole"],
        "where": "Solo in risaie a sommersione, con argini più alti e un fosso più profondo come rifugio per i pesci.",
        "needs": {},
        "only_if": "Solo se coltivi riso in sommersione.",
        "benefits": ["Meno erbe infestanti e insetti", "Un secondo raccolto (il pesce)"],
        "cautions": ["Si usano pochissimi antiparassitari: molti sono tossici per i pesci.",
                     "Servono argini di 40–50 cm e un rifugio (fosso o buca) dove i pesci restano quando l'acqua cala.",
                     VET_CHECK],
        "sources": ["fao_ricefish", "eu_ahl"],
    },
    {
        "key": "pond", "icon": "drop", "title": "Stagno per la fauna utile",
        "summary": "Un piccolo stagno di acqua pulita attira rane, rospi, libellule e uccelli che mangiano parassiti.",
        "pairs": ["Rospi e rane: mangiano lumache e insetti", "Libellule: mangiano zanzare",
                  "NON mettere pesci: mangiano uova e girini e intorbidano l'acqua"],
        "where": "Nella zona più bassa o non coltivabile, lontano da scoli di campi concimati.",
        "needs": {},
        "benefits": ["Meno lumache e insetti dannosi", "Più biodiversità senza costi di gestione"],
        "cautions": ["Usa acqua pulita (piovana o di falda), mai acqua di scolo dei campi.",
                     "Sponde molto dolci: la parte più ricca di vita è quella bassa.",
                     "Non aggiungere piante, pesci o animali: lo stagno si popola da solo.",
                     "Il livello cala di 30–80 cm tra primavera e autunno: prevedilo nello scavo."],
        "sources": ["fht_ponds"],
    },
    {
        "key": "hedges", "icon": "leaf", "title": "Siepi e fasce fiorite",
        "summary": "Strisce di fiori e siepi lungo i bordi danno cibo e rifugio a api e insetti utili.",
        "pairs": ["Utili soprattutto per colture che hanno bisogno degli insetti: zucchino, zucca, melone, "
                  "anguria, cetriolo, fragola"],
        "where": "Lungo i bordi, gli accessi e i sentieri dell'appezzamento: non tolgono spazio alle aiuole.",
        "needs": {},
        "benefits": ["Più impollinazione", "Rifugio per insetti che mangiano i parassiti", "Riparo dal vento"],
        "cautions": ["Usa specie locali.", "Non trattare con insetticidi durante la fioritura."],
        "sources": ["eu_pollinators", "fao_10el"],
        "pollinated": ["zucchini", "pumpkin", "melon", "watermelon", "cucumber", "strawberry"],
    },
    {
        "key": "animals", "icon": "paw", "title": "Galline o anatre dopo il raccolto",
        "summary": "Dopo il raccolto gli animali mangiano residui, insetti e semi di infestanti e lasciano concime.",
        "pairs": ["Galline: dopo ortaggi e cereali", "Anatre: utili contro le lumache"],
        "where": "Nelle aiuole appena raccolte, con un recinto spostabile; poi tocca alla coltura successiva.",
        "needs": {},
        "benefits": ["Meno lavoro di pulizia", "Concime direttamente sul terreno", "Uova o carne"],
        "cautions": ["Tieni gli animali lontani dagli ortaggi da mangiare crudi che stai per raccogliere.",
                     VET_CHECK],
        "sources": ["fao_10el", "eu_ahl"],
    },
]


def _src(keys: list[str]) -> list[dict]:
    return [{"id": k, **SOURCES[k]} for k in keys]


def suggest(conditions: dict, crops: set[str], area_m2: float | None) -> list[dict]:
    """Ecosystems ranked for one plot. conditions: plot answers (water, irrigation...), crops: crop keys
    grown or planned there. Never hides an option: it explains why it fits or not."""
    out = []
    for e in ECOSYSTEMS:
        fit, why = True, []
        for k, allowed in e["needs"].items():
            v = conditions.get(k)
            if v is None:
                why.append("Non sappiamo ancora com'è l'acqua di questo appezzamento: rispondi al questionario.")
            elif v not in allowed:
                fit = False
                why.append("Serve acqua disponibile, e hai indicato che ne hai poca o niente.")
        if e["key"] == "rice_fish":
            fit = False  # rice is not in the rotation crop list yet: shown only as information
            why.append(e["only_if"])
        if e["key"] == "hedges":
            hit = sorted(c for c in crops if c in e["pollinated"])
            if hit:
                why.append("Coltivi colture che hanno bisogno degli impollinatori: qui una fascia fiorita aiuta subito.")
        if e["key"] == "pond" and area_m2 is not None and area_m2 < 50:
            why.append("Appezzamento piccolo: basta una vasca interrata di 1–2 m².")
        if e["key"] == "animals" and conditions.get("manure") == "no":
            why.append("Non usi letame: gli animali portano concime organico senza trasportarlo.")
        out.append({k: v for k, v in e.items() if k not in ("needs", "pollinated", "only_if")} |
                   {"fit": fit, "why": why, "sources": _src(e["sources"]), "level": "buona_pratica"})
    out.sort(key=lambda x: (not x["fit"], x["key"] != "hedges"))
    return out


def aquaponics(bed_m2: float, fruiting: bool = False) -> dict:
    """FAO 2014 sizing: feed rate ratio 40–50 g/m²/day (leafy) or 50–80 (fruiting); fish eat 1–2% of their
    weight per day; at most 20 kg of fish per 1000 L."""
    lo, hi = (50, 80) if fruiting else (40, 50)
    feed = (bed_m2 * lo, bed_m2 * hi)
    fish = (feed[0] / 0.02 / 1000, feed[1] / 0.01 / 1000)  # kg of fish
    water = fish[1] / 20 * 1000                              # litres needed for the largest stock
    return {"bed_m2": bed_m2, "kind": "fruiting" if fruiting else "leafy",
            "feed_g_day": [round(feed[0]), round(feed[1])],
            "fish_kg": [round(fish[0], 1), round(fish[1], 1)],
            "water_l_min": round(water, -1),
            "fish": FISH, "source": {"id": "fao_aquaponics", **SOURCES["fao_aquaponics"]},
            "note": "Valori guida FAO per piccoli impianti: si regolano osservando pesci e piante."}
