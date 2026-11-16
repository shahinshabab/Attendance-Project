# Wiring — ESP32 development board

Your board has an ESP-WROOM-32 module mounted on a larger PCB with a USB connector. This guide is for that development board. **Do not apply this power wiring to a bare ESP32 module.** Pin positions vary between 30-pin/38-pin boards: follow printed GPIO/power labels and your board's schematic.

Open [wiring.svg](wiring.svg) in a browser for the complete labelled diagram. The drawing is a functional connection diagram, not a physical pin-order drawing.

## Connection table (current setup)

Board: 30-pin ESP32 DevKit (ESP-WROOM-32, CP2102), labels as printed on the board. [wiring.png](wiring.png) shows both the connections and where each pin sits on the board.

| From | To ESP32 pin (printed label) | Notes |
| --- | --- | --- |
| 5 V USB phone charger | micro-USB port | 1 A or more. Powers the board, and the R307 through VIN |
| R307 VCC | **VIN** (bottom left) | 5 V while the board is USB-powered |
| R307 GND | **GND** (left, next to VIN) | |
| R307 TX | **RX2** (GPIO16) | Sensor sends → board receives |
| R307 RX | **TX2** (GPIO17) | Board sends → sensor receives. Not detected? Swap TX/RX |
| R307 Touch | **D27** | Finger-detect output: the sensor (and its light) is only used while a finger touches it |
| R307 3.3V-T | **3V3** | Power for the touch circuit |
| TFT VCC, TFT LED | **3V3** | 1.8″ ST7735 128×160; LED is the backlight |
| TFT GND | **GND** (right, next to 3V3) | |
| TFT SCK | **D18** | SPI clock |
| TFT SDA | **D23** | SPI data (MOSI) |
| TFT A0 (DC/RS) | **D4** | Data/command |
| TFT RESET | **D19** | |
| TFT CS | **D5** | Chip select |
| DS3231 VCC | **3V3** | Use 3.3 V so the module does not try to charge a CR2032 |
| DS3231 GND | **GND** | |
| DS3231 SDA | **D21** | I²C data (shared bus; address 0x68) |
| DS3231 SCL | **D22** | I²C clock |
| Buzzer driver input | **D32** | Through a 1 kΩ resistor to the S8050 base (see below) |
| Buzzer driver supply | **VIN** and **GND** | 5 V for the buzzer, shared with the R307 |

3V3 feeds four wires and GND several: join them on a small rail or terminal block. The firmware detects the touch wire at boot; without it, it keeps polling the sensor (the light blinks). If the screen says "Place your finger" but the sensor never lights up, the touch wire is held at one level: check that 3.3V-T has 3.3 V and that the Touch wire is on the R307's touch pin, or send `TOUCH 0` over USB to poll instead. The DS3231 sets the clock at boot, so offline scans after a power cut keep their real time. The ESP32 firmware drives the TFT (screens as in [tft-screens.png](tft-screens.png)); the OLED is no longer used on the ESP32. If the picture is upside down, shifted, or has wrong colours or a noisy edge, fix it over USB without rebuilding: `TFTROT 2` turns it 180°, and `TFTTAB 0`, `1` or `2` selects the ST7735 variant (green, red or black tab; black is the default). Both settings are saved on the board.

### Buzzer (TMB12A05)

The TMB12A05 is an active 5 V magnetic buzzer (it beeps by itself when powered, about 30 mA). That is more current than a GPIO should supply and needs 5 V, so a small NPN transistor switches it:

| Part | Connect |
| --- | --- |
| Buzzer **+** (longer leg, “+” on top) | **VIN** (5 V) |
| Buzzer **−** | S8050 **collector** |
| S8050 **emitter** | **GND** |
| S8050 **base** | 1 kΩ resistor → **D32**; and 10 kΩ resistor → **GND** (keeps it silent while the board boots) |
| 1N4148 diode | Across the buzzer: **stripe (cathode) to 5 V**, other end to the collector. Absorbs the coil's voltage spike |

S8050 pins, flat face toward you, legs down: **E B C** (left to right). A 2N2222A/PN2222A in a plastic TO-92 package has the same E B C order; BC547 is C B E, so check your part's pinout. If you have a three-pin buzzer *module* (VCC, I/O, GND) instead of the bare buzzer, it already contains the transistor: VCC → VIN, GND → GND, I/O → D32 directly.

Sounds: one short beep = verified (also enrolled, already scanned); three quick beeps = try again; one long beep = not registered or an error. During enrollment a tick means a capture was taken. Over USB, `BEEP` plays all three, and `BUZZER 0` / `BUZZER 1` mutes or unmutes it (saved on the board).

Power rules learned on this project:

