# Attendance scanner main board: PCB design specification

This folder will hold the custom main board for the office fingerprint attendance scanner. The aim is one PCB that JLCPCB manufactures **and assembles**. You plug the fingerprint sensor, display and button into it, mount it in the enclosure, and it runs the existing firmware with no pin changes.

**Status:** specification only. No schematic or layout files exist yet. Everything below is what the board must do; part numbers marked *(verify)* must be checked against the JLCPCB/LCSC parts library, with stock, before ordering.

## 1. What the board replaces

| Today (prototype) | On the PCB |
| --- | --- |
| ESP32 DevKit with a USB port | Bare **ESP32-WROOM-32E** module soldered to the board (see §4.1) |
| DS3231 breakout module | **DS3231SN chip on the board** with its own CR2032 coin-cell holder |
| Phone charger into the DevKit's USB port | **On-board power supply**: protected DC input, 5 V and 3.3 V regulators |
| DevKit's 3.3 V regulator feeding everything | Dedicated 1 A 3.3 V regulator with proper bulk capacitance |
| USB port for flashing (an open door) | **No USB on the board.** Flashing uses a small internal header and a USB-UART adapter |
| Loose jumper wires | **Keyed, locking connectors** that can't be plugged in backwards |
| Nothing during power cuts | **Battery backup**: 1-cell LiPo with charger, protection and automatic switch-over |

## 2. Block diagram

```
 12 V DC adapter ─► J1 ─► polyfuse ─► reverse-polarity MOSFET ─► TVS ─► 5 V buck (2 A) ─┐
 (barrel jack, standard)                                                                 ├─► EXT 5 V
 5 V USB-C (power only) ─► J2 ─► Schottky ──────────────────────────────────────────────┘     │
                                                                                               │
          ┌──────────────── battery charger (from EXT 5 V) ◄───────────────────────────────────┤
          ▼                                                                                    │
 1-cell LiPo ─► J_BAT ─► protection (DW01A + dual MOSFET) ─► 5 V boost ──► ideal-diode OR ◄───┘
 (3.7 V, 2000–3000 mAh)                                     (on only when EXT 5 V is absent)  │
                                                                                         5 V rail
                                                                        ┌────────────────┬─────┘
                                                                        ▼                ▼
                                                                3.3 V LDO (1 A)    R307 main supply
                                                                        │
              ┌─────────────────────┬──────────────────┬───────────────┼──────────────┐
              ▼                     ▼                  ▼               ▼              ▼
       ESP32-WROOM-32E ◄─I²C─► DS3231SN + CR2032   TFT 3.3 V   R307 touch    buzzer, LEDs
              │  ▲  ▲
              │  │  └── battery voltage (ADC) and "mains present" sense
              └─ J_PROG (internal 6-pin header) ◄── USB-UART adapter for flashing
```

## 3. Requirements

### 3.1 Functional

1. Run the existing firmware (`firmware/`, `-Board esp32`) **with the same GPIO numbers** as the prototype (§5).
2. Connect, through keyed connectors: R307 fingerprint sensor (6 wires, including touch), 1.8″ ST7735 TFT (8 wires), IN/OUT button, case tamper switch.
3. Keep accurate time with no power and no internet: an on-board DS3231 with a coin-cell backup.
4. Give clear feedback: a buzzer and two status LEDs (green = OK, red = error), in addition to the TFT.
5. Flash firmware **without a USB port on the board**, through an internal header (§4.5).

### 3.2 Power

| Rail | Source | Loads | Budget |
| --- | --- | --- | --- |
| VIN | **12 V barrel jack** (standard; accepts **7–24 V**) **or** 5 V USB-C (power only) | input protection | — |
| EXT 5 V | Buck converter from VIN, 2 A; USB-C 5 V ORed in through a Schottky diode | 5 V rail, battery charger | 0.5 A + charge current |
| VBAT | 1-cell LiPo/Li-ion, 3.0–4.2 V, through the protection circuit | 5 V boost during power cuts | ≈0.35 A average while on battery |
| 5 V | EXT 5 V, or the battery boost when EXT 5 V is absent (ideal-diode OR) | R307 main supply (≈50 mA, 150 mA peak), TFT VCC (≈10 mA), 3.3 V LDO input | 0.25 A typical, 0.7 A peak |
| 3.3 V | LDO from 5 V, **1 A** rated | ESP32 (150 mA average, **500 mA Wi-Fi peaks**), TFT backlight (≈40 mA), DS3231 (<1 mA), R307 touch circuit (<1 mA), LEDs and buzzer driver | 0.25 A typical, 0.65 A peak |
| RTC | CR2032 | DS3231 timekeeping only | µA |

