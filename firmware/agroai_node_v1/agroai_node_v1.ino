/*
 * AgroAI Node v1 — field node firmware for Heltec WiFi LoRa 32 V3 (ESP32-S3 + SX1262)
 * Hardware: hardware/agroai-node-v1 (solar + 18650, IP65 box, radiation shield).
 *
 * STATUS: targets Arduino-ESP32 core 4.0 + RadioLib 8.0 (arduino-cli builds, see README).
 * NOT YET TESTED ON REAL HARDWARE. Use BENCH_MODE 1 on the table first (see README.md).
 *
 * Every SEND_INTERVAL_S the node wakes from deep sleep, powers the sensors (Vext), measures,
 * optionally runs one irrigation (latching valve, local rules from config.h), signs the
 * telemetry with HMAC-SHA256 and sends it over WiFi (HTTP) or LoRa (via agroai_lora_gateway),
 * then goes back to deep sleep. A rain-gauge tip wakes it just long enough to count.
 *
 * Libraries (Arduino Library Manager):
 *   - "RadioLib" (jgromes)                       if TRANSPORT == TRANSPORT_LORA
 *   - "OneWire" + "DallasTemperature"            if USE_DS18B20
 * Board: "Heltec WiFi LoRa 32(V3)" or "ESP32S3 Dev Module", esp32 by Espressif 3.x.
 * config.h: AgroAI dashboard → Dispositivi → hardware "AgroAI Node v1" → Crea chiave.
 */
#define TRANSPORT_WIFI 1
#define TRANSPORT_LORA 2

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <SPI.h>
#include <time.h>
#include <sys/time.h>
#include "mbedtls/md.h"
#include "esp_sleep.h"
#include "driver/rtc_io.h"
#include "driver/gpio.h"
#include "config.h"
#include "board_heltec_v3.h"
#include "agroai_protocol.h"

#define FIRMWARE_VERSION "agroai-node-v1-0.1.0"

// ---------------------------------------------------------------- defaults (override in config.h)
#ifndef TRANSPORT
#define TRANSPORT TRANSPORT_WIFI
#endif
#ifndef BENCH_MODE
#define BENCH_MODE 0
#endif
#ifndef SEND_INTERVAL_S
#define SEND_INTERVAL_S 600
#endif
#ifndef LOCAL_TZ
#define LOCAL_TZ "CET-1CEST,M3.5.0,M10.5.0/3"
#endif
#ifndef SENSOR_WARMUP_MS
#define SENSOR_WARMUP_MS 300
#endif
#ifndef BAT_DIVIDER
#define BAT_DIVIDER 4.9
#endif
#ifndef BAT_ADC_CTRL_ON
#define BAT_ADC_CTRL_ON HIGH
#endif
#ifndef VALVE_COUNT
#define VALVE_COUNT 0
#endif
#ifndef VALVE_AUTO
#define VALVE_AUTO 0
#endif
#ifndef VALVE_PULSE_MS
#define VALVE_PULSE_MS 100
#endif
#ifndef VALVE_OPEN_FORWARD
#define VALVE_OPEN_FORWARD 1
#endif
#ifndef BOOST_EN_ON
#define BOOST_EN_ON HIGH
#endif
#ifndef BOOST_SETTLE_MS
#define BOOST_SETTLE_MS 300
#endif
#ifndef VALVE_MAX_RUN_S
#define VALVE_MAX_RUN_S 1800
#endif
#ifndef VALVE_MIN_BAT_V
#define VALVE_MIN_BAT_V 3.5
#endif
#ifndef NO_FLOW_TIMEOUT_S
#define NO_FLOW_TIMEOUT_S 60
#endif
#ifndef LORA_FREQ_MHZ
#define LORA_FREQ_MHZ 869.525
#endif
#ifndef LORA_BW_KHZ
#define LORA_BW_KHZ 125.0
#endif
#ifndef LORA_SF
#define LORA_SF 9
#endif
#ifndef LORA_TX_DBM
#define LORA_TX_DBM 14
#endif
#ifndef LORA_RX_WINDOW_MS
#define LORA_RX_WINDOW_MS 3000
#endif

