// AgroAI Node v1 <-> LoRa gateway protocol + telemetry JSON builder.
//
// !!! This file must be IDENTICAL in firmware/agroai_node_v1 and firmware/agroai_lora_gateway !!!
// The node signs the JSON produced by buildTelemetryJson(); over LoRa it sends only the
// numbers + the signature, and the gateway rebuilds the very same JSON with the very same
// function, so the server can verify the node's HMAC. If the two copies differ, the server
// answers 401 "bad signature" (safe failure: nothing wrong gets stored).
#pragma once
#include <Arduino.h>
#include <time.h>

#define AG_PROTO_VERSION 1
#define AG_PKT_TELEMETRY 1
#define AG_PKT_TIME_REQ  2
#define AG_PKT_TIME      3
#define AG_MAX_PACKET    255

// Index -> backend sensor type (backend/app/schemas/telemetry.py SENSOR_TYPES) and unit.
enum AgField : uint8_t {
  F_SOIL_MOISTURE = 0,
  F_SOIL_TEMPERATURE,
  F_AIR_TEMPERATURE,
  F_AIR_HUMIDITY,
  F_LIGHT,
  F_RAINFALL,
  F_BATTERY,
  F_IRR_WATER,
  F_IRR_TIME,
  F_COUNT
};

static const char* const AG_TYPES[F_COUNT] = {
  "soil_moisture", "soil_temperature", "air_temperature", "air_humidity",
  "light_intensity", "rainfall", "battery_voltage", "irrigation_water", "irrigation_time",
};
static const char* const AG_UNITS[F_COUNT] = {"%", "C", "C", "%", "lx", "mm", "V", "L", "min"};

struct AgValues {
  uint16_t mask = 0;  // bit i set = field i measured
  float v[F_COUNT];
  void set(AgField f, float value) {
    if (isnan(value)) return;  // never send invented values
    v[f] = value;
    mask |= (1u << f);
  }
  bool has(uint8_t f) const { return mask & (1u << f); }
};

inline String agIsoFromTs(uint32_t ts) {
  time_t t = (time_t)ts;
  struct tm tmv;
  gmtime_r(&t, &tmv);
  char buf[25];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &tmv);
  return String(buf);
}

// Deterministic JSON: same input -> same bytes on node and gateway.
inline String buildTelemetryJson(const char* deviceId, const char* farmId, const char* zoneId,
                                 uint32_t ts, const AgValues& vals) {
  String json = "{\"device_id\":\"";
  json += deviceId;
  json += "\",";
  if (farmId && strlen(farmId)) { json += "\"farm_id\":\""; json += farmId; json += "\","; }
  if (zoneId && strlen(zoneId)) { json += "\"zone_id\":\""; json += zoneId; json += "\","; }
  json += "\"timestamp\":\"" + agIsoFromTs(ts) + "\",\"source\":\"device\",\"sensors\":{";
  bool first = true;
  for (uint8_t i = 0; i < F_COUNT; i++) {
    if (!vals.has(i)) continue;
    if (!first) json += ",";
    first = false;
    json += "\"";
    json += AG_TYPES[i];
    json += "\":{\"value\":";
    json += String(vals.v[i], 2);
    json += ",\"unit\":\"";
    json += AG_UNITS[i];
    json += "\"}";
  }
  json += "}}";
  return json;
}

// ---- binary packet helpers (little endian) ----
inline void agPutU32(uint8_t* p, uint32_t x) { p[0] = x; p[1] = x >> 8; p[2] = x >> 16; p[3] = x >> 24; }
inline uint32_t agGetU32(const uint8_t* p) { return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24); }

inline bool agPutStr(uint8_t* buf, size_t& n, const char* s) {
  size_t l = s ? strlen(s) : 0;
  if (l > 64 || n + 1 + l > AG_MAX_PACKET) return false;
  buf[n++] = (uint8_t)l;
  memcpy(buf + n, s, l);
  n += l;
  return true;
}

inline bool agGetStr(const uint8_t* buf, size_t len, size_t& n, char* out, size_t outSize) {
  if (n >= len) return false;
  size_t l = buf[n++];
  if (l >= outSize || n + l > len) return false;
  memcpy(out, buf + n, l);
  out[l] = 0;
  n += l;
  return true;
}

// Telemetry packet: 'A''G' ver type | ts u32 | mask u16 | id | farm | zone | float32 per set bit | sig[32]
inline size_t agEncodeTelemetry(uint8_t* buf, const char* id, const char* farm, const char* zone,
                                uint32_t ts, const AgValues& vals, const uint8_t sig[32]) {
  size_t n = 0;
  buf[n++] = 'A'; buf[n++] = 'G'; buf[n++] = AG_PROTO_VERSION; buf[n++] = AG_PKT_TELEMETRY;
  agPutU32(buf + n, ts); n += 4;
  buf[n++] = vals.mask & 0xFF; buf[n++] = vals.mask >> 8;
  if (!agPutStr(buf, n, id) || !agPutStr(buf, n, farm) || !agPutStr(buf, n, zone)) return 0;
  for (uint8_t i = 0; i < F_COUNT; i++) {
    if (!vals.has(i)) continue;
    if (n + 4 > AG_MAX_PACKET) return 0;
    memcpy(buf + n, &vals.v[i], 4); n += 4;
  }
  if (n + 32 > AG_MAX_PACKET) return 0;
  memcpy(buf + n, sig, 32); n += 32;
  return n;
}

inline bool agDecodeTelemetry(const uint8_t* buf, size_t len, char* id, char* farm, char* zone,
                              uint32_t& ts, AgValues& vals, uint8_t sig[32]) {
  if (len < 4 + 4 + 2 + 3 + 32 || buf[0] != 'A' || buf[1] != 'G' || buf[2] != AG_PROTO_VERSION ||
      buf[3] != AG_PKT_TELEMETRY) return false;
  size_t n = 4;
  ts = agGetU32(buf + n); n += 4;
  vals.mask = buf[n] | (buf[n + 1] << 8); n += 2;
  if (!agGetStr(buf, len, n, id, 65) || !agGetStr(buf, len, n, farm, 65) || !agGetStr(buf, len, n, zone, 65))
    return false;
  for (uint8_t i = 0; i < F_COUNT; i++) {
    if (!vals.has(i)) continue;
    if (n + 4 > len) return false;
    memcpy(&vals.v[i], buf + n, 4); n += 4;
  }
  if (vals.mask >> F_COUNT) return false;  // unknown fields
  if (n + 32 != len) return false;
  memcpy(sig, buf + n, 32);
  return true;
}
