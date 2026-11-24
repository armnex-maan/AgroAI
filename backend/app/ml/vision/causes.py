"""Knowledge base of common causes of visible plant symptoms, with vetted fix tips (Italian).

The vision model may only choose causes from this list, so the advice shown to the
farmer is always one of these pre-written, conservative recommendations. No doses or
brand names: product choice must follow the label and national authorisation.
"""
from __future__ import annotations

UC_IPM = {"title": "UC IPM – Università della California, guide ai sintomi e difesa integrata",
          "url": "https://ipm.ucanr.edu/"}
FAO_SOILS = {"title": "FAO – Portale suoli (gestione dei nutrienti)", "url": "https://www.fao.org/soils-portal/en/"}
FAO_56 = {"title": "FAO-56 – Evapotraspirazione delle colture (irrigazione)",
          "url": "https://www.fao.org/4/x0490e/x0490e00.htm"}

def _uc(slug: str, title: str) -> dict:
    return {"title": f"UC IPM – {title}", "url": f"https://ipm.ucanr.edu/agriculture/tomato/{slug}/"}


PRODUCT_RULE = ("Se serve un trattamento, usa solo prodotti autorizzati in Italia per questa coltura, "
                "alla dose in etichetta e rispettando il tempo di carenza prima della raccolta.")

