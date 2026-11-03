# Selected parts (stage 1)

Real JLCPCB/LCSC parts for every block in [README.md](README.md). Stock and unit prices are from JLCPCB's parts search on **2026-11-03**; recheck them right before ordering, because both change daily.

**Basic** parts are always loaded on JLCPCB's machines. Each different **Extended** part adds a one-time loading fee per order (about US$3 at the time of writing).

## Main parts

| Block | Ref | Part | LCSC | Type | Stock | Unit $ | Why this one |
| --- | --- | --- | --- | --- | ---: | ---: | --- |
| MCU | U1 | ESP32-WROOM-32E-N4 (4 MB) | C701341 | Extended | 60,757 | 3.77 | Current module, chip rev 3 (Secure Boot V2 capable); same footprint as WROOM-32 |
| Clock | U2 | DS3231MZ+TRL (SOIC-8, ±5 ppm) | C107410 | Extended | 10,325 | 3.35 | In KiCad's library; the SOIC-16 DS3231SN costs $9–11 for ±2 ppm the server corrects anyway |
| Clock | BT1 | Keystone 3034 CR2032 holder | C5213768 | Extended | 776 | 0.39 | Replaces CR2032-BS-6-1 (C70377), which has no EasyEDA footprint data; KiCad has the exact Keystone 3034 footprint |
| 5 V buck | U3 | XL1509-5.0E1 (40 V in, 2 A, fixed 5 V) | C61063 | **Basic** | 426,392 | 0.25 | No feedback divider; Basic part |
| 5 V buck | L1 | FNR8040S680MT 68 µH, 8 × 8 mm | C168140 | Extended | 4,472 | 0.12 | 68 µH per the XL1509 datasheet's 12 V → 5 V example; check saturation current ≥ 1.5 A before ordering |
| 5 V buck | D1 | SS34 Schottky (catch diode) | C8678 | **Basic** | 3,180,122 | 0.04 | |
| 3.3 V | U4 | AMS1117-3.3 (1 A, SOT-223) | C6186 | **Basic** | 1,720,437 | 0.21 | |
| Input | Q1 | AO3401A P-MOSFET (reverse polarity) | C15127 | **Basic** | 1,677,808 | 0.10 | |
| Input | Q2 | AO3401A P-MOSFET (TFT backlight switch) | C15127 | **Basic** | — | — | Same part as Q1 |
| Input | D2 | BZT52C10 10 V Zener (Q1 gate clamp) | C173431 | Extended | 273,442 | 0.02 | |
| Input | D3 | SMBJ24A TVS | C87268 | Extended | 40,422 | 0.06 | |
| Input | F1 | SMD1812P150TF/24 polyfuse (1.5 A, 24 V) | C32404 | Extended | 14,735 | 0.14 | 24 V rating for the 24 V maximum input |
| Input | D4 | SS34 Schottky (USB-C 5 V OR) | C8678 | **Basic** | — | — | Same part as D1 |
| Input | J1 | DC-005 barrel jack 5.5 × 2.1 mm | C16214 | Extended | 83,244 | 0.06 | Through-hole |
| Input | J2 | USB-C 6-pin, power only | C456012 | Extended | 1,011,002 | 0.04 | 6-pin type has no data pins at all |
| Battery | U5 | TP4056 charger (ESOP-8) | C725790 | Extended | 337,106 | 0.08 | 500 mA via 2.4 kΩ PROG resistor |
| Battery | U6 | DW01A protection IC | C351410 | Extended | 98,579 | 0.05 | |
| Battery | Q3 | FS8205A dual N-MOSFET | C2830320 | Extended | 138,703 | 0.05 | |
| Battery | U7 | TPS61023DRLR 5 V boost (SOT-563) | C919459 | Extended | 39,356 | 0.23 | Higher efficiency than MT3608; feedback 220 k / 30 k = 4.96 V (both Basic) |
| Battery | L2 | PRS4018-1R0NT 1 µH, 4 × 4 mm | C96152 | Extended | 2,999 | 0.06 | Check saturation current ≥ 3 A in the schematic stage |
| Battery | U8, U9 | LM66100DCKR ideal diode (×2: EXT 5 V and boost) | C2869734 | Extended | 11,069 | 0.21 | |
| Battery | J3 | JST-PH 2.0 2-pin SMD (+ 2 solder pads) | C722761 | Extended | 43,845 | 0.04 | |
| Program | Q4, Q5 | MMBT3904 NPN (auto-program) | C20526 | **Basic** | 2,851,963 | 0.01 | |
| Feedback | Q6 | MMBT3904 NPN (buzzer driver) | C20526 | **Basic** | — | — | Same part |
| Feedback | BZ1 | MLT-8530 SMD buzzer 8.5 × 8.5 mm | C94599 | Extended | 141,271 | 0.20 | Pads 1 (+) and 4 (−) per datasheet; pads 2/3 are dummies |
| Feedback | D6 | 1N4148W flyback diode (buzzer) | C81598 | **Basic** | 3,836,332 | 0.01 | |
| Feedback | LED1 | Red 0805 (error, charging) | C84256 | **Basic** | 2,370,309 | 0.01 | |
| Feedback | LED2 | Green 0805 (OK, power) | C84260 | Extended | 494,742 | 0.02 | |
| Buttons | SW1, SW2 | TS-1187A tactile switch (RESET, BOOT) | C318884 | **Basic** | 1,044,364 | 0.02 | |
| Sensor | J4 | MX1.25 6-pin SMD socket (+ 6 solder pads) | C3029354 | Extended | 4,023 | 0.10 | For R307/AS608 cables |
| Display | J5 | 1 × 8 female header, 2.54 mm | C42431840 | Extended | 11,111 | 0.11 | Through-hole; TFT plugs in directly |
| Button | J6 | JST B2B-XH-A 2-pin (IN/OUT button) | C158012 | Extended | 608,675 | 0.04 | Through-hole |
| Tamper | J7 | JST B2B-XH-A 2-pin | C158012 | Extended | — | — | Same part as J6 |
| I²C | J8 | JST B4B-XH-A 4-pin | C144395 | Extended | 666,320 | 0.06 | Through-hole |
| Program | J9 | 1 × 6 pin header, 2.54 mm | — | DNP | — | — | Left unfitted; hand-solder if needed |

