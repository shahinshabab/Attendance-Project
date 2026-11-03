#include <Arduino.h>
#include <Wire.h>
#include <RTClib.h>
#if defined(ESP8266)
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <EEPROM.h>
#include <SoftwareSerial.h>
#include <umm_malloc/umm_heap_select.h>
#else
#include <WiFi.h>
#include <HTTPClient.h>
#include <Preferences.h>
#endif
#include <WiFiClientSecure.h>
#include <LittleFS.h>
#include <ArduinoJson.h>
#include <Adafruit_Fingerprint.h>
#include <Adafruit_SSD1306.h>
#include <sys/time.h>
#include <errno.h>
#include <vector>
#include <algorithm>
#include "config.h"

constexpr char FIRMWARE_VERSION[] = "0.4.0-dev";
constexpr uint32_t WIFI_ATTEMPT_MS = 20000;   // per network before trying the other one
constexpr uint32_t OFFICE_RETRY_MS = 300000;  // while on the fallback hotspot, retry office Wi-Fi
constexpr uint32_t SYNC_INTERVAL_MS = 10000;  // server check-in: Wi-Fi updates and enrollment requests
constexpr uint32_t ENROLL_WAIT_MS = 120000;   // first finger for a server-requested enrollment

#if defined(ESP8266)
// Preferences-style settings kept as JSON in the emulated EEPROM sector, separate from LittleFS.
class Settings {
  StaticJsonDocument<768> doc;
  void save() {
    String text; serializeJson(doc, text);
    if (text.length() > 1020) { Serial.println("{\"type\":\"status\",\"message\":\"Settings too large; not saved\"}"); return; }
    EEPROM.write(0, 'A'); EEPROM.write(1, 'T');
    for (size_t i = 0; i <= text.length(); ++i) EEPROM.write(2 + i, i < text.length() ? text[i] : 0);
    EEPROM.commit();
  }
  template <typename T> void put(const char *key, T value) { doc.garbageCollect(); doc[key] = value; save(); }
 public:
  void begin(const char *, bool) {
    EEPROM.begin(1024);
    if (EEPROM.read(0) != 'A' || EEPROM.read(1) != 'T') return;
    String text; for (int i = 2; i < 1024 && EEPROM.read(i); ++i) text += (char)EEPROM.read(i);
    deserializeJson(doc, text);
  }
  bool isKey(const char *key) { return doc.containsKey(key); }
  bool getBool(const char *key, bool fallback) { return doc[key] | fallback; }
  int32_t getInt(const char *key, int32_t fallback) { return doc[key] | fallback; }
  uint32_t getUInt(const char *key, uint32_t fallback) { return doc[key] | fallback; }
  String getString(const char *key, const String &fallback) { return doc.containsKey(key) ? doc[key].as<String>() : fallback; }
  void putBool(const char *key, bool value) { put(key, value); }
  void putInt(const char *key, int32_t value) { put(key, value); }
  void putUInt(const char *key, uint32_t value) { put(key, value); }
  void putString(const char *key, const String &value) { put(key, value); }
};
SoftwareSerial sensorSerial(SENSOR_RX, SENSOR_TX);
WiFiEventHandler disconnectHandler;  // must stay alive to keep receiving events
uint32_t randomWord() { return ESP.random(); }
#else
using Settings = Preferences;
HardwareSerial sensorSerial(2);
uint32_t randomWord() { return esp_random(); }
#endif
Settings settings;
Adafruit_Fingerprint finger(&sensorSerial);
Adafruit_SSD1306 oled(128, 64, &Wire, -1);
// Kept for the whole run so HTTPS keep-alive avoids a TLS handshake on every request.
WiFiClientSecure tls;
HTTPClient http;
bool displayReady = false, sensorReady = false, storageReady = false;
uint8_t oledAddress = 0;
bool isOut = false;
std::vector<String> pending;
String serialLine, screenLine = "Starting", screenDetail;
uint32_t lastSend = 0, lastScan = 0, lastMatch = 0, lastSync = 0, lastResult = 0;
uint16_t lastFinger = 0;
bool requireRemoval = false, lastButton = HIGH;
RTC_DS3231 rtc;
bool rtcReady = false;
int touchActive = -1;  // level of the R307 touch wire while a finger is present; -1 = no wire, poll the sensor

// Office Wi-Fi comes from the server and is stored in flash; the fallback hotspot is built in.
enum NetTarget : uint8_t { NET_OFFICE, NET_FALLBACK };
NetTarget netTarget = NET_FALLBACK;
bool netUp = false, serverOk = false;
uint32_t netSince = 0, wifiVersion = 0;
String officeSsid, officePass, officeError;
volatile uint8_t disconnectReason = 0;
int resultId = 0;  // enrollment result waiting to be reported; persisted across resets

