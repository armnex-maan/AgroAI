"""Cost-reduction tips and integrated rice systems — rule-based, each with the
data that triggered it and the sources behind it. No invented yield or savings
figures: numbers appear only when they come from the cited source."""
from __future__ import annotations

from app.integrations.soilgrids import TEXTURE_GROUP, TEXTURE_IT

EU_COUNTRIES = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT",
                "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"}

SRC = {
    "fao56": {"title": "FAO – Evapotraspirazione delle colture (quaderno 56)",
              "url": "https://www.fao.org/4/x0490e/x0490e00.htm"},
    "fao_iwm3": {"title": "FAO – Gestione dell'irrigazione, manuale 3 (efficienza dei metodi irrigui)",
                 "url": "https://www.fao.org/4/s2022e/s2022e00.htm"},
    "fao_soc": {"title": "FAO (2017) – Il carbonio organico del suolo: il potenziale nascosto",
                "url": "https://www.fao.org/3/i6937e/i6937e.pdf"},
    "fao_ca": {"title": "FAO – Agricoltura conservativa",
               "url": "https://www.fao.org/conservation-agriculture/en/"},
    "fao_soils": {"title": "FAO – Portale suoli", "url": "https://www.fao.org/soils-portal/en/"},
    "irri_kb": {"title": "IRRI – Rice Knowledge Bank (gestione dell'acqua, AWD, ingegneria ecologica)",
                "url": "https://www.knowledgebank.irri.org/"},
    "elife2022": {"title": "eLife (2022) – Animali acquatici in risaia: più resa e azoto nel suolo",
                  "url": "https://elifesciences.org/articles/73869"},
    "crab_density": {"title": "FAO AGRIS – Densità ottimale del granchio cinese in risaia",
                     "url": "https://agris.fao.org/search/zh/records/65e0050a0f3e94b9e5de76d9"},
    "crab_snail": {"title": "MDPI Animals 15(1):85 (2025) – Granchi giovani contro la chiocciola Pomacea in risaia",
                   "url": "https://www.mdpi.com/2076-2615/15/1/85"},
    "eu_ias": {"title": "Regolamento di esecuzione (UE) 2016/1141 – elenco delle specie esotiche invasive",
               "url": "https://eur-lex.europa.eu/eli/reg_impl/2016/1141"},
    "ticino_ducks": {"title": "Parco del Ticino – Cascina Gambarina (riso biologico diserbato con le anatre)",
                     "url": "https://ente.parcoticino.it/wp-content/uploads/2023/03/Pannello_Cascina-Gambarina.pdf"},
    "polito_rice": {"title": "Politecnico di Torino – tesi su risaie con anatre, pesci e sistemi misti (Vercellese)",
                    "url": "https://webthesis.biblio.polito.it/18985/1/tesi.pdf"},
    "unimi_organic": {"title": "Università di Milano – ricerca sul riso biologico (progetto Risobiosystems)",
                      "url": "https://air.unimi.it/handle/2434/924462"},
    "slow_rice": {"title": "Rete Slow Rice – risicoltura agroecologica in Italia",
                  "url": "https://www.quotidiano.net/itinerari/news/rete-slow-rice-pmqtft2o"},
}


def _n(v: float) -> str:
    return f"{v:.0f}"


