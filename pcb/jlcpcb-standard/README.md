# Standard-PCBA JLCPCB variant (ESP32 placed by JLCPCB)

Same circuit, 70 x 150 mm outline, layout and GPIO map as the other boards. It uses the Economic variant's
part choices (`../jlcpcb-economic`), and JLCPCB also places the ESP32 module U1. The module
(ESP32-WROOM-32E-N4, C701341) is **Standard-only** at JLCPCB, so this board must be ordered with
**Standard PCBA**. Its ground pad is the normal library footprint (no hand-solder holes).

| Ref | Part | Note |
| --- | --- | --- |
| U1 | C701341 ESP32-WROOM-32E-N4 | placed by JLCPCB (Standard PCBA) |
| C1, C3 | C2836436 470 uF 35 V 10 x 10.2 mm | |
| LED2, LED4, LED5 | C2297 KT-0805G green (Basic) | |
| D2 | C19077408 BZT52C10 SOD-123 | |
| L2 | rotated 180 degrees | so the boost switch node routes |

You hand-solder (see `production/hand-solder.csv`): on the front the headers J5 (display), J9 (programming,
optional) and J11 (R307); on the back BT1 (CR2032 holder), J3 (LiPo) and J7 (tamper). Standard PCBA can also
assemble the back side, but that doubles the setup and stencil fees for three easy parts.

## Files

| Path | What |
| --- | --- |
| `generator/` | Copy of `../jlcpcb-economic/generator` with U1 placed (`design.HAND` empty) |
| `attendance-board-standard/` | KiCad project, schematic PDF, DRC report |
| `production/` (git-ignored) | `attendance-board-standard-gerbers.zip`, `bom.csv`, `cpl.csv`, `hand-solder.csv`, renders |

## Ordering

PCB Assembly -> **Standard**, top side only; upload `bom.csv` and `cpl.csv`; check rotations in the preview.

## Cost estimate (JLCPCB price page, updated 2026-10-22)

Standard PCBA: $25.56 setup, $8.21 stencil, $1.53 feeder loading for every BOM line (42 here), fixtures $16.42
(1-29 boards) or $24.63 (30-99), $3.58 hand-soldering labour for J1/J8, $0.0016 per SMT joint, plus parts
(about $11.20 per board with the ESP32). A handling fee of at least $14.93 may be added. Excludes the bare PCB
and shipping.

| Boards | Standard (this board) | Economic + ESP32 soldered by you (`../jlcpcb-economic`) |
| --- | --- | --- |
| 5 | ~ $177 (up to ~ $192 with handling fee) | ~ $121 |
| 10 | ~ $236 | ~ $180 |
| 30 | ~ $480 | ~ $414 |