CAUSES: dict[str, dict] = {
    "healthy": {
        "name": "Nessun problema evidente", "category": "none", "urgency": "none",
        "signs": "Colore verde uniforme, nessuna macchia, nessuna deformazione.",
        "fix": ["Nessun intervento. Continua a fotografare le stesse piante ogni settimana, dalla stessa angolazione."],
        "prevent": ["Tieni uno storico di foto per ogni zona: così noti i cambiamenti presto."],
        "verify": ["Guarda anche la pagina inferiore delle foglie e i germogli nuovi, che spesso non si vedono in foto."],
        "sources": [UC_IPM],
    },
    "water_stress": {
        "name": "Stress idrico (siccità)", "category": "abiotic", "urgency": "high",
        "signs": "Piante appassite nelle ore calde, foglie opache o arrotolate, bordi secchi, ingiallimento uniforme delle foglie vecchie.",
        "fix": ["Irriga subito, meglio al mattino presto, e controlla che l'acqua arrivi alle radici.",
                "Se l'impianto è a goccia, controlla gocciolatori, tubi e pressione."],
        "prevent": ["Irriga in base all'umidità del terreno (sensori AGROAI) invece che a calendario.",
                    "Pacciama o lascia i residui sul terreno per ridurre l'evaporazione."],
        "verify": ["Scava 15–20 cm vicino alle radici: se la terra non sta insieme nel pugno è secca.",
                   "Se la pianta si riprende la sera, è quasi sempre mancanza d'acqua."],
        "sources": [FAO_56],
    },
    "waterlogging": {
        "name": "Ristagno d'acqua / drenaggio scarso", "category": "abiotic", "urgency": "high",
        "signs": "Ingiallimento e appassimento nonostante il terreno bagnato, radici scure o marce, peggio nelle zone basse.",
        "fix": ["Sospendi l'irrigazione finché il terreno non sgronda; apri piccoli solchi di scolo dalle zone basse."],
        "prevent": ["Migliora il drenaggio, evita di compattare il terreno (niente mezzi sul bagnato), aiuole rialzate per le colture delicate."],
        "verify": ["Guarda le radici: quelle sane sono bianche e sode, quelle danneggiate marroni, molli e con odore acido."],
        "sources": [FAO_56],
    },
    "nitrogen_deficiency": {
        "name": "Carenza di azoto", "category": "nutrient", "urgency": "medium",
        "signs": "Colore verde pallido o giallo che parte dalle foglie VECCHIE (in basso), uniforme sulla foglia, crescita lenta.",
        "fix": ["Concima con azoto in base a un'analisi del terreno o delle foglie; meglio in più volte che tutto insieme.",
                "In biologico: letame ben maturo o concimi organici azotati ammessi."],
        "prevent": ["Leguminose o sovescio nella rotazione; concimazione basata sulle analisi del suolo."],
        "verify": ["Analisi fogliare o misuratore di clorofilla; confronta con una pianta ben nutrita della stessa varietà."],
        "sources": [FAO_SOILS],
    },
    "iron_chlorosis": {
        "name": "Clorosi ferrica (spesso per terreno calcareo)", "category": "nutrient", "urgency": "medium",
        "signs": "Giallo TRA le nervature che restano verdi, sulle foglie PIÙ GIOVANI; frequente su terreni calcarei con pH sopra 7,5.",
        "fix": ["Chelati di ferro adatti ai terreni alcalini, per via fogliare o al terreno, seguendo l'etichetta.",
                "Evita di irrigare troppo: sui terreni calcarei peggiora la clorosi."],
        "prevent": ["Su terreni alcalini scegli varietà o portinnesti tolleranti; aggiungi sostanza organica."],
        "verify": ["Misura pH e calcare attivo del terreno; analisi fogliare (il ferro totale può sembrare normale, conta il sintomo)."],
        "sources": [FAO_SOILS],
    },
    "magnesium_deficiency": {
        "name": "Carenza di magnesio", "category": "nutrient", "urgency": "low",
        "signs": "Giallo tra le nervature sulle foglie VECCHIE, a volte con sfumature rossastre; le nervature restano verdi.",
        "fix": ["Concime fogliare a base di magnesio o un concime che lo contenga, in base all'analisi del terreno."],
        "prevent": ["Concimazione potassica equilibrata (troppo potassio blocca il magnesio); controlla il magnesio nel suolo."],
        "verify": ["Analisi del terreno (magnesio scambiabile e rapporto K/Mg) e analisi fogliare."],
        "sources": [FAO_SOILS],
    },
    "potassium_deficiency": {
        "name": "Carenza di potassio", "category": "nutrient", "urgency": "medium",
        "signs": "BORDI delle foglie vecchie prima gialli poi bruciati e marroni; steli deboli, frutti di qualità scarsa.",
        "fix": ["Concimazione potassica in base all'analisi del terreno."],
        "prevent": ["Interra i residui colturali; analisi del suolo regolari, soprattutto nei terreni sabbiosi."],
        "verify": ["Analisi del potassio nel terreno e nelle foglie; escludi la siccità controllando l'umidità del suolo."],
        "sources": [FAO_SOILS],
    },
    "fungal_leaf_spot": {
        "name": "Macchie fogliari da funghi o batteri", "category": "disease", "urgency": "medium",
        "signs": "Macchie rotonde o angolose marroni/nere, spesso con alone giallo o anelli concentrici; si diffondono dopo la pioggia.",
        "fix": ["Togli e distruggi le foglie più colpite; non metterle nel compost.",
                "Non bagnare le foglie: irriga alla base, al mattino.", PRODUCT_RULE],
        "prevent": ["Rotazione delle colture, sesti più larghi per far circolare l'aria, varietà resistenti, seme sano."],
        "verify": ["Con una lente cerca le spore; il Servizio Fitosanitario Regionale o un laboratorio può confermare."],
        "sources": [UC_IPM],
    },
    "powdery_mildew": {
        "name": "Oidio (mal bianco)", "category": "disease", "urgency": "medium",
        "signs": "Macchie bianco-grigie polverose sulla pagina superiore che si tolgono con un dito; poi le foglie ingialliscono e seccano.",
        "fix": ["Togli le foglie più colpite e migliora la circolazione dell'aria.", PRODUCT_RULE],
        "prevent": ["Varietà resistenti, niente eccesso di azoto, distanze adeguate tra le piante."],
        "verify": ["Strofina la macchia: l'oidio viene via con il dito come polvere."],
        "sources": [UC_IPM],
    },
    "downy_mildew": {
        "name": "Peronospora", "category": "disease", "urgency": "high",
        "signs": "Macchie gialle 'a olio' sopra e muffa grigio-violacea SOTTO la foglia, dopo notti umide.",
        "fix": ["Intervieni presto: con tempo umido si diffonde in pochi giorni. Togli le foglie colpite.", PRODUCT_RULE],
        "prevent": ["Segui gli avvisi meteo (bagnatura fogliare, umidità); non bagnare le foglie; buon drenaggio."],
        "verify": ["Al mattino presto guarda sotto le macchie: la peronospora mostra una muffetta grigia."],
        "sources": [UC_IPM],
    },
    "rust": {
        "name": "Ruggine", "category": "disease", "urgency": "medium",
        "signs": "Piccole pustole in rilievo arancioni, marroni o gialle, soprattutto sotto la foglia; lasciano una polvere arancione.",
        "fix": ["Togli presto le foglie colpite e distruggi i residui.", PRODUCT_RULE],
        "prevent": ["Varietà resistenti, rotazione, evita chiome troppo fitte e foglie bagnate a lungo."],
        "verify": ["Passa una pustola su un foglio bianco: la ruggine lascia una polvere arancio-marrone."],
        "sources": [UC_IPM],
    },
    "chewing_insects": {
        "name": "Insetti che mangiano le foglie (bruchi, coleotteri, lumache)", "category": "pest", "urgency": "medium",
        "signs": "Buchi, bordi rosicchiati, foglie ridotte a scheletro, escrementi o scie di bava.",
        "fix": ["Controlla all'alba o al tramonto e, su piccole superfici, togli gli insetti a mano.",
                "Favorisci i loro nemici naturali; tratta solo se il danno supera la soglia di intervento.",
                PRODUCT_RULE],
        "prevent": ["Strisce fiorite per i predatori, nidi per uccelli insettivori, trappole a feromoni per il monitoraggio."],
        "verify": ["Trova il colpevole: guarda sotto le foglie e sul terreno, anche di notte con una torcia."],
        "sources": [UC_IPM],
    },
    "sucking_insects": {
        "name": "Insetti succhiatori (afidi, mosche bianche, acari, tripidi)", "category": "pest", "urgency": "medium",
        "signs": "Foglie nuove arricciate o deformate, melata appiccicosa, fumaggine nera, puntini chiari o ragnatele sottili.",
        "fix": ["Su piccole superfici un getto d'acqua forte; elimina i germogli più infestati.",
                "Proteggi coccinelle, crisope e sirfidi; evita insetticidi ad ampio spettro.", PRODUCT_RULE],
        "prevent": ["Niente eccesso di azoto (la vegetazione tenera attira gli afidi); trappole cromotropiche gialle per il monitoraggio."],
        "verify": ["Con una lente guarda sotto le foglie giovani; scuoti un germoglio su un foglio bianco per vedere gli acari."],
        "sources": [UC_IPM],
    },
    "viral_disease": {
        "name": "Possibile virosi", "category": "disease", "urgency": "high",
        "signs": "Mosaico di verde chiaro e scuro, macchie ad anello, foglie molto deformate o piante nane.",
        "fix": ["Non esiste cura: estirpa e distruggi le piante colpite per proteggere le altre.",
                "Controlla gli insetti che trasmettono i virus (afidi, mosche bianche, tripidi)."],
        "prevent": ["Seme e piantine certificati; controllo degli insetti vettori; elimina le erbe infestanti che ospitano i virus."],
        "verify": ["Serve un test di laboratorio (ELISA/PCR) tramite il Servizio Fitosanitario: i sintomi da soli non bastano."],
        "sources": [UC_IPM],
    },
    "heat_sunscald": {
        "name": "Colpo di calore / scottatura solare", "category": "abiotic", "urgency": "medium",
        "signs": "Zone chiare, biancastre o giallastre, poi secche e come carta, solo sul lato dei frutti o delle foglie "
                 "più esposto al sole; il tessuto resta asciutto finché non arrivano muffe secondarie.",
        "fix": ["I frutti scottati non guariscono: raccoglili presto e usali se sani nel resto, o eliminali se marciscono.",
                "Reti ombreggianti temporanee sulle colture di valore durante le ondate di calore."],
        "prevent": ["Lascia foglie a coprire i frutti; evita potature e sfogliature forti prima del caldo.",
                    "Controlla le malattie delle foglie: piante defogliate espongono i frutti al sole."],
        "verify": ["Se il danno è solo sul lato rivolto al sole, sui frutti scoperti, e dopo giorni caldi e sereni, è scottatura.",
                   "I frutti all'ombra della stessa pianta dovrebbero essere sani."],
        "sources": [_uc("sunscald", "Scottatura solare del pomodoro"), FAO_56],
    },
    "chemical_damage": {
        "name": "Danno da diserbante o da prodotti chimici", "category": "abiotic", "urgency": "medium",
        "signs": "Foglie attorcigliate o a coppa, bruciature a chiazze come da deriva, sintomi lungo i bordi del campo o le passate.",
        "fix": ["Irriga per aiutare la ripresa; annota data, prodotto e vento dei trattamenti vicini."],
        "prevent": ["Lava bene l'irroratrice tra un prodotto e l'altro; non trattare con vento; rispetta le fasce di rispetto."],
        "verify": ["Se il danno segue le passate dell'irroratrice o il bordo del campo, è l'indizio più forte."],
        "sources": [UC_IPM],
    },
    "mechanical_damage": {
        "name": "Danno meccanico, da grandine o vento", "category": "abiotic", "urgency": "low",
        "signs": "Foglie strappate, ammaccature, steli rotti, danni da un solo lato dopo un temporale.",
        "fix": ["Togli le parti rotte con tagli netti e puliti per limitare le infezioni."],
        "prevent": ["Frangivento; reti antigrandine sulle colture di valore."],
        "verify": ["Controlla il meteo dei giorni precedenti: grandine o vento forte confermano."],
        "sources": [UC_IPM],
    },
    "natural_senescence": {
        "name": "Invecchiamento naturale delle foglie vecchie", "category": "none", "urgency": "none",
        "signs": "Ingialliscono solo le foglie più vecchie e basse, mentre la vegetazione nuova è verde e vigorosa.",
        "fix": ["Nessun intervento se i germogli nuovi sono sani."],
        "prevent": [],
        "verify": ["Controlla che foglie giovani e apici siano sani."],
        "sources": [UC_IPM],
    },

    "blossom_end_rot": {
        "name": "Marciume apicale", "category": "abiotic", "urgency": "medium",
        "signs": "Macchia prima acquosa, poi scura, secca, piatta o infossata e come cuoio, all'ESTREMITÀ FIORALE del frutto "
                 "(il punto opposto al picciolo, in basso). Le foglie restano sane. Colpisce pomodoro, peperone, melanzana, "
                 "zucchina e anguria.",
        "fix": ["I frutti già colpiti non guariscono: toglili, così la pianta nutre quelli sani.",
                "Rendi regolare l'irrigazione: il problema nasce da poco calcio che arriva al frutto quando l'acqua va e viene."],
        "prevent": ["Irrigazione regolare e pacciamatura per tenere il terreno umido in modo costante.",
                    "Evita eccessi di azoto ammoniacale e di potassio; correggi il calcio solo se l'analisi del suolo lo indica.",
                    "Varietà meno sensibili (spesso i pomodori allungati sono i più colpiti)."],
        "verify": ["Guarda dove è la macchia: deve essere sull'estremità opposta al picciolo, non vicino al calice.",
                   "Le foglie e i fusti sono sani? Se anche loro hanno macchie, la causa è probabilmente un'altra."],
        "sources": [_uc("blossom-end-rot", "Marciume apicale")],
    },
    "late_blight": {
        "name": "Peronospora del pomodoro e della patata (Phytophthora infestans)", "category": "disease", "urgency": "high",
        "signs": "Sui frutti: grandi chiazze brune o verde-oliva, marmorizzate e come unte, SODE, spesso sulla parte alta "
                 "(spalle, vicino al picciolo). Sulle foglie: macchie grandi scure che seccano in pochi giorni, con muffetta "
                 "bianca sotto con tempo umido. Anche i fusti si anneriscono.",
        "fix": ["Agisci subito: con tempo umido si diffonde in pochi giorni a tutto il campo e ai vicini.",
                "Togli e distruggi (non nel compost) piante, foglie e frutti colpiti, in sacchi chiusi.",
                "Proteggi le piante ancora sane: i prodotti agiscono in prevenzione, non guariscono i tessuti già colpiti.",
                PRODUCT_RULE],
        "prevent": ["Non bagnare le foglie; irriga alla base e al mattino.",
                    "Distanze ampie, sfogliatura bassa e tutori per far asciugare la vegetazione.",
                    "Segui i bollettini di difesa della tua Regione nei periodi piovosi; varietà tolleranti.",
                    "Elimina patate spontanee e residui infetti; non coltivare pomodoro vicino a patate malate."],
        "verify": ["Al mattino con tempo umido cerca una muffetta bianca sul bordo delle macchie, sotto le foglie.",
                   "Le chiazze sui frutti sono sode (non molli) e partono spesso dall'alto: tipico della peronospora.",
                   "Per conferma porta un campione al Servizio Fitosanitario Regionale."],
        "sources": [_uc("late-blight", "Peronospora (late blight)")],
    },
    "early_blight": {
        "name": "Alternariosi (Alternaria)", "category": "disease", "urgency": "medium",
        "signs": "Macchie scure con ANELLI CONCENTRICI ('a bersaglio') e alone giallo, prima sulle foglie vecchie in basso; "
                 "sui frutti macchie scure infossate vicino al picciolo, con anelli e muffetta nera vellutata.",
        "fix": ["Togli le foglie basse colpite e i frutti macchiati.", PRODUCT_RULE],
        "prevent": ["Rotazione di almeno 2–3 anni lontano da pomodoro, patata e melanzana; pacciamatura contro gli schizzi di terra.",
                    "Concimazione equilibrata: le piante deboli o stressate si ammalano di più."],
        "verify": ["Cerca gli anelli concentrici con una lente: sono il segno più caratteristico."],
        "sources": [_uc("early-blight", "Alternariosi (early blight)")],
    },
    "anthracnose": {
        "name": "Antracnosi dei frutti (Colletotrichum)", "category": "disease", "urgency": "medium",
        "signs": "Sui frutti MATURI: macchie rotonde, piccole all'inizio, poi INFOSSATE e molli, spesso con anelli e "
                 "puntini scuri al centro; con l'umidità compare una massa rosata o arancione di spore.",
        "fix": ["Raccogli presto i frutti maturi e elimina quelli colpiti: la malattia peggiora con frutti stramaturi.",
                PRODUCT_RULE],
        "prevent": ["Pacciamatura e tutori: i frutti non devono toccare il terreno.",
                    "Rotazione e eliminazione dei residui; irrigazione a goccia invece che a pioggia."],
        "verify": ["Le macchie sono rotonde, infossate e solo sui frutti maturi? Con una lente cerca i puntini scuri al centro."],
        "sources": [_uc("anthracnose", "Antracnosi")],
    },
    "grey_mould": {
        "name": "Muffa grigia (Botrytis)", "category": "disease", "urgency": "medium",
        "signs": "Marciume MOLLE e acquoso coperto da una muffa GRIGIA e polverosa; spesso parte da ferite, fiori secchi o "
                 "dal calice. Frequente in serra e con umidità alta. Colpisce moltissime colture.",
        "fix": ["Togli con cura le parti colpite senza scuoterle (le spore si spargono) e portale fuori dalla serra o dal campo.",
                "Arieggia e abbassa l'umidità; evita ferite durante la potatura.", PRODUCT_RULE],
        "prevent": ["Buona aerazione, niente eccesso di azoto, potature con tagli netti nelle giornate asciutte."],
        "verify": ["La muffa grigia polverosa che si solleva quando tocchi è il segno tipico."],
        "sources": [_uc("gray-mold", "Muffa grigia")],
    },
    "bacterial_wilt": {
        "name": "Avvizzimento batterico (Ralstonia solanacearum)", "category": "disease", "urgency": "high",
        "signs": "La pianta appassisce di colpo nelle ore calde anche con terreno umido, prima le foglie giovani, e "
                 "non si riprende; tagliando il fusto alla base i vasi sono bruni e, in un bicchiere d'acqua, esce un "
                 "filo lattiginoso di batteri.",
        "fix": ["È un organismo da quarantena nell'UE: se lo sospetti avvisa subito il Servizio Fitosanitario Regionale.",
                "Non esistono cure: estirpa le piante colpite con le radici e il terreno attorno, senza spostarle in altri campi.",
                "Disinfetta attrezzi e stivali; non riusare l'acqua di drenaggio."],
        "prevent": ["Piantine certificate e innesti su portinnesti tolleranti; rotazione lunga con colture non ospiti.",
                    "Evita ferite alle radici e ristagni d'acqua; usa acqua di irrigazione pulita."],
        "verify": ["Test del bicchiere: un pezzo di fusto alla base, in acqua limpida, rilascia filamenti lattiginosi in pochi minuti.",
                   "La conferma ufficiale la dà il laboratorio del Servizio Fitosanitario."],
        "sources": [_uc("bacterial-wilt", "Avvizzimento batterico"),
                    {"title": "EPPO – Ralstonia solanacearum, organismo da quarantena nell'UE (Reg. 2019/2072)",
                     "url": "https://gd.eppo.int/taxon/RALSSL"}],
    },
    "fruit_cracking": {
        "name": "Spaccature dei frutti", "category": "abiotic", "urgency": "low",
        "signs": "Crepe a raggiera o ad anello attorno al picciolo, spesso dopo una pioggia forte o un'irrigazione abbondante "
                 "dopo un periodo secco.",
        "fix": ["Raccogli presto i frutti spaccati: dalle crepe entrano muffe e marciumi."],
        "prevent": ["Irrigazione regolare e pacciamatura; raccogli un po' prima della piena maturazione se sono previste piogge.",
                    "Varietà resistenti alle spaccature."],
        "verify": ["Se le crepe sono comparse subito dopo pioggia o irrigazione abbondante, la causa è l'acqua irregolare."],
        "sources": [_uc("fruit-cracking", "Spaccature dei frutti")],
    },
}