Required protection and stability features:

- **Polyfuse** on the input (about 1.5 A hold).
- **Reverse-polarity protection** with a P-MOSFET (low loss), with a gate Zener so 24 V input can't exceed the MOSFET's gate rating. A reversed plug must not damage anything; that is exactly how the first prototype board was killed.
- **TVS diode** on VIN (rated for the 24 V maximum) against surges and plug-in spikes.
- **Bulk capacitance:** at least 470 µF on 5 V, and at least 100 µF plus 10 µF plus 100 nF next to the ESP32's 3.3 V pin, so Wi-Fi bursts don't cause resets or display glitches.
- **USB-C gives 5 V only.** Without a USB Power Delivery controller chip, a USB-C charger supplies 5 V. That is all this board needs, because 12 V arrives through the barrel jack. Higher USB-C voltages (9–20 V) would need a PD controller; not planned.
- **USB-C power-only input:** connect only VBUS and GND, plus 5.1 kΩ resistors on CC1/CC2 so USB-C chargers supply 5 V. **Leave D+/D− unconnected**, so the port can't be used for data or flashing.
- Power LED on 3.3 V, and test points on VIN, 5 V, 3.3 V and GND.
- **No battery charging circuit for the coin cell.** Many DS3231 breakout boards try to charge a CR2032, which is unsafe.

### 3.3 Battery backup

- **Cell:** one LiPo/Li-ion cell, 3.7 V nominal. Recommended: a **flat LiPo pouch, 2000–3000 mAh** (e.g. a 103450 or 104060 size), mounted behind the board like a phone battery. Runtime on 3000 mAh: about **6–8 hours** at ≈1.2 W.
- **Connection:** **JST-PH 2.0 mm 2-pin** connector (`J_BAT`, polarity printed on the silkscreen) **plus a pair of large solder pads** in parallel, for a cell soldered directly in the battery area. The keyed connector prevents reverse connection; check polarity before soldering to the pads.
- **Charger:** single-cell Li-ion linear charger from EXT 5 V, about 500 mA, with thermal regulation and a charge-status output, e.g. TP4056 / MCP73831 class *(verify)*. Charge LED (red = charging, green = full).
- **Protection:** dedicated protection IC + dual N-MOSFET (DW01A + FS8205A class *(verify)*) for over-charge (4.25 V), over-discharge (≈2.5 V) and short circuit, even if the cell has its own protection board.
- **Boost:** 5 V boost converter from the cell, ≥ 1 A, enabled **only when EXT 5 V is absent**, so the battery isn't drained while mains is present.
- **Switch-over:** an ideal-diode OR controller (or a low-drop Schottky, simpler but warmer) between EXT 5 V and the boost output. With the 5 V bulk capacitance, a power cut causes **no reset**.
- **Monitoring for the firmware:**
  - Battery voltage through a high-value divider (e.g. 220 kΩ / 100 kΩ, with a MOSFET to disconnect it when idle) to **IO34** (ADC).
  - "Mains present" (EXT 5 V divided to 3.3 V) to **IO36 / VP**.
  - Charger status to **IO39 / VN**.

  The TFT can then show battery level and "On battery", and the server is told about power cuts.
- **Battery placement:** keep the cell away from the buck converter, the LDO and the antenna, with a mechanical retainer in the enclosure. An 18650 holder (77 mm long) does not fit across a 70 mm board; a flat pouch is preferred.

### 3.4 Security (decided from the risk review)

