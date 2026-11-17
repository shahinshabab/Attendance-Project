# Low-cost JLCPCB variant of the main board

The same circuit, outline (70 x 150 mm), enclosure positions and GPIO map as the main board in
`../attendance-board` (tag `jlcpcb-production-v0.2`, which is left untouched). Only the assembly split differs:

- **JLCPCB places only Basic parts.** Basic parts have no feeder or extended-component fee.
- **You hand-solder every Extended part**, listed in `production/hand-solder.csv` with its LCSC number so
  you can order it from LCSC (or the same part from robu.in).
- **Three small chips are optional**: U7 TPS61023 (SOT-563, 0.5 mm pitch), U5 TP4056 (ESOP-8 with an exposed pad)
  and U8/U9/U10 LM66100 (SC-70-6, 0.65 mm pitch). They are hard to solder by hand. Upload
  `bom-with-small-chips.csv` / `cpl-with-small-chips.csv` instead of `bom.csv` / `cpl.csv` to have JLCPCB place
  them (about 3 Extended fees, ~$3.07 each on Economic PCBA).

Other changes from the main board:

- Green LEDs (LED2, LED4, LED5) are the Basic KT-0805G (C2297) instead of C84260.
- The ESP32 module (U1) is hand-soldered. Its ground pad is one solid 3.7 mm pad with five 0.6 mm plated
  holes: solder the castellated edge pins first, then feed solder into the holes from the back with the iron.

## Files

| Path | What |
| --- | --- |
| `generator/` | Copy of `../generator` with the assembly flags (`design.py`: `EXTENDED`, `OPTIONAL`, `assembly`) |
| `attendance-board-lowcost/` | KiCad project (schematic, board, DRC report) |
| `production/` (git-ignored) | Gerbers zip, `bom.csv` + `cpl.csv` (Basic only), `bom-with-small-chips.csv` + `cpl-with-small-chips.csv`, `hand-solder.csv`, renders |

Regenerate with KiCad's Python from `generator/`: `gen_schematic.py`, `gen_pcb.py --route`, `gen_production.py`.

## Ordering

Choose **Economic PCBA** (top side only, 2-layer, 1.6 mm, 2-50 boards; the 0.5 mm pitch of the optional
SOT-563 is above Economic's 0.4 mm minimum). Economic charges no fee for Basic parts, while Standard PCBA charges
a feeder fee for every Basic and Extended line, which is why the Standard quote for the main board was high.
Check the part rotations in JLCPCB's assembly preview before paying.

## Hand-soldering order

1. Small parts first on the front: D2, U6, Q3, L2, U2, then (if you did not order them placed) U5, U7, U8, U9, U10.
2. L1, F1, D3, C7, C11, BZ1, then the tall C1 and C3.
3. U1 ESP32 (edge pins, then the ground holes from the back).
4. Connectors J1, J2, J8, the headers J5, J9, J11, then on the back BT1, J3, J7.