def cost_tips(climate: dict, soil: dict, ranked: list[dict], has_moisture_sensors: bool) -> list[dict]:
    tips: list[dict] = []
    summer = climate["seasons"]["summer"]
    deficit = summer["et0_mm"] - 0.8 * summer["precip_mm"]
    texture = soil.get("texture")
    group = TEXTURE_GROUP.get(texture or "", None)
    soc = soil.get("soc_g_kg")
    ph = soil.get("ph")

    if deficit > 150:
        tips.append({
            "id": "sensor_irrigation", "category": "water", "impact": "high",
            "title": "Irriga quando il terreno è secco, non a calendario",
            "why": f"D'estate le piante consumano circa {_n(summer['et0_mm'])} mm d'acqua, ma la pioggia utile è "
                   f"solo {_n(0.8 * summer['precip_mm'])} mm: mancano circa {_n(deficit)} mm.",
            "action": ("I sensori di umidità AGROAI sono già attivi: imposta una soglia per ogni coltura e irriga "
                       "solo quando il valore scende sotto." if has_moisture_sensors else
                       "Metti sonde di umidità (nodo ESP32) all'altezza delle radici in ogni zona e irriga solo "
                       "quando il valore scende sotto la soglia della coltura."),
            "sources": [SRC["fao56"]],
        })
    if deficit > 250 and group in ("light", "medium"):
        tips.append({
            "id": "drip", "category": "water", "impact": "high",
            "title": "Passa all'irrigazione a goccia per orticole e frutteti",
            "why": f"Grande deficit estivo (circa {_n(deficit)} mm) su terreno {TEXTURE_IT.get(texture, texture)}.",
            "action": "Secondo la FAO, dell'acqua pompata arriva alle piante circa il 60% con lo scorrimento, il 75% "
                      "con l'aspersione e il 90% con la goccia: a parità di raccolto si pompa meno acqua. "
                      "Confronta il costo dell'impianto con il prezzo di acqua ed energia.",
            "sources": [SRC["fao_iwm3"]],
        })
    if soc is not None and soc < 12:
        tips.append({
            "id": "organic_matter", "category": "soil", "impact": "medium",
            "title": "Aumenta la sostanza organica con cover crop, sovesci o letame",
            "why": f"Il carbonio organico stimato è di circa {soc:.1f} g/kg: piuttosto basso.".replace(".", ",", 1),
            "action": "Colture di copertura invernali (miscugli con leguminose) e residui interrati trattengono più "
                      "acqua e forniscono azoto: col tempo si compra meno concime.",
            "sources": [SRC["fao_soc"]],
        })
    legumes = [r["name"] for r in ranked if r["legume"] and r["score_irrigated"] >= 0.6]
    if legumes:
        tips.append({
            "id": "legume_rotation", "category": "fertilizer", "impact": "medium",
            "title": "Inserisci una leguminosa nella rotazione",
            "why": f"Leguminose adatte a questo terreno: {', '.join(legumes[:3])}.",
            "action": "Le leguminose prendono l'azoto dall'aria: il cereale che viene dopo ha bisogno di meno "
                      "concime azotato. Decidi la dose con un'analisi del terreno, non a occhio.",
            "sources": [SRC["fao_ca"]],
        })
    if ph is not None and ph < 5.5:
        tips.append({
            "id": "liming", "category": "fertilizer", "impact": "medium",
            "title": "Correggi l'acidità prima di aumentare i concimi",
            "why": f"Il pH del terreno è circa {ph:.1f}.".replace(".", ",", 1),
            "action": "Con pH basso molti nutrienti restano bloccati e parte del concime si spreca. Confermalo con "
                      "un'analisi di laboratorio e poi fai la calcitazione consigliata.",
            "sources": [SRC["fao_soils"]],
        })
    if ph is not None and ph > 8.0:
        tips.append({
            "id": "alkaline", "category": "fertilizer", "impact": "low",
            "title": "Scegli colture e concimi adatti al terreno alcalino",
            "why": f"Il pH del terreno è circa {ph:.1f}.".replace(".", ",", 1),
            "action": "Preferisci colture tolleranti (orzo, frumento duro, barbabietola, olivo) e osserva se compaiono "
                      "carenze di ferro o zinco: un concime fogliare costa meno che correggere il terreno.",
            "sources": [SRC["fao_soils"]],
        })
    if group == "heavy":
        tips.append({
            "id": "reduced_tillage", "category": "energy", "impact": "medium",
            "title": "Riduci le lavorazioni sul terreno pesante",
            "why": f"Terreno {TEXTURE_IT.get(texture, texture)}: arare un terreno pesante è il lavoro che consuma più gasolio.",
            "action": "Minima lavorazione o semina su sodo con il terreno sempre coperto riducono gasolio e ore di "
                      "lavoro; programma il passaggio in più stagioni (gestione di infestanti e residui).",
            "sources": [SRC["fao_ca"]],
        })
    tips.append({
        "id": "soil_test", "category": "fertilizer", "impact": "high",
        "title": "Concima in base a un'analisi del terreno",
        "why": "I valori del terreno mostrati qui sono stimati da una mappa a 250 m, non misurati nel tuo campo.",
        "action": "Un'analisi di laboratorio per ogni zona omogenea (pH, sostanza organica, N, P, K, tessitura) "
                  "evita di concimare troppo; AGROAI userà i tuoi valori al posto della stima.",
        "sources": [SRC["fao_soils"]],
    })
    tips.append({
        "id": "natural_enemies", "category": "pest", "impact": "medium",
        "title": "Lascia lavorare gli insetti utili: strisce fiorite, nidi, posatoi",
        "why": "Si comprano meno insetticidi e si proteggono gli impollinatori.",
        "action": "Le strisce fiorite ai bordi dei campi ospitano predatori e parassitoidi dei parassiti; nidi per "
                  "uccelli insettivori e pipistrelli; posatoi per rapaci vicino alle zone con roditori. Evita "
                  "trattamenti ad ampio spettro a inizio stagione, che uccidono gli insetti utili.",
        "sources": [SRC["irri_kb"]],
    })
    tips.append({
        "id": "weather_spraying", "category": "pest", "impact": "low",
        "title": "Tratta guardando le previsioni del tempo",
        "why": "Un prodotto lavato via dalla pioggia è un prodotto pagato due volte.",
        "action": "Con le previsioni Open-Meteo AGROAI può sconsigliare un trattamento se nelle ore successive "
                  "sono attesi pioggia o vento forte.",
        "sources": [SRC["fao56"]],
    })
    return tips


