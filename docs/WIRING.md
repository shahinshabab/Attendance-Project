# Wiring — ESP32 development board

Your board has an ESP-WROOM-32 module mounted on a larger PCB with a USB connector. This guide is for that development board. **Do not apply this power wiring to a bare ESP32 module.** Pin positions vary between 30-pin/38-pin boards: follow printed GPIO/power labels and your board's schematic.

Open [wiring.svg](wiring.svg) in a browser for the complete labelled diagram. The drawing is a functional connection diagram, not a physical pin-order drawing.

## Connection table (current setup)

Board: 30-pin ESP32 DevKit (ESP-WROOM-32, CP2102), labels as printed on the board. [wiring.png](wiring.png) shows both the connections and where each pin sits on the board.

| From | To ESP32 pin (printed label) | Notes |
| --- | --- | --- |
| 5 V USB phone charger | micro-USB port | 1 A or more. Powers the board, and the R307 through VIN |
| R307 VCC | **VIN** (bottom left) | 5 V while the board is USB-powered |
| R307 GND | **GND** (left, next to VIN) | Shared with the button |
| R307 TX | **RX2** (GPIO16) | Sensor sends → board receives |
| R307 RX | **TX2** (GPIO17) | Board sends → sensor receives. Not detected? Swap TX/RX |
| R307 Touch, 3.3V-T | not connected | Not used by this firmware |
| OLED VCC | **3V3** (bottom right) | 3.3 V only |
| OLED GND | **GND** (right, next to 3V3) | |
| OLED SDA | **D21** | I²C data |
| OLED SCL | **D22** | I²C clock |
| IN/OUT button (optional) | **D25** and **GND** | Normally open; also cancels an enrollment |

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
| Optional IN/OUT button | **D7** (GPIO13) and **G** | Also cancels an enrollment |

Leave D3, D4, D8, RX and TX unconnected (boot and USB pins). Do not connect the buck converter and the computer USB at the same time; unplug the buck output before uploading firmware. Limitations versus the ESP32: the sensor uses software serial, HTTPS waits for NTP time, and the offline queue holds 150 scans.