- **No USB data path on the board.** The external port (USB-C) is power only.
- The programming header (§4.5) is **inside the case**, and may be left unpopulated on installed units.
- **Tamper switch input:** the case-closed switch reports to the server when the case is opened.
- Choose a module that supports **Secure Boot V2 and Flash Encryption** (ESP32 chip revision v3 or later), to be enabled once the firmware is final.

### 3.5 Front and back of the board

The enclosure is designed around this board, phone style:

- **Front (user side):** the TFT module plugs into J_TFT near the top; the R307 sits below it, held by its mounting ears on two standoffs, its window facing the user, and its cable going to J_R307. Leave clearance for the sensor body depth and its cable bend.
- **Back:** all SMT parts (assembled by JLCPCB on this one side), the battery area, the DS3231 coin cell, and the internal J_PROG header.
- **Edges:** 12 V barrel jack and USB-C (power only) at the bottom edge; the ESP32 module at the **top edge on the back**, with its antenna keep-out clear of the TFT's metal frame.
- **Silkscreen outlines** of the TFT and R307 on the front, so the enclosure designer can take dimensions from the board files.

### 3.6 Mechanical and manufacturing

- 2-layer FR-4, 1.6 mm, HASL lead-free (or ENIG), green or black solder mask. **Single-sided SMT assembly on the back** at JLCPCB; the front carries only the TFT socket, the sensor connector and mounting points.
- Board size: **70 × 110 mm** (decided; portrait, phone-like). 60 × 120 mm is the alternative if the enclosure needs it. **4 × M3 mounting holes** with keep-out rings.
- **ESP32 antenna:** place the module at a board edge with the antenna **overhanging the edge, or over a copper-free keep-out on both layers** (no ground pour, tracks or parts under or around the antenna). Keep metal, the TFT and the R307 away from it inside the enclosure.
- Prefer 0603/0805 passives and **JLCPCB "Basic" parts** to avoid extended-part setup fees.
- Through-hole parts (barrel jack, headers): choose SMD versions where available, or order JLCPCB's through-hole assembly, or hand-solder them.
- Silkscreen: label every connector pin (e.g. `R307: 5V GND TX RX TCH 3V3`), board name, version and date.

## 4. Circuit blocks

### 4.1 ESP32 module

- **Module:** ESP32-WROOM-32**E** with 4 MB flash *(verify)* is recommended. It has the same footprint and pinout as the ESP32-WROOM-32 (your robu.in link), and the firmware is identical.
  - Original **WROOM-32** modules are older and may carry an early chip revision. These can't use Secure Boot V2, the version we'd enable later.
  - If you solder your robu.in WROOM-32 yourself, order the board with the module marked **DNP (do not place)**.
- **EN (reset):** 10 kΩ pull-up to 3.3 V, plus 1 µF to GND, plus a **RESET** push button to GND.
- **IO0 (boot):** 10 kΩ pull-up, plus a **BOOT** push button to GND.
- **Strapping pins:** IO12 must **not** be pulled high at boot (wrong flash voltage). IO2 must be low or floating to enter download mode. IO5 and IO15 stay at their defaults. The pin plan in §5 respects this.
- Decoupling: 10 µF + 100 nF at the 3.3 V pin; 100 µF bulk nearby.

### 4.2 Real-time clock

- **DS3231SN** (SOIC-16W; the temperature-compensated version, ±2 ppm, about 1 minute per year) *(verify)*.
- VCC from 3.3 V. **VBAT from a CR2032 holder**, with 100 nF decoupling. No charging path.
- I²C on **IO21 (SDA) / IO22 (SCL)** with 4.7 kΩ pull-ups to 3.3 V. Address 0x68; the firmware already expects it.
- **INT/SQW** to **IO35** (input only) with a 10 kΩ pull-up. This is for future wake or alarm use; the 32 kHz output is unconnected.

### 4.3 Peripheral connectors

Locking, keyed **JST-XH 2.5 mm** connectors unless noted. Pin 1 is marked on the silkscreen.

