# AgroAI LoRa gateway

> **Stato:** non ancora compilato né provato su hardware reale.

Un secondo **Heltec WiFi LoRa 32 V3** che resta in casa, alimentato via USB e collegato al WiFi.

Cosa fa:
- riceve i pacchetti LoRa dei nodi AgroAI Node v1;
- risponde a ogni pacchetto con l'ora (sincronizzata via NTP);
- inoltra la telemetria al backend AgroAI con la firma originale del nodo.

Non conosce le chiavi dei nodi.

## Passi

1. Arduino IDE:
   - **esp32 by Espressif 3.x**;
   - libreria **RadioLib**.
2. Copia `config.example.h` in `config.h` e inserisci:
   - WiFi;
   - indirizzo del server (quello mostrato in AgroAI → Dispositivi).
   Le impostazioni LoRa devono essere **uguali** a quelle dei nodi.
3. Carica il programma e apri il monitor seriale a 115200 baud. Per ogni pacchetto vedrai il nodo che l'ha inviato, la qualità del segnale (RSSI/SNR) e la risposta del server (200 = salvato).
4. Metti il gateway in alto, vicino a una finestra verso i campi, con l'antenna verticale.

`agroai_protocol.h` deve restare **identico** a quello di `firmware/agroai_node_v1`.