#if USE_DS18B20
#include <OneWire.h>
#include <DallasTemperature.h>
OneWire oneWire(DS18B20_PIN);
DallasTemperature soilProbe(&oneWire);
#endif

#if TRANSPORT == TRANSPORT_LORA
#include <RadioLib.h>
SX1262 radio = new Module(LORA_NSS, LORA_DIO1, LORA_RST, LORA_BUSY);
volatile bool loraFlag = false;
void IRAM_ATTR onLoraDio1() { loraFlag = true; }
bool loraReady = false;
#endif

// ---------------------------------------------------------------- state kept across deep sleep
RTC_DATA_ATTR uint32_t rainTips = 0;       // tips not yet delivered
RTC_DATA_ATTR uint32_t nextSendTs = 0;     // unix time of the next scheduled cycle
RTC_DATA_ATTR uint32_t bootCount = 0;
RTC_DATA_ATTR uint32_t irrDayKey = 0;      // local day of dailyRunS
RTC_DATA_ATTR uint32_t dailyRunS = 0;      // irrigation seconds today
RTC_DATA_ATTR bool valveOpen[2] = {false, false};

volatile uint32_t flowPulses = 0;
void IRAM_ATTR onFlowPulse() { flowPulses = flowPulses + 1; }
bool boostOn = false;

// ---------------------------------------------------------------- time + signing
bool timeReady() { return time(nullptr) > 1700000000; }

// SHA-256 over up to three buffers (plain mbedtls_md API: present in core 3.x and 4.x).
static void sha256Parts(const uint8_t* a, size_t al, const uint8_t* b, size_t bl, const uint8_t* c, size_t cl,
                        uint8_t out[32]) {
  mbedtls_md_context_t ctx;
  mbedtls_md_init(&ctx);
  mbedtls_md_setup(&ctx, mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), 0);
  mbedtls_md_starts(&ctx);
  if (al) mbedtls_md_update(&ctx, a, al);
  if (bl) mbedtls_md_update(&ctx, b, bl);
  if (cl) mbedtls_md_update(&ctx, c, cl);
  mbedtls_md_finish(&ctx, out);
  mbedtls_md_free(&ctx);
}

// HMAC-SHA256 (RFC 2104) built on SHA-256: core 4.x (mbedtls 4) removed mbedtls_md_hmac_*.
void hmacRaw(const String& ts, const String& body, uint8_t out[32]) {
  String prefix = ts + ".";  // Signature = HMAC(secret, "<ts>." + body)
  uint8_t key[64] = {0}, ipad[64], opad[64], inner[32];
  size_t kl = strlen(DEVICE_SECRET);
  if (kl > 64) sha256Parts((const uint8_t*)DEVICE_SECRET, kl, nullptr, 0, nullptr, 0, key);
  else memcpy(key, DEVICE_SECRET, kl);
  for (int i = 0; i < 64; i++) { ipad[i] = key[i] ^ 0x36; opad[i] = key[i] ^ 0x5c; }
  sha256Parts(ipad, 64, (const uint8_t*)prefix.c_str(), prefix.length(), (const uint8_t*)body.c_str(),
              body.length(), inner);
  sha256Parts(opad, 64, inner, 32, nullptr, 0, out);
}

String toHex(const uint8_t* b, size_t n) {
  char hex[3];
  String s;
  for (size_t i = 0; i < n; i++) { sprintf(hex, "%02x", b[i]); s += hex; }
  return s;
}

void setClock(uint32_t ts) {
  struct timeval tv = {(time_t)ts, 0};
  settimeofday(&tv, nullptr);
}

// ---------------------------------------------------------------- power rails + valves
void vext(bool on) {
  pinMode(VEXT_CTRL, OUTPUT);
  digitalWrite(VEXT_CTRL, on ? LOW : HIGH);
}