| Ref | Connects to | Pins (in order) | Notes |
| --- | --- | --- | --- |
| J_R307 | GROW R307 (or Adafruit AS608) fingerprint sensor | 1 +5V, 2 GND, 3 TXD (sensor out → IO16), 4 RXD (sensor in ← IO17), 5 Touch Sense (→ IO27), 6 Touch Sense Power (3.3 V) | Two footprints wired in parallel: a **1.25 mm 6-pin socket** (MX1.25 / PicoBlade-compatible) for double-ended cables, **and 6 × 2.54 mm solder pads** for the R307's loose leads. **Wire colours vary by seller: check each lead against the sensor's datasheet before soldering** |
| JP_SENSOR | Sensor supply select | 5 V (default) / 3.3 V | Solder jumper: R307 needs 4.2–6 V; some AS608 boards are 3.3 V only. If 3.3 V is chosen for an R307, its own "3.3V interface" pads must also be shorted; with the default 5 V, leave them open. The R307's USB pads (5V, D+, D−, GND) are not used |
| J_TFT | 1.8″ ST7735 TFT module ("1.8TFT SPI 128*160 V1.1", red board) | 1 VCC, 2 GND, 3 CS, 4 RESET, 5 A0, 6 SDA, 7 SCK, 8 LED | **8-pin 2.54 mm female header on the board's front**, so the module plugs straight in, plus a 2.54 mm mounting standoff position under each of the module's corner holes. Order confirmed from the V1.1 module's silkscreen. **VCC is fed from 5 V**: the module's own regulator (U1) makes its 3.3 V, with its J1 jumper left as supplied, which takes load off the board's 3.3 V rail. Its signal pins are 3.3 V logic, matching the ESP32. LED (backlight) comes from the switched 3.3 V (§4.4). The module's 4-pin SD-card header (J4) is not used |
| J_BTN | IN/OUT button | IO25, GND | 10 kΩ pull-up on the board (the firmware also enables the internal one) |
| J_TAMPER | Case switch (normally closed when the case is shut) | IO26, GND | 10 kΩ pull-up; RC filter (1 kΩ + 100 nF) against noise |
| J_I2C | Expansion (optional) | 3.3V, GND, SDA, SCL | For a future sensor; same bus as the DS3231 |
| J_PROG | Flashing (internal) | see §4.5 | |

### 4.4 Feedback and display control

- **Buzzer:** 3.3–5 V magnetic or piezo buzzer driven by an NPN transistor (or small N-MOSFET) on **IO32**, with a flyback diode for a magnetic type.
- **Status LEDs:** green on **IO33**, red on **IO13**, each with about 1 kΩ in series. Plus a power LED.
- **TFT backlight switch:** the TFT's LED pin is fed through a P-MOSFET high-side switch on **IO14**, defaulting to ON. This lets the firmware dim or turn off the screen at night.

### 4.5 Programming without USB

The board has **no USB-to-serial chip**. Flashing uses a cheap external **USB-UART adapter** (CP2102 or CH340, 3.3 V logic) plugged into an internal header:

| J_PROG pin | Signal | Notes |
| --- | --- | --- |
| 1 | GND | |
| 2 | TXD0 (ESP32 out) | to the adapter's RX |
| 3 | RXD0 (ESP32 in) | from the adapter's TX |
| 4 | DTR | auto-program circuit → IO0 |
| 5 | RTS | auto-program circuit → EN |
| 6 | 3V3 | **reference only; do not power the board from the adapter.** Use a solder jumper, open by default |

- **Auto-program circuit:** the standard two-transistor DTR/RTS circuit (2 × NPN such as MMBT3904/S8050 *(verify)*, plus 2 × 10 kΩ) on EN and IO0. With an adapter that exposes DTR and RTS, `scripts/device.ps1 upload` works with no button presses.
- **Without DTR/RTS:** connect only GND/TX/RX, hold **BOOT**, tap **RESET**, release BOOT, then upload.
- Series resistors (about 470 Ω) on TXD0/RXD0 protect against a wrongly wired adapter.
- The header can be left unpopulated on installed units. Combined with the firmware lock and, later, Secure Boot, this closes the USB attack path.

## 5. GPIO map (must match the firmware)

