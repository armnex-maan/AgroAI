// Copy to config.h and fill in. The LoRa settings MUST match the nodes' config.h.
#pragma once

#define WIFI_SSID      "YOUR_WIFI_SSID"
#define WIFI_PASSWORD  "YOUR_WIFI_PASSWORD"
#define AGROAI_SERVER  "http://192.168.1.10:8000"   // the LAN URL shown in AgroAI → Dispositivi

// EU 869.4–869.65 MHz sub-band (check current national rules: duty cycle and power limits apply)
#define LORA_FREQ_MHZ  869.525
#define LORA_BW_KHZ    125.0
#define LORA_SF        9
#define LORA_TX_DBM    14