void boost(bool on) {
  digitalWrite(BOOST_EN, on ? BOOST_EN_ON : !BOOST_EN_ON);
  boostOn = on;
}

void valvePins(uint8_t v, uint8_t& a, uint8_t& b) {
  a = v == 0 ? VALVE1_IN1 : VALVE2_IN1;
  b = v == 0 ? VALVE1_IN2 : VALVE2_IN2;
}

// Latching solenoid: a short pulse one way opens, the other way closes; no power while it stays.
void valvePulse(uint8_t v, bool open) {
  uint8_t a, b;
  valvePins(v, a, b);
  bool wasOn = boostOn;
  if (!wasOn) { boost(true); delay(BOOST_SETTLE_MS); }
  bool fwd = (open == (bool)VALVE_OPEN_FORWARD);
  digitalWrite(a, fwd ? HIGH : LOW);
  digitalWrite(b, fwd ? LOW : HIGH);
  delay(VALVE_PULSE_MS);
  digitalWrite(a, LOW);
  digitalWrite(b, LOW);
  if (!wasOn) boost(false);
  valveOpen[v] = open;
  Serial.printf("valve %u -> %s\n", v + 1, open ? "OPEN" : "CLOSED");
}

void initOutputs() {
  const uint8_t outs[] = {BOOST_EN, VALVE1_IN1, VALVE1_IN2, VALVE2_IN1, VALVE2_IN2};
  for (uint8_t p : outs) {
    gpio_hold_dis((gpio_num_t)p);
    pinMode(p, OUTPUT);
    digitalWrite(p, LOW);
  }
  boost(false);
}

void holdOutputsForSleep() {
  const uint8_t outs[] = {BOOST_EN, VALVE1_IN1, VALVE1_IN2, VALVE2_IN1, VALVE2_IN2};
  for (uint8_t p : outs) gpio_hold_en((gpio_num_t)p);
  gpio_deep_sleep_hold_en();
}

// ---------------------------------------------------------------- sensors
float readSoilMoisture() {
#if USE_SOIL_MOISTURE
  long acc = 0;
  for (int i = 0; i < 16; i++) { acc += analogRead(SOIL_MOISTURE_PIN); delay(5); }
  float raw = acc / 16.0;
  if (raw < 50 || raw > 4050) return NAN;  // disconnected / shorted probe
  float pct = (SOIL_RAW_DRY - raw) * 100.0 / (SOIL_RAW_DRY - SOIL_RAW_WET);
  return constrain(pct, 0.0, 100.0);
#else
  return NAN;
#endif
}

uint8_t sensirionCrc(const uint8_t* d) {
  uint8_t crc = 0xFF;
  for (int i = 0; i < 2; i++) {
    crc ^= d[i];
    for (int b = 0; b < 8; b++) crc = (crc & 0x80) ? (crc << 1) ^ 0x31 : (crc << 1);
  }
  return crc;
}

// SHT40: command 0xFD = high precision measurement (Sensirion SHT4x datasheet).
bool readSHT40(float& t, float& rh) {
  Wire.beginTransmission(0x44);
  Wire.write(0xFD);
  if (Wire.endTransmission() != 0) return false;
  delay(10);
  uint8_t d[6];
  if (Wire.requestFrom(0x44, 6) != 6) return false;
  for (int i = 0; i < 6; i++) d[i] = Wire.read();
  if (sensirionCrc(d) != d[2] || sensirionCrc(d + 3) != d[5]) return false;
  uint16_t rt = (d[0] << 8) | d[1], rr = (d[3] << 8) | d[4];
  t = -45.0 + 175.0 * rt / 65535.0;
  rh = constrain(-6.0 + 125.0 * rr / 65535.0, 0.0, 100.0);
  return true;
}

