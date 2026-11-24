/*
 * AGROAI field node — ESP32 (Arduino core 3.x)
 *
 * Reads the sensors enabled in config.h, signs the telemetry with
 * HMAC-SHA256 (per-device secret) and POSTs it to the AGROAI API.
 * Optionally records a short WAV from an INMP441 I2S microphone and uploads it
 * to the Acoustic Lab.
 *
 * Libraries (Arduino Library Manager):
 *   - "DHT sensor library" (Adafruit) + "Adafruit Unified Sensor"   if USE_DHT22
 *   - "OneWire" + "DallasTemperature"                               if USE_DS18B20
 * ESP32 board package: "esp32" by Espressif, version 3.x.
 *
 * Generate config.h from the AGROAI dashboard: Devices → Provision.
 */
#include <WiFi.h>
#include <HTTPClient.h>
#include <time.h>
#include "mbedtls/md.h"
#include "config.h"

#if USE_DHT22
#include <DHT.h>
DHT dht(DHT_PIN, DHT22);
#endif

#if USE_DS18B20
#include <OneWire.h>
#include <DallasTemperature.h>
OneWire oneWire(DS18B20_PIN);
DallasTemperature soilProbe(&oneWire);
#endif

#if USE_I2S_MIC
#include <ESP_I2S.h>
I2SClass i2s;
#endif

#define FIRMWARE_VERSION "agroai-esp32-1.0.0"

#if USE_RAIN_GAUGE
volatile uint32_t rainTips = 0;
volatile uint32_t lastTipMs = 0;
void IRAM_ATTR onRainTip() {
  uint32_t now = millis();
  if (now - lastTipMs > 200) {  // debounce reed switch
    rainTips++;
    lastTipMs = now;
  }
}
#endif

static uint32_t lastSend = 0;
static uint32_t lastAudio = 0;

// ---------------------------------------------------------------- utils
String hmacHex(const String& key, const uint8_t* data1, size_t len1, const uint8_t* data2, size_t len2) {
  uint8_t out[32];
  mbedtls_md_context_t ctx;
  mbedtls_md_init(&ctx);
  mbedtls_md_setup(&ctx, mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), 1);
  mbedtls_md_hmac_starts(&ctx, (const unsigned char*)key.c_str(), key.length());
  mbedtls_md_hmac_update(&ctx, data1, len1);
  if (data2 && len2) mbedtls_md_hmac_update(&ctx, data2, len2);
  mbedtls_md_hmac_finish(&ctx, out);
  mbedtls_md_free(&ctx);
  char hex[65];
  for (int i = 0; i < 32; i++) sprintf(hex + i * 2, "%02x", out[i]);
  hex[64] = 0;
  return String(hex);
}

// Signature = HMAC(secret, "<ts>." + body)
String signBody(const String& ts, const uint8_t* body, size_t len) {
  String prefix = ts + ".";
  return hmacHex(DEVICE_SECRET, (const uint8_t*)prefix.c_str(), prefix.length(), body, len);
}

bool timeReady() { return time(nullptr) > 1700000000; }

String isoNow() {
  time_t now = time(nullptr);
  struct tm t;
  gmtime_r(&now, &t);
  char buf[25];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &t);
  return String(buf);
}

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("WiFi");
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(WiFi.status() == WL_CONNECTED ? " connected " + WiFi.localIP().toString() : " FAILED");
}

void addSensor(String& json, bool& first, const char* type, float value, const char* unit) {
  if (isnan(value)) return;  // never send invented values
  if (!first) json += ",";
  first = false;
  json += "\"";
  json += type;
  json += "\":{\"value\":";
  json += String(value, 2);
  json += ",\"unit\":\"";
  json += unit;
  json += "\"}";
}

// ---------------------------------------------------------------- sensors
float readSoilMoisture() {
#if USE_SOIL_MOISTURE
  long acc = 0;
  for (int i = 0; i < 16; i++) { acc += analogRead(SOIL_MOISTURE_PIN); delay(5); }
  float raw = acc / 16.0;
  float pct = (SOIL_RAW_DRY - raw) * 100.0 / (SOIL_RAW_DRY - SOIL_RAW_WET);
  return constrain(pct, 0.0, 100.0);
#else
  return NAN;
#endif
}

