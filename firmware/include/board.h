#pragma once
// Hardware variant: pins and display. Chosen by the PlatformIO environment (build flags), never by
// config.h, which only holds this device's identity and network secrets.
//   esp32dev / esp32-st7735   ESP32 DevKit or bare ESP-WROOM-32, 1.8" ST7735 (default)
//   esp32-ili9488             same wiring, 3.5" ILI9488 SPI module
//   board-ili9488             the main PCB (ESP32-WROOM-32E) with the 3.5" ILI9488; -D BOARD_MAIN
//   nodemcu                   temporary NodeMCU ESP8266 with the 128x64 I2C OLED
#include <Arduino.h>

#if !defined(CONFIG_H_VERSION) || CONFIG_H_VERSION < 2
#error "firmware/include/config.h is from an older version (it still holds pins). Regenerate it with: .venv\\Scripts\\python.exe -m tools.firmware_config  (keeps the hotspot password; the device key comes from .env)"
#endif

#if defined(ESP8266)
#define DISPLAY_OLED 1
constexpr char HARDWARE_NAME[] = "nodemcu-oled";
// NodeMCU ESP8266: GPIO numbers, NodeMCU label in brackets. Sensor uses software serial.
constexpr int SENSOR_RX = 14; // [D5] ESP RX <- R307 TX
constexpr int SENSOR_TX = 12; // [D6] ESP TX -> R307 RX
constexpr int I2C_SDA = 4;    // [D2]
constexpr int I2C_SCL = 5;    // [D1]
constexpr int FINGER_TOUCH_PIN = -1; // no spare pin: poll the sensor
constexpr uint8_t TFT_ROTATION = 0, TFT_TAB = 0; // unused: this build drives the OLED
constexpr int BUZZER_PIN = -1; // no spare pin
constexpr unsigned MAX_PENDING_EVENTS = 150; // limited RAM

#else
#if !defined(DISPLAY_ST7735) && !defined(DISPLAY_ILI9488)
#define DISPLAY_ST7735 1
#endif
#if defined(DISPLAY_ST7735) && defined(DISPLAY_ILI9488)
#error "Choose one display: DISPLAY_ST7735 or DISPLAY_ILI9488"
#endif
// Same GPIOs on the DevKit wiring (docs/WIRING.md) and the main PCB (pcb/generator/design.py).
constexpr int SENSOR_RX = 16; // ESP RX <- R307 TX
constexpr int SENSOR_TX = 17; // ESP TX -> R307 RX
constexpr int I2C_SDA = 21;   // I2C bus: DS3231 clock (0x68)
constexpr int I2C_SCL = 22;
// R307 "Touch" (finger-detect) output. The sensor is only read while a finger touches it, so its
// light stays off when idle. Polarity is detected at boot; if the wire is absent the firmware polls.
constexpr int FINGER_TOUCH_PIN = 27;
// TFT on the hardware SPI bus: SCK = IO18, MOSI (SDA/SDI) = IO23. MISO and the touch pins are unused.
constexpr int TFT_SCK = 18;
constexpr int TFT_MOSI = 23;
constexpr int TFT_CS = 5;
constexpr int TFT_DC = 4;   // labelled A0, DC or RS on the module
constexpr int TFT_RST = 19;
// Orientation and controller variant, changeable over USB without rebuilding (TFTROT n / TFTTAB n).
// ST7735: rotation 0 or 2 is portrait; TFTTAB 0 green tab, 1 red tab, 2 black tab.
// ILI9488: rotation 0 or 2 is portrait; TFTTAB 0 normal colours, 1 inverted (IPS panels).
constexpr uint8_t TFT_ROTATION = 0;
#if defined(DISPLAY_ST7735)
constexpr uint8_t TFT_TAB = 2;
#else
constexpr uint8_t TFT_TAB = 0;
#endif
// Buzzer switched by an NPN transistor: HIGH = sound. The DevKit prototype uses an active TMB12A05,
// the main PCB a passive MLT-8530; both sound with the PWM tone in main.cpp.
constexpr int BUZZER_PIN = 32;
constexpr unsigned MAX_PENDING_EVENTS = 500;

#if defined(BOARD_MAIN)
#if !defined(DISPLAY_ILI9488)
#error "The main PCB is built for the 3.5\" ILI9488 only"
#endif
constexpr char HARDWARE_NAME[] = "board-ili9488";
// Main PCB extras (pcb/generator/design.py, ESP32-WROOM-32E)
constexpr int LED_OK_PIN = 33;        // green status LED, HIGH = on
constexpr int LED_ERR_PIN = 13;       // red status LED, HIGH = on
constexpr int TFT_BL_PIN = 14;        // P-MOSFET backlight switch: LOW = on, HIGH = off (pulled on by default)
constexpr int TAMPER_PIN = 26;        // case switch: LOW = case closed (10k pull-up on the board)
constexpr int RTC_INT_PIN = 35;       // DS3231 INT/SQW, open drain, input only
constexpr int BAT_SENSE_PIN = 34;     // battery through 100k/220k: Vbat = Vadc * 320 / 220
constexpr int MAINS_SENSE_PIN = 36;   // EXT_5V through 100k/220k: about 3.4 V when external power is present
constexpr int CHRG_PIN = 39;          // TP4056 CHRG: LOW = charging
#else
constexpr char HARDWARE_NAME[] =
#if defined(DISPLAY_ST7735)
    "esp32-st7735";
#else
    "esp32-ili9488";
#endif
#endif
#endif

constexpr unsigned long SENSOR_BAUD = 57600;