| GPIO | Function | Firmware constant | Notes |
| --- | --- | --- | --- |
| IO16 | R307 TX → ESP RX (UART2) | `SENSOR_RX` | |
| IO17 | ESP TX → R307 RX (UART2) | `SENSOR_TX` | |
| IO27 | R307 TOUCH (finger detect) | `FINGER_TOUCH_PIN` | Polarity auto-detected at boot |
| IO18 | TFT SCK | hardware SPI | |
| IO23 | TFT SDA / MOSI | hardware SPI | |
| IO5 | TFT CS | `TFT_CS` | Strapping pin; default high at boot is fine |
| IO4 | TFT A0 / DC | `TFT_DC` | |
| IO19 | TFT RESET | `TFT_RST` | |
| IO14 | TFT backlight switch | *new* | P-MOSFET gate; default ON |
| IO21 | I²C SDA (DS3231, J_I2C) | `OLED_SDA` | 4.7 kΩ pull-up |
| IO22 | I²C SCL | `OLED_SCL` | 4.7 kΩ pull-up |
| IO35 | DS3231 INT/SQW | *new* | Input only; 10 kΩ pull-up |
| IO25 | IN/OUT button | `MODE_BUTTON` | |
| IO26 | Tamper switch | *new* | |
| IO32 | Buzzer | *new* | |
| IO33 | Green LED | *new* | |
| IO13 | Red LED | *new* | |
| IO0 | BOOT button / auto-program | — | 10 kΩ pull-up |
| EN | RESET button / auto-program | — | 10 kΩ + 1 µF |
| IO1 / IO3 | TXD0 / RXD0 → J_PROG | — | Also the USB-STATUS debug console |
| IO2, IO12, IO15 | **unused** | — | Strapping pins: leave without pull-ups |
| IO34 | Battery voltage (ADC) | *new* | Input only; through the divider |
| IO36 / VP | Mains present (EXT 5 V sense) | *new* | Input only |
| IO39 / VN | Charger status | *new* | Input only; pull-up |
| IO6–IO11 | **never use** | — | Connected to the module's internal flash |

## 6. Bill of materials (draft)

**Stage 1 result:** real JLCPCB parts with LCSC numbers, stock and prices are in [parts.md](parts.md). The table below is the original target list.

Choose final LCSC part numbers in the design tool, preferring **Basic** parts, and check stock. Values here are design targets, not ordered parts.

| Qty | Part | Example *(verify)* |
| --- | --- | --- |
| 1 | ESP32-WROOM-32E, 4 MB | Espressif |
| 1 | DS3231SN RTC, SOIC-16W | Analog Devices / Maxim |
| 1 | CR2032 holder, SMD | — |
| 1 | Buck regulator, 4.5–28 V in, 5 V / 2 A out, with inductor and capacitors per datasheet | TPS54202 or MP1584 class |
| 1 | LDO 3.3 V, 1 A, SOT-223 | AMS1117-3.3 or AP7361C |
| 1 | P-MOSFET, reverse-polarity protection, ≥ 30 V | AO3401-class (+ 10 V Zener on the gate) |
| 1 | P-MOSFET, TFT backlight | AO3401-class |
| 1 | TVS diode, 24 V standoff | SMBJ24A |
| 1 | Polyfuse, ≈ 1.5 A hold | 1812 size |
| 1 | Schottky diode for USB-C ORing, ≥ 2 A | SS34-class |
| 1 | DC barrel jack, 5.5 × 2.1 mm, centre positive | — |
| 1 | USB-C receptacle (power only) + 2 × 5.1 kΩ (CC) | — |
| 3 | NPN transistors (2 auto-program, 1 buzzer) | MMBT3904 / S8050 |
| 1 | Buzzer, 3.3–5 V | — |
| 1 | Li-ion charger IC, 1-cell, ≈500 mA, with status output | TP4056 / MCP73831 class |
| 1 | Battery protection IC + dual N-MOSFET | DW01A + FS8205A class |
| 1 | 5 V boost converter, ≥ 1 A, with enable pin (+ inductor) | TPS61023 / MT3608 class |
| 1 | Ideal-diode OR controller (or Schottky), ≥ 2 A | LM66100 class |
| 1 | JST-PH 2-pin battery connector + 2 solder pads | — |
| 1 | LiPo cell, 2000–3000 mAh (bought separately, not assembled) | 103450 / 104060 size |
| 3 | LEDs: power, green, red | 0805 |
| 2 | Tactile switches: RESET, BOOT | — |
| 6 | Connectors: J_R307 (MX1.25-6 socket + 6 solder pads), J_TFT (1×8 2.54 mm female header), J_BTN (XH-2), J_TAMPER (XH-2), J_I2C (XH-4), J_PROG (1×6 2.54 mm) | JST-XH / compatible |
| — | Capacitors: 470 µF (5 V bulk), 100 µF + 10 µF (3.3 V bulk), 1 µF (EN), 100 nF decoupling × ~10 | electrolytic / MLCC |
| — | Resistors: 10 kΩ (pull-ups), 4.7 kΩ (I²C), 1 kΩ (LEDs), 470 Ω (prog series), 5.1 kΩ (CC) | 0603 |