String networkName() {
  if (!USE_WIFI) return "USB";
  if (!netUp) return "OFFLINE";
  return netTarget == NET_OFFICE ? "OFFICE" : "HOTSPOT";
}
void screen(const String &line, const String &detail = "") {
  screenLine = line; screenDetail = detail;
  if (!displayReady) return;
  oled.clearDisplay(); oled.setTextColor(SSD1306_WHITE); oled.setTextSize(1);
  oled.setCursor(0, 0); oled.println("OFFICE ATTENDANCE");
  oled.println(isOut ? "MODE: OUT" : "MODE: IN");
  oled.println("NET: " + networkName() + (USE_WIFI && netUp ? (serverOk ? " SRV OK" : " SRV --") : ""));
  oled.println(line); oled.println(detail);
  oled.println("Pending: " + String(pending.size())); oled.display();
}
void redraw() { screen(screenLine, screenDetail); }
void logMessage(const String &message) {
  StaticJsonDocument<512> d; d["type"] = "status"; d["message"] = message;
  serializeJson(d, Serial); Serial.println();
}
void setMode(bool out) {
  isOut = out; settings.putBool("out", out); screen("Ready");
}
String filePath(const String &id) { return "/events/" + id + ".json"; }
void acknowledge(const String &id) {
  if (pending.empty() || pending.front() != id) return;
  if (LittleFS.remove(filePath(id))) pending.erase(pending.begin());
  else logMessage("Cannot remove queued event; retrying safely");
}
void loadQueue() {
  LittleFS.mkdir("/events");
#if defined(ESP8266)
  Dir directory = LittleFS.openDir("/events");
  while (directory.next()) {
    String name = directory.fileName();
    if (name.endsWith(".json")) pending.push_back(name.substring(0, name.length() - 5));
  }
#else
  File directory = LittleFS.open("/events");
  for (File f = directory.openNextFile(); f; f = directory.openNextFile()) {
    String name = f.name();
    int slash = name.lastIndexOf('/'); if (slash >= 0) name = name.substring(slash + 1);
    if (name.endsWith(".json")) pending.push_back(name.substring(0, name.length() - 5));
    f.close();
  }
#endif
  std::sort(pending.begin(), pending.end());
}
// Write/close a temp file first, then rename. Never auto-format a failed filesystem.
// Returns "" on success, otherwise the failing step for diagnosis.
String writeAtomic(const String &path, const String &content) {
  errno = 0;
  if (LittleFS.exists("/pending.tmp") && !LittleFS.remove("/pending.tmp")) return "cannot remove stale temp file (errno " + String(errno) + ")";
  File f = LittleFS.open("/pending.tmp", "w");
  if (!f) return "cannot create temp file (errno " + String(errno) + ")";
  size_t written = f.print(content);
  f.flush(); f.close();
  if (written != content.length()) return "short write " + String(written) + "/" + String(content.length()) + " (errno " + String(errno) + ")";
  if (!LittleFS.rename("/pending.tmp", path)) return "rename to " + path + " failed (errno " + String(errno) + ")";
  return "";
}
bool enqueue(uint16_t slot, uint16_t confidence) {
  if (!storageReady) { logMessage("Scan NOT saved: storage not mounted"); return false; }
  if (pending.size() >= MAX_PENDING_EVENTS) { logMessage("Scan NOT saved: queue full"); return false; }
  time_t now = time(nullptr);
  // 96-bit random identity; collisions do not depend on uptime or the device clock. Kept to 24 characters
  // because the event file name ("<id>.json") must fit LittleFS's 31-character name limit.
  char id[25]; snprintf(id, sizeof(id), "%08lx%08lx%08lx",
      (unsigned long)randomWord(), (unsigned long)randomWord(), (unsigned long)randomWord());
  StaticJsonDocument<512> event;
  event["event_id"] = id; event["device_id"] = DEVICE_ID;
  event["template_id"] = slot; event["confidence"] = confidence;
  event["action"] = isOut ? "OUT" : "IN"; event["uptime_ms"] = millis();
  if (now > 1700000000) {
    char stamp[25]; struct tm utc; gmtime_r(&now, &utc);
    strftime(stamp, sizeof(stamp), "%Y-%m-%dT%H:%M:%SZ", &utc);
    event["occurred_at"] = stamp;
  } else event["occurred_at"] = nullptr;
  String body; serializeJson(event, body);
  String problem = writeAtomic(filePath(id), body);
  if (problem.length()) { logMessage("Scan NOT saved: " + problem); return false; }
  pending.push_back(id); return true;
}