URGENCY_ORDER = {"high": 0, "medium": 1, "low": 2, "none": 3}


def sensor_checks(cause_id: str, ctx: dict) -> list[dict]:
    """Field measurements that support or weaken a cause. ctx values may be None."""
    sm, ph = ctx.get("soil_moisture"), ctx.get("soil_ph")
    t, rh = ctx.get("air_temperature"), ctx.get("air_humidity")
    out: list[dict] = []

    def add(effect: str, text: str):
        out.append({"effect": effect, "text": text})

    if cause_id == "water_stress" and sm is not None:
        if sm < 20:
            add("supports", f"Il terreno è secco (umidità {sm:.0f}%).")
        elif sm > 35:
            add("weakens", f"Il terreno ha acqua a sufficienza ({sm:.0f}%): la siccità è meno probabile.")
    if cause_id == "waterlogging" and sm is not None:
        if sm > 45:
            add("supports", f"Il terreno è molto bagnato (umidità {sm:.0f}%).")
        elif sm < 30:
            add("weakens", f"Il terreno non è saturo d'acqua ({sm:.0f}%).")
    if cause_id == "iron_chlorosis" and ph is not None:
        if ph > 7.5:
            add("supports", f"Il pH del terreno è alcalino ({ph:.1f}).")
        elif ph < 6.8:
            add("weakens", f"Il pH del terreno è {ph:.1f}: sotto 7 la clorosi ferrica è rara.")
    if cause_id in ("fungal_leaf_spot", "downy_mildew", "rust") and rh is not None:
        if rh > 80:
            add("supports", f"L'umidità dell'aria è alta ({rh:.0f}%), favorevole alle malattie fungine.")
        elif rh < 50:
            add("weakens", f"L'aria è secca ({rh:.0f}%), poco favorevole alle malattie fungine.")
    if cause_id == "heat_sunscald" and t is not None:
        if t > 32:
            add("supports", f"La temperatura dell'aria è alta ({t:.0f} °C).")
        elif t < 25:
            add("weakens", f"La temperatura attuale è moderata ({t:.0f} °C).")
    return out


def colour_candidates(color: dict) -> list[dict]:
    """Fallback when no vision model is available: possible causes from the colour pattern only."""
    y, b = color.get("chlorotic_yellow", 0), color.get("necrotic_brown", 0)
    why = "Solo dai colori della foto (senza intelligenza artificiale): è un indizio, non una diagnosi."
    if color.get("pattern") == "looks_healthy":
        return [{"id": "healthy", "likelihood": "low", "why": why}]
    cands = []
    if y >= b:
        cands += [{"id": "nitrogen_deficiency", "likelihood": "low", "why": why},
                  {"id": "water_stress", "likelihood": "low", "why": why},
                  {"id": "iron_chlorosis", "likelihood": "low", "why": why}]
    if b > 0.05:
        cands += [{"id": "fungal_leaf_spot", "likelihood": "low", "why": why},
                  {"id": "potassium_deficiency", "likelihood": "low", "why": why}]
    return cands