// BH1750: power on (0x01), one-time high-resolution mode (0x20), lux = raw / 1.2 (datasheet).
float readBH1750() {
  Wire.beginTransmission(0x23);
  Wire.write(0x01);
  if (Wire.endTransmission() != 0) return NAN;
  Wire.beginTransmission(0x23);
  Wire.write(0x20);
  if (Wire.endTransmission() != 0) return NAN;
  delay(180);
  if (Wire.requestFrom(0x23, 2) != 2) return NAN;
  uint16_t raw = (Wire.read() << 8) | Wire.read();
  return raw / 1.2;
}

float readBattery() {
#if USE_BATTERY
  pinMode(VBAT_ADC_CTRL, OUTPUT);
  digitalWrite(VBAT_ADC_CTRL, BAT_ADC_CTRL_ON);
  delay(10);
  uint32_t mv = 0;
  for (int i = 0; i < 8; i++) mv += analogReadMilliVolts(VBAT_ADC);
  digitalWrite(VBAT_ADC_CTRL, !BAT_ADC_CTRL_ON);
  float v = (mv / 8.0) * BAT_DIVIDER / 1000.0;
  if (v < 2.5 || v > 4.5) {  // not a plausible 18650 voltage: wrong divider polarity or no battery
    Serial.printf("battery reading %.2f V not plausible — check BAT_ADC_CTRL_ON / BAT_DIVIDER\n", v);
    return NAN;
  }
  return v;
#else
  return NAN;
#endif
}

void readSensors(AgValues& vals) {
  vext(true);
  delay(SENSOR_WARMUP_MS);
  vals.set(F_SOIL_MOISTURE, readSoilMoisture());
#if USE_DS18B20
  soilProbe.begin();
  soilProbe.requestTemperatures();
  float st = soilProbe.getTempCByIndex(0);
  vals.set(F_SOIL_TEMPERATURE, st == DEVICE_DISCONNECTED_C ? NAN : st);
#endif
#if USE_SHT40 || USE_BH1750
  Wire.begin(I2C_SDA, I2C_SCL, 100000);
#endif
#if USE_SHT40
  float t, rh;
  if (readSHT40(t, rh)) {
    vals.set(F_AIR_TEMPERATURE, t);
    vals.set(F_AIR_HUMIDITY, rh);
  } else {
    Serial.println("SHT40 not responding");
  }
#endif
#if USE_BH1750
  vals.set(F_LIGHT, readBH1750());
#endif
#if USE_SHT40 || USE_BH1750
  Wire.end();
#endif
  vext(false);
#if USE_RAIN_GAUGE
  vals.set(F_RAINFALL, rainTips * RAIN_MM_PER_TIP);
#endif
  vals.set(F_BATTERY, readBattery());
}

// ---------------------------------------------------------------- irrigation (local rules)
uint32_t localDayKey(int* hourOut) {
  time_t now = time(nullptr);
  struct tm lt;
  localtime_r(&now, &lt);
  if (hourOut) *hourOut = lt.tm_hour;
  return (lt.tm_year + 1900) * 1000 + lt.tm_yday;
}

uint32_t irrigationSeconds(const AgValues& v) {
#if VALVE_COUNT > 0 && VALVE_AUTO
  if (!v.has(F_SOIL_MOISTURE)) { Serial.println("irrigation: no soil reading -> skip"); return 0; }
  if (v.v[F_SOIL_MOISTURE] >= VALVE_ON_BELOW_PCT) return 0;
  if (rainTips > 0) { Serial.println("irrigation: rain since last cycle -> skip"); return 0; }
  if (!timeReady()) { Serial.println("irrigation: no clock -> skip"); return 0; }
  if (v.has(F_BATTERY) && v.v[F_BATTERY] < VALVE_MIN_BAT_V) { Serial.println("irrigation: battery low -> skip"); return 0; }
  int hour;
  uint32_t day = localDayKey(&hour);
  if (hour < IRR_START_HOUR || hour >= IRR_END_HOUR) return 0;
  if (day != irrDayKey) { irrDayKey = day; dailyRunS = 0; }
  if (dailyRunS >= VALVE_MAX_DAILY_S) { Serial.println("irrigation: daily limit reached"); return 0; }
  uint32_t s = VALVE_RUN_S;
  s = min<uint32_t>(s, VALVE_MAX_RUN_S);
  s = min<uint32_t>(s, VALVE_MAX_DAILY_S - dailyRunS);
  return s;
#else
  return 0;
#endif
}