// ---- Wi-Fi: office network first, fallback hotspot when the office one fails ----
bool hasOffice() { return officeSsid.length() > 0; }
bool hasFallback() { return strlen(FALLBACK_WIFI_SSID) > 0; }
String wifiReason() {
  switch (disconnectReason) {
    case 201: return "network not found";
    case 2: case 15: case 202: case 204: return "wrong password or rejected";
    case 0: return "no response";
    default: return "reason " + String(disconnectReason);
  }
}
void startWifi(NetTarget target) {
  netTarget = target; netUp = false; serverOk = false; netSince = millis(); disconnectReason = 0;
  tls.stop(); WiFi.disconnect(); delay(50);
  if (target == NET_OFFICE) WiFi.begin(officeSsid.c_str(), officePass.c_str());
  else WiFi.begin(FALLBACK_WIFI_SSID, FALLBACK_WIFI_PASSWORD);
  logMessage("Wi-Fi: trying " + String(target == NET_OFFICE ? "office network " + officeSsid : "fallback hotspot " + String(FALLBACK_WIFI_SSID)));
  redraw();
}
void wifiTick() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!netUp) {
      netUp = true; netSince = millis(); lastSync = 0;
      if (netTarget == NET_OFFICE) officeError = "";
      logMessage("Wi-Fi connected: " + WiFi.SSID() + " IP " + WiFi.localIP().toString());
      redraw();
    }
    if (netTarget == NET_FALLBACK && hasOffice() && millis() - netSince > OFFICE_RETRY_MS) startWifi(NET_OFFICE);
    return;
  }
  if (netUp) { netUp = false; serverOk = false; netSince = millis(); tls.stop(); logMessage("Wi-Fi disconnected"); redraw(); }
  if (millis() - netSince < WIFI_ATTEMPT_MS) return;  // the Wi-Fi driver keeps retrying meanwhile
  if (netTarget == NET_OFFICE) { officeError = wifiReason(); logMessage("Office Wi-Fi failed: " + officeError); }
  NetTarget next = netTarget == NET_OFFICE ? NET_FALLBACK : NET_OFFICE;
  if (next == NET_OFFICE && !hasOffice()) next = NET_FALLBACK;
  if (next == NET_FALLBACK && !hasFallback()) next = NET_OFFICE;
  if (next == NET_OFFICE && !hasOffice()) { netSince = millis(); logMessage("No Wi-Fi configured"); return; }
  startWifi(next);
}
void applyWifi(JsonObject wifi) {
  uint32_t version = wifi["version"] | 0;
  String ssid = wifi["ssid"] | "", pass = wifi["password"] | "";
  if (!version || !ssid.length()) return;
  settings.putString("wifi_ssid", ssid); settings.putString("wifi_pass", pass); settings.putUInt("wifi_ver", version);
  officeSsid = ssid; officePass = pass; wifiVersion = version; officeError = "";
  logMessage("Office Wi-Fi saved from server: " + ssid + " (version " + String(version) + "); switching");
  screen("Wi-Fi updated", ssid.substring(0, 21));
  startWifi(NET_OFFICE);
}

// ---- HTTPS to the attendance server ----
int post(const String &path, const String &body, String &reply) {
  if (!String(SERVER_URL).startsWith("https://") || strlen_P(ROOT_CA) < 100) {
    logMessage("Configure HTTPS URL and ROOT_CA; queue retained"); return -1;
  }
#if defined(ESP8266)
  // BearSSL checks certificate dates against the clock, so HTTPS waits for NTP.
  if (time(nullptr) < 1700000000) { logMessage("Waiting for NTP clock before HTTPS"); return -1; }
#else
  http.setConnectTimeout(5000);
#endif
  if (!http.begin(tls, String(SERVER_URL) + path)) return -1;
  http.setTimeout(6000);
  http.addHeader("Content-Type", "application/json"); http.addHeader("X-API-Key", DEVICE_API_KEY);
  int code = http.POST(body);
  if (code > 0) reply = http.getString();
  http.end();
  if (code <= 0) tls.stop();  // drop a half-open connection; the next request reconnects
  serverOk = code > 0;
  return code;
}
void sendPending() {
  if (pending.empty() || millis() - lastSend < 1000) return;
  lastSend = millis();
  File f = LittleFS.open(filePath(pending.front()), "r");
  StaticJsonDocument<512> event;
  if (!f || deserializeJson(event, f)) { logMessage("Queue file unreadable: " + pending.front()); return; }
  f.close();
  if (!USE_WIFI) {
    StaticJsonDocument<768> packet; packet["type"] = "attendance";
    packet["event"].set(event.as<JsonObject>());
    serializeJson(packet, Serial); Serial.println(); lastSend += 2000; return;
  }
  String body, reply; serializeJson(event, body);
  int code = post("/api/events", body, reply);
  if (code == 200) {
    StaticJsonDocument<256> answer;
    if (!deserializeJson(answer, reply)) {
      String status = answer["status"] | "";
      if (String(answer["event_id"] | "") == pending.front() &&
          (status == "recorded" || status == "duplicate" || status == "unmapped")) { acknowledge(pending.front()); redraw(); return; }
    }
  } else logMessage("Server HTTP " + String(code) + "; queue retained");
  lastSend += 2000;  // back off after a failure
}

