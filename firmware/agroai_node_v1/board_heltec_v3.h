// Pin map: Heltec WiFi LoRa 32 V3 (ESP32-S3 + SX1262) as wired in hardware/agroai-node-v1.
// !!! Check every pin against the official Heltec V3 pinout BEFORE soldering. !!!
#pragma once

// ---- used on-board by the Heltec V3 (do not reuse) ----
#define LORA_NSS      8
#define LORA_SCK      9
#define LORA_MOSI     10
#define LORA_MISO     11
#define LORA_RST      12
#define LORA_BUSY     13
#define LORA_DIO1     14
#define VEXT_CTRL     36   // LOW = Vext (3.3 V for external sensors) ON
#define VBAT_ADC      1    // battery through on-board divider
#define VBAT_ADC_CTRL 37   // enables the divider (polarity differs between board revisions)

// ---- AgroAI Node v1 wiring ----
#define SOIL_MOISTURE_PIN 7    // ADC1
#define DS18B20_PIN       6    // + 4.7 kOhm to 3.3 V
#define RAIN_PIN          5    // reed to GND; RTC GPIO -> wakes the node from deep sleep
#define FLOW_PIN          4    // flow meter pulses (through 10k/4.7k divider when fed at 9 V)
#define I2C_SDA           41   // external sensors: SHT40 (0x44) + BH1750 (0x23)
#define I2C_SCL           42
#define VALVE1_IN1        47   // DRV8833 AIN1
#define VALVE1_IN2        48   // DRV8833 AIN2
#define VALVE2_IN1        39   // DRV8833 BIN1
#define VALVE2_IN2        40   // DRV8833 BIN2
#define BOOST_EN          2    // switches the MT3608 9 V boost (via AO3401 high-side)
