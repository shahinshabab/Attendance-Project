#include "display.h"
#include "config.h"
#include "board.h"

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
// ---------------------------------------------------------------- SPI TFT, portrait
// One layout, drawn in the coordinates of the original 128x160 design and scaled to the panel:
// identical on the 1.8" ST7735, 2.5x (horizontal) and 3x (vertical) on the 3.5" ILI9488.
#include <SPI.h>
#if defined(DISPLAY_ST7735)
#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
static Adafruit_ST7735 tft(TFT_CS, TFT_DC, TFT_RST);
static const char PANEL[] = "st7735";
#else
#include <Arduino_GFX_Library.h>
// The ILI9488 SPI interface only takes 18-bit colour; this driver converts from RGB565.
static Arduino_DataBus *bus = new Arduino_ESP32SPI(TFT_DC, TFT_CS, TFT_SCK, TFT_MOSI, GFX_NOT_DEFINED, VSPI);
static Arduino_ILI9488_18bit tft(bus, TFT_RST, 0, false);
static const char PANEL[] = "ili9488";
static bool started = false;
constexpr int32_t ILI9488_SPI_HZ = 27000000;  // conservative for a 14-wire cable
#endif
// Fonts are Adafruit GFX font files; the Arduino_GFX driver reads the same GFXfont format.
#include <Fonts/FreeSansBold9pt7b.h>
#include <Fonts/FreeSansBold12pt7b.h>
#include <Fonts/FreeSansBold18pt7b.h>
#include <Fonts/FreeSansBold24pt7b.h>

static uint8_t rotation = 0, tab = 0;
static bool ready = false;

constexpr uint16_t rgb(uint8_t r, uint8_t g, uint8_t b) { return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3); }
// Palette from docs/tft-screens.html
const uint16_t BG_TOP = rgb(0x10, 0x1c, 0x2e), BG_BOTTOM = rgb(0x08, 0x10, 0x1b);
const uint16_t C_TEXT = rgb(0xf2, 0xf6, 0xfa), C_MUTED = rgb(0x8e, 0xa3, 0xb8);
const uint16_t C_GREEN = rgb(0x3d, 0xdc, 0x84), C_AMBER = rgb(0xf5, 0xa5, 0x24), C_RED = rgb(0xff, 0x5a, 0x5f);
const uint16_t C_BLUE = rgb(0x4a, 0xa8, 0xff), C_PURPLE = rgb(0xb1, 0x8c, 0xff);
const uint16_t WAVE_1 = rgb(0x18, 0x30, 0x4d), WAVE_2 = rgb(0x20, 0x3e, 0x63);

// Panel size after rotation, and the scale from the 128x160 design.
static int16_t W = 128, H = 160;
static float K = 1;
static int16_t X(float v) { return int16_t(roundf(v * W / 128)); }
static int16_t Y(float v) { return int16_t(roundf(v * H / 160)); }
static int16_t S(float v) { return int16_t(roundf(v * K)); }
static int16_t S1(float v) { return max(int16_t(1), S(v)); }  // at least one pixel

// Text roles. Small on the ST7735 is the built-in 6x8 font (font == nullptr), positioned by its top
// edge; GFX fonts are positioned by their baseline.
struct TextStyle { const GFXfont *font; uint8_t size; };
#if defined(DISPLAY_ST7735)
const TextStyle SMALL = {nullptr, 1}, MEDIUM = {&FreeSansBold9pt7b, 1}, LARGE = {&FreeSansBold18pt7b, 1};
#else
const TextStyle SMALL = {&FreeSansBold12pt7b, 1}, MEDIUM = {&FreeSansBold18pt7b, 1}, LARGE = {&FreeSansBold24pt7b, 2};
#endif

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
    float u = x / K;  // design x
    int16_t y1 = Y(146) + int16_t(S(4) * sinf(u * 0.05f));
    int16_t y2 = Y(152) + int16_t(S(3) * sinf(u * 0.07f + 1.0f));
    tft.drawFastVLine(x, y1, H - y1, WAVE_1);
    tft.drawFastVLine(x, y2, H - y2, WAVE_2);
  }
}
// Centre and radius in panel pixels; thickness in design pixels.
static void arc(int16_t cx, int16_t cy, float r, int from, int to, uint16_t colour, uint8_t thickness = 1) {
  int step = K < 1.5f ? 2 : 1;
  int layers = S1(thickness);
  for (int t = 0; t < layers; ++t)
    for (int a = from; a <= to; a += step) {
      float rad = a * DEG_TO_RAD;
      tft.drawPixel(cx + int16_t(roundf((r - t * 0.8f) * cosf(rad))), cy - int16_t(roundf((r - t * 0.8f) * sinf(rad))), colour);
    }
}
static void thickLine(int16_t x0, int16_t y0, int16_t x1, int16_t y1, uint16_t colour) {
  int16_t half = S1(1);
  for (int16_t d = -half; d <= half; ++d) { tft.drawLine(x0 + d, y0, x1 + d, y1, colour); tft.drawLine(x0, y0 + d, x1, y1 + d, colour); }
}