// ---- Fingerprint enrollment (USB command or server request) ----
String captureError;
bool cancelPressed() {
  if (digitalRead(MODE_BUTTON) != LOW) return false;
  lastButton = LOW;  // the loop must not also treat this press as an IN/OUT toggle
  return true;
}
bool capture(uint8_t buffer, uint32_t timeout) {
  uint32_t start = millis();
  int lastError = -1;
  bool settling = true;
  while (millis() - start < timeout) {
    if (cancelPressed()) { captureError = "cancelled at scanner"; logMessage("Enrollment cancelled with the button"); return false; }
    int result = finger.getImage();
    if (result == FINGERPRINT_OK && settling) {
      settling = false; delay(250); continue;  // the first frame is often a half-pressed finger
    }
    if (result == FINGERPRINT_OK) {
      result = finger.image2Tz(buffer);
      if (result == FINGERPRINT_OK) return true;
      if (result != lastError) {
        logMessage("Capture image2Tz error=0x" + String(result, HEX) + "; lift finger and try again");
        screen("Read unclear", "Lift and place again");
      }
    } else if (result == FINGERPRINT_NOFINGER) {
      settling = true; delay(75); continue;
    } else if (result != lastError) {
      logMessage("Capture getImage error=0x" + String(result, HEX) + "; retrying");
    }
    lastError = result;
    delay(100);
  }
  captureError = lastError < 0 ? "no finger placed in time" : "sensor error 0x" + String(lastError, HEX);
  logMessage(lastError < 0 ? "Capture timeout: no finger image received" :
      "Capture timeout; last error=0x" + String(lastError, HEX));
  return false;
}
bool waitRemoved(uint32_t timeout) {
  uint32_t start = millis();
  while (millis() - start < timeout) { if (finger.getImage() == FINGERPRINT_NOFINGER) return true; delay(50); }
  return false;
}
// Occupied-slot bitmap for one 256-slot page (R30x ReadIndexTable, 0x1F); retries communication errors.
bool readIndexPage(uint8_t page, uint8_t bitmap[32]) {
  for (int attempt = 0; attempt < 3; ++attempt) {
    uint8_t data[] = {0x1F, page};
    Adafruit_Fingerprint_Packet packet(FINGERPRINT_COMMANDPACKET, sizeof(data), data);
    finger.writeStructuredPacket(packet);
    if (finger.getStructuredPacket(&packet) == FINGERPRINT_OK && packet.type == FINGERPRINT_ACKPACKET &&
        packet.length >= 35 && packet.data[0] == FINGERPRINT_OK) {
      memcpy(bitmap, packet.data + 1, 32); return true;
    }
    delay(100);
  }
  return false;
}
// Empty string when the slot is confirmed empty; otherwise why enrollment must not write it.
// A communication error must never be treated as permission to overwrite a slot.
String slotProblem(uint16_t slot) {
  uint8_t bitmap[32]; int indexed = -1;
  if (readIndexPage(slot / 256, bitmap)) indexed = (bitmap[(slot % 256) / 8] >> (slot % 8)) & 1;
  if (indexed == 1) return "Slot occupied; use a fresh slot";
  int code = -1;
  for (int attempt = 0; attempt < 3; ++attempt) {
    code = finger.loadModel(slot);
    if (code == FINGERPRINT_OK) return "Slot occupied; use a fresh slot";
    if (code == FINGERPRINT_BADLOCATION || code == FINGERPRINT_DBRANGEFAIL) return "";
    delay(100);
  }
  if (indexed == 0) return "";  // the index table is authoritative when the load probe is inconclusive
  return "Could not confirm an empty slot (sensor code 0x" + String(code, HEX) + ")";
}
// Returns the outcome message; the prefixes are parsed by tools/device.py.
bool enroll(int slot, const String &who, uint32_t firstWait, String &message) {
  auto fail = [&](const String &text) {
    message = text; logMessage(text); screen("Enroll failed", text.substring(0, 21)); requireRemoval = true; return false;
  };
  if (!sensorReady || slot < 1 || slot >= finger.capacity) return fail("Invalid slot or sensor unavailable");
  String problem = slotProblem(slot);
  if (problem.length()) return fail(problem);
  String title = who.length() ? "Enroll " + who.substring(0, 14) : "Enroll slot " + String(slot);
  constexpr int ATTEMPTS = 3;
  for (int attempt = 1; ; ++attempt) {
    screen(title, attempt == 1 ? "Place finger" : "Again: place finger");
    uint32_t wait = attempt == 1 ? firstWait : 60000;
    logMessage("Place finger (" + String(wait / 1000) + " seconds), attempt " + String(attempt) + " of " + String(ATTEMPTS));
    if (!capture(1, wait)) return fail("First capture failed: " + captureError);
    screen(title, "Remove finger"); logMessage("Remove finger");
    if (!waitRemoved(10000)) return fail("Removal timed out");
    screen(title, "Same finger again"); logMessage("Place the same finger again (60 seconds)");
    if (!capture(2, 60000)) return fail("Enrollment failed: second capture: " + captureError);
    int result = finger.createModel();
    if (result == FINGERPRINT_OK) break;
    if (result != FINGERPRINT_ENROLLMISMATCH || attempt == ATTEMPTS)
      return fail("Enrollment failed: fingers did not match after " + String(attempt) + " attempts (code 0x" + String(result, HEX) + ")");
    logMessage("The two scans did not match; lift and start again");
    screen(title, "No match. Lift finger");
    if (!waitRemoved(10000)) return fail("Removal timed out");
    delay(800);
  }
  int result = finger.storeModel(slot);
  if (result != FINGERPRINT_OK) return fail("Enrollment failed: storeModel code=0x" + String(result, HEX));
  message = "Enrolled slot " + String(slot) + (who.length() ? " for " + who : ". Assign it to a staff member in the dashboard.");
  logMessage(message); screen("Enrolled!", who.length() ? who.substring(0, 21) : "Slot " + String(slot));
  requireRemoval = true;
  return true;
}
void sendResult() {
  if (!resultId || millis() - lastResult < 3000) return;
  lastResult = millis();
  StaticJsonDocument<384> d;
  d["device_id"] = DEVICE_ID; d["success"] = settings.getBool("res_ok", false); d["message"] = settings.getString("res_msg", "");
  String body, reply; serializeJson(d, body);
  int code = post("/api/device/enrollments/" + String(resultId) + "/result", body, reply);
  // 404/409/422 will never succeed on retry; 401 (key) and 5xx are retried.
  if (code == 200 || code == 404 || code == 409 || code == 422) {
    logMessage("Enrollment " + String(resultId) + " reported to server (HTTP " + String(code) + ")");
    resultId = 0; settings.putInt("res_id", 0);
  }
}
void runCommand(JsonObject command) {
  if (String(command["type"] | "") != "enroll") return;
  int id = command["id"] | 0, slot = command["slot"] | 0;
  String who = command["employee_name"] | "";
  if (!who.length()) who = command["employee_code"] | "";
  if (id <= 0) return;
  logMessage("Server requested enrollment " + String(id) + " for " + who + " in slot " + String(slot));
  tls.stop();  // the server closes idle connections during a long enrollment
  String message; bool ok = enroll(slot, who, ENROLL_WAIT_MS, message);
  delay(2500);  // keep the outcome readable on the OLED
  // Persist before reporting so a reset or outage cannot lose a stored template's result.
  settings.putBool("res_ok", ok); settings.putString("res_msg", message.substring(0, 190)); settings.putInt("res_id", id);
  resultId = id; lastResult = 0;
  sendResult();
}

