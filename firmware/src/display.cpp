#include "display.h"
#include "config.h"

#if defined(ESP8266)
// ---------------------------------------------------------------- 128x64 OLED (NodeMCU build)
#include <Wire.h>
#include <Adafruit_SSD1306.h>

static Adafruit_SSD1306 oled(128, 64, &Wire, -1);
static bool ready = false;
static uint8_t address = 0;

bool displayBegin() {
  // Probe first: display.begin alone does not reliably identify a missing panel.
  for (unsigned attempt = 0; attempt < 5 && !ready; ++attempt) {
    for (uint8_t candidate : {0x3C, 0x3D}) {
      Wire.beginTransmission(candidate);
      if (Wire.endTransmission() == 0 && oled.begin(SSD1306_SWITCHCAPVCC, candidate)) { ready = true; address = candidate; break; }
    }
    if (!ready) delay(100);
  }
  return ready;
}
String displayInfo() { return ready ? "oled@0x" + String(address, HEX) : String("oled missing"); }
void displaySetup(uint8_t, uint8_t) {}

void displayShow(View view, const String &title, const String &line1, const String &line2, const ScreenStatus &s) {
  if (!ready) return;
  oled.clearDisplay(); oled.setTextColor(SSD1306_WHITE); oled.setTextSize(1); oled.setCursor(0, 0);
  oled.println("ATTENDANCE     " + s.clock);
  oled.println(String(s.online ? "ONLINE" : "OFFLINE") + (s.online ? (s.serverOk ? " SRV OK" : " SRV --") : ""));
  oled.println();
  if (view == View::Idle) { oled.println("Place your finger"); }
  else { oled.println(title); oled.println(line1); oled.println(line2); }
  oled.setCursor(0, 56); oled.print("Pending: " + String(s.pending));
  oled.display();
}
void displayEnroll(const String &who, const String &prompt, int step, const ScreenStatus &s) {
  displayShow(View::Enroll, "Enroll " + who, prompt, "Step " + String(step) + " of 2", s);
}

#else
// ---------------------------------------------------------------- 1.8" ST7735 TFT, 128x160 portrait
#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <Fonts/FreeSansBold9pt7b.h>
#include <Fonts/FreeSansBold18pt7b.h>

static Adafruit_ST7735 tft(TFT_CS, TFT_DC, TFT_RST);
static uint8_t rotation = 0, tab = 0;
static bool ready = false;

constexpr uint16_t rgb(uint8_t r, uint8_t g, uint8_t b) { return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3); }
// Palette from docs/tft-screens.html
const uint16_t BG_TOP = rgb(0x10, 0x1c, 0x2e), BG_BOTTOM = rgb(0x08, 0x10, 0x1b);
const uint16_t TEXT = rgb(0xf2, 0xf6, 0xfa), MUTED = rgb(0x8e, 0xa3, 0xb8);
const uint16_t GREEN = rgb(0x3d, 0xdc, 0x84), AMBER = rgb(0xf5, 0xa5, 0x24), RED = rgb(0xff, 0x5a, 0x5f);
const uint16_t BLUE = rgb(0x4a, 0xa8, 0xff), PURPLE = rgb(0xb1, 0x8c, 0xff);
const uint16_t WAVE_1 = rgb(0x18, 0x30, 0x4d), WAVE_2 = rgb(0x20, 0x3e, 0x63);
const int16_t W = 128, H = 160;

static uint16_t blend(uint16_t a, uint16_t b, float t) {  // t = share of a
  uint8_t ar = (a >> 11) & 31, ag = (a >> 5) & 63, ab = a & 31, br = (b >> 11) & 31, bg = (b >> 5) & 63, bb = b & 31;
  return (uint16_t(ar * t + br * (1 - t)) << 11) | (uint16_t(ag * t + bg * (1 - t)) << 5) | uint16_t(ab * t + bb * (1 - t));
}
static uint16_t backgroundAt(int16_t y) { return blend(BG_BOTTOM, BG_TOP, float(y) / H); }

