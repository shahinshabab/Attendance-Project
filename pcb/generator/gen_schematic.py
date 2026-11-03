"""Generate the KiCad project and schematic from design.py.

Run with KiCad's Python:  <KiCad>/bin/python.exe gen_schematic.py
Connections are made with net labels at every pin, so the schematic matches design.py exactly.
"""
import math
import re
import sys
import uuid
from pathlib import Path

import symbols
from design import BLOCKS, COMPONENTS
from sexpr import Sym, dump, find, find_all

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent / 'attendance-board'
NAME = 'attendance-board'
GRID = 2.54
FONT = [Sym('effects'), [Sym('font'), [Sym('size'), 1.27, 1.27]]]
NS = uuid.UUID('6f1d6c1e-6b8e-4e0b-9a54-1f2b3c4d5e6f')  # stable UUIDs between runs


def uid(*parts):
    return str(uuid.uuid5(NS, '/'.join(map(str, parts))))


def snap(value):
    return round(value / GRID) * GRID


def stacked(number):
    """KiCad 10 stacked pins are numbered like "[1,15,38,39]"."""
    return number[1:-1].split(',') if number.startswith('[') else [number]


def footprint_exists(fp):
    lib, name = fp.split(':', 1)
    root = HERE.parent / 'libraries/attendance.pretty' if lib == 'attendance' else symbols.KICAD / f'share/kicad/footprints/{lib}.pretty'
    return (root / f'{name}.kicad_mod').exists()


def symbol_footprint(defn):
    for prop in find_all(defn, 'property'):
        if prop[1] == 'Footprint' and prop[2]:
            return prop[2] if ':' in prop[2] else f'attendance:{prop[2]}'
    return None


def bbox(pins):
    if not pins:
        return -2.54, -2.54, 2.54, 2.54
    xs = [p['x'] for p in pins]
    ys = [-p['y'] for p in pins]  # schematic Y points down
    return min(xs), min(ys), max(xs), max(ys)


def label_angle(pin_angle):
    # Pin angle is the direction from the connection point into the symbol body.
    return {0: 180, 180: 0, 90: 270, 270: 90}[int(pin_angle) % 360]


def prop(name, value, x, y, hide=False, angle=0):
    node = [Sym('property'), name, value, [Sym('at'), x, y, angle]]
    if hide:
        node.append([Sym('hide'), Sym('yes')])
    node.append(FONT)
    return node