// ---- DS3231 battery clock: keeps UTC through power cuts while offline ----
void startClock() {
  if (!rtc.begin(&Wire)) { logMessage("DS3231 clock not found; time comes from the network only"); return; }
  rtcReady = true;
  if (rtc.lostPower()) { logMessage("DS3231 has no valid time (new or flat battery); waiting for network time"); return; }
  time_t saved = rtc.now().unixtime();
  if (saved > 1700000000) { struct timeval tv = {saved, 0}; settimeofday(&tv, nullptr); logMessage("Clock set from DS3231"); }
}
// The server time arrives over verified HTTPS; it corrects both the system clock and the DS3231.
void trustServerTime(time_t serverTime) {
  if (serverTime < 1700000000) return;
  time_t now = time(nullptr);
  if (now < 1700000000 || labs((long)(now - serverTime)) > 5) {
    struct timeval tv = {serverTime, 0}; settimeofday(&tv, nullptr); logMessage("Clock set from server");
  }
  if (rtcReady && (rtc.lostPower() || labs((long)rtc.now().unixtime() - (long)serverTime) > 2)) {
    rtc.adjust(DateTime((uint32_t)serverTime)); logMessage("DS3231 clock updated");
  }
}

// ---- R307 touch wire: read the sensor only while a finger touches it, so its light stays off ----
void detectTouchWire() {
#if !defined(ESP8266)
  if (FINGER_TOUCH_PIN < 0) return;
  pinMode(FINGER_TOUCH_PIN, INPUT_PULLDOWN); delay(5); int pulledDown = digitalRead(FINGER_TOUCH_PIN);
  pinMode(FINGER_TOUCH_PIN, INPUT_PULLUP); delay(5); int pulledUp = digitalRead(FINGER_TOUCH_PIN);
  if (pulledDown == LOW && pulledUp == HIGH) {  // the line follows the pulls: nothing drives it
    pinMode(FINGER_TOUCH_PIN, INPUT_PULLDOWN); logMessage("R307 touch wire not detected; polling the sensor"); return;
  }
  pinMode(FINGER_TOUCH_PIN, INPUT);
  touchActive = pulledDown == HIGH ? LOW : HIGH;  // boot level means "no finger"
  logMessage(String("R307 touch wire detected; finger = ") + (touchActive == HIGH ? "HIGH" : "LOW"));
#endif
}
bool fingerTouched() { return touchActive < 0 || digitalRead(FINGER_TOUCH_PIN) == touchActive; }

