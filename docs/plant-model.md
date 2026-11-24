# Modello immagini AGROAI (malattie delle piante)

## Come funziona
1. **DINOv2-small** (Meta, licenza Apache-2.0, ONNX su CPU) trasforma la foto in 768 numeri
   (token CLS + media dei patch). File: `backend/media/models/dinov2_small/model.onnx`.
2. Una **regressione logistica** addestrata sui dataset pubblici trasforma quei numeri in una classe
   «coltura/condizione» (`backend/app/ml/vision/plant_labels.py`).
3. Nella diagnosi il modello è **un indizio in più**, non il verdetto: il motore differenziale
   (`differential.py`) lo pesa in base all'accuratezza misurata su foto reali e lo ignora quando la coltura
   o l'organo (es. frutti di pomodoro) non erano nei dati di addestramento.

## Dataset usati
| Dataset | Licenza | Uso | Note |
|---|---|---|---|
| PlantDoc (Singh et al. 2020) | CC BY 4.0 | train + **test** (split ufficiale) | foto reali, foglie |
| PlantVillage (Mohanty et al. 2016) | CC BY-SA 3.0 | solo train (200 foto per classe) | foto di laboratorio, sfondo uniforme |
| MultiFruit-6D / ABCGMP (MNIT Jaipur) | CC BY 4.0 | train 80% + **test** 20% | frutti e foglie di melo e agrumi |
| Tomato Disease, Liu 2025 (Data in Brief 63:112032) | CC BY 4.0 | ritagli dei riquadri, split per foto | pomodoro in serra: muffa grigia su frutto e foglia, virosi, avvizzimento batterico |
| Citrus Fruits and Leaves (Rauf et al. 2019) | CC BY 4.0 | train 80% + test 20% | frutti e foglie di agrumi: macchia nera, cancro, greening, melanosi, scabbia |
| Comprehensive Vegetable Leaf Disease (Ikteshad et al. 2025) | CC BY 4.0 | train 80% + test 20% | broccolo, cavolo, cavolfiore, rapa |
| Unified Tomato Ripeness (Karkooti 2026, da 6 dataset Roboflow CC BY 4.0) | CC BY 4.0 | split ufficiale | pomodori **sani** (acerbi, invaiati, maturi) e **marci** |
| Fresh and Rotten Fruits (Sultana et al. 2022) | CC BY 4.0 | 160 per classe, 80/20 | mela, uva, arancia, fragola, melograno, banana, guava, giuggiola: sani e marci |
| DiaMOS Plant – pero (Fenu & Malloci 2021, Sardegna) | CC BY 4.0 | campione, 80/20 | pere sane in 4 fasi di crescita; foglie sane, septoriosi, accartocciate, lumache |

Preparazione dei dataset Hugging Face: `scripts/prepare_hf_datasets.py` (ritaglia i riquadri del dataset del
pomodoro, una parte di pianta per immagine).

Esclusi: **PlantWild** (CC BY-NC-ND, non commerciale e senza modifiche), **MangoFruitDDS** (CC BY-NC),
**Manalagi Apple** (nella versione pubblica le foto non hanno l'etichetta della classe), le cartelle
«Apple___Black_rot / Apple___healthy» di MultiFruit-6D (sembrano copie di PlantVillage).

CC BY-SA 3.0 (PlantVillage): il modello deriva anche da questi dati; in caso di distribuzione commerciale
citare gli autori e valutare con un legale l'obbligo di «condividi allo stesso modo».

## Dove sono i dati
Fuori da OneDrive (diversi GB): `C:\Users\armaa\agroai-data\datasets`
(`plantdoc/`, `plantvillage/raw/color/`, `multifruit6d/`, cache `dinov2_small_features.npz`).

## Riaddestrare
```
cd backend
.venv\Scripts\python.exe scripts\train_plant_model.py --data C:\Users\armaa\agroai-data\datasets
```
Ogni addestramento crea una nuova versione (`media/models/plant_clf/vN`) con `card.json`
(dataset, numeri di foto, accuratezza su foto reali, classi peggiori, confusioni più frequenti).
La versione usata dall'app cambia **solo** con `--activate` o da `POST /api/v1/vision/model/activate`.

## Risultati (v4, attiva) su foto reali mai viste in addestramento
| Gruppo di prova | Foto | Classe esatta | Tra le prime 3 | Causa giusta |
|---|---|---|---|---|
| Tutte | 1.813 | 90,3% | 98,8% | 94,0% |
| PlantDoc + MultiFruit (la prova più dura, uguale per tutte le versioni) | 375 | 73,3% | 96,0% | 87,2% |
| Frutti (tutte le specie) | 875 | 93,1% | 99,8% | 95,7% |
| Frutti di pomodoro (sani / marci / muffa grigia) | 236 | 90,7% | 100% | 90,7% |
| Foglie di pomodoro | 723 | 90,6% | 98,1% | 92,8% |

Storico sulla stessa prova dura (causa giusta): v2 84,8% → v3 86,4% → **v4 87,2%**.
I valori su pomodoro in serra, frutti e ortaggi sono **probabilmente ottimistici** (stesse piante o lotti
fotografati più volte; 534 quasi-duplicati già tolti).

## Limiti noti e regole di sicurezza
- Sui frutti il modello conosce: sano/marcio di 10 frutti, malattie degli agrumi, muffa grigia del pomodoro.
  **Non conosce** peronospora, marciume apicale, scottatura e antracnosi **sul frutto**: su un pomodoro con
  peronospora risponde «muffa grigia 84%» (scelta tra le sole malattie che conosce). Perciò, nella diagnosi:
  - sui frutti il suo «sì» conta solo come indizio debole quando esistono malattie simili che non conosce;
  - può contare **contro** una causa solo se ha imparato a riconoscerla su quella parte della pianta;
  - le pere sono solo sane nei dati (nessuna malattia del frutto di pero).
- I frutti marci di Sultana et al. sono foto post-raccolta: utili per «sano/marcio», non per la malattia precisa.
- Le foto di PlantVillage sono di laboratorio: da sole funzionano male sulle foto vere (41%).