static void useStyle(const TextStyle &style) { tft.setFont(style.font); tft.setTextSize(style.size); }
static void bounds(const String &text, int16_t *x1, int16_t *y1, uint16_t *w, uint16_t *h) {
  tft.getTextBounds(text, 0, 100, x1, y1, w, h);
  *y1 -= 100;  // relative to the baseline (GFX fonts) or the top edge (built-in font)
}
static String fit(String text, const TextStyle &style) {
  useStyle(style);
  int16_t x1, y1; uint16_t w, h;
  for (;;) {
    bounds(text, &x1, &y1, &w, &h);
    if (w <= W - S(6) || text.length() <= 1) return text;
    text.remove(text.length() - 1);
  }
}
static void centred(const String &raw, int16_t baseline, uint16_t colour, const TextStyle &style) {
  String text = fit(raw, style);
  int16_t x1, y1; uint16_t w, h;
  useStyle(style); tft.setTextColor(colour);
  bounds(text, &x1, &y1, &w, &h);
  tft.setCursor((W - int16_t(w)) / 2 - x1, style.font ? baseline : baseline - 7);
  tft.print(text);
}
static void pill(const String &label, int16_t y, uint16_t colour) {
  String text = fit(label, SMALL);
  if (!SMALL.font) {  // the original 1.8" geometry
    int16_t w = text.length() * 6 + 16;
    tft.fillRoundRect((W - w) / 2, y, w, 13, 6, blend(colour, backgroundAt(y), 0.22f));
    centred(text, y + 10, colour, SMALL);
    return;
  }
  int16_t x1, y1; uint16_t tw, th;
  bounds(text, &x1, &y1, &tw, &th);
  int16_t w = tw + S(16), h = th + S(6);
  tft.fillRoundRect((W - w) / 2, y, w, h, h / 2, blend(colour, backgroundAt(y), 0.22f));
  centred(text, y + (h - int16_t(th)) / 2 - y1, colour, SMALL);
}

