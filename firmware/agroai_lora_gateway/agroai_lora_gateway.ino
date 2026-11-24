/*
 * AgroAI LoRa gateway — Heltec WiFi LoRa 32 V3 kept indoors on USB power.
 *
 * STATUS: targets Arduino-ESP32 core 4.0 + RadioLib 8.0. NOT YET TESTED ON REAL HARDWARE.
 *
 * Receives AgroAI Node v1 packets over LoRa, answers each one with the current time (the nodes
 * have no internet clock), rebuilds the node's telemetry JSON with agroai_protocol.h and POSTs it
 * to the AgroAI backend with the node's own timestamp + HMAC signature.
 * The gateway holds NO device secrets: it cannot forge data, it only forwards it.
 *
 * Libraries: "RadioLib" (jgromes). Copy config.example.h to config.h and fill it in.
 */
#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <SPI.h>
#include <time.h>
#include <RadioLib.h>
#include "config.h"
#include "agroai_protocol.h"

#define GW_VERSION "agroai-lora-gw-0.1.0"

// Heltec V3 on-board SX1262
#define LORA_NSS  8
#define LORA_SCK  9
#define LORA_MOSI 10
#define LORA_MISO 11
#define LORA_RST  12
#define LORA_BUSY 13
#define LORA_DIO1 14

SX1262 radio = new Module(LORA_NSS, LORA_DIO1, LORA_RST, LORA_BUSY);
volatile bool loraFlag = false;
void IRAM_ATTR onLoraDio1() { loraFlag = true; }

uint32_t forwarded = 0, rejected = 0;

bool timeReady() { return time(nullptr) > 1700000000; }

void wifiUp() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) delay(500);
  Serial.println(WiFi.status() == WL_CONNECTED ? "WiFi ok " + WiFi.localIP().toString() : "WiFi FAILED");
}

void replyTime() {
  if (!timeReady()) return;  // never hand out a wrong clock
  uint8_t pkt[8] = {'A', 'G', AG_PROTO_VERSION, AG_PKT_TIME};
  agPutU32(pkt + 4, (uint32_t)time(nullptr));
  delay(50);  // let the node switch from TX to RX
  radio.transmit(pkt, sizeof(pkt));
}

void forward(const char* id, const char* farm, const char* zone, uint32_t ts, const AgValues& vals,
             const uint8_t sig[32]) {
  String json = buildTelemetryJson(id, farm, zone, ts, vals);
  char hex[65];
  for (int i = 0; i < 32; i++) sprintf(hex + i * 2, "%02x", sig[i]);
  hex[64] = 0;
  wifiUp();
  HTTPClient http;
  http.begin(String(AGROAI_SERVER) + "/api/v1/telemetry");
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-AGROAI-Timestamp", String(ts));
  http.addHeader("X-AGROAI-Signature", hex);
  int code = http.POST(json);
  Serial.printf("  -> server %d %s\n", code, http.getString().c_str());
  http.end();
  if (code == 200) forwarded++; else rejected++;
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n" GW_VERSION);
  wifiUp();
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  for (int i = 0; i < 40 && !timeReady(); i++) delay(250);
  Serial.println(timeReady() ? "time " + agIsoFromTs(time(nullptr)) : "NTP FAILED — nodes will get no clock");

  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_NSS);
  radio.tcxoVoltage = Voltage1V8;  // Heltec V3: SX1262 with 1.8 V TCXO (RadioLib 8.x API)
  ConfigLoRa_t cfg;                // syncWord default = private 0x12, same as the nodes
  cfg.frequency = (uint32_t)(LORA_FREQ_MHZ * 1000000.0 + 0.5);
  cfg.bandwidth = (uint32_t)(LORA_BW_KHZ * 1000.0 + 0.5);
  cfg.spreadingFactor = LORA_SF;
  cfg.codingRate = 5;              // 4/5
  cfg.power = LORA_TX_DBM;
  cfg.preambleLength = 8;
  int st = radio.begin(cfg);
  if (st != RADIOLIB_ERR_NONE) {
    Serial.printf("LoRa init failed %d — halting\n", st);
    for (;;) delay(1000);
  }
  radio.setDio1Action(onLoraDio1);
  radio.startReceive();
  Serial.printf("listening %.3f MHz SF%d BW%.0f\n", (double)LORA_FREQ_MHZ, LORA_SF, (double)LORA_BW_KHZ);
}

void loop() {
  static uint32_t lastNtp = 0;
  if (millis() - lastNtp > 3600000UL) {  // keep WiFi + clock fresh
    wifiUp();
    configTime(0, 0, "pool.ntp.org", "time.google.com");
    lastNtp = millis();
  }
  if (!loraFlag) { delay(5); return; }
  loraFlag = false;

  uint8_t buf[AG_MAX_PACKET];
  size_t len = radio.getPacketLength();
  if (len > sizeof(buf)) len = sizeof(buf);
  int st = radio.readData(buf, len);
  float rssi = radio.getRSSI(), snr = radio.getSNR();
  if (st != RADIOLIB_ERR_NONE || len < 4 || buf[0] != 'A' || buf[1] != 'G' || buf[2] != AG_PROTO_VERSION) {
    radio.startReceive();
    return;  // not ours (or CRC error)
  }

  if (buf[3] == AG_PKT_TIME_REQ) {
    char id[65] = "";
    size_t n = 4;
    agGetStr(buf, len, n, id, sizeof(id));
    Serial.printf("time request from %s (RSSI %.0f, SNR %.1f)\n", id, rssi, snr);
    replyTime();
  } else if (buf[3] == AG_PKT_TELEMETRY) {
    char id[65], farm[65], zone[65];
    uint32_t ts;
    AgValues vals;
    uint8_t sig[32];
    if (agDecodeTelemetry(buf, len, id, farm, zone, ts, vals, sig)) {
      Serial.printf("telemetry from %s, %u bytes (RSSI %.0f, SNR %.1f)\n", id, (unsigned)len, rssi, snr);
      replyTime();
      forward(id, farm, zone, ts, vals, sig);
    } else {
      Serial.println("malformed telemetry packet");
    }
  }
  radio.startReceive();
}
