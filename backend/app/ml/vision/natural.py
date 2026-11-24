"""Natural and biological remedies, linked to the causes in causes.py.

Types: insetto utile (beneficial organism to release or attract), microrganismo (biological
product), prodotto naturale (substance allowed in organic farming), pratica (cultural method),
tradizionale (folk remedy — little scientific evidence, flagged as such).

Evidence levels: "provato" (in professional use / official lists), "alcuni studi", "tradizionale".
Biological products and natural substances are still plant-protection products: buy authorised
products and follow the label. No doses are given here on purpose.
"""
from __future__ import annotations

EPPO = {"title": "EPPO PM 6/3 – Agenti di controllo biologico usati in Europa",
        "url": "https://www.eppo.int/media/uploaded_images/RESOURCES/eppo_standards/pm6/pm6-03-2020-en.pdf"}
EU_ORGANIC = {"title": "Reg. (UE) 2021/1165 – prodotti ammessi in agricoltura biologica",
              "url": "https://eur-lex.europa.eu/eli/reg_impl/2021/1165/oj"}
EU_COPPER = {"title": "Reg. (UE) 2018/1981 – limite del rame: 28 kg/ha in 7 anni",
             "url": "https://eur-lex.europa.eu/eli/reg_impl/2018/1981/oj"}
UC_IPM = {"title": "UC IPM – nemici naturali e difesa integrata", "url": "https://ipm.ucanr.edu/"}
INRAE_TRICHO = {"title": "INRAE – Trichogramma contro la piralide del mais",
                "url": "https://www.inrae.fr/en/news/trichogramma-effective-biocontrol-solution-corn-borer"}
WUR_TRICHO = {"title": "Studio in campo (2016): Trichogramma contro la piralide in Italia e Francia",
              "url": "https://research.wur.nl/en/publications/on-farm-evaluation-of-inundative-biological-control-of-ostrinia-n"}
FAO_SOC = {"title": "FAO – sostanza organica del suolo", "url": "https://www.fao.org/3/i6937e/i6937e.pdf"}

BUY_BENEFICIAL = ("Si comprano dalle biofabbriche (aziende che allevano insetti utili): usa solo specie "
                  "vendute per l'uso in Italia. Funzionano meglio in serra; in campo aperto conviene "
                  "soprattutto attirare quelli che ci sono già.")
LABEL = "È comunque un prodotto fitosanitario: usa un prodotto autorizzato e segui l'etichetta."