// ---------------------------------------------------------------- telemetry
bool sendTelemetry() {
  String json = "{\"device_id\":\"" DEVICE_ID "\",";
  if (strlen(FARM_ID)) json += "\"farm_id\":\"" FARM_ID "\",";
  if (strlen(ZONE_ID)) json += "\"zone_id\":\"" ZONE_ID "\",";
  json += "\"timestamp\":\"" + isoNow() + "\",\"source\":\"device\",\"sensors\":{";
  bool first = true;

  addSensor(json, first, "soil_moisture", readSoilMoisture(), "%");
#if USE_DHT22
  addSensor(json, first, "air_temperature", dht.readTemperature(), "C");
  addSensor(json, first, "air_humidity", dht.readHumidity(), "%");
#endif
#if USE_DS18B20
  soilProbe.requestTemperatures();
  float st = soilProbe.getTempCByIndex(0);
  addSensor(json, first, "soil_temperature", st == DEVICE_DISCONNECTED_C ? NAN : st, "C");
#endif
#if USE_RAIN_GAUGE
  noInterrupts();
  uint32_t tips = rainTips;
  rainTips = 0;
  interrupts();
  addSensor(json, first, "rainfall", tips * RAIN_MM_PER_TIP, "mm");
#endif
#if USE_LIGHT_LDR
  // Relative light level only — an LDR is not a calibrated lux meter.
  addSensor(json, first, "light_intensity", analogRead(LDR_PIN) * 100.0 / 4095.0, "%");
#endif
  json += "}}";

  if (first) {
    Serial.println("no sensor values — nothing sent");
    return false;
  }

  String ts = String((uint32_t)time(nullptr));
  String sig = signBody(ts, (const uint8_t*)json.c_str(), json.length());

  HTTPClient http;
  http.begin(String(AGROAI_SERVER) + "/api/v1/telemetry");
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-AGROAI-Timestamp", ts);
  http.addHeader("X-AGROAI-Signature", sig);
  int code = http.POST(json);
  Serial.printf("telemetry -> %d %s\n", code, http.getString().c_str());
  http.end();
  return code == 200;
}

// ---------------------------------------------------------------- audio
#if USE_I2S_MIC
bool sendAudio() {
  size_t wavSize = 0;
  uint8_t* wav = i2s.recordWAV(AUDIO_SECONDS, &wavSize);
  if (!wav || wavSize == 0) {
    Serial.println("audio: record failed");
    return false;
  }
  String ts = String((uint32_t)time(nullptr));
  String sig = signBody(ts, wav, wavSize);

  const String boundary = "----agroai" + ts;
  String head = "--" + boundary + "\r\nContent-Disposition: form-data; name=\"device_id\"\r\n\r\n" DEVICE_ID "\r\n";
  head += "--" + boundary + "\r\nContent-Disposition: form-data; name=\"source\"\r\n\r\ndevice\r\n";
  head += "--" + boundary + "\r\nContent-Disposition: form-data; name=\"file\"; filename=\"node.wav\"\r\n";
  head += "Content-Type: audio/wav\r\n\r\n";
  String tail = "\r\n--" + boundary + "--\r\n";

  size_t total = head.length() + wavSize + tail.length();
  uint8_t* body = (uint8_t*)ps_malloc(total);
  if (!body) body = (uint8_t*)malloc(total);
  if (!body) {
    free(wav);
    Serial.println("audio: out of memory");
    return false;
  }
  memcpy(body, head.c_str(), head.length());
  memcpy(body + head.length(), wav, wavSize);
  memcpy(body + head.length() + wavSize, tail.c_str(), tail.length());
  free(wav);

  HTTPClient http;
  http.begin(String(AGROAI_SERVER) + "/api/v1/audio/upload");
  http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);
  http.addHeader("X-AGROAI-Timestamp", ts);
  http.addHeader("X-AGROAI-Signature", sig);
  int code = http.POST(body, total);
  Serial.printf("audio -> %d\n", code);
  http.end();
  free(body);
  return code == 201;
}
#endif

// ---------------------------------------------------------------- main
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\nAGROAI node " FIRMWARE_VERSION " / " DEVICE_ID);
  analogReadResolution(12);
#if USE_DHT22
  dht.begin();
#endif
#if USE_DS18B20
  soilProbe.begin();
#endif
#if USE_RAIN_GAUGE
  pinMode(RAIN_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(RAIN_PIN), onRainTip, FALLING);
#endif
#if USE_I2S_MIC
  i2s.setPins(I2S_SCK_PIN, I2S_WS_PIN, -1, I2S_SD_PIN);
  if (!i2s.begin(I2S_MODE_STD, 16000, I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_MONO, I2S_STD_SLOT_LEFT)) {
    Serial.println("I2S init failed");
  }
#endif
  connectWiFi();
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  for (int i = 0; i < 30 && !timeReady(); i++) delay(500);
  Serial.println(timeReady() ? "time synced " + isoNow() : "NTP failed — server will reject unsigned clock");
}

void loop() {
  connectWiFi();
  uint32_t now = millis();
  if (WiFi.status() == WL_CONNECTED && timeReady()) {
    if (lastSend == 0 || now - lastSend >= SEND_INTERVAL_S * 1000UL) {
      sendTelemetry();
      lastSend = now;
    }
#if USE_I2S_MIC
    if (lastAudio == 0 || now - lastAudio >= AUDIO_INTERVAL_S * 1000UL) {
      sendAudio();
      lastAudio = now;
    }
#endif
  }
  delay(250);
}