## 7. Files to produce for JLCPCB

Recommended tool: **KiCad 8 or newer**. Its files are plain text, so changes can be reviewed in git. The **"Fabrication Toolkit"** plugin exports JLCPCB-ready files. EasyEDA Pro is the alternative if you prefer JLCPCB's own editor with its built-in parts library.

Planned layout of this folder:

```
pcb/
  README.md                  this specification
  attendance-board/          KiCad project (.kicad_pro, .kicad_sch, .kicad_pcb)
  libraries/                 project-specific symbols and footprints
  production/                generated; git-ignored (attach to a GitHub release per order)
    gerbers.zip              copper, mask, silkscreen, outline, drill
    bom.csv                  Comment, Designator, Footprint, LCSC Part #
    positions.csv            pick-and-place (CPL) for top-side assembly
```

Before ordering, check:

1. ERC (schematic) and DRC (layout, using JLCPCB's 2-layer design rules) are clean.
2. Every BOM line has an in-stock LCSC part, and footprint rotations are checked in JLCPCB's assembly preview.
3. The antenna keep-out is clear on both layers.
4. Every connector pin-1 and silkscreen label matches the cable you will plug in.

## 8. Bring-up checklist (first boards)

1. Inspect for solder bridges, especially around the ESP32 module and the DS3231.
2. **No module powered yet:** apply 12 V through a current-limited bench supply (200 mA limit). Check 5 V and 3.3 V at the test points, then try a reversed input and confirm nothing happens.
3. Connect the USB-UART adapter to J_PROG and upload the firmware (`-Board esp32`). Initialise storage **once** with `init-storage`.
4. Check STATUS over the header: `rtc=1`, `storage=1`. Then plug in the R307 (`sensor=1`, `touch=high/low`) and the TFT.
5. Connect to Wi-Fi through the fallback hotspot, then confirm the scanner appears online in the admin panel.
6. Test a scan, offline queueing, a power-cut while offline (the time must survive thanks to the DS3231), and the tamper switch.

## 9. Decisions

Decided (2026-11-03):

- **Board size 70 × 110 mm**, portrait; 60 × 120 mm as the fallback.
- **JLCPCB assembles everything it stocks**, including the ESP32-WROOM-32E. Anything out of stock becomes DNP for hand soldering.
- **Power input: 12 V barrel jack** (standard) **plus USB-C 5 V power-only**.
- **Battery backup included:** 1-cell LiPo with charger, protection, 5 V boost and automatic switch-over; connector plus solder pads.

- **Sensor:** GROW R307 (Adafruit AS608 also supported), 6-wire cable; board takes both the 1.25 mm plug and loose leads.
- **Display:** red 1.8″ ST7735 128×160 module, plugged onto the board front.
- **Enclosure is designed around the board**, so the board defines the mounting holes and outlines.

Still to confirm on the actual parts before ordering:

- That your TFT is the same "1.8TFT SPI 128*160 V1.1" board as the reference photo (pin order VCC, GND, CS, RESET, A0, SDA, SCK, LED).
- The R307 lead colours against pin numbers 1–6 at the sensor's own connector (colours vary by seller; the pin numbers don't).
- Exact module dimensions (TFT board, R307 body and ear holes), measured with calipers.