- Use a 5 V USB phone charger. The HW-131 / MB102 breadboard supply uses linear AMS1117 regulators and overheats under the ESP32's Wi-Fi load.
- If you use a buck converter, set it to 5.0 V and confirm **+5.0 V** (not −5.0 V) at the wire ends before connecting. A reversed supply damaged the first board.
- Never put 5 V on 3V3, and never power from computer USB and an external 5 V supply at the same time.

The Robocraze four-pin display is described as I²C with VCC/GND/SCL/SDA despite “SPI/I2C” wording. Firmware probes `0x3C` and `0x3D` and uses the SSD1306 library. Robocraze also mentions SSD1315 on current stock: confirm the controller if the screen is blank or distorted. A display with CS/DC/RES pins needs different wiring and code.

## Power and signal checks before connecting

1. Unplug USB while wiring. Check labels instead of wire colours or connector position. The R307's 5 V supply and its UART logic voltage are different specifications.
2. The ESP32 GPIOs are **3.3 V only**. R307 documentation describes TTL UART compatible with 3.3 V MCUs, but confirm your exact unit's TX output and RX input specifications. If TX exceeds 3.3 V, use a UART-rated level translator on the R307 → ESP32 line. Do not put an arbitrary divider on a confirmed 3.3 V UART line. A 5 V-to-3.3 V translator/divider selection depends on the actual signal; verify it before connecting.
3. Confirm that your development board exposes USB 5 V on a pin marked `5V`, `VBUS`, or appropriately documented `VIN`. Some boards expose an input-only or differently protected rail. Do not assume every VIN label means usable USB 5 V output.
4. Start with USB as the board's only supply. The R307 can draw about 80 mA peak in its manual; allow margin for ESP32 Wi-Fi peaks and use a reliable cable/source. If the rail cannot supply the sensor, power the R307 from a separate regulated 5 V source and join **grounds only** to the ESP32. Do not connect that external positive rail to the USB-powered ESP32's power pins.
5. Do not feed external 5 V into board power pins while USB is connected unless the exact board documentation explicitly supports it. Espressif's DevKitC guide requires one supply method at a time.
6. GPIO16/17 are suitable for ESP-WROOM-32 here. Other ESP32 variants (notably some PSRAM/WROVER boards) can reserve those pins; verify the module label if yours differs.

## Sources checked

- [Robocraze R307 specifications](https://robocraze.com/products/r307-optical-fingerprint-sensor-module): main supply information and UART interface. The listing contains inconsistent voltage statements, so use the supplied module manual/markings for the final check.
- [R307 manufacturer manual, hosted by Robu](https://robu.in/wp-content/uploads/2018/05/r307-fingerprint-module-user-manual.pdf): 4.2–6 V main supply, UART connector functions, 57600 baud default. Pin order must be verified on the actual assembly.
- [Robocraze four-pin OLED guide](https://robocraze.com/blogs/post/how-to-interface-0-96-inch-oled-with-arduino-esp32-beginners-guide): I²C wiring, 3.3 V ESP32 supply, controller variation.
- [Espressif DevKitC guide](https://documentation.espressif.com/esp-dev-kits/en/latest/esp32/esp32-devkitc/user_guide.html): USB bridge, board pin functions, and power-source restrictions.
- [PlatformIO ESP32 Dev Module](https://docs.platformio.org/en/stable/boards/espressif32/esp32dev.html): build target.

## Temporary board: NodeMCU ESP8266 (V1.2, CH340)

Used until the replacement ESP32 arrives. Same firmware source (`device.ps1 ... -Board nodemcu`), same device ID `office-01`, same server and sensor fingerprints. Wire with all power off. Use the printed D-labels.

| From | To NodeMCU | Notes |
| --- | --- | --- |
| Buck converter **+5.0 V** | **VIN** | Measure +5.0 V (not −5.0 V) at the wire ends before connecting. Never 5 V into 3V3. |
| Buck converter **GND** | **G** (GND) | All grounds joined |
| R307 **VCC** | Buck **+5.0 V** | Not from the NodeMCU 3V3 pin |
| R307 **GND** | **G** | |
| R307 **TX** | **D5** (GPIO14) | Sensor → board |
| R307 **RX** | **D6** (GPIO12) | Board → sensor |
| OLED **VCC** | **3V3** | |
| OLED **GND** | **G** | |
| OLED **SDA** | **D2** (GPIO4) | |
| OLED **SCL** | **D1** (GPIO5) | |

Leave D3, D4, D8, RX and TX unconnected (boot and USB pins). Do not connect the buck converter and the computer USB at the same time; unplug the buck output before uploading firmware. Limitations versus the ESP32: the sensor uses software serial, HTTPS waits for NTP time, and the offline queue holds 150 scans.
