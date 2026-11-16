#pragma once
// Scanner display: 1.8" ST7735 (128x160) or 3.5" ILI9488 (320x480) TFT on the ESP32, one layout scaled
// to the panel (designs in docs/tft-screens.png); the 128x64 I2C OLED on the ESP8266 build.
#include <Arduino.h>

enum class View : uint8_t { Idle, Ok, Info, Warn, Error, Enroll };

struct ScreenStatus {
  String clock;     // "09:02" or "--:--"
  String date;      // "Sun, 15 Nov" or ""
  bool online;      // Wi-Fi connected (or USB mode)
  bool serverOk;
  unsigned pending; // scans waiting to be sent
};

bool displayBegin();                 // call after Wire.begin(); returns whether a display answered
String displayInfo();                // for the USB STATUS line
void displaySetup(uint8_t rotation, uint8_t tab);  // TFT orientation and controller variant; re-initialises
// title/line1/line2 meaning depends on the view; Idle ignores them.
void displayShow(View view, const String &title, const String &line1, const String &line2, const ScreenStatus &status);
// step: 1 or 2 (dots on screen), prompt such as "Place your finger".
void displayEnroll(const String &who, const String &prompt, int step, const ScreenStatus &status);
