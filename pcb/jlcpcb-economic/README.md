# Economic-PCBA JLCPCB variant of the main board

Same circuit, 70 x 150 mm outline, layout, enclosure positions and GPIO map as the Standard-PCBA board in
`../attendance-board` (tag `jlcpcb-production-v0.2`, untouched). Every part on its BOM is available for
JLCPCB's cheaper **Economic PCBA** (checked on jlcpcb.com/parts on 2026-11-17). Changes:

| Ref | Standard board | This board | Why |
| --- | --- | --- | --- |
| C1, C3 | C976030 470 uF 35 V | **C2836436** KNSCHA 470 uF 35 V, same 10 x 10.2 mm body | C976030 is Standard-only |
| LED2, LED4, LED5 | C84260 green | **C2297** KT-0805G (Basic) | no Extended fee |
| D2 | C173431 BZT52C10 | **C19077408** BZT52C10, SOD-123 (Promotional Extended) | no fee on Economic PCBA |
| U1 | ESP32-WROOM-32E-N4 placed by JLCPCB | **hand-soldered** (not on the BOM) | every in-stock WROOM-32E with a PCB antenna is Standard-only |

U1's ground pad is one solid pad with five 0.6 mm plated holes: solder the module's edge pins first, then
feed solder into the holes from the back with the iron. Buy the module separately (ESP32-WROOM-32E-N4,
LCSC C701341, or the same module from robu.in).

JLCPCB places everything else, including the through-hole DC jack J1 and the XH connector J8.

`bom-with-esp32.csv` / `cpl-with-esp32.csv` add U1 to the JLCPCB order. JLCPCB lists U1 (C701341) as
**Standard-only**, so expect the quote page to refuse it on Economic or switch the order to Standard PCBA
(about $163 for 5 boards instead of about $102 + the module). If it does, use `bom.csv` / `cpl.csv` and solder
U1 yourself. The ground-pad holes do no harm when JLCPCB places the module.

## Files

| Path | What |
| --- | --- |
| `generator/` | Copy of `../generator` with the part swaps and `assembly` flags in `design.py` |
| `attendance-board-economic/` | KiCad project, schematic PDF, DRC report |
| `production/` (git-ignored) | `attendance-board-economic-gerbers.zip`, `bom.csv`, `cpl.csv`, `hand-solder.csv`, renders |

Regenerate with KiCad's Python from `generator/`: `gen_schematic.py`, `gen_pcb.py --route`, `gen_production.py`.

## Ordering

1. PCB: upload the Gerber zip (2 layers, 1.6 mm, 70 x 150 mm).
2. Assembly: **Economic PCBA, top side**, then upload `bom.csv` and `cpl.csv`. Economic allows 2-50 boards,
   top-side placement including through-hole parts, 0.4 mm minimum pitch (finest here: 0.5 mm, TPS61023).
3. Check part rotations in the assembly preview before paying.
4. You solder: U1, then on the back BT1 (CR2032 holder), J3 (battery), J7 (tamper), and the headers J5, J9, J11
   (`hand-solder.csv`).

## Cost estimate (2026-11-17)

JLCPCB fees from its PCBA price page (updated 2026-10-22): Economic setup $8.18, stencil $1.53, $3.07 per
Extended line (16 lines here; Basic and Promotional parts are free), $0.0016 per SMT joint, $0.0164 per
through-hole joint, $3.58 hand-soldering labour per order. Parts at JLCPCB's 1+ prices are about $7.44 per board
(DS3231MZ alone is $3.13). Excludes the bare PCB, shipping, attrition and the hand-soldered ESP32 (~$3.76).

| Boards | Economic (this board) | Standard (main board) |
| --- | --- | --- |
| 5 | ~ $102 | $163 quoted |
| 10 | ~ $142 | ~ $240 estimated |
| 30 | ~ $301 | ~ $460 estimated |

Public coupons listed on jlcpcb.com/coupon-center on 2026-11-17 (not claimed): "PCBA Special Offer" $9 and $6
(orders over $1, valid until 2026-11-29), Stencil $5 (over $1), Parts $5 off $60. "PCBA $10 - EasyEDA Design" is only
for EasyEDA designs.