static void wifiIcon(bool online) {
  const int16_t cx = W - S(10), cy = S(12);
  uint16_t colour = online ? C_TEXT : C_MUTED;
  arc(cx, cy, S(7), 45, 135, colour, 2);
  arc(cx, cy, S(4), 45, 135, colour, 2);
  tft.fillCircle(cx, cy - S(1), S1(1), colour);
  if (!online) thickLine(cx - S(6), cy - S(9), cx + S(6), cy + S(1), C_RED);
}
static void statusBar(const String &left, bool online) {
  useStyle(SMALL); tft.setTextColor(C_TEXT);
  if (!SMALL.font) tft.setCursor(5, 4);
  else {
    int16_t x1, y1; uint16_t w, h;
    bounds("Ag", &x1, &y1, &w, &h);
    tft.setCursor(S(5), S(4) - y1);
  }
  tft.print(left);
  wifiIcon(online);
}
static void ring(int16_t cx, int16_t cy, int16_t r, uint16_t colour) {
  tft.fillCircle(cx, cy, r + S(3), blend(colour, backgroundAt(cy), 0.14f));
  tft.fillCircle(cx, cy, r, backgroundAt(cy));
  for (int16_t i = 0; i < max(int16_t(2), S(2)); ++i) tft.drawCircle(cx, cy, r - i, colour);
}
static void fingerprint(int16_t cx, int16_t cy, uint16_t colour) {
  for (int r = 3; r <= 13; r += 3) {
    arc(cx, cy + S(2), S(r), 25, 155, colour, 2);
    int16_t dx = int16_t(r * 0.9f * K);
    for (int16_t i = 0; i < S1(1); ++i) {
      tft.drawFastVLine(cx - dx + i, cy + S(2), S(r / 2 + 1), colour);
      tft.drawFastVLine(cx + dx - i, cy + S(2), S(r / 3 + 1), colour);
    }
  }
  for (int16_t i = 0; i < S1(1); ++i) tft.drawFastVLine(cx + i, cy, S(8), colour);
}
static void icon(View view, int16_t cx, int16_t cy) {
  switch (view) {
    case View::Ok:    thickLine(cx - S(7), cy, cx - S(2), cy + S(5), C_GREEN); thickLine(cx - S(2), cy + S(5), cx + S(8), cy - S(6), C_GREEN); break;
    case View::Error: thickLine(cx - S(6), cy - S(6), cx + S(6), cy + S(6), C_RED); thickLine(cx + S(6), cy - S(6), cx - S(6), cy + S(6), C_RED); break;
    case View::Warn:  tft.fillRoundRect(cx - S(1), cy - S(8), S(4), S(10), S(2), C_AMBER); tft.fillCircle(cx + S(1), cy + S(6), S(2), C_AMBER); break;
    default:          tft.fillCircle(cx + S(1), cy - S(7), S(2), C_BLUE); tft.fillRoundRect(cx - S(1), cy - S(3), S(4), S(11), S(2), C_BLUE); break;
  }
}
static uint16_t viewColour(View view) {
  switch (view) {
    case View::Ok: return C_GREEN;
    case View::Warn: return C_AMBER;
    case View::Error: return C_RED;
    case View::Enroll: return C_PURPLE;
    default: return C_BLUE;
  }
}

static void initialise() {
#if defined(DISPLAY_ST7735)
  tft.initR(tab);
  tft.setRotation(rotation);
#else
  if (!started) started = tft.begin(ILI9488_SPI_HZ);
  tft.setRotation(rotation);
  tft.invertDisplay(tab & 1);
#endif
  W = tft.width(); H = tft.height();
  K = min(W / 128.0f, H / 160.0f);
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
String displayInfo() {
  return String(PANEL) + " " + String(W) + "x" + String(H) + " rotation=" + String(rotation) + " tab=" + String(tab);
}

void displayShow(View view, const String &title, const String &line1, const String &line2, const ScreenStatus &s) {
  if (!ready) return;
  background();
  statusBar(s.date.length() ? s.date : String("ATTENDANCE"), s.online);
  const int16_t cx = X(64);
  if (view == View::Idle) {
    centred(s.clock, Y(54), C_TEXT, LARGE);
    ring(cx, Y(92), S(20), C_GREEN);
    fingerprint(cx, Y(92), C_GREEN);
    centred("Place your finger", Y(131), C_TEXT, SMALL);
    if (!s.online || s.pending) pill(String(s.online ? "" : "OFFLINE  ") + String(s.pending) + " WAITING", Y(140), C_AMBER);
    else waves();
    return;
  }
  uint16_t colour = viewColour(view);
  ring(cx, Y(40), S(16), colour);
  icon(view, cx, Y(40));
  centred(title, Y(76), colour, MEDIUM);
  if (line1.length()) centred(line1, Y(98), C_TEXT, MEDIUM);
  if (line2.length()) centred(line2, Y(116), C_MUTED, SMALL);
  centred(s.clock, Y(140), C_MUTED, SMALL);
}

void displayEnroll(const String &who, const String &prompt, int step, const ScreenStatus &s) {
  if (!ready) return;
  background();
  statusBar("ENROLLMENT", s.online);
  const int16_t cx = X(64);
  centred(who, Y(36), C_TEXT, MEDIUM);
  ring(cx, Y(76), S(20), C_PURPLE);
  fingerprint(cx, Y(76), C_PURPLE);
  centred(prompt, Y(117), C_TEXT, SMALL);
  for (int i = 1; i <= 2; ++i) {
    int16_t x = X(58 + (i - 1) * 12);
    if (i <= step) tft.fillCircle(x, Y(133), S(3), C_PURPLE); else tft.drawCircle(x, Y(133), S(3), C_PURPLE);
  }
  centred("Step " + String(step) + " of 2", Y(152), C_MUTED, SMALL);
}
#endif