// Opens valve 1, stays awake (radio off) counting flow, always closes at the end.
void runIrrigation(uint32_t seconds, AgValues& vals) {
#if VALVE_COUNT > 0
  Serial.printf("irrigation: %lu s\n", (unsigned long)seconds);
  boost(true);  // also feeds the flow meter
  delay(BOOST_SETTLE_MS);
#if USE_FLOW_METER
  flowPulses = 0;
  pinMode(FLOW_PIN, INPUT);
  attachInterrupt(digitalPinToInterrupt(FLOW_PIN), onFlowPulse, FALLING);
#endif
  valvePulse(0, true);
  uint32_t start = millis(), elapsed = 0;
  while (elapsed < seconds) {
    delay(1000);
    elapsed = (millis() - start) / 1000;
#if USE_FLOW_METER
    if (elapsed >= NO_FLOW_TIMEOUT_S && flowPulses == 0) {
      Serial.println("irrigation: NO FLOW detected -> closing (dry line, closed tap or broken valve?)");
      break;
    }
#endif
  }
  valvePulse(0, false);
#if USE_FLOW_METER
  detachInterrupt(digitalPinToInterrupt(FLOW_PIN));
  vals.set(F_IRR_WATER, flowPulses / (float)FLOW_PULSES_PER_L);
#endif
  boost(false);
  dailyRunS += elapsed;
  vals.set(F_IRR_TIME, elapsed / 60.0);
#endif
}

// ---------------------------------------------------------------- transport: WiFi
#if TRANSPORT == TRANSPORT_WIFI
bool wifiUp() {
  if (WiFi.status() == WL_CONNECTED) return true;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  for (int i = 0; i < 30 && WiFi.status() != WL_CONNECTED; i++) delay(500);
  Serial.println(WiFi.status() == WL_CONNECTED ? "WiFi ok " + WiFi.localIP().toString() : "WiFi FAILED");
  return WiFi.status() == WL_CONNECTED;
}

bool syncTime() {
  if (!wifiUp()) return timeReady();
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  for (int i = 0; i < 20 && !timeReady(); i++) delay(250);
  setenv("TZ", LOCAL_TZ, 1);  // configTime resets TZ
  tzset();
  return timeReady();
}

bool sendTelemetry(const AgValues& vals) {
  if (!wifiUp() || !timeReady()) return false;
  uint32_t ts = time(nullptr);
  String json = buildTelemetryJson(DEVICE_ID, FARM_ID, ZONE_ID, ts, vals);
  uint8_t sig[32];
  hmacRaw(String(ts), json, sig);
  HTTPClient http;
  http.begin(String(AGROAI_SERVER) + "/api/v1/telemetry");
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-AGROAI-Timestamp", String(ts));
  http.addHeader("X-AGROAI-Signature", toHex(sig, 32));
  int code = http.POST(json);
  Serial.printf("telemetry -> %d %s\n", code, http.getString().c_str());
  http.end();
  return code == 200;
}

void radioOff() { WiFi.disconnect(true); WiFi.mode(WIFI_OFF); }
#endif

// ---------------------------------------------------------------- transport: LoRa
#if TRANSPORT == TRANSPORT_LORA
bool loraBegin() {
  if (loraReady) return true;
  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_NSS);
  radio.tcxoVoltage = Voltage1V8;  // Heltec V3: SX1262 with 1.8 V TCXO (RadioLib 8.x API)
  ConfigLoRa_t cfg;                // syncWord default = private 0x12
  cfg.frequency = (uint32_t)(LORA_FREQ_MHZ * 1000000.0 + 0.5);
  cfg.bandwidth = (uint32_t)(LORA_BW_KHZ * 1000.0 + 0.5);
  cfg.spreadingFactor = LORA_SF;
  cfg.codingRate = 5;              // 4/5
  cfg.power = LORA_TX_DBM;
  cfg.preambleLength = 8;
  int st = radio.begin(cfg);
  if (st != RADIOLIB_ERR_NONE) { Serial.printf("LoRa init failed %d\n", st); return false; }
  radio.setDio1Action(onLoraDio1);
  loraReady = true;
  return true;
}