static void background() {
  for (int16_t y = 0; y < H; ++y) tft.drawFastHLine(0, y, W, backgroundAt(y));
}
static void waves() {
  for (int16_t x = 0; x < W; ++x) {
    int16_t y1 = 146 + int16_t(4 * sinf(x * 0.05f));
    int16_t y2 = 152 + int16_t(3 * sinf(x * 0.07f + 1.0f));
    tft.drawFastVLine(x, y1, H - y1, WAVE_1);
    tft.drawFastVLine(x, y2, H - y2, WAVE_2);
  }
}
static void arc(int16_t cx, int16_t cy, float r, int from, int to, uint16_t colour, uint8_t thickness = 1) {
  for (uint8_t t = 0; t < thickness; ++t)
    for (int a = from; a <= to; a += 2) {
      float rad = a * DEG_TO_RAD;
      tft.drawPixel(cx + int16_t(roundf((r - t * 0.8f) * cosf(rad))), cy - int16_t(roundf((r - t * 0.8f) * sinf(rad))), colour);
    }
}
static void thickLine(int16_t x0, int16_t y0, int16_t x1, int16_t y1, uint16_t colour) {
  for (int8_t d = -1; d <= 1; ++d) { tft.drawLine(x0 + d, y0, x1 + d, y1, colour); tft.drawLine(x0, y0 + d, x1, y1 + d, colour); }
}

// Text: GFX fonts position by baseline; the built-in 6x8 font (font == nullptr) by its top edge.
static String fit(String text, const GFXfont *font) {
  tft.setFont(font);
  int16_t x1, y1; uint16_t w, h;
  for (;;) {
    tft.getTextBounds(text, 0, 20, &x1, &y1, &w, &h);
    if (w <= W - 6 || text.length() <= 1) return text;
    text.remove(text.length() - 1);
  }
}
static void centred(const String &raw, int16_t baseline, uint16_t colour, const GFXfont *font) {
  String text = fit(raw, font);
  int16_t x1, y1; uint16_t w, h;
  tft.setFont(font); tft.setTextSize(1); tft.setTextColor(colour);
  tft.getTextBounds(text, 0, baseline, &x1, &y1, &w, &h);
  tft.setCursor((W - int16_t(w)) / 2 - x1, font ? baseline : baseline - 7);
  tft.print(text);
}
static void pill(const String &label, int16_t y, uint16_t colour) {
  String text = fit(label, nullptr);
  int16_t w = text.length() * 6 + 16;
  tft.fillRoundRect((W - w) / 2, y, w, 13, 6, blend(colour, backgroundAt(y), 0.22f));
  centred(text, y + 10, colour, nullptr);
}

