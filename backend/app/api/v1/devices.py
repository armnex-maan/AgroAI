import secrets
import socket
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.config import settings
from app.core.database import get_db
from app.models import Device, Sensor
from app.schemas.device import DeviceCreate, DeviceOut, SensorSpec, SensorConfigUpdate

router = APIRouter()


def _to_out(d: Device) -> DeviceOut:
    return DeviceOut(
        id=d.id, name=d.name, farm_id=d.farm_id, zone_id=d.zone_id,
        hardware_type=d.hardware_type, firmware=d.firmware, source=d.source,
        status=d.status, last_seen=d.last_seen,
        provisioned=bool(d.api_secret), ip_address=d.ip_address,
        sensors=[SensorSpec(id=s.id, type=s.type, unit=s.unit, min_value=s.min_value,
                            max_value=s.max_value, enabled=s.enabled) for s in d.sensors],
    )


@router.get("/devices", response_model=list[DeviceOut])
def list_devices(db: Session = Depends(get_db)):
    return [_to_out(d) for d in db.query(Device).all()]


@router.post("/devices", response_model=DeviceOut, status_code=201)
def create_device(payload: DeviceCreate, db: Session = Depends(get_db)):
    if db.get(Device, payload.id):
        raise HTTPException(409, "Esiste già un dispositivo con questo codice.")
    d = Device(
        id=payload.id, name=payload.name, farm_id=payload.farm_id, zone_id=payload.zone_id,
        hardware_type=payload.hardware_type, firmware=payload.firmware, source=payload.source,
        status="offline", config=payload.config, created_at=datetime.now(timezone.utc),
    )
    db.add(d)
    db.flush()
    for spec in payload.sensors:
        db.add(Sensor(device_id=d.id, type=spec.type, unit=spec.unit,
                      min_value=spec.min_value, max_value=spec.max_value, enabled=spec.enabled))
    db.commit()
    db.refresh(d)
    return _to_out(d)


@router.get("/devices/{device_id}", response_model=DeviceOut)
def get_device(device_id: str, db: Session = Depends(get_db)):
    d = db.get(Device, device_id)
    if d is None:
        raise HTTPException(404, "not found")
    return _to_out(d)


@router.delete("/devices/{device_id}", status_code=204)
def delete_device(device_id: str, db: Session = Depends(get_db)):
    d = db.get(Device, device_id)
    if d is None:
        raise HTTPException(404, "not found")
    db.delete(d)
    db.commit()


@router.post("/devices/{device_id}/provision")
def provision(device_id: str, request: Request, db: Session = Depends(get_db)):
    """Generate a fresh per-device HMAC secret. It is returned ONCE, together
    with a ready-to-flash config.h for the AGROAI ESP32 firmware."""
    d = db.get(Device, device_id)
    if d is None:
        raise HTTPException(404, "not found")
    if d.source == "simulation":
        raise HTTPException(400, "simulated devices do not need provisioning")
    d.api_secret = secrets.token_hex(32)
    db.commit()
    server = settings.public_api_url or _guess_server_url(request)
    return {
        "device_id": d.id,
        "secret": d.api_secret,
        "server_url": server,
        "telemetry_endpoint": f"{server}/api/v1/telemetry",
        "audio_endpoint": f"{server}/api/v1/audio/upload",
        "mqtt_topic": f"agroai/{d.farm_id or 'farm'}/{d.id}/telemetry",
        "config_h": render_config_h(d, server),
        "warning": "Salva subito questo file: la chiave segreta non verrà più mostrata. Se ne generi una nuova, "
                   "quella vecchia smette di funzionare.",
    }


def _guess_server_url(request: Request) -> str:
    host = request.headers.get("host", "localhost:8000").split(":")[0]
    if host in ("localhost", "127.0.0.1"):
        host = lan_ip()
    return f"http://{host}:8000"


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


NODE_V1 = "agroai-node-v1"


