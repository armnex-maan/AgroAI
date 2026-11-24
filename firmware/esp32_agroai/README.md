# AGROAI ESP32 field node

> Status: written against Arduino-ESP32 core 3.x APIs. **Not yet compiled or tested on real hardware.**
> Validate on a bench before deploying in the field.

## Bill of materials (indicative)

| Part | Measures | Notes |
|---|---|---|
| ESP32 DevKit (ESP32-WROOM-32, or a WROVER with PSRAM for audio) | — | WROVER recommended if `USE_I2S_MIC` |
| Capacitive soil moisture sensor v1.2 | soil moisture (%) | Calibrate dry/wet raw values |
| DHT22 (or SHT31 for better accuracy) | air temperature, humidity | Keep in a radiation shield |
| DS18B20 waterproof probe | soil temperature | 4.7 kΩ pull-up on data line |
| Tipping-bucket rain gauge (reed switch) | rainfall (mm) | Set `RAIN_MM_PER_TIP` from the gauge datasheet |
| INMP441 I2S MEMS microphone | airborne sound | L/R pin to GND (left channel) |
| Piezo contact disc + preamp + I2S ADC | ground vibration | For underground research; future firmware |

## Wiring (defaults in `config.h`)

| Signal | GPIO |
|---|---|
| Soil moisture AOUT | 34 (ADC1) |
| DHT22 DATA | 4 |
| DS18B20 DATA | 5 |
| Rain gauge | 27 (to GND via reed switch) |
| LDR divider | 35 |
| INMP441 SCK / WS / SD | 26 / 25 / 33 |

Use ADC1 pins only (32–39): ADC2 does not work while Wi-Fi is on.

## Flashing

1. Arduino IDE → Boards Manager → install **esp32 by Espressif (3.x)**.
2. Install the libraries listed at the top of `esp32_agroai.ino`.
3. In the AGROAI dashboard: **Devices → Add device (source: device) → Provision**.
   Download the generated `config.h` and place it next to the `.ino`.
4. Edit `WIFI_SSID` / `WIFI_PASSWORD` in `config.h`.
5. Upload, open Serial Monitor at 115200 baud.

The PC running AGROAI must be reachable from the ESP32 (same network, Windows firewall
allowing inbound TCP 8000). The dashboard shows the LAN URL to use.

## Security

- Each device has its own secret (shown once at provisioning). Re-provision to rotate it.
- Every request is signed: `HMAC-SHA256(secret, "<unix_ts>." + body)` in
  `X-AGROAI-Signature`, with `X-AGROAI-Timestamp`. Requests older than 5 minutes are rejected,
  so the node needs NTP time.
- The node sends only values it actually measured; a failed sensor is omitted, never zero-filled.

## MQTT (optional)

Publish to `agroai/<farm_id>/<device_id>/telemetry` with
`{"ts": "<unix>", "sig": "<hex>", "body": "<telemetry JSON string>"}` and run
`python -m app.integrations.mqtt_bridge` against a Mosquitto broker.
The HTTP path above needs no broker and is the default.