// Sends a packet, then listens for the gateway's time reply (which also confirms reception).
bool loraExchange(const uint8_t* pkt, size_t n) {
  if (!loraBegin()) return false;
  int st = radio.transmit((uint8_t*)pkt, n);
  if (st != RADIOLIB_ERR_NONE) { Serial.printf("LoRa tx failed %d\n", st); return false; }
  loraFlag = false;
  radio.startReceive();
  uint32_t t0 = millis();
  while (millis() - t0 < LORA_RX_WINDOW_MS) {
    if (loraFlag) {
      loraFlag = false;
      uint8_t buf[AG_MAX_PACKET];
      size_t len = radio.getPacketLength();
      if (len > sizeof(buf)) len = sizeof(buf);
      if (radio.readData(buf, len) == RADIOLIB_ERR_NONE && len >= 8 && buf[0] == 'A' && buf[1] == 'G' &&
          buf[2] == AG_PROTO_VERSION && buf[3] == AG_PKT_TIME) {
        uint32_t ts = agGetU32(buf + 4);
        if (ts > 1700000000) setClock(ts);
        Serial.printf("gateway ack, RSSI %.0f dBm, SNR %.1f dB\n", radio.getRSSI(), radio.getSNR());
        return true;
      }
      radio.startReceive();
    }
    delay(5);
  }
  Serial.println("no gateway reply");
  return false;
}

bool syncTime() {
  if (timeReady()) return true;
  uint8_t pkt[80];
  size_t n = 0;
  pkt[n++] = 'A'; pkt[n++] = 'G'; pkt[n++] = AG_PROTO_VERSION; pkt[n++] = AG_PKT_TIME_REQ;
  agPutStr(pkt, n, DEVICE_ID);
  for (int i = 0; i < 3 && !timeReady(); i++) loraExchange(pkt, n);
  return timeReady();
}

bool sendTelemetry(const AgValues& vals) {
  if (!timeReady()) return false;
  uint32_t ts = time(nullptr);
  String json = buildTelemetryJson(DEVICE_ID, FARM_ID, ZONE_ID, ts, vals);
  uint8_t sig[32], pkt[AG_MAX_PACKET];
  hmacRaw(String(ts), json, sig);
  size_t n = agEncodeTelemetry(pkt, DEVICE_ID, FARM_ID, ZONE_ID, ts, vals, sig);
  if (!n) { Serial.println("packet too large: shorten DEVICE_ID/FARM_ID/ZONE_ID"); return false; }
  Serial.printf("LoRa telemetry %u bytes: %s\n", (unsigned)n, json.c_str());
  return loraExchange(pkt, n);
}

void radioOff() {
  if (loraReady) radio.sleep();
  WiFi.mode(WIFI_OFF);
}
#endif

// ---------------------------------------------------------------- one cycle + sleep
void runCycle() {
  bootCount++;
  syncTime();
  AgValues vals;
  readSensors(vals);
  uint32_t irr = irrigationSeconds(vals);
  if (irr > 0) {
    radioOff();  // nothing to transmit while watering
    runIrrigation(irr, vals);
  }
#if VALVE_COUNT > 0
  if (!vals.has(F_IRR_TIME)) vals.set(F_IRR_TIME, 0);  // valve stayed closed this cycle
#endif
  if (vals.mask == 0) { Serial.println("no sensor values — nothing sent"); return; }
  if (sendTelemetry(vals)) rainTips = 0;  // tips stay counted until they are delivered
}

