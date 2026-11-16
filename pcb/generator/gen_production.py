"""Export JLCPCB order files from the routed board: Gerbers + drill (zip), BOM and CPL.

Run with KiCad's Python after gen_schematic.py, gen_pcb.py --route and a clean DRC:
    <KiCad>/bin/python.exe gen_production.py
Writes pcb/production/ (git-ignored): attendance-board-gerbers.zip, bom.csv, cpl.csv.
Only FRONT-side parts with an LCSC number that are not DNP go in the BOM and CPL; BT1, J3 and J7
(back side) and the headers J5/J9/J11 are hand-soldered.
"""
import csv
import shutil
import subprocess
import tempfile
import zipfile
from collections import OrderedDict
from pathlib import Path

import pcbnew
import symbols
from design import COMPONENTS

HERE = Path(__file__).resolve().parent
BOARD_FILE = HERE.parent / 'attendance-board/attendance-board.kicad_pcb'
OUT = HERE.parent / 'production'
CLI = symbols.KICAD / 'bin' / ('kicad-cli.exe' if (symbols.KICAD / 'bin/kicad-cli.exe').exists() else 'kicad-cli')
LAYERS = 'F.Cu,B.Cu,F.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts'

# JLCPCB's placement angle differs from KiCad's for some footprints. Fill in after checking the
# assembly preview on jlcpcb.com: ref or footprint name -> degrees to add.
ROTATION_FIX = {}


def assembled(comp):
    return comp['lcsc'] and not comp['dnp']


def export_gerbers():
    tmp = Path(tempfile.mkdtemp())
    subprocess.run([str(CLI), 'pcb', 'export', 'gerbers', '--layers', LAYERS, '--subtract-soldermask',
                    '--no-protel-ext', '--output', str(tmp), str(BOARD_FILE)], check=True)
    subprocess.run([str(CLI), 'pcb', 'export', 'drill', '--format', 'excellon', '--drill-origin', 'absolute',
                    '--excellon-units', 'mm', '--excellon-separate-th', '--output', str(tmp), str(BOARD_FILE)], check=True)
    zip_path = OUT / 'attendance-board-gerbers.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(tmp.iterdir()):
            z.write(f, f.name)
    shutil.rmtree(tmp)
    return zip_path


def export_bom_cpl():
    board = pcbnew.LoadBoard(str(BOARD_FILE))
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    groups, rows, problems = OrderedDict(), [], []
    origin = board.GetDesignSettings().GetAuxOrigin()
    for ref, comp in COMPONENTS.items():
        if not assembled(comp):
            continue
        fp = fps[ref]
        if fp.IsFlipped():
            problems.append(f'{ref} is on the back but has an LCSC part and is not DNP')
            continue
        key = (comp['value'], comp['lcsc'], fp.GetFPID().GetLibItemName().wx_str())
        groups.setdefault(key, []).append(ref)
        pos = fp.GetPosition()
        rot = (fp.GetOrientationDegrees() + ROTATION_FIX.get(ref, ROTATION_FIX.get(key[2], 0))) % 360
        rows.append([ref, f'{pcbnew.ToMM(pos.x - origin.x):.3f}mm', f'{-pcbnew.ToMM(pos.y - origin.y):.3f}mm', 'Top', f'{rot:.1f}'])
    with open(OUT / 'bom.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        for (value, lcsc, footprint), refs in groups.items():
            w.writerow([value, ','.join(refs), footprint, lcsc])
    with open(OUT / 'cpl.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        w.writerows(rows)
    return len(groups), len(rows), problems


if __name__ == '__main__':
    OUT.mkdir(exist_ok=True)
    print('Gerbers:', export_gerbers().name)
    lines, parts, problems = export_bom_cpl()
    print(f'BOM: {lines} lines, CPL: {parts} parts')
    for p in problems:
        print('PROBLEM:', p)