def rice_systems(country_code: str | None, rice_rank: dict | None) -> dict:
    cc = (country_code or "").upper()
    in_eu = cc in EU_COUNTRIES
    systems = [
        {
            "id": "natural_enemies_rice", "name": "Risaia «ecologica» (senza introdurre animali)",
            "what": "Fiori sugli argini, niente insetticidi a inizio stagione, rifugi per ragni, rane e libellule "
                    "che mangiano i parassiti del riso.",
            "benefits": ["parassiti tenuti a bada dai loro nemici naturali", "meno trattamenti insetticidi"],
            "requirements": ["gestione della vegetazione sugli argini", "controlli in campo invece dei trattamenti a calendario"],
            "legal": {"status": "allowed", "note": "Non si introduce nessuna specie."},
            "sources": [SRC["irri_kb"], SRC["slow_rice"]],
        },
        {
            "id": "rice_duck", "name": "Riso con anatre",
            "what": "Le anatre vengono messe in risaia quando il riso è già ben radicato: mangiano erbe infestanti e "
                    "insetti, smuovono l'acqua e concimano con le loro deiezioni. Già usato in alcune aziende "
                    "biologiche italiane (es. Cascina Gambarina, Parco del Ticino).",
            "benefits": ["controllo meccanico delle infestanti", "mangiano gli insetti", "concimazione naturale", "reddito da carne e uova"],
            "requirements": ["riso trapiantato o già ben sviluppato", "recinzione contro le volpi",
                             "riparo e gestione dell'acqua", "togliere le anatre prima della maturazione del chicco"],
            "legal": {"status": "allowed_with_conditions",
                      "note": ("In Italia gli avicoli vanno registrati presso l'ASL (servizio veterinario) e seguono le "
                               "regole di biosicurezza contro l'influenza aviaria; verifica anche il disciplinare bio."
                               if in_eu or not cc else
                               "Verifica le regole locali di registrazione degli animali e di biosicurezza.")},
            "sources": [SRC["ticino_ducks"], SRC["polito_rice"], SRC["unimi_organic"]],
        },
        {
            "id": "rice_fish", "name": "Riso con pesci",
            "what": "Pesci allevati in risaia con un fosso più profondo come rifugio: mangiano erbe, insetti e "
                    "plancton. Era una pratica tradizionale nelle risaie italiane; uno studio di 4 anni in più siti "
                    "ha trovato che la coltura con animali acquatici mantiene l'azoto del suolo e le rese.",
            "benefits": ["pulizia da insetti ed erbe", "riciclo dei nutrienti", "reddito dal pesce"],
            "requirements": ["fossi o vasche di rifugio", "argini più alti", "nessun prodotto tossico per i pesci",
                             "acqua sempre presente"],
            "legal": {"status": "allowed_with_conditions",
                      "note": ("Solo specie autoctone o autorizzate, rispettando le regole regionali su acquacoltura e pesca."
                               if in_eu or not cc else
                               "Usa solo specie autorizzate e verifica i permessi per l'acquacoltura.")},
            "sources": [SRC["elife2022"], SRC["polito_rice"]],
        },
        {
            "id": "rice_crab", "name": "Riso con granchi (granchio cinese, Eriocheir sinensis)",
            "what": "Molto diffuso nel nord-est della Cina. Gli studi riportano rese di riso pari o superiori alla "
                    "monocoltura più 0,52–2,57 t/ha di granchi, ma serve mangime extra; uno studio indica come densità "
                    "ottimale circa 0,4 granchi/m², e si sta provando a usarli contro la chiocciola invasiva Pomacea.",
            "benefits": ["mangiano chiocciole e infestanti (in studio)", "reddito da granchi di valore"],
            "requirements": ["recinzioni anti-fuga", "mangime aggiuntivo", "controllo della qualità dell'acqua"],
            "legal": ({"status": "prohibited",
                       "note": "Il granchio cinese è nell'elenco UE delle specie esotiche invasive: in Italia è vietato "
                               "tenerlo, allevarlo, trasportarlo o liberarlo. Non è un'opzione."}
                      if in_eu else
                      {"status": "check_local",
                       "note": "Fuori dal suo areale è invasivo: verifica le leggi del tuo Paese prima di pensarci."}),
            "sources": [SRC["elife2022"], SRC["crab_density"], SRC["crab_snail"], SRC["eu_ias"]],
        },
        {
            "id": "rice_crayfish", "name": "Riso con gamberi (gambero della Louisiana, Procambarus clarkii)",
            "what": "Sistema molto esteso nella Cina centrale.",
            "benefits": ["reddito dai gamberi"],
            "requirements": ["barriere anti-fuga", "mangime"],
            "legal": ({"status": "prohibited",
                       "note": "Il gambero della Louisiana è nell'elenco UE delle specie invasive e già danneggia "
                               "risaie e canali italiani scavando gli argini. Vietato nell'UE."}
                      if in_eu else
                      {"status": "check_local",
                       "note": "Molto invasivo: danneggia argini e fauna locale. Verifica le leggi del tuo Paese."}),
            "sources": [SRC["eu_ias"], SRC["elife2022"]],
        },
    ]
    water = []
    if rice_rank:
        water.append({
            "title": "Asciutte alternate (AWD)",
            "text": "Invece di tenere la risaia sempre allagata, si lascia scendere l'acqua sotto la superficie del "
                    "terreno tra un'irrigazione e l'altra. L'IRRI la promuove per risparmiare acqua senza perdere "
                    "resa; non è compatibile con pesci o granchi, che hanno bisogno di acqua sempre presente. "
                    "Verifica i turni d'acqua del tuo consorzio irriguo.",
            "sources": [SRC["irri_kb"]],
        })
    return {
        "country": cc or None,
        "in_eu": in_eu,
        "rice_suitability": rice_rank,
        "systems": systems,
        "water_saving": water,
        "disclaimer": "Lo stato legale è un aiuto basato sul regolamento citato, non una consulenza legale. "
                      "Prima di introdurre animali chiedi conferma agli uffici regionali.",
    }