def main():
    errors, lib_cache = [], {}
    for comp in COMPONENTS.values():
        if comp['symbol'] not in lib_cache:
            lib_cache[comp['symbol']] = symbols.load(comp['symbol'])
        defn = lib_cache[comp['symbol']]
        comp['pinlist'] = symbols.pins(defn)
        if comp['footprint'] is None:
            comp['footprint'] = symbol_footprint(defn)
        if not comp['footprint'] or not footprint_exists(comp['footprint']):
            errors.append(f"{comp['ref']}: footprint not found: {comp['footprint']}")
        known = {n for p in comp['pinlist'] for n in stacked(p['number'])}
        for number in comp['pins']:
            if number not in known:
                errors.append(f"{comp['ref']}: design pin {number} not on symbol {comp['symbol']}")
        for p in comp['pinlist']:
            nets = {comp['pins'].get(n) for n in stacked(p['number'])}
            if None in nets:
                errors.append(f"{comp['ref']}: symbol pin {p['number']} ({p['name']}) has no net in design.py")
            elif len(nets) > 1:
                errors.append(f"{comp['ref']}: stacked pin {p['number']} given different nets {nets}")
    if errors:
        print('\n'.join(errors))
        sys.exit(1)

    items = []  # labels, no_connects, symbols, text
    root = uid('root')

    def place_component(comp, x, y):
        pins = comp['pinlist']
        refs_y = bbox(pins)
        items.append([
            Sym('symbol'), [Sym('lib_id'), comp['symbol']], [Sym('at'), x, y, 0], [Sym('unit'), 1],
            [Sym('exclude_from_sim'), Sym('no')], [Sym('in_bom'), Sym('yes') if comp['lcsc'] else Sym('no')],
            [Sym('on_board'), Sym('yes')], [Sym('dnp'), Sym('yes') if comp['dnp'] else Sym('no')],
            [Sym('uuid'), uid('sym', comp['ref'])],
            prop('Reference', comp['ref'], x, round(y + refs_y[1] - 3.81, 2)),
            prop('Value', comp['value'], x, round(y + refs_y[3] + 3.81, 2)),
            prop('Footprint', comp['footprint'], x, y, hide=True),
            prop('Datasheet', '', x, y, hide=True),
            prop('LCSC', comp['lcsc'], x, y, hide=True),
            *([prop('Note', comp['note'], x, y, hide=True)] if comp['note'] else []),
            *[[Sym('pin'), p['number'], [Sym('uuid'), uid('pin', comp['ref'], p['number'])]] for p in pins],
            [Sym('instances'), [Sym('project'), NAME, [Sym('path'), f'/{root}', [Sym('reference'), comp['ref']], [Sym('unit'), 1]]]],
        ])
        for p in pins:
            px, py = round(x + p['x'], 2), round(y - p['y'], 2)
            net = comp['pins'][stacked(p['number'])[0]]
            if net == 'NC':
                items.append([Sym('no_connect'), [Sym('at'), px, py], [Sym('uuid'), uid('nc', comp['ref'], p['number'])]])
            else:
                angle = label_angle(p['angle'])
                justify = [Sym('justify'), Sym('right') if angle in (180, 270) else Sym('left'), Sym('bottom')]
                items.append([Sym('label'), net, [Sym('at'), px, py, angle],
                              [Sym('effects'), [Sym('font'), [Sym('size'), 1.27, 1.27]], justify],
                              [Sym('uuid'), uid('label', comp['ref'], p['number'])]])

    # Layout: blocks packed in rows across the sheet; parts in a grid inside each block.
    def cell(comp):
        x0, y0, x1, y1 = bbox(comp['pinlist'])
        longest = max([len(n) for n in comp['pins'].values()] + [4])
        label_room = longest * 1.0 + 3
        return (x1 - x0) + 2 * label_room + 6, (y1 - y0) + 14

    sheet_w, sheet_h = 841, 594  # A1 landscape
    margin, cursor_x, cursor_y, row_h = 20, 20, 30, 0
    for title, refs in BLOCKS:
        comps = [COMPONENTS[r] for r in refs]
        cw = max(cell(c)[0] for c in comps)
        ch = max(cell(c)[1] for c in comps)
        cols = max(1, min(len(comps), int(math.ceil(math.sqrt(len(comps) * 1.6)))))
        if cw > 120:
            cols = 1
        rows = int(math.ceil(len(comps) / cols))
        bw, bh = cols * cw + 10, rows * ch + 16
        if cursor_x + bw > sheet_w - margin:
            cursor_x, cursor_y, row_h = margin, cursor_y + row_h + 10, 0
        items.append([Sym('text_box'), title, [Sym('exclude_from_sim'), Sym('no')],
                      [Sym('at'), snap(cursor_x), snap(cursor_y), 0], [Sym('size'), snap(bw), snap(bh)],
                      [Sym('margins'), 1.5, 1.5, 1.5, 1.5],
                      [Sym('stroke'), [Sym('width'), 0.3], [Sym('type'), Sym('dash')]], [Sym('fill'), [Sym('type'), Sym('none')]],
                      [Sym('effects'), [Sym('font'), [Sym('size'), 2.5, 2.5], [Sym('bold'), Sym('yes')]], [Sym('justify'), Sym('left'), Sym('top')]],
                      [Sym('uuid'), uid('block', title)]])
        for i, comp in enumerate(comps):
            col, row = i % cols, i // cols
            x0, y0, x1, y1 = bbox(comp['pinlist'])
            cx = cursor_x + 5 + col * cw + cw / 2 - (x0 + x1) / 2
            cy = cursor_y + 14 + row * ch + ch / 2 - (y0 + y1) / 2
            place_component(comp, snap(cx), snap(cy))
        cursor_x += bw + 10
        row_h = max(row_h, bh)
    if cursor_y + row_h > sheet_h - margin:
        print(f'warning: layout height {cursor_y + row_h:.0f} mm exceeds the sheet')

    # PWR_FLAG on supply nets that are fed only through passive pins.
    flags = ['GND', '+5V', 'VIN_JACK', 'USB_5V', 'BAT_P', 'BAT_N', 'VBAT_RTC']
    flag_def = symbols.load('power:PWR_FLAG')
    lib_cache['power:PWR_FLAG'] = flag_def
    fx = margin + 10
    flag_y = cursor_y + row_h + 30
    items.append([Sym('text'), 'Power flags: tell ERC these nets are supplied (connector, battery or regulator through passive pins)',
                  [Sym('exclude_from_sim'), Sym('no')], [Sym('at'), snap(margin), snap(flag_y - 15), 0],
                  [Sym('effects'), [Sym('font'), [Sym('size'), 2, 2]], [Sym('justify'), Sym('left'), Sym('bottom')]],
                  [Sym('uuid'), uid('flagtext')]])
    for net in flags:
        x, y = snap(fx), snap(flag_y)
        items.append([Sym('symbol'), [Sym('lib_id'), 'power:PWR_FLAG'], [Sym('at'), x, y, 0], [Sym('unit'), 1],
                      [Sym('exclude_from_sim'), Sym('no')], [Sym('in_bom'), Sym('yes')], [Sym('on_board'), Sym('yes')],
                      [Sym('dnp'), Sym('no')], [Sym('uuid'), uid('flag', net)],
                      prop('Reference', f'#FLG{flags.index(net) + 1:02d}', x, y - 6, hide=True),
                      prop('Value', 'PWR_FLAG', x, y - 4),
                      prop('Footprint', '', x, y, hide=True), prop('Datasheet', '', x, y, hide=True),
                      [Sym('pin'), '1', [Sym('uuid'), uid('flagpin', net)]],
                      [Sym('instances'), [Sym('project'), NAME, [Sym('path'), f'/{root}', [Sym('reference'), f'#FLG{flags.index(net) + 1:02d}'], [Sym('unit'), 1]]]]])
        items.append([Sym('label'), net, [Sym('at'), x, y, 270],
                      [Sym('effects'), [Sym('font'), [Sym('size'), 1.27, 1.27]], [Sym('justify'), Sym('right'), Sym('bottom')]],
                      [Sym('uuid'), uid('flaglabel', net)]])
        fx += 25

    sch = [Sym('kicad_sch'), [Sym('version'), 20250610], [Sym('generator'), 'attendance_gen'], [Sym('generator_version'), '1.0'],
           [Sym('uuid'), root], [Sym('paper'), 'A1'],
           [Sym('title_block'), [Sym('title'), 'Attendance scanner main board'], [Sym('date'), '2026-11-03'], [Sym('rev'), '0.1'],
            [Sym('comment'), 1, 'Generated from pcb/generator/design.py - edit that file, not this schematic']],
           [Sym('lib_symbols'), *lib_cache.values()],
           *items,
           [Sym('sheet_instances'), [Sym('path'), '/', [Sym('page'), '1']]],
           [Sym('embedded_fonts'), Sym('no')]]
    PROJECT.mkdir(exist_ok=True)
    (PROJECT / f'{NAME}.kicad_sch').write_text(dump(sch) + '\n', encoding='utf-8')
    # Project library tables: our LCSC library plus every standard library the design uses,
    # so kicad-cli and a fresh KiCad install resolve everything without global setup.
    sym_libs = sorted({c['symbol'].split(':')[0] for c in COMPONENTS.values()} | {'power'})
    fp_libs = sorted({c['footprint'].split(':')[0] for c in COMPONENTS.values()})

    def table(kind, libs, ext, env):
        lines = [f'({kind}_lib_table', '\t(version 7)']
        for lib in libs:
            uri = f'${{KIPRJMOD}}/../libraries/attendance{ext}' if lib == 'attendance' else f'${{{env}}}/{lib}{ext}'
            lines.append(f'\t(lib (name "{lib}") (type "KiCad") (uri "{uri}") (options "") (descr ""))')
        return '\n'.join(lines) + '\n)\n'
    (PROJECT / 'sym-lib-table').write_text(table('sym', sym_libs, '.kicad_sym', 'KICAD10_SYMBOL_DIR'), encoding='utf-8')
    (PROJECT / 'fp-lib-table').write_text(table('fp', fp_libs, '.pretty', 'KICAD10_FOOTPRINT_DIR'), encoding='utf-8')
    pro = PROJECT / f'{NAME}.kicad_pro'
    if not pro.exists():
        pro.write_text('{\n  "meta": {"filename": "%s.kicad_pro", "version": 3},\n  "schematic": {},\n  "board": {}\n}\n' % NAME, encoding='utf-8')
    nets = {n for c in COMPONENTS.values() for n in c['pins'].values() if n != 'NC'}
    print(f'Wrote {PROJECT.name}/{NAME}.kicad_sch: {len(COMPONENTS)} components, {len(nets)} nets')


if __name__ == '__main__':
    main()