REMEDIES: dict[str, dict] = {
    # ---------- insetti e acari utili ----------
    "ladybirds": {
        "name": "Coccinelle (es. Adalia bipunctata)", "type": "insetto utile", "evidence": "provato",
        "against": "afidi (pidocchi delle piante)",
        "how": "Una coccinella mangia decine di afidi al giorno, anche da larva. Non trattare con insetticidi "
               "ad ampio spettro, che uccidono anche loro. " + BUY_BENEFICIAL,
        "sources": [EPPO, UC_IPM],
    },
    "lacewings": {
        "name": "Crisopa (Chrysoperla carnea)", "type": "insetto utile", "evidence": "provato",
        "against": "afidi, mosche bianche, piccoli bruchi, acari",
        "how": "Le larve della crisopa sono predatori voraci. Gli adulti vengono attirati da fiori con polline "
               "e nettare ai bordi del campo. " + BUY_BENEFICIAL,
        "sources": [EPPO, UC_IPM],
    },
    "aphidius": {
        "name": "Aphidius colemani (vespina parassitoide)", "type": "insetto utile", "evidence": "provato",
        "against": "afidi",
        "how": "Depone le uova dentro gli afidi, che diventano «mummie» gonfie e dorate: quando le vedi, "
               "il controllo sta funzionando. Usata soprattutto in serra. " + BUY_BENEFICIAL,
        "sources": [EPPO],
    },
    "phytoseiulus": {
        "name": "Phytoseiulus persimilis (acaro predatore)", "type": "insetto utile", "evidence": "provato",
        "against": "ragnetto rosso (Tetranychus urticae)",
        "how": "Mangia solo ragnetti rossi: si libera sui focolai appena compaiono le prime foglie puntinate. "
               "Ama l'umidità, rende meglio in serra e in estati non troppo secche. " + BUY_BENEFICIAL,
        "sources": [EPPO],
    },
    "encarsia": {
        "name": "Encarsia formosa (vespina parassitoide)", "type": "insetto utile", "evidence": "provato",
        "against": "mosca bianca delle serre",
        "how": "Parassitizza le larve della mosca bianca, che diventano nere. Si usa in serra su pomodoro, "
               "cetriolo, fagiolo. " + BUY_BENEFICIAL,
        "sources": [EPPO],
    },
    "macrolophus": {
        "name": "Macrolophus pygmaeus (cimice predatrice)", "type": "insetto utile", "evidence": "provato",
        "against": "mosca bianca, Tuta absoluta (tignola del pomodoro), afidi",
        "how": "Molto usato nelle serre di pomodoro: si insedia sulla pianta e caccia uova e larve. " + BUY_BENEFICIAL,
        "sources": [EPPO],
    },
    "orius": {
        "name": "Orius laevigatus (cimice predatrice)", "type": "insetto utile", "evidence": "provato",
        "against": "tripidi",
        "how": "Predatore dei tripidi su peperone, fragola e fiori; si mantiene meglio dove ci sono fiori con polline. "
               + BUY_BENEFICIAL,
        "sources": [EPPO],
    },
    "swirskii": {
        "name": "Amblyseius swirskii (acaro predatore)", "type": "insetto utile", "evidence": "provato",
        "against": "tripidi e mosca bianca",
        "how": "Si mette in serra in bustine appese alle piante; resiste al caldo. " + BUY_BENEFICIAL,
        "sources": [EPPO],
    },
    "trichogramma": {
        "name": "Trichogramma brassicae (micro-vespina)", "type": "insetto utile", "evidence": "provato",
        "against": "piralide del mais e altre farfalle (uova)",
        "how": "Parassitizza le uova della piralide prima che nascano i bruchi. In Francia protegge circa 120.000 "
               "ettari di mais l'anno; uno studio in Nord Italia l'ha trovato efficace come la difesa chimica. "
               "Si distribuisce con capsule all'inizio del volo della piralide. " + BUY_BENEFICIAL,
        "sources": [EPPO, INRAE_TRICHO, WUR_TRICHO],
    },
    "nematodes_soil": {
        "name": "Nematodi entomopatogeni (Heterorhabditis, Steinernema)", "type": "insetto utile", "evidence": "provato",
        "against": "larve nel terreno: oziorrinco, maggiolino, elateridi, moscerini dei terricci",
        "how": "Vermi microscopici che entrano nelle larve e le uccidono. Si sciolgono in acqua e si danno con "
               "l'irrigazione su terreno umido, la sera, con il suolo sopra i 12 °C circa. " + BUY_BENEFICIAL,
        "sources": [EPPO],
    },
    # ---------- microrganismi ----------
    "bt": {
        "name": "Bacillus thuringiensis", "type": "microrganismo", "evidence": "provato",
        "against": "bruchi (larve di farfalle e falene)",
        "how": "Batterio che uccide solo i bruchi che mangiano le foglie trattate; innocuo per api, coccinelle e "
               "persone. Funziona sulle larve giovani; tratta al tramonto perché il sole lo degrada. " + LABEL,
        "sources": [EU_ORGANIC],
    },
    "beauveria": {
        "name": "Beauveria bassiana (fungo entomopatogeno)", "type": "microrganismo", "evidence": "provato",
        "against": "mosche bianche, tripidi, alcuni coleotteri",
        "how": "Un fungo che infetta gli insetti al contatto; ha bisogno di umidità per funzionare. " + LABEL,
        "sources": [EU_ORGANIC],
    },
    "bacillus_fungi": {
        "name": "Bacillus subtilis / amyloliquefaciens", "type": "microrganismo", "evidence": "provato",
        "against": "muffe e macchie fogliari (botrite, alcune batteriosi e funghi)",
        "how": "Batteri utili che occupano la foglia e ostacolano i funghi: vanno usati in prevenzione, "
               "prima che la malattia si diffonda. " + LABEL,
        "sources": [EU_ORGANIC],
    },
    "ampelomyces": {
        "name": "Ampelomyces quisqualis (fungo antagonista)", "type": "microrganismo", "evidence": "provato",
        "against": "oidio (mal bianco)",
        "how": "Un fungo che parassitizza l'oidio. Funziona all'inizio dell'infezione e con un po' di umidità. " + LABEL,
        "sources": [EU_ORGANIC],
    },
    "trichoderma": {
        "name": "Trichoderma (funghi utili del terreno)", "type": "microrganismo", "evidence": "provato",
        "against": "marciumi del colletto e delle radici",
        "how": "Si danno al terreno o al trapianto: colonizzano le radici e competono con i funghi dannosi. " + LABEL,
        "sources": [EU_ORGANIC],
    },
    # ---------- prodotti naturali ammessi in biologico ----------
    "copper": {
        "name": "Rame", "type": "prodotto naturale", "evidence": "provato",
        "against": "peronospora, macchie fogliari, batteriosi",
        "how": "Ammesso in biologico ma con un limite di legge: al massimo 28 kg di rame per ettaro in 7 anni, "
               "perché si accumula nel terreno. Usa le dosi più basse e solo quando il meteo è a rischio. " + LABEL,
        "sources": [EU_COPPER, EU_ORGANIC],
    },
    "sulfur": {
        "name": "Zolfo", "type": "prodotto naturale", "evidence": "provato",
        "against": "oidio (mal bianco), alcuni acari",
        "how": "Il rimedio classico contro l'oidio, ammesso in biologico. Sopra i 30 °C circa può bruciare le "
               "foglie: tratta nelle ore fresche. " + LABEL,
        "sources": [EU_ORGANIC],
    },
    "bicarbonate": {
        "name": "Bicarbonato di potassio", "type": "prodotto naturale", "evidence": "provato",
        "against": "oidio, alcune muffe",
        "how": "Sostanza a basso rischio ammessa in biologico: agisce per contatto, va ripetuto dopo la pioggia. " + LABEL,
        "sources": [EU_ORGANIC],
    },
    "potassium_soap": {
        "name": "Sapone molle potassico (sali di acidi grassi)", "type": "prodotto naturale", "evidence": "provato",
        "against": "afidi, mosche bianche, acari, cocciniglie",
        "how": "Uccide per contatto gli insetti a corpo molle e lascia pochi residui; bagna bene anche sotto le "
               "foglie. Non colpisce gli insetti che non tocca. " + LABEL,
        "sources": [EU_ORGANIC],
    },
    "neem": {
        "name": "Olio di neem (azadiractina)", "type": "prodotto naturale", "evidence": "provato",
        "against": "afidi, tripidi, mosche bianche, alcuni bruchi",
        "how": "Estratto dei semi di neem: blocca la crescita e l'alimentazione degli insetti. Tratta la sera "
               "per proteggere le api. " + LABEL,
        "sources": [EU_ORGANIC],
    },
    "ferric_phosphate": {
        "name": "Fosfato ferrico (esche per lumache)", "type": "prodotto naturale", "evidence": "provato",
        "against": "lumache e limacce",
        "how": "Esca ammessa in biologico: le lumache smettono di mangiare e muoiono nel terreno. Molto meno "
               "pericolosa per cani, ricci e uccelli delle vecchie esche chimiche. " + LABEL,
        "sources": [EU_ORGANIC],
    },
    "kaolin": {
        "name": "Caolino (argilla bianca)", "type": "prodotto naturale", "evidence": "provato",
        "against": "scottature da sole, mosca dell'olivo, alcuni insetti",
        "how": "Crea una pellicola bianca sulle foglie e sui frutti che riflette il sole e confonde gli insetti. "
               "Va rinnovato dopo piogge forti. " + LABEL,
        "sources": [EU_ORGANIC],
    },
    # ---------- pratiche ----------
    "flower_strips": {
        "name": "Strisce fiorite e siepi", "type": "pratica", "evidence": "provato",
        "against": "afidi e molti altri parassiti (attirando i loro nemici)",
        "how": "Facelia, alisso, grano saraceno, fiordaliso e siepi miste ai bordi danno cibo e rifugio a "
               "sirfidi, coccinelle, crisope e vespine utili, che poi entrano nel campo.",
        "sources": [UC_IPM],
    },
    "nest_boxes": {
        "name": "Nidi per uccelli e pipistrelli, posatoi per rapaci", "type": "pratica", "evidence": "provato",
        "against": "bruchi, insetti volanti, roditori",
        "how": "Cince e pipistrelli mangiano moltissimi insetti; un posatoio alto 2–3 m attira poiane e "
               "gufi che cacciano arvicole e topi.",
        "sources": [UC_IPM],
    },
    "pheromone_traps": {
        "name": "Trappole a feromoni e confusione sessuale", "type": "pratica", "evidence": "provato",
        "against": "tignole e falene (es. carpocapsa, Tuta absoluta, tignola della vite)",
        "how": "Le trappole dicono quando arrivano i maschi, così tratti solo se serve; i diffusori per la "
               "confusione sessuale impediscono gli accoppiamenti su superfici grandi.",
        "sources": [UC_IPM],
    },
    "sticky_traps": {
        "name": "Trappole adesive colorate", "type": "pratica", "evidence": "provato",
        "against": "mosche bianche e afidi alati (gialle), tripidi (blu)",
        "how": "Servono soprattutto per accorgersi presto del problema; in serra ne catturano anche molti.",
        "sources": [UC_IPM],
    },
    "insect_nets": {
        "name": "Reti anti-insetto", "type": "pratica", "evidence": "provato",
        "against": "insetti che trasmettono virus, cavolaia, mosca della carota",
        "how": "Una rete a maglia fine sopra la coltura impedisce agli insetti di arrivare: niente trattamenti.",
        "sources": [UC_IPM],
    },
    "mulch": {
        "name": "Pacciamatura (paglia, foglie, teli)", "type": "pratica", "evidence": "provato",
        "against": "siccità, erbe infestanti, schizzi di terra che portano malattie sulle foglie",
        "how": "5–10 cm di paglia o residui sul terreno trattengono l'umidità e lo tengono più fresco.",
        "sources": [FAO_SOC],
    },
    "compost": {
        "name": "Compost e letame maturo", "type": "pratica", "evidence": "provato",
        "against": "terreno povero, carenze di nutrienti, terreno che non trattiene l'acqua",
        "how": "Aumentano la sostanza organica: il terreno trattiene più acqua e libera nutrienti piano piano.",
        "sources": [FAO_SOC],
    },
    "green_manure": {
        "name": "Sovescio di leguminose (veccia, trifoglio, favino)", "type": "pratica", "evidence": "provato",
        "against": "carenza di azoto, terreno povero",
        "how": "Si semina in autunno e si interra in primavera: le leguminose portano nel terreno l'azoto preso "
               "dall'aria.",
        "sources": [FAO_SOC],
    },
    "radish_decompact": {
        "name": "Rafano da foraggio o ravizzone come «aratro naturale»", "type": "pratica", "evidence": "alcuni studi",
        "against": "terreno compattato e ristagni",
        "how": "Le radici profonde a fittone aprono canali nel terreno compatto che migliorano il drenaggio.",
        "sources": [FAO_SOC],
    },
    "reflective_mulch": {
        "name": "Pacciamatura riflettente (argentata)", "type": "pratica", "evidence": "alcuni studi",
        "against": "afidi e tripidi che trasmettono virus",
        "how": "La luce riflessa disorienta gli insetti in arrivo nelle prime settimane dopo il trapianto.",
        "sources": [UC_IPM],
    },
    "beer_traps": {
        "name": "Trappole con birra per lumache", "type": "tradizionale", "evidence": "tradizionale",
        "against": "lumache e limacce",
        "how": "Un vasetto interrato a filo del terreno con un po' di birra attira le lumache. Utile negli orti "
               "piccoli, poco pratico in campo.",
        "sources": [UC_IPM],
    },
    "milk_spray": {
        "name": "Latte diluito contro l'oidio", "type": "tradizionale", "evidence": "alcuni studi",
        "against": "oidio su zucchine e cucurbitacee",
        "how": "Alcune prove sperimentali su zucchina l'hanno trovato utile, ma l'efficacia varia molto: "
               "consideralo un tentativo per l'orto, non una difesa professionale.",
        "sources": [UC_IPM],
    },
    "grass_cover": {
        "name": "Inerbimento tra i filari", "type": "pratica", "evidence": "alcuni studi",
        "against": "clorosi ferrica su terreni calcarei, erosione",
        "how": "Studi su vite e pesco indicano che un prato tra i filari riduce la clorosi su suoli calcarei e "
               "migliora la struttura del terreno.",
        "sources": [FAO_SOC],
    },
    "kieserite": {
        "name": "Kieserite (solfato di magnesio naturale)", "type": "prodotto naturale", "evidence": "provato",
        "against": "carenza di magnesio",
        "how": "Minerale ammesso in biologico che porta magnesio senza alzare il pH. Usalo dopo un'analisi del terreno.",
        "sources": [EU_ORGANIC],
    },
    "wood_ash": {
        "name": "Cenere di legna", "type": "tradizionale", "evidence": "alcuni studi",
        "against": "carenza di potassio su terreni acidi",
        "how": "Contiene potassio e calcio ma alza il pH: non usarla su terreni calcarei o alcalini, e solo "
               "cenere di legna non trattata.",
        "sources": [FAO_SOC],
    },
}

