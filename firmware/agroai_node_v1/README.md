# AgroAI Node v1 — firmware

> **Stato:** scritto per Arduino-ESP32 core 3.x + RadioLib 7.x. **Non ancora compilato né provato su hardware reale.**
> Prima di usarlo in campo: prova al banco con `BENCH_MODE 1`.

Hardware: [`hardware/agroai-node-v1`](../../hardware/agroai-node-v1/README.md) (Heltec WiFi LoRa 32 V3, pannello + 18650, scatola IP65).
Gateway LoRa: [`firmware/agroai_lora_gateway`](../agroai_lora_gateway).

## Cosa fa

Ogni `SEND_INTERVAL_S` (10 min di default) il nodo:
1. si sveglia dal deep sleep e accende i sensori (`Vext`);
2. misura: umidità e temperatura del suolo, aria (SHT40), luce in lux (BH1750), pioggia, batteria;
3. **se** `VALVE_AUTO 1`: irriga una volta con le regole di `config.h`;
4. firma i dati (HMAC-SHA256, chiave della scheda) e li invia via **WiFi** o **LoRa**;
5. torna in deep sleep. Una vaschetta del pluviometro lo sveglia solo per contarla.

Un sensore che non risponde viene **omesso**, mai sostituito con un valore inventato.

## Irrigazione: regole e sicurezze

Per default `VALVE_AUTO` è **0**: la valvola si muove solo a mano in modalità banco.
Con `VALVE_AUTO 1` la valvola 1 apre solo se valgono **tutte** queste condizioni:
- umidità del suolo misurata e sotto `VALVE_ON_BELOW_PCT`;
- nessuna pioggia dall'ultimo ciclo;
- orologio valido e ora locale dentro `IRR_START_HOUR`–`IRR_END_HOUR`;
- batteria sopra `VALVE_MIN_BAT_V`;
- limite giornaliero `VALVE_MAX_DAILY_S` non raggiunto.

La soglia `VALVE_ON_BELOW_PCT` la decidi tu per coltura e terreno: il valore 30 nel file è solo un segnaposto.

Sicurezze:
- **Tempo massimo** per ogni irrigazione (`VALVE_MAX_RUN_S`) e al giorno.
- Durante l'irrigazione il nodo **resta sveglio** e chiude sempre la valvola alla fine.
- **Nessun flusso** per `NO_FLOW_TIMEOUT_S` (con flussimetro) → chiude subito.
- **Dopo qualsiasi reset** (mancanza di corrente, brownout, crash) il nodo invia subito un impulso di **chiusura** a tutte le valvole.
- Durante il deep sleep i pin di valvole e boost restano bloccati a livello basso (`gpio_hold`).

⚠️ Limite fisico: una valvola latching rimane nello stato in cui si trova se la batteria muore proprio mentre è aperta.
Per questo esiste il limite giornaliero, e conviene un rubinetto a monte. Non è ancora un sistema certificato.

Dati inviati in più rispetto al firmware generico: `battery_voltage` (V), `irrigation_time` (min, 0 se la valvola è rimasta chiusa), `irrigation_water` (L, solo con flussimetro).

## LoRa: come funziona

- Il nodo non ha internet, quindi non può sincronizzare l'ora: **gliela dà il gateway**, che risponde a ogni pacchetto con l'ora attuale.
- Il nodo manda solo i numeri e la firma, in pacchetti di ~100–190 byte. Il gateway ricostruisce il JSON identico con `agroai_protocol.h` e lo inoltra al backend con la firma del nodo.
- **Il gateway non conosce le chiavi**: non può inventare dati.
- `agroai_protocol.h` deve essere **identico** nelle due cartelle. Se non lo è, il server risponde 401 e non salva nulla.
- I pacchetti non sono cifrati: chi è vicino può leggere le misure, ma non falsificarle.
- Default: 869,525 MHz, SF9, 14 dBm. Nella banda 869,4–869,65 MHz valgono limiti di duty cycle e potenza: verifica le regole nazionali in vigore.

## Passi

1. **AgroAI → Dispositivi → Aggiungi una scheda**:
   - Tipo di scheda: **AgroAI Node v1**;
   - Collegamento: WiFi o LoRa;
   - spunta i sensori montati: "Valvola" e "Flussimetro" attivano l'irrigazione, "Tensione batteria" la lettura della batteria.
2. **Crea chiave** → scarica `config.h` → mettilo in questa cartella. Per WiFi compila anche `WIFI_SSID`/`WIFI_PASSWORD`.
3. Arduino IDE:
   - Boards Manager → **esp32 by Espressif 3.x**;
   - Library Manager → **RadioLib**, **OneWire**, **DallasTemperature**;
   - scheda: *Heltec WiFi LoRa 32(V3)* (o *ESP32S3 Dev Module*).
4. **Banco**: in `config.h` metti `BENCH_MODE 1`, carica il programma e apri il monitor seriale a 115200 baud. Comandi disponibili:
   - `r` leggi sensori;
   - `s` invia;
   - `o` / `c` apri / chiudi valvola 1;
   - `f` impulsi flussimetro;
   - `t` ora.
5. **Calibra**:
   - `SOIL_RAW_DRY` e `SOIL_RAW_WET` (sonda all'aria / in acqua);
   - `BAT_DIVIDER` (confronta col multimetro; se legge ~0 V prova `BAT_ADC_CTRL_ON LOW`);
   - `FLOW_PULSES_PER_L` (con un secchio graduato);
   - `VALVE_OPEN_FORWARD` (se "apri" chiude, mettilo a 0).
6. Rimetti `BENCH_MODE 0` e ricarica: il nodo entra nel ciclo con deep sleep.
7. Solo dopo prove manuali riuscite: `VALVE_AUTO 1` con la tua soglia.

I pin sono in `board_heltec_v3.h`: **verificali sul pinout ufficiale Heltec V3 prima di saldare.**