def render_config_h(d: Device, server: str) -> str:
    if d.hardware_type == NODE_V1:
        return render_node_v1_config_h(d, server)
    types = {s.type for s in d.sensors}
    flag = lambda t: "1" if t in types else "0"  # noqa: E731
    return f"""// AGROAI ESP32 configuration — generated for {d.id}
#pragma once

#define WIFI_SSID        "YOUR_WIFI_SSID"
#define WIFI_PASSWORD    "YOUR_WIFI_PASSWORD"

#define AGROAI_SERVER    "{server}"
#define DEVICE_ID        "{d.id}"
#define FARM_ID          "{d.farm_id or ''}"
#define ZONE_ID          "{d.zone_id or ''}"
#define DEVICE_SECRET    "{d.api_secret}"

#define SEND_INTERVAL_S  60

// Sensors (1 = installed)
#define USE_SOIL_MOISTURE   {flag('soil_moisture')}   // capacitive v1.2 on SOIL_MOISTURE_PIN
#define USE_DHT22           {"1" if {'air_temperature', 'air_humidity'} & types else "0"}   // air temperature + humidity
#define USE_DS18B20         {flag('soil_temperature')}   // waterproof soil temperature probe
#define USE_RAIN_GAUGE      {flag('rainfall')}   // tipping bucket reed switch
#define USE_LIGHT_LDR       {flag('light_intensity')}   // LDR divider (relative, uncalibrated)
#define USE_I2S_MIC         0   // INMP441 microphone: uploads a WAV every AUDIO_INTERVAL_S

#define SOIL_MOISTURE_PIN   34
#define DHT_PIN             4
#define DS18B20_PIN         5
#define RAIN_PIN            27
#define LDR_PIN             35
#define I2S_SCK_PIN         26
#define I2S_WS_PIN          25
#define I2S_SD_PIN          33

// Calibrate: raw ADC reading in dry air and in a glass of water
#define SOIL_RAW_DRY        3200
#define SOIL_RAW_WET        1300
#define RAIN_MM_PER_TIP     0.2794
#define AUDIO_SECONDS       3
#define AUDIO_INTERVAL_S    900
"""


