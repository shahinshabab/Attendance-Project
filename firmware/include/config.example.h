#pragma once
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
#if defined(ESP8266)
// NodeMCU ESP8266: GPIO numbers, NodeMCU label in brackets. Sensor uses software serial.
constexpr int SENSOR_RX = 14; // [D5] ESP RX <- R307 TX
constexpr int SENSOR_TX = 12; // [D6] ESP TX -> R307 RX
constexpr int OLED_SDA = 4;   // [D2]
constexpr int OLED_SCL = 5;   // [D1]
constexpr int MODE_BUTTON = 13; // [D7] optional normally-open button to GND; also cancels an enrollment
constexpr unsigned MAX_PENDING_EVENTS = 150; // limited RAM
#else
constexpr int SENSOR_RX = 16; // ESP RX <- R307 TX
constexpr int SENSOR_TX = 17; // ESP TX -> R307 RX
constexpr int OLED_SDA = 21;
constexpr int OLED_SCL = 22;
constexpr int MODE_BUTTON = 25; // optional normally-open button to GND; also cancels an enrollment
constexpr unsigned MAX_PENDING_EVENTS = 500;
#endif
constexpr unsigned long SENSOR_BAUD = 57600;