void sleepUntilNext() {
  radioOff();
  vext(false);
  uint32_t now = time(nullptr);
  if (!timeReady() || nextSendTs <= now) nextSendTs = (timeReady() ? now : 0) + SEND_INTERVAL_S;
  uint32_t sleepS = timeReady() ? max<int32_t>(5, (int32_t)(nextSendTs - now)) : SEND_INTERVAL_S;
  esp_sleep_enable_timer_wakeup((uint64_t)sleepS * 1000000ULL);
#if USE_RAIN_GAUGE
  if (digitalRead(RAIN_PIN) == HIGH) {  // never arm on a stuck-closed reed (endless wake-ups)
    esp_sleep_pd_config(ESP_PD_DOMAIN_RTC_PERIPH, ESP_PD_OPTION_ON);
    rtc_gpio_pullup_en((gpio_num_t)RAIN_PIN);
    rtc_gpio_pulldown_dis((gpio_num_t)RAIN_PIN);
    esp_sleep_enable_ext0_wakeup((gpio_num_t)RAIN_PIN, 0);
  }
#endif
  holdOutputsForSleep();
  Serial.printf("sleep %lu s\n", (unsigned long)sleepS);
  Serial.flush();
  esp_deep_sleep_start();
}

// ---------------------------------------------------------------- bench mode (USB, no sleep)
#if BENCH_MODE
void benchLoop() {
  Serial.println("BENCH MODE: r=read  s=send  o/c=open/close valve 1  f=flow pulses  t=time");
  for (;;) {
    if (Serial.available()) {
      char c = Serial.read();
      AgValues vals;
      if (c == 'r' || c == 's') {
        readSensors(vals);
        if (c == 'r') Serial.println(buildTelemetryJson(DEVICE_ID, FARM_ID, ZONE_ID, time(nullptr), vals));
        else { syncTime(); Serial.println(sendTelemetry(vals) ? "sent" : "send failed"); }
      }
#if VALVE_COUNT > 0
      if (c == 'o') valvePulse(0, true);
      if (c == 'c') valvePulse(0, false);
#endif
      if (c == 'f') Serial.printf("flow pulses %lu\n", (unsigned long)flowPulses);
      if (c == 't') Serial.println(syncTime() ? agIsoFromTs(time(nullptr)) : "no clock");
    }
    delay(20);
  }
}
#endif

// ---------------------------------------------------------------- main
void setup() {
  Serial.begin(115200);
  delay(50);
  analogReadResolution(12);
  setenv("TZ", LOCAL_TZ, 1);
  tzset();
  initOutputs();
  vext(false);
#if USE_RAIN_GAUGE
  rtc_gpio_deinit((gpio_num_t)RAIN_PIN);
  pinMode(RAIN_PIN, INPUT_PULLUP);
#endif

  uint32_t causes = esp_sleep_get_wakeup_causes();  // bitmask (core 4.x API)
  bool rainWake = causes & (1UL << ESP_SLEEP_WAKEUP_EXT0);
  (void)rainWake;
  if (esp_reset_reason() != ESP_RST_DEEPSLEEP) {
    Serial.println("\nAgroAI " FIRMWARE_VERSION " / " DEVICE_ID " — cold boot");
#if VALVE_COUNT > 0
    // Safety: after any reset (power loss, brownout, crash) we do not know the valve state -> close.
    delay(2000);
    for (uint8_t v = 0; v < VALVE_COUNT; v++) valvePulse(v, false);
#endif
  }

#if USE_RAIN_GAUGE
  if (rainWake) {
    rainTips++;
    uint32_t t0 = millis();
    while (digitalRead(RAIN_PIN) == LOW && millis() - t0 < 500) delay(5);  // debounce / wait release
    delay(50);
    if (timeReady() && (uint32_t)time(nullptr) + 5 < nextSendTs) sleepUntilNext();  // just count it
  }
#endif

#if BENCH_MODE
  benchLoop();
#endif
  runCycle();
  nextSendTs = (timeReady() ? (uint32_t)time(nullptr) : 0) + SEND_INTERVAL_S;
  sleepUntilNext();
}

void loop() {}  // never reached: every cycle ends in deep sleep