BY_CAUSE: dict[str, list[str]] = {
    "healthy": ["flower_strips", "nest_boxes", "compost"],
    "water_stress": ["mulch", "compost"],
    "waterlogging": ["radish_decompact", "compost"],
    "nitrogen_deficiency": ["green_manure", "compost"],
    "iron_chlorosis": ["grass_cover", "compost"],
    "magnesium_deficiency": ["kieserite", "compost"],
    "potassium_deficiency": ["compost", "wood_ash"],
    "fungal_leaf_spot": ["bacillus_fungi", "copper", "mulch"],
    "powdery_mildew": ["sulfur", "bicarbonate", "ampelomyces", "milk_spray"],
    "downy_mildew": ["copper", "bacillus_fungi"],
    "rust": ["sulfur", "bacillus_fungi"],
    "chewing_insects": ["bt", "trichogramma", "nematodes_soil", "ferric_phosphate", "nest_boxes", "pheromone_traps", "beer_traps"],
    "sucking_insects": ["ladybirds", "lacewings", "aphidius", "phytoseiulus", "encarsia", "macrolophus", "orius",
                        "swirskii", "potassium_soap", "neem", "beauveria", "flower_strips", "sticky_traps"],
    "viral_disease": ["insect_nets", "reflective_mulch", "sticky_traps"],
    "heat_sunscald": ["kaolin", "mulch"],
    "chemical_damage": ["compost"],
    "mechanical_damage": [],
    "natural_senescence": [],
    "blossom_end_rot": ["mulch", "compost"],
    "late_blight": ["copper"],
    "early_blight": ["copper", "bacillus_fungi", "mulch"],
    "anthracnose": ["copper", "mulch"],
    "grey_mould": ["bacillus_fungi"],
    "fruit_cracking": ["mulch"],
    "bacterial_wilt": [],
}


def for_cause(cause_id: str) -> list[dict]:
    return [{"id": rid, **REMEDIES[rid]} for rid in BY_CAUSE.get(cause_id, [])]


def catalog() -> list[dict]:
    used_by: dict[str, list[str]] = {}
    for cid, rids in BY_CAUSE.items():
        for rid in rids:
            used_by.setdefault(rid, []).append(cid)
    return [{"id": rid, **r, "causes": used_by.get(rid, [])} for rid, r in REMEDIES.items()]
