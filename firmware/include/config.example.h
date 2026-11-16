#pragma once
// Identity and network only; pins and display come from board.h (chosen by the PlatformIO environment).
#define CONFIG_H_VERSION 2
// Generate the real config.h with: .venv\Scripts\python.exe -m tools.firmware_config
// true: the ESP32 talks to the server over Wi-Fi. false: USB bridge through this computer.
constexpr bool USE_WIFI = true;
constexpr char DEVICE_ID[] = "office-01";
// Built-in fallback: turn on a phone hotspot with exactly this name/password (2.4 GHz)
// when the office Wi-Fi fails. Office Wi-Fi itself is sent from the dashboard, never compiled in.
constexpr char FALLBACK_WIFI_SSID[] = "Attendance-Setup";
constexpr char FALLBACK_WIFI_PASSWORD[] = "";
constexpr char SERVER_URL[] = "https://attendance.example.com"; // no trailing slash
constexpr char DEVICE_API_KEY[] = ""; // device key from .env; never the admin key
// PEM root CA(s) for the certificate authority serving SERVER_URL. No insecure TLS.
// PROGMEM keeps it in flash on the ESP8266 (no effect on ESP32).
constexpr char ROOT_CA[] PROGMEM = R"PEM(
)PEM";
// On-screen clock only (scans are stored in UTC): India Standard Time = UTC+5:30.
constexpr long DISPLAY_UTC_OFFSET = 19800;