void syncServer() {
  if (lastSync && millis() - lastSync < SYNC_INTERVAL_MS) return;
  lastSync = millis();
  if (sensorReady) finger.getTemplateCount();
  StaticJsonDocument<512> d;
  d["device_id"] = DEVICE_ID; d["firmware"] = FIRMWARE_VERSION;
  d["network"] = netTarget == NET_OFFICE ? "office" : "fallback"; d["ssid"] = WiFi.SSID();
  d["rssi"] = constrain(WiFi.RSSI(), -127, 0); d["wifi_version"] = wifiVersion; d["office_error"] = officeError;
  d["pending"] = pending.size(); d["sensor"] = sensorReady;
  d["templates"] = sensorReady ? finger.templateCount : 0; d["capacity"] = sensorReady ? finger.capacity : 0;
  d["mode"] = isOut ? "OUT" : "IN"; d["clock_ok"] = time(nullptr) > 1700000000; d["rtc"] = rtcReady; d["touch"] = touchActive >= 0; d["uptime_ms"] = millis();
  String body, reply; serializeJson(d, body);
  bool wasOk = serverOk;
  int code = post("/api/device/sync", body, reply);
  if (code != 200) { logMessage("Server sync HTTP " + String(code)); if (wasOk) redraw(); return; }
  if (!wasOk) redraw();
  DynamicJsonDocument answer(1536);
  if (deserializeJson(answer, reply)) return;
  // Server time over verified HTTPS covers offices where NTP is blocked.
  trustServerTime(answer["server_time"] | 0);
  if (answer["wifi"].is<JsonObject>()) { applyWifi(answer["wifi"].as<JsonObject>()); return; }
  if (answer["command"].is<JsonObject>()) runCommand(answer["command"].as<JsonObject>());
}

bool probeSensor() { return finger.verifyPassword() && finger.getParameters() == FINGERPRINT_OK; }
// A sensor powered late or reconnected is picked up without a reset.
void retrySensor() {
  static uint32_t lastProbe = 0;
  if (sensorReady || millis() - lastProbe < 10000) return;
  lastProbe = millis();
  if (!probeSensor()) return;
  sensorReady = true;
  logMessage("Fingerprint sensor ready; capacity=" + String(finger.capacity));
  screen(storageReady ? "Ready" : "Hardware/storage error");
}

