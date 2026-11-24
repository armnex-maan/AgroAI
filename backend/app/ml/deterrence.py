"""Bird deterrence knowledge base (Italian).

Principles from the literature:
- birds do not hear ultrasound: no species tested hears above ~20 kHz, most stop around 10 kHz;
- the most effective acoustic signals are the species' own alarm/distress calls and predator calls,
  played at irregular times; birds habituate to any fixed sound;
- sound works best combined with nets and visual scarers; nets are the most effective protection.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

LIBRARY_DIR = Path(__file__).resolve().parent.parent / "data" / "deterrent_sounds"

SRC = {
    "sparrow_hearing": {"title": "Henry & Lucas (2008) – udito del passero: massima sensibilità tra 2,2 e 3,2 kHz",
                        "url": "https://www.bio.purdue.edu/People/faculty/lucas/2008.Henry_and_Lucas.ANBEHAV.pdf"},
    "bird_hearing": {"title": "Revisione sull'udito degli uccelli: nessuna specie sente gli ultrasuoni, limite tipico ~10 kHz",
                     "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC3574405"},
    "ultrasound_review": {"title": "Revisione: i dissuasori a ultrasuoni non funzionano sugli uccelli",
                          "url": "https://escholarship.org/uc/item/25t7d8gj"},
    "nap_airports": {"title": "National Academies – dissuasori per uccelli negli aeroporti (ultrasuoni inefficaci)",
                     "url": "https://www.nap.edu/read/14566/chapter/6"},
    "ucdavis_crows": {"title": "UC Davis – richiami di allarme contro i corvi nei mandorleti",
                      "url": "https://ucdavis.edu/news/crop-protection-worth-crowing-about"},
    "vineyard": {"title": "UC Davis – richiami di allarme in vigneto: utili, ma meno delle reti",
                 "url": "https://wineserver.ucdavis.edu/sites/g/files/dgvnsk2676/files/research-summaries/92%20bird%20damage.pdf"},
    "auditory_review": {"title": "Revisione internazionale sull'efficacia dei metodi sonori per allontanare gli uccelli",
                        "url": "https://brocku.ca/niagara-community-observatory/wp-content/uploads/sites/117/Review-of-international-research-regarding-the-effectiveness-of-auditory-bird-scaring-techniques-and-potental-alternatives.pdf"},
    "law_fauna": {"title": "Legge 157/1992 – protezione della fauna selvatica",
                  "url": "https://www.regione.fvg.it/rafvg/cms/RAFVG/ambiente-territorio/tutela-ambiente-gestione-risorse-naturali/FOGLIA52/allegati/NORMATTIVA_-_Stampa_157-1992.htm"},
    "law_noise": {"title": "Legge 447/1995 – legge quadro sull'inquinamento acustico",
                  "url": "https://www.isprambiente.gov.it/contentfiles/00005500/5533-legge-447-95.pdf"},
    "conover": {"title": "Conover (1994) – i gridi di allarme durano meno di 5 s, seguiti da silenzio; abbinati a un rapace finto si abituano più tardi",
                "url": "https://escholarship.org/uc/item/1s35m7b3"},
    "pear_orchard": {"title": "Chen et al. (2024) – pereto: dissuasore sonoro attivato solo quando vede uccelli, 6% di frutti beccati contro 13% senza",
                     "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11416946/"},
    "xeno_canto": {"title": "xeno-canto – archivio libero di versi di uccelli", "url": "https://xeno-canto.org"},
}

PROFILES: dict[str, dict] = {
    "sparrows": {
        "name": "Passeri", "sound_efficacy": "media", "examples": "passera d'Italia, passera europea, passera mattugia",
        "genera": ["Passer"],
        "best_band_hz": [2200, 3200], "audible_band_hz": [500, 8000],
        "hearing": "Sentono meglio tra 2,2 e 3,2 kHz; sopra i 5–6 kHz la sensibilità cala in fretta.",
        "alarm_call": "Passer italiae alarm call",
        "predator": "Sparviero (Accipiter nisus)", "predator_query": "Accipiter nisus",
        "when": "All'alba e nel tardo pomeriggio, quando vanno a mangiare; soprattutto su cereali in maturazione e semine.",
        "notes": "Vivono in gruppo vicino a case e stalle: le reti e la chiusura dei punti di accesso a magazzini e sili sono la difesa più duratura.",
        "sources": [SRC["sparrow_hearing"], SRC["bird_hearing"]],
    },
    "starlings": {
        "name": "Storni", "sound_efficacy": "buona", "examples": "storno comune",
        "genera": ["Sturnus"],
        "best_band_hz": [1000, 4000], "audible_band_hz": [400, 8000],
        "hearing": "Come la maggior parte dei piccoli uccelli canori: meglio tra 1 e 4 kHz.",
        "alarm_call": "Sturnus vulgaris distress call",
        "predator": "Falco pellegrino (Falco peregrinus)", "predator_query": "Falco peregrinus",
        "when": "In stormi su vigneti, frutteti e oliveti in maturazione, soprattutto in autunno.",
        "notes": "Rispondono bene ai richiami di allarme, ma solo all'inizio: alterna i suoni e usa le reti sulle colture di valore.",
        "sources": [SRC["vineyard"], SRC["bird_hearing"]],
    },
    "pigeons": {
        "name": "Piccioni e tortore", "sound_efficacy": "bassa", "examples": "piccione, colombaccio, tortora dal collare",
        "genera": ["Columba", "Streptopelia"],
        "best_band_hz": [500, 3000], "audible_band_hz": [200, 7000],
        "hearing": "Sentono bene i suoni bassi; i suoni acuti li disturbano poco.",
        "alarm_call": "Columba palumbus alarm",
        "predator": "Astore (Accipiter gentilis)", "predator_query": "Accipiter gentilis",
        "when": "Su semine, legumi e cavoli; spesso a gruppi a metà mattina.",
        "notes": "Con i colombi i suoni funzionano poco: meglio reti, fili tesi e protezione delle semine.",
        "sources": [SRC["auditory_review"], SRC["bird_hearing"]],
    },
    "corvids": {
        "name": "Corvidi", "sound_efficacy": "buona", "examples": "cornacchia grigia, corvo, gazza",
        "genera": ["Corvus", "Pica", "Garrulus"],
        "best_band_hz": [1000, 4000], "audible_band_hz": [300, 8000],
        "hearing": "Sentono meglio tra 1 e 4 kHz.",
        "alarm_call": "Corvus cornix alarm call",
        "predator": "Astore (Accipiter gentilis)", "predator_query": "Accipiter gentilis",
        "when": "Su semine di mais, frutta e mandorle; molto intelligenti, imparano presto.",
        "notes": "Uno studio nei mandorleti ha trovato che i richiami di allarme li tengono lontani per settimane prima che si abituino.",
        "sources": [SRC["ucdavis_crows"], SRC["bird_hearing"]],
    },
}

METHODS = [
    {"name": "Reti antiuccello", "evidence": "il metodo più efficace", "tone": "ok",
     "text": "Impediscono fisicamente l'accesso: costano di più all'inizio ma non perdono efficacia nel tempo.",
     "sources": [SRC["vineyard"]]},
    {"name": "Richiami di allarme della specie", "evidence": "funziona per un periodo", "tone": "ok",
     "text": "Gli uccelli riconoscono il grido di pericolo dei loro simili e scappano. Funziona meglio a orari casuali "
             "e insieme ad altri metodi; dopo alcune settimane si abituano.",
     "sources": [SRC["ucdavis_crows"], SRC["vineyard"], SRC["auditory_review"]]},
    {"name": "Rapace finto vicino all'altoparlante", "evidence": "rende il suono più credibile", "tone": "ok",
     "text": "Gli uccelli che sentono il grido d'allarme si avvicinano per vedere il predatore: se trovano un rapace "
             "finto (meglio se spostato spesso) la paura si rafforza e si abituano più tardi.",
     "sources": [SRC["conover"]]},
    {"name": "Suonare a ondate, non sempre", "evidence": "si abituano più lentamente", "tone": "ok",
     "text": "Brevi raffiche di richiami seguite da silenzio funzionano meglio di un suono continuo; ancora meglio "
             "se il suono parte solo quando gli uccelli ci sono davvero.",
     "sources": [SRC["conover"], SRC["pear_orchard"]]},
    {"name": "Versi del predatore", "evidence": "funziona per un periodo", "tone": "ok",
     "text": "Il verso di un rapace che li caccia (per i passeri lo sparviero) li mette in allarme. Alternalo ai richiami di allarme.",
     "sources": [SRC["auditory_review"]]},
    {"name": "Spaventapasseri visivi in movimento", "evidence": "funziona per un periodo", "tone": "info",
     "text": "Nastri riflettenti, palloni con occhi, aquiloni a forma di falco: spostali spesso, altrimenti si abituano.",
     "sources": [SRC["auditory_review"]]},
    {"name": "Toni, fischi e sirene", "evidence": "efficacia bassa", "tone": "warn",
     "text": "Un suono che non significa pericolo viene ignorato in pochi giorni. Se lo usi, cambia spesso frequenza e ritmo.",
     "sources": [SRC["auditory_review"]]},
    {"name": "Ultrasuoni", "evidence": "non funziona", "tone": "bad",
     "text": "Gli uccelli non sentono gli ultrasuoni (sopra i 20 kHz): gli apparecchi venduti come «dissuasori a "
             "ultrasuoni per uccelli» non hanno effetto dimostrato.",
     "sources": [SRC["ultrasound_review"], SRC["nap_airports"], SRC["bird_hearing"]]},
]

LEGAL = {
    "text": "Usa solo metodi che allontanano senza fare del male: la fauna selvatica è tutelata dalla legge 157/1992. "
            "I suoni all'aperto devono rispettare la legge 447/1995 sul rumore e il piano acustico del tuo Comune "
            "(orari e volumi, distanza dalle case): chiedi al Comune prima di installare un altoparlante.",
    "sources": [SRC["law_fauna"], SRC["law_noise"]],
}

SOUND_TYPES = {
    "mix": {"name": "Mix: allarme + predatore", "evidence": "consigliato"},
    "alarm_call": {"name": "Richiamo di allarme della specie", "evidence": "consigliato"},
    "predator_call": {"name": "Verso del predatore", "evidence": "consigliato"},
    "tones": {"name": "Toni variabili generati da AGROAI", "evidence": "efficacia bassa"},
}

ULTRASOUND_HZ = 20000


@lru_cache(maxsize=1)
def library() -> list[dict]:
    """Real recordings bundled with AGROAI (xeno-canto, Creative Commons), each checked with Perch."""
    f = LIBRARY_DIR / "library.json"
    if not f.exists():
        return []
    return [e for e in json.loads(f.read_text(encoding="utf-8")) if e.get("verified")]


def library_for(target: str, sound_type: str) -> list[dict]:
    kinds = {"mix": {"alarm_call", "predator_call"}, "alarm_call": {"alarm_call"},
             "predator_call": {"predator_call"}}.get(sound_type, set())
    return [e for e in library() if e["target"] == target and e["kind"] in kinds]