static void wifiIcon(bool online) {
  const int16_t cx = 118, cy = 12;
  uint16_t colour = online ? TEXT : MUTED;
  arc(cx, cy, 7, 45, 135, colour, 2);
  arc(cx, cy, 4, 45, 135, colour, 2);
  tft.fillCircle(cx, cy - 1, 1, colour);
  if (!online) thickLine(cx - 6, cy - 9, cx + 6, cy + 1, RED);
}
static void statusBar(const String &left, bool online) {
  tft.setFont(nullptr); tft.setTextSize(1); tft.setTextColor(TEXT);
  tft.setCursor(5, 4); tft.print(left);
  wifiIcon(online);
}
static void ring(int16_t cx, int16_t cy, int16_t r, uint16_t colour) {
  tft.fillCircle(cx, cy, r + 3, blend(colour, backgroundAt(cy), 0.14f));
  tft.fillCircle(cx, cy, r, backgroundAt(cy));
  tft.drawCircle(cx, cy, r, colour);
  tft.drawCircle(cx, cy, r - 1, colour);
}
static void fingerprint(int16_t cx, int16_t cy, uint16_t colour) {
  for (int r = 3; r <= 13; r += 3) {
    arc(cx, cy + 2, r, 25, 155, colour, 2);
    int16_t dx = int16_t(r * 0.9f);
    tft.drawFastVLine(cx - dx, cy + 2, r / 2 + 1, colour);
    tft.drawFastVLine(cx + dx, cy + 2, r / 3 + 1, colour);
  }
  tft.drawFastVLine(cx, cy, 8, colour);
}
static void icon(View view, int16_t cx, int16_t cy) {
  switch (view) {
    case View::Ok:    thickLine(cx - 7, cy, cx - 2, cy + 5, GREEN); thickLine(cx - 2, cy + 5, cx + 8, cy - 6, GREEN); break;
    case View::Error: thickLine(cx - 6, cy - 6, cx + 6, cy + 6, RED); thickLine(cx + 6, cy - 6, cx - 6, cy + 6, RED); break;
    case View::Warn:  tft.fillRoundRect(cx - 1, cy - 8, 4, 10, 2, AMBER); tft.fillCircle(cx + 1, cy + 6, 2, AMBER); break;
    default:          tft.fillCircle(cx + 1, cy - 7, 2, BLUE); tft.fillRoundRect(cx - 1, cy - 3, 4, 11, 2, BLUE); break;
  }
}
static uint16_t viewColour(View view) {
  switch (view) {
    case View::Ok: return GREEN;
    case View::Warn: return AMBER;
    case View::Error: return RED;
    case View::Enroll: return PURPLE;
    default: return BLUE;
  }
}

static void initialise() {
  tft.initR(tab);
  tft.setRotation(rotation);
  tft.fillScreen(BG_BOTTOM);
}
bool displayBegin() {
  initialise();
  ready = true;  // SPI displays do not answer; correct colours and orientation are checked by eye
  return ready;
}
void displaySetup(uint8_t newRotation, uint8_t newTab) {
  rotation = newRotation & 3; tab = newTab;
  if (ready) initialise();
}
String displayInfo() { return "tft rotation=" + String(rotation) + " tab=" + String(tab); }

void displayShow(View view, const String &title, const String &line1, const String &line2, const ScreenStatus &s) {
  if (!ready) return;
  background();
  statusBar(s.date.length() ? s.date : String("ATTENDANCE"), s.online);
  if (view == View::Idle) {
    centred(s.clock, 54, TEXT, &FreeSansBold18pt7b);
    ring(64, 92, 20, GREEN);
    fingerprint(64, 92, GREEN);
    centred("Place your finger", 131, TEXT, nullptr);
    if (!s.online || s.pending) pill(String(s.online ? "" : "OFFLINE  ") + String(s.pending) + " WAITING", 140, AMBER);
    else waves();
    return;
  }
  uint16_t colour = viewColour(view);
  ring(64, 40, 16, colour);
  icon(view, 64, 40);
  centred(title, 76, colour, &FreeSansBold9pt7b);
  if (line1.length()) centred(line1, 98, TEXT, &FreeSansBold9pt7b);
  if (line2.length()) centred(line2, 116, MUTED, nullptr);
  centred(s.clock, 140, MUTED, nullptr);
}

void displayEnroll(const String &who, const String &prompt, int step, const ScreenStatus &s) {
  if (!ready) return;
  background();
  statusBar("ENROLLMENT", s.online);
  centred(who, 36, TEXT, &FreeSansBold9pt7b);
  ring(64, 76, 20, PURPLE);
  fingerprint(64, 76, PURPLE);
  centred(prompt, 117, TEXT, nullptr);
  for (int i = 1; i <= 2; ++i) {
    int16_t x = 58 + (i - 1) * 12;
    if (i <= step) tft.fillCircle(x, 133, 3, PURPLE); else tft.drawCircle(x, 133, 3, PURPLE);
  }
  centred("Step " + String(step) + " of 2", 152, MUTED, nullptr);
}
#endif