def render_node_v1_config_h(d: Device, server: str) -> str:
    """config.h for firmware/agroai_node_v1 (Heltec WiFi LoRa 32 V3). Pins live in board_heltec_v3.h."""
    types = {s.type for s in d.sensors}
    flag = lambda t: "1" if t in types else "0"  # noqa: E731
    cfg = d.config if isinstance(d.config, dict) else {}
    transport = "TRANSPORT_LORA" if cfg.get("transport") == "lora" else "TRANSPORT_WIFI"
    valves = "1" if "irrigation_time" in types or "irrigation_water" in types else "0"
    return f"""// AgroAI Node v1 configuration — generated for {d.id}
#pragma once

#define TRANSPORT        {transport}   // TRANSPORT_WIFI or TRANSPORT_LORA (needs agroai_lora_gateway)
#define BENCH_MODE       0   // 1 = on the table via USB: no deep sleep, serial commands

#define WIFI_SSID        "YOUR_WIFI_SSID"
#define WIFI_PASSWORD    "YOUR_WIFI_PASSWORD"
#define AGROAI_SERVER    "{server}"
#define DEVICE_ID        "{d.id}"
#define FARM_ID          "{d.farm_id or ''}"
#define ZONE_ID          "{d.zone_id or ''}"
#define DEVICE_SECRET    "{d.api_secret}"

#define SEND_INTERVAL_S  600   // deep sleep between measurements
#define LOCAL_TZ         "CET-1CEST,M3.5.0,M10.5.0/3"   // Italy; used for the irrigation window

// Sensors (1 = installed)
#define USE_SOIL_MOISTURE   {flag('soil_moisture')}   // capacitive probe
#define USE_DS18B20         {flag('soil_temperature')}   // soil temperature probe
#define USE_SHT40           {"1" if {'air_temperature', 'air_humidity'} & types else "0"}   // air temperature + humidity (I2C 0x44)
#define USE_BH1750          {flag('light_intensity')}   // light in lux (I2C 0x23)
#define USE_RAIN_GAUGE      {flag('rainfall')}   // tipping bucket reed switch (wakes the node)
#define USE_FLOW_METER      {flag('irrigation_water')}   // pulse flow meter on the drip line
#define USE_BATTERY         {flag('battery_voltage')}   // 18650 voltage via the Heltec divider

// Calibration — MEASURE, these are only starting points
#define SOIL_RAW_DRY        3200   // raw ADC in dry air
#define SOIL_RAW_WET        1300   // raw ADC in water up to the line
#define RAIN_MM_PER_TIP     0.2794 // from your rain gauge datasheet
#define FLOW_PULSES_PER_L   450.0  // from your flow meter datasheet, then check with a bucket
#define BAT_DIVIDER         4.9    // compare with a multimeter and correct
#define BAT_ADC_CTRL_ON     HIGH   // if the battery reads ~0 V, try LOW (depends on board revision)

// Latching valve on DRV8833 + 9 V boost
#define VALVE_COUNT         {valves}
#define VALVE_AUTO          0      // 1 = water automatically with the rules below (test by hand first!)
#define VALVE_PULSE_MS      100    // from the solenoid datasheet
#define VALVE_OPEN_FORWARD  1      // swap to 0 if "open" closes the valve
#define VALVE_ON_BELOW_PCT  30     // YOUR threshold for this crop/soil — no default is agronomically right
#define VALVE_RUN_S         600    // one irrigation
#define VALVE_MAX_RUN_S     1800   // hard limit per irrigation
#define VALVE_MAX_DAILY_S   3600   // hard limit per day
#define VALVE_MIN_BAT_V     3.5    // do not start below this battery voltage
#define IRR_START_HOUR      5      // local time window
#define IRR_END_HOUR        9
#define NO_FLOW_TIMEOUT_S   60     // close if the flow meter sees nothing

// LoRa (must match the gateway). EU 869.4–869.65 MHz sub-band: duty-cycle and power limits apply.
#define LORA_FREQ_MHZ       869.525
#define LORA_BW_KHZ         125.0
#define LORA_SF             9
#define LORA_TX_DBM         14
"""


@router.get("/devices/network/info")
def network_info():
    return {"lan_ip": lan_ip(), "api_port": 8000,
            "suggested_server_url": settings.public_api_url or f"http://{lan_ip()}:8000"}


@router.post("/devices/{device_id}/sensors", response_model=SensorSpec, status_code=201)
def add_sensor(device_id: str, spec: SensorSpec, db: Session = Depends(get_db)):
    d = db.get(Device, device_id)
    if d is None:
        raise HTTPException(404, "device not found")
    s = Sensor(device_id=device_id, type=spec.type, unit=spec.unit,
               min_value=spec.min_value, max_value=spec.max_value, enabled=spec.enabled)
    db.add(s)
    db.commit()
    db.refresh(s)
    return SensorSpec(id=s.id, type=s.type, unit=s.unit, min_value=s.min_value,
                      max_value=s.max_value, enabled=s.enabled)


@router.patch("/sensors/{sensor_id}", response_model=SensorSpec)
def update_sensor(sensor_id: str, patch: SensorConfigUpdate, db: Session = Depends(get_db)):
    s = db.get(Sensor, sensor_id)
    if s is None:
        raise HTTPException(404, "sensor not found")
    for k, v in patch.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return SensorSpec(id=s.id, type=s.type, unit=s.unit, min_value=s.min_value,
                      max_value=s.max_value, enabled=s.enabled)


@router.delete("/sensors/{sensor_id}", status_code=204)
def delete_sensor(sensor_id: str, db: Session = Depends(get_db)):
    s = db.get(Sensor, sensor_id)
    if s is None:
        raise HTTPException(404, "sensor not found")
    db.delete(s)
    db.commit()