String fsUsage() {
#if defined(ESP8266)
  FSInfo info; if (!LittleFS.info(info)) return "";
  return "; fs_used=" + String(info.usedBytes) + "/" + String(info.totalBytes);
#else
  return "; fs_used=" + String(LittleFS.usedBytes()) + "/" + String(LittleFS.totalBytes());
#endif
}
String iramHeap() {
#if defined(MMU_IRAM_HEAP)
  HeapSelectIram iram; return "; iram_heap=" + String(ESP.getFreeHeap());
#else
  return "";
#endif
}
void command(String line) {
  line.trim();
  if (line.startsWith("ACK ") && !USE_WIFI) acknowledge(line.substring(4));
  else if (line.startsWith("TIME ")) {
    time_t epoch = strtoll(line.substring(5).c_str(), nullptr, 10);
    if (epoch > 1700000000) { struct timeval tv = {epoch, 0}; settimeofday(&tv, nullptr); }
  } else if (line == "IN" || line == "OUT") { setMode(line == "OUT"); }
  else if (line == "STATUS") {
    if (sensorReady) finger.getTemplateCount();
    logMessage("Device " + String(DEVICE_ID) + "; firmware=" + FIRMWARE_VERSION + "; sensor=" + String(sensorReady) +
      "; oled=" + String(displayReady) + "; oled_address=0x" + String(oledAddress, HEX) +
      "; storage=" + String(storageReady) + (storageReady ? fsUsage() : String("")) + "; pending=" + String(pending.size()) +
      "; mode=" + (isOut ? "OUT" : "IN") + "; capacity=" + String(finger.capacity) +
      "; templates=" + String(finger.templateCount) + "; rtc=" + String(rtcReady) + "; touch=" + String(touchActive >= 0 ? (touchActive == HIGH ? "high" : "low") : "none") + "; heap=" + String(ESP.getFreeHeap()) + iramHeap() + "; net=" + networkName() +
      (USE_WIFI ? "; ssid=" + WiFi.SSID() + "; ip=" + WiFi.localIP().toString() + "; server=" + String(serverOk) +
       "; office_wifi=" + (hasOffice() ? officeSsid + " v" + String(wifiVersion) : String("none")) +
       (officeError.length() ? "; office_error=" + officeError : "") : ""));
  } else if (line == "FSCHECK") {
    // Same write/rename path and name length as a real scan, under a name the queue ignores.
    if (!storageReady) { logMessage("FSCHECK: storage not mounted"); return; }
    LittleFS.mkdir("/events");
    String path = "/events/" + String("0123456789abcdef01234567") + ".chk0";
    String problem = writeAtomic(path, "{\"check\":true}");
    bool removed = problem.length() ? true : LittleFS.remove(path);
    logMessage("FSCHECK: " + (problem.length() ? "FAILED " + problem : String(removed ? "OK" : "OK but test file not removed")) +
      "; events_dir=" + String(LittleFS.exists("/events")) + fsUsage());
  } else if (line == "SLOTS") {
    if (!sensorReady) { logMessage("Sensor unavailable"); return; }
    String list; uint8_t bitmap[32];
    for (uint16_t page = 0; page * 256 < finger.capacity; ++page) {
      if (!readIndexPage(page, bitmap)) { logMessage("Could not read sensor index page " + String(page)); return; }
      for (uint16_t i = 0; i < 256; ++i) if ((bitmap[i / 8] >> (i % 8)) & 1) list += (list.length() ? "," : "") + String(page * 256 + i);
    }
    logMessage("Occupied slots: " + (list.length() ? list : String("none")));
  } else if (line.startsWith("ENROLL ")) { String message; enroll(line.substring(7).toInt(), "", 60000, message); }
  else if (line.startsWith("DELETE ")) {
    int slot = line.substring(7).toInt();
    if (!pending.empty()) { logMessage("Drain queued events before deleting a fingerprint"); return; }
    if (sensorReady && slot > 0 && slot < finger.capacity)
      logMessage(finger.deleteModel(slot) == FINGERPRINT_OK ? "Deleted; keep historical slot assignment" : "Delete failed");
  }
}
void setup() {
  Serial.begin(115200); delay(400);
  settings.begin("attendance", false); isOut = settings.getBool("out", false);
  if (settings.isKey("wifi_ssid")) { officeSsid = settings.getString("wifi_ssid", ""); officePass = settings.getString("wifi_pass", ""); }
  wifiVersion = settings.getUInt("wifi_ver", 0); resultId = settings.getInt("res_id", 0);
  pinMode(MODE_BUTTON, INPUT_PULLUP);
  Wire.begin(OLED_SDA, OLED_SCL);
  startClock();
  // Probe first: display.begin alone does not reliably identify a missing panel.
  for (unsigned attempt = 0; attempt < 5 && !displayReady; ++attempt) {
    for (uint8_t address : {0x3C, 0x3D}) {
      Wire.beginTransmission(address);
      if (Wire.endTransmission() == 0 && oled.begin(SSD1306_SWITCHCAPVCC, address)) {
        displayReady = true; oledAddress = address; break;
      }
    }
    if (!displayReady) delay(100);
  }
#if defined(ESP8266)
  LittleFS.setConfig(LittleFSConfig(false));  // never auto-format: a mount failure must not erase queued scans
  storageReady = LittleFS.begin();
#else
  storageReady = LittleFS.begin(false);
#endif
  if (storageReady) loadQueue();
#if !defined(ESP8266)
  sensorSerial.begin(SENSOR_BAUD, SERIAL_8N1, SENSOR_RX, SENSOR_TX);
#endif
  finger.begin(SENSOR_BAUD); delay(300);
  sensorReady = probeSensor();
  detectTouchWire();
  if (USE_WIFI) {
    WiFi.persistent(false);  // credentials live in our own settings, not the SDK's flash copy
#if defined(ESP8266)
    tls.setTrustAnchors(new BearSSL::X509List(ROOT_CA));
    WiFi.hostname("attendance-" + String(DEVICE_ID)); WiFi.mode(WIFI_STA);
    disconnectHandler = WiFi.onStationModeDisconnected([](const WiFiEventStationModeDisconnected &e) { disconnectReason = e.reason; });
#else
    tls.setCACert(ROOT_CA); tls.setHandshakeTimeout(15);  // seconds; the default would stall scanning for 2 minutes
    WiFi.setHostname(("attendance-" + String(DEVICE_ID)).c_str()); WiFi.mode(WIFI_STA);
    WiFi.onEvent([](WiFiEvent_t, WiFiEventInfo_t info) { disconnectReason = info.wifi_sta_disconnected.reason; },
                 ARDUINO_EVENT_WIFI_STA_DISCONNECTED);
#endif
    configTime(0, 0, "pool.ntp.org", "time.google.com");
    if (hasOffice() || hasFallback()) startWifi(hasOffice() ? NET_OFFICE : NET_FALLBACK);
    else logMessage("No Wi-Fi configured: set FALLBACK_WIFI_SSID in config.h");
  }
  logMessage(storageReady ? "Storage ready" : "Storage unavailable: attendance disabled; provision filesystem once");
  logMessage(sensorReady ? "Fingerprint sensor ready" : "Fingerprint sensor missing; check wiring and power");
  logMessage(displayReady ? "OLED ready at 0x" + String(oledAddress, HEX) : "OLED missing; check SDA/SCL and power");
  screen(storageReady && sensorReady ? "Ready" : "Hardware/storage error");
}
void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') { command(serialLine); serialLine = ""; }
    else if (serialLine.length() < 200) serialLine += c;
    else serialLine = "";
  }
  static uint32_t buttonTime = 0;
  bool button = digitalRead(MODE_BUTTON);
  if (button == LOW && lastButton == HIGH && millis() - buttonTime > 300) {
    setMode(!isOut); buttonTime = millis();
  }
  lastButton = button;
  if (USE_WIFI) {
    wifiTick();
    if (netUp) {
      if (resultId) sendResult();  // report a finished enrollment before asking for more work
      else { sendPending(); syncServer(); }
    }
  } else sendPending();
  retrySensor();
  if (!sensorReady || !storageReady || millis() - lastScan < 150) { delay(5); return; }
  lastScan = millis();
  if (!fingerTouched()) {  // touch wire says no finger: leave the sensor (and its light) idle
    if (requireRemoval) screen("Ready");
    requireRemoval = false; return;
  }
  if (requireRemoval && touchActive >= 0) return;  // finger still resting after a scan
  int image = finger.getImage();
  if (image == FINGERPRINT_NOFINGER) { if (requireRemoval) screen("Ready"); requireRemoval = false; return; }
  if (image != FINGERPRINT_OK || requireRemoval) return;
  requireRemoval = true;
  if (finger.image2Tz() != FINGERPRINT_OK) { screen("Try again"); return; }
  int result = finger.fingerSearch();
  if (result == FINGERPRINT_NOTFOUND) { screen("Unknown fingerprint"); return; }
  if (result != FINGERPRINT_OK) { screen("Sensor read error"); return; }
  if (finger.fingerID == lastFinger && millis() - lastMatch < 10000) { screen("Already scanned"); return; }
  if (enqueue(finger.fingerID, finger.confidence)) {
    lastFinger = finger.fingerID; lastMatch = millis(); screen("Saved on device", "Slot " + String(finger.fingerID));
  } else screen("NOT SAVED", "Queue full/storage error");
}