## Capacitors and resistors (all Basic)

| Value | Package | LCSC | Used for |
| --- | --- | --- | --- |
| 100 nF | 0603 | C14663 | Decoupling at every IC |
| 1 µF | 0603 | C15849 | ESP32 EN delay, LDO input |
| 10 µF | 0603 | C19702 | LDO, charger |
| 10 µF | 0805 | C15850 | ESP32 3.3 V pin |
| 22 µF | 0805 | C45783 | Boost input/output, buck output |
| 470 µF / 35 V electrolytic | 10 × 10 mm | C976030 *(Extended)* | Input bulk |
| 100 µF / 10 V tantalum | 3528 | C129567 *(Extended)* | 3.3 V and 5 V bulk near the ESP32 and R307 |
| 10 kΩ | 0603 | C25804 | Pull-ups, base resistors |
| 4.7 kΩ | 0603 | C23162 | I²C pull-ups |
| 1 kΩ | 0603 | C21190 | LED resistors, tamper filter |
| 5.1 kΩ | 0603 | C23186 | USB-C CC1/CC2 |
| 100 kΩ | 0603 | C25803 | Dividers |
| 220 kΩ | 0603 | C22961 | Battery divider, boost feedback |
| 2.4 kΩ | 0603 | C22940 | TP4056 charge current (500 mA) |
| 2 kΩ | 0603 | C22975 | Spare / LED current tuning |
| 470 Ω | 0603 | C23179 | Programming-header series resistors |
| 30 kΩ | 0603 | C22984 | Boost feedback lower resistor (220 k / 30 k = 4.96 V) |
| 100 Ω | 0603 | C22775 | DW01A supply resistor |

## Cost estimate (per order)

- **Parts per board:** about **US$10–11**. Most of that is the ESP32 module ($3.77) and the DS3231 ($3.35); everything else is under $3 together.
- **Extended-part loading fees:** about **22 different Extended parts × ~$3 ≈ US$65 per order**, paid once whether you order 2 or 20 boards. The battery block alone adds 8 of them.
- **Through-hole parts** (barrel jack, TFT header, JST-XH connectors): either pay JLCPCB's through-hole assembly or solder them by hand (5 minutes per board).
- Plus the bare PCB, assembly setup and shipping, quoted by JLCPCB when the files are uploaded.

Ways to cut cost later:

- Hand-solder the through-hole connectors.
- Replace Extended passives with Basic equivalents where the schematic allows.
- Order more boards at once, so the fixed fees are shared.

## Still to verify in the schematic stage

- Inductor saturation currents (L1 ≥ 1.5 A, L2 ≥ 3 A) against their datasheets.
- Pick-and-place rotations in JLCPCB's assembly preview (EasyEDA-derived footprints are usually right; KiCad standard ones sometimes need an offset).

Checked during the schematic stage (2026-11-03), against datasheets: XL1509 (ON/OFF low = on, internal 5 V divider), TPS61023 (pinout, VREF 0.595 V), LM66100 (pinout, active-low CE), DC-005 2.0 (pin 4 = centre +, pin 2 = sleeve), TS-1187A (A-B and C-D joined), MLT-8530 (+/− pads), TP4056, DW01A, FS8205A, USB-C 6P.
