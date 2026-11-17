"""Generate the PCB (placement, outline, rules, zones) from design.py, then optionally autoroute.

Run with KiCad's Python:  <KiCad>/bin/python.exe gen_pcb.py [--route]
Coordinates below are board millimetres seen from the FRONT (the side facing the display and
sensor): x right, y down, board 70 x 150 mm. JLCPCB assembles the FRONT. 'B' parts are hand-soldered
on the back: only the coin-cell holder (BT1), battery connector (J3) and tamper connector (J7).
Layout agreed with the enclosure (see /enclosure in the project files):
  - 3.5" ILI9488 module in front of x 7-63, y 1-99; a 14-wire cable runs from its top header to J5.
  - ESP32 turned 90 degrees with the antenna at the RIGHT edge, beside the display, not behind it.
  - SENSOR_ZONE (lower middle) stays empty: the upright R307S sits in front of it. Its cable goes
    to the J11 pads just above it.
  - Status LEDs left of the sensor (light holes in the front shell); buzzer by the right-wall slots.
"""
import json
import subprocess
import sys
from pathlib import Path

import pcbnew
import footprints
import symbols
from design import COMPONENTS
from gen_schematic import symbol_footprint, uid

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent / 'attendance-board-economic'
BOARD_FILE = PROJECT / 'attendance-board-economic.kicad_pcb'
# Freerouting 1.9.0 (Java 17). The native freerouting-cli 2.5.0 crashes on this board (GraalVM serialization) and 2.5.0's jar needs Java 25.
FREEROUTING = Path.home() / 'AppData/Local/Programs/Freerouting/freerouting-1.9.0.jar'
OX, OY = 100.0, 50.0           # board origin on the KiCad page
W, H, CORNER = 70.0, 150.0, 3.0
SENSOR_ZONE = (17.5, 97.0, 52.5, 150.0)   # x0, y0, x1, y1: no front parts except J11
U1_POS, U1_ROT = (56.5, 19.0), -90       # antenna (module top) pointing to the right edge


def pt(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))


# ---------------------------------------------------------------- placement (x, y, rotation, side)
# The centre of each part's real extent (courtyard plus pads) goes to (x, y). U1 is placed by origin.
PLACE = {
    # mounting holes (case bosses at the corners)
    'H1': (4, 4, 0, 'F'), 'H2': (66, 4, 0, 'F'), 'H3': (4, 146, 0, 'F'), 'H4': (66, 146, 0, 'F'),
    # top left: programming header, auto-reset, BOOT/RESET, I2C pull-ups
    'J9': (4.5, 19.5, 0, 'F'), 'JP1': (10, 28.5, 0, 'F'),
    'R22': (10, 12.5, 90, 'F'), 'R23': (12.5, 12.5, 90, 'F'),
    'R20': (17, 9.5, 0, 'F'), 'Q4': (17, 14, 0, 'F'),
    'R21': (11, 20.5, 90, 'F'), 'Q5': (17, 20.5, 0, 'F'),
    'R19': (22, 18.5, 90, 'F'), 'SW2': (19, 26.5, 0, 'F'), 'SW1': (27.5, 26.5, 0, 'F'),
    'R25': (22, 10.5, 90, 'F'), 'R26': (24.5, 14, 90, 'F'),
    'R5': (29, 6.5, 0, 'F'), 'LED5': (33, 6.5, 0, 'F'),
    # 3.3 V regulator left of the ESP32; EN RC and decoupling along the module's pin-1 side
    'C9': (39, 9.5, 0, 'F'), 'U4': (38, 17, 0, 'F'), 'C10': (32, 17, 90, 'F'), 'C11': (39, 24.5, 0, 'F'),
    'C19': (60.5, 6.5, 90, 'F'), 'C20': (58, 6.5, 90, 'F'), 'R18': (55.5, 6.5, 90, 'F'), 'C21': (53, 6.5, 90, 'F'),
    'TP3': (48, 6.5, 0, 'F'),
    # display header (cable to the module) and backlight switch
    'J5': (35, 33, 90, 'F'),
    'Q2': (12, 34, 0, 'F'), 'R27': (12, 38, 0, 'F'), 'R28': (8, 34, 90, 'F'),
    # left edge: I2C expansion, tamper connector (back) and its filter
    'J8': (4.5, 50, 90, 'F'), 'J7': (4.5, 64, 90, 'B'),
    'R30': (11, 62, 90, 'F'), 'R31': (13.5, 62, 90, 'F'), 'C25': (16, 62, 90, 'F'),
    # RTC (coin cell on the back, lower middle, above the sensor pads)
    'U2': (27, 64, 0, 'F'), 'C22': (22, 62, 90, 'F'), 'C23': (32, 64, 90, 'F'), 'R24': (21.5, 67, 0, 'F'),
    'BT1': (35, 86.5, 0, 'B'),
    # battery: charger, protection, boost, switch-over (right, below the ESP32); connector on the back
    'J3': (58.8, 44, 90, 'B'), 'J10': (66.5, 55, 90, 'F'), 'TP5': (63, 50, 0, 'F'),
    'C12': (40, 39, 0, 'F'), 'C13': (40, 42, 0, 'F'), 'U5': (46.5, 41.5, 0, 'F'), 'R6': (46.5, 46.5, 0, 'F'),
    'R7': (39, 48, 0, 'F'), 'LED3': (43, 48, 0, 'F'), 'R8': (39, 51, 0, 'F'), 'LED4': (43, 51, 0, 'F'),
    'R9': (47.5, 50, 90, 'F'),
    'R10': (55, 40, 0, 'F'), 'U6': (55, 44, 0, 'F'), 'C14': (51.5, 44, 90, 'F'), 'R11': (55, 48, 0, 'F'),
    'Q3': (59, 48, 0, 'F'),
    'U7': (55, 56.5, 0, 'F'), 'L2': (60, 56.5, 180, 'F'), 'R12': (51, 55, 0, 'F'), 'R13': (51, 58, 0, 'F'),
    'C15': (60, 62, 0, 'F'), 'C16': (55.5, 61, 90, 'F'), 'C17': (53, 61, 90, 'F'), 'U9': (48.5, 61.5, 0, 'F'),
    'R16': (64, 62, 90, 'F'), 'R17': (66.5, 62, 90, 'F'), 'C18': (66.5, 66.5, 90, 'F'),
    # 12 V input protection and 5 V buck (middle band, under the lower part of the display)
    'C1': (9, 78, 0, 'F'), 'D3': (9, 88, 0, 'F'), 'F1': (9, 94, 0, 'F'),
    'Q1': (16.5, 88, 0, 'F'), 'R1': (16.5, 92.5, 0, 'F'), 'D2': (21.5, 88, 0, 'F'), 'C2': (21.5, 92.5, 0, 'F'),
    'TP1': (25, 92.5, 0, 'F'),
    'U3': (24, 79, 0, 'F'), 'D1': (31, 79, 90, 'F'), 'L1': (40, 79, 0, 'F'), 'C4': (31, 86, 90, 'F'),
    'C3': (40, 90.5, 0, 'F'), 'U8': (49, 86, 0, 'F'),
    # 5 V rail, external-power OR and mains sense (middle band, right)
    'C7': (51.5, 76, 0, 'F'), 'C8': (52, 80.5, 0, 'F'), 'TP2': (53, 85, 0, 'F'),
    'D4': (58, 75, 0, 'F'), 'D5': (58, 80, 0, 'F'), 'C6': (64, 77.5, 90, 'F'),
    'R14': (63, 84, 90, 'F'), 'R15': (65.5, 84, 90, 'F'),
    # sensor pads just above the sensor, supply jumper and its capacitor
    'J11': (35, 99.7, 90, 'F'), 'JP2': (24, 95.5, 0, 'F'), 'C24': (48.5, 95.5, 0, 'F'),
    # left of the sensor: status LEDs behind the light holes, GND test point; 12 V jack at the bottom
    'LED1': (12, 118, 90, 'F'), 'LED2': (15, 118, 90, 'F'), 'R33': (12, 113.5, 90, 'F'), 'R34': (15, 113.5, 90, 'F'),
    'TP4': (5, 113, 0, 'F'),
    'J1': (12.6, 143, 0, 'F'),
    # right of the sensor: buzzer by the sound slots, USB-C at the bottom
    'BZ1': (62, 105, 0, 'F'), 'Q6': (57.5, 114, 0, 'F'), 'R32': (62, 114, 0, 'F'), 'D6': (65.5, 118, 0, 'F'),
    'U10': (66, 134, 0, 'F'),
    'J2': (57.4, 146.5, 0, 'F'), 'R2': (57, 139.5, 90, 'F'), 'R3': (59.5, 139.5, 90, 'F'), 'C5': (62, 139.5, 90, 'F'),
}

POWER = ['+5V', '+3V3', 'BAT_P', 'BAT_N', 'BOOST_5V', 'BOOST_SW', 'USB_5V', 'EXT_5V', 'SENSOR_VCC', 'TFT_LED', 'FET_DRAIN', 'VBAT_RTC']
HIGH_CURRENT = ['VIN_JACK', 'VIN_FUSED', 'VIN', 'SW_BUCK', 'BUCK_5V']


def footprint_id(comp):
    return comp['footprint'] or symbol_footprint(symbols.load(comp['symbol']))


def courtyard_box(fp):
    for layer in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
        poly = fp.GetCourtyard(layer)
        if poly.OutlineCount():
            return poly.BBox()
    return fp.GetBoundingBox(False)


def extent(fp):
    """(x0, y0, x1, y1) in nm: courtyard plus every pad. Imported courtyards often omit the pads."""
    box = courtyard_box(fp)
    xs, ys = [box.GetX(), box.GetRight()], [box.GetY(), box.GetBottom()]
    for pad in fp.Pads():
        b = pad.GetBoundingBox()
        xs += [b.GetX(), b.GetRight()]
        ys += [b.GetY(), b.GetBottom()]
    return min(xs), min(ys), max(xs), max(ys)


def repair_footprint(ref, fp):
    """Fix import artefacts: SMD pads converted as through-holes with a near-zero drill, and the
    ESP32's 0.2 mm thermal vias (below JLCPCB's standard 0.3 mm; the module grounds through its pad)."""
    for pad in list(fp.Pads()):
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_PTH:
            continue
        drill = pcbnew.ToMM(min(pad.GetDrillSize().x, pad.GetDrillSize().y))
        if drill < 0.05 or (ref != 'U1' and drill < 0.3):
            pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
            pad.SetDrillSize(pcbnew.VECTOR2I(0, 0))
            pad.SetLayerSet(pcbnew.PAD.SMDMask())
        elif ref == 'U1' and drill < 0.3:
            fp.Remove(pad)
    if ref == 'U1':
        add_esp32_solder_holes(fp)


def add_esp32_solder_holes(fp):
    """Low-cost board: the ESP32 is hand-soldered, so its ground pad becomes one solid pad with five
    0.6 mm plated holes. Solder fed from the back with an iron flows through to the module's pad."""
    def mm(x, y):
        return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))
    solid = pcbnew.PAD(fp)
    solid.SetNumber('39'); solid.SetAttribute(pcbnew.PAD_ATTRIB_SMD); solid.SetShape(pcbnew.PAD_SHAPE_RECT)
    solid.SetSize(mm(3.7, 3.7)); solid.SetLayerSet(pcbnew.PAD.SMDMask()); solid.SetFPRelativePosition(mm(-1.5, 2.46))
    fp.Add(solid)
    for x, y in [(-2.2, 1.76), (-0.8, 1.76), (-1.5, 2.46), (-2.2, 3.16), (-0.8, 3.16)]:
        hole = pcbnew.PAD(fp)
        hole.SetNumber('39'); hole.SetAttribute(pcbnew.PAD_ATTRIB_PTH); hole.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        hole.SetSize(mm(1.0, 1.0)); hole.SetDrillSize(mm(0.6, 0.6)); hole.SetLayerSet(pcbnew.PAD.PTHMask())
        hole.SetFPRelativePosition(mm(x, y))
        fp.Add(hole)


def move_to(fp, x, y):
    x0, y0, x1, y1 = extent(fp)
    target = pt(x, y)
    fp.Move(pcbnew.VECTOR2I(target.x - (x0 + x1) // 2, target.y - (y0 + y1) // 2))


def mouth_direction(fp):
    """Direction (dx, dy) a connector opens toward: the side its courtyard extends farthest past the pads."""
    box = courtyard_box(fp)
    xs = [p.GetPosition().x for p in fp.Pads()]
    ys = [p.GetPosition().y for p in fp.Pads()]
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
    reach = {(-1, 0): cx - box.GetX(), (1, 0): box.GetRight() - cx, (0, -1): cy - box.GetY(), (0, 1): box.GetBottom() - cy}
    return max(reach, key=reach.get)


def tighten_esp32_courtyard(fp):
    """KiCad draws the courtyard around the whole antenna keep-out; keep it to the module body.
    The keep-out rule area itself stays and still forbids copper near the antenna."""
    for item in list(fp.GraphicalItems()):
        if item.GetLayer() in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            fp.Remove(item)
    rect = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_RECT)
    rect.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(-9.6), pcbnew.FromMM(-13.05)))
    rect.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(9.6), pcbnew.FromMM(13.6)))
    rect.SetLayer(pcbnew.F_CrtYd)
    rect.SetWidth(pcbnew.FromMM(0.05))
    fp.Add(rect)


def check_overlaps(board):
    """Report parts whose extents overlap on the same side; through-hole parts count on both sides."""
    boxes = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        x0, y0, x1, y1 = extent(fp)
        tht = any(p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) for p in fp.Pads())
        sides = {'F', 'B'} if tht else {'B' if fp.IsFlipped() else 'F'}
        boxes.append((ref, sides, x0, y0, x1, y1))
    gap = pcbnew.FromMM(0.2)
    found = []
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            if a[1] & b[1] and a[2] < b[4] + gap and b[2] < a[4] + gap and a[3] < b[5] + gap and b[3] < a[5] + gap:
                found.append(f'{a[0]}-{b[0]}')
    bx0, by0, bx1, by1 = pt(0, 0).x, pt(0, 0).y, pt(W, H).x, pt(W, H).y
    edge = [ref for ref, _, x0, y0, x1, y1 in boxes
            if ref not in ('J1', 'J2', 'U1') and (x0 < bx0 or y0 < by0 or x1 > bx1 or y1 > by1)]
    zx0, zy0, zx1, zy1 = pt(SENSOR_ZONE[0], SENSOR_ZONE[1]).x, pt(SENSOR_ZONE[0], SENSOR_ZONE[1]).y, pt(SENSOR_ZONE[2], SENSOR_ZONE[3]).x, pt(SENSOR_ZONE[2], SENSOR_ZONE[3]).y
    in_zone = [ref for ref, sides, x0, y0, x1, y1 in boxes
               if ref != 'J11' and 'F' in sides and x0 < zx1 and zx0 < x1 and y0 < zy1 and zy0 < y1]
    print('OVERLAPS:', ' '.join(found) if found else 'none')
    print('IN SENSOR ZONE:', ' '.join(in_zone) if in_zone else 'none')
    print('OFF BOARD:', ' '.join(edge) if edge else 'none')
    return found


def add_edge_cuts(board):
    def seg(a, b):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pt(*a)); s.SetEnd(pt(*b)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(pcbnew.FromMM(0.1))
        board.Add(s)

    def arc(start, mid, end):
        a = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
        a.SetArcGeometry(pt(*start), pt(*mid), pt(*end)); a.SetLayer(pcbnew.Edge_Cuts); a.SetWidth(pcbnew.FromMM(0.1))
        board.Add(a)
    r, k = CORNER, CORNER * (1 - 0.70710678)
    seg((r, 0), (W - r, 0)); seg((W, r), (W, H - r)); seg((W - r, H), (r, H)); seg((0, H - r), (0, r))
    arc((W - r, 0), (W - k, k), (W, r)); arc((W, H - r), (W - k, H - k), (W - r, H))
    arc((r, H), (k, H - k), (0, H - r)); arc((0, r), (k, k), (r, 0))


def add_text(board, text, x, y, layer, size=1.2, mirrored=False):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text); t.SetPosition(pt(x, y)); t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size))); t.SetTextThickness(pcbnew.FromMM(size * 0.15))
    t.SetMirrored(mirrored)
    board.Add(t)


def add_outline(board, x0, y0, x1, y1, layer, width=0.15):
    for a, b in [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]:
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pt(*a)); s.SetEnd(pt(*b)); s.SetLayer(layer); s.SetWidth(pcbnew.FromMM(width))
        board.Add(s)


def add_gnd_zone(board, net, layer):
    zone = pcbnew.ZONE(board)
    zone.SetLayer(layer)
    zone.SetNet(net)
    outline = zone.Outline()
    outline.NewOutline()
    inset = 0.5
    for x, y in [(inset, inset), (W - inset, inset), (W - inset, H - inset), (inset, H - inset)]:
        outline.Append(pt(x, y))
    zone.SetLocalClearance(pcbnew.FromMM(0.25))
    zone.SetMinThickness(pcbnew.FromMM(0.25))
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)   # SMD pads solid, through-holes with reliefs
    zone.SetThermalReliefGap(pcbnew.FromMM(0.3))
    zone.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.4))
    board.Add(zone)


def net_name(net):
    """Schematic nets come from local labels on the root sheet, which KiCad names '/<label>'."""
    return '/' + net


def sync_project_rules():
    """kicad-cli DRC reads rules and net classes from the .kicad_pro, not the board: keep them equal."""
    pro = PROJECT / 'attendance-board-economic.kicad_pro'
    data = json.loads(pro.read_text(encoding='utf-8'))
    rules = data['board']['design_settings']['rules']
    rules.update(min_track_width=0.15, min_clearance=0.15, min_copper_edge_clearance=0.3,
                 min_via_diameter=0.5, min_through_hole_diameter=0.3)
    data['board']['design_settings']['defaults']['zones']['min_clearance'] = 0.25
    ns = data['net_settings']
    template = next(c for c in ns['classes'] if c['name'] == 'Default')
    classes = [dict(template, track_width=0.25, clearance=0.15, via_diameter=0.6, via_drill=0.3)]
    for i, (name, width, via, drill) in enumerate([('Power', 0.4, 0.7, 0.35), ('HighCurrent', 0.8, 0.8, 0.4)]):
        classes.append(dict(template, name=name, track_width=width, clearance=0.15, via_diameter=via, via_drill=drill, priority=i))
    ns['classes'] = classes
    ns['netclass_patterns'] = ([{'netclass': 'Power', 'pattern': net_name(n)} for n in POWER]
                               + [{'netclass': 'HighCurrent', 'pattern': net_name(n)} for n in HIGH_CURRENT])
    ns['netclass_assignments'] = {}
    pro.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def configure_rules(board):
    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = pcbnew.FromMM(0.15)
    ds.m_ViasMinSize = pcbnew.FromMM(0.5)
    ds.m_MinThroughDrill = pcbnew.FromMM(0.3)
    ds.m_MinClearance = pcbnew.FromMM(0.15)
    ds.m_CopperEdgeClearance = pcbnew.FromMM(0.3)
    ns = ds.m_NetSettings
    default = ns.GetDefaultNetclass()
    default.SetTrackWidth(pcbnew.FromMM(0.25)); default.SetClearance(pcbnew.FromMM(0.15))
    default.SetViaDiameter(pcbnew.FromMM(0.6)); default.SetViaDrill(pcbnew.FromMM(0.3))
    for name, width, via, via_drill, nets in [('Power', 0.4, 0.7, 0.35, POWER), ('HighCurrent', 0.8, 0.8, 0.4, HIGH_CURRENT)]:
        nc = pcbnew.NETCLASS(name)
        nc.SetTrackWidth(pcbnew.FromMM(width)); nc.SetClearance(pcbnew.FromMM(0.15))
        nc.SetViaDiameter(pcbnew.FromMM(via)); nc.SetViaDrill(pcbnew.FromMM(via_drill))
        ns.SetNetclass(name, nc)
        for net in nets:
            ns.SetNetclassPatternAssignment(net_name(net), name)
    ns.RecomputeEffectiveNetclasses()


def build():
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(2)
    configure_rules(board)
    nets = {}
    for comp in COMPONENTS.values():
        for net in comp['pins'].values():
            if net != 'NC' and net not in nets:
                nets[net] = pcbnew.NETINFO_ITEM(board, net_name(net))
                board.Add(nets[net])

    unplaced, unmatched = [], []
    for ref, comp in COMPONENTS.items():
        fp = footprints.load(footprint_id(comp))
        fp.SetParent(board)
        lib, name = footprint_id(comp).split(':', 1)
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetPath(pcbnew.KIID_PATH('/' + uid('sym', ref)))
        repair_footprint(ref, fp)
        fp.SetReference(ref)
        fp.SetValue(comp['value'])
        for name, text in (('LCSC', comp['lcsc'] or ''), ('Note', comp['note'])):
            if name == 'LCSC' or text:   # same fields as the schematic symbol (schematic parity)
                field = pcbnew.PCB_FIELD(fp, fp.GetNextFieldOrdinal(), name)
                field.SetText(text); field.SetVisible(False); field.SetLayer(pcbnew.F_Fab)
                fp.Add(field)
        attrs = fp.GetAttributes()
        if comp['dnp']:
            attrs |= pcbnew.FP_DNP
        if not comp['lcsc']:
            attrs |= pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES
        fp.SetAttributes(attrs)
        for pad in fp.Pads():
            number = pad.GetNumber()
            net = comp['pins'].get(number)
            if net and net != 'NC':
                pad.SetNet(nets[net])
            elif net == 'NC':   # KiCad's name for a pin with a no-connect flag
                pin_name = {p['number']: p['name'] for p in symbols.pins(symbols.load(comp['symbol']))}.get(number, '~')
                key = f'unconnected-({ref}-Pad{number})' if pin_name in ('', '~', number) else f'unconnected-({ref}-{pin_name}-Pad{number})'
                if key not in nets:
                    nets[key] = pcbnew.NETINFO_ITEM(board, key)
                    board.Add(nets[key])
                pad.SetNet(nets[key])
            elif number and net is None and pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                unmatched.append(f'{ref}.{number}')
        board.Add(fp)
        if ref == 'U1':
            tighten_esp32_courtyard(fp)
            fp.SetPosition(pt(*U1_POS))
            fp.SetOrientationDegrees(U1_ROT)   # antenna end 0.5 mm inside the right edge
            continue
        if ref not in PLACE:
            unplaced.append(ref)
            continue
        x, y, rot, side = PLACE[ref]
        fp.SetOrientationDegrees(rot)
        if side == 'B':
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        if ref in ('J1', 'J2'):  # turn edge connectors until their mouth faces the bottom edge
            for _ in range(4):
                if mouth_direction(fp) == (0, 1):
                    break
                fp.Rotate(fp.GetPosition(), pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T))
        move_to(fp, x, y)

    check_overlaps(board)
    add_edge_cuts(board)
    # Front silkscreen: where the display and sensor sit, so the enclosure can follow the board.
    add_outline(board, 7.0, 1.0, 63.0, 99.0, pcbnew.F_SilkS)
    add_text(board, '3.5in ILI9488 module (cable to J5)', 25, 45, pcbnew.F_SilkS)
    add_outline(board, 22.0, 104.0, 48.0, 147.0, pcbnew.F_SilkS)
    add_text(board, 'R307S: keep clear', 35, 125, pcbnew.F_SilkS)
    add_text(board, 'J11: 5V GND TX RX TCH 3V3', 35, 102.5, pcbnew.F_SilkS, 1.0)
    add_text(board, 'ATTENDANCE BOARD v0.2 ECONOMIC  2026-11', 35, 120, pcbnew.B_SilkS, 1.0, mirrored=True)
    add_text(board, 'LiPo +', 58.8, 37.5, pcbnew.B_SilkS, 0.9, mirrored=True)
    add_text(board, 'TAMPER', 4.5, 58.5, pcbnew.B_SilkS, 0.9, mirrored=True)
    # H2 is inside the antenna keep-out (fixed case boss): a metal screw there would detune the antenna.
    add_text(board, 'H2: nylon screw (antenna)', 52, 2.2, pcbnew.B_SilkS, 0.8, mirrored=True)
    add_gnd_zone(board, nets['GND'], pcbnew.F_Cu)
    add_gnd_zone(board, nets['GND'], pcbnew.B_Cu)
    pcbnew.SaveBoard(str(BOARD_FILE), board)
    sync_project_rules()
    print(f'Wrote {BOARD_FILE.name}: {len(COMPONENTS)} footprints, {len(nets)} nets')
    if unplaced:
        print('NOT PLACED:', ' '.join(unplaced))
    if unmatched:
        print('pads without a net in design.py:', ' '.join(unmatched))
    return board


def unrouted(board):
    board.BuildConnectivity()
    return board.GetConnectivity().GetUnconnectedCount(False)


def route(board, attempts=5):
    """Freerouting with GND routed as an ordinary net (the pours are removed for routing and added back
    afterwards, so ground never depends on pour islands). Passes repeat on the routed board until every
    connection is made."""
    gnd = board.FindNet(net_name('GND'))
    for zone in list(board.Zones()):
        if not zone.GetIsRuleArea():
            board.Remove(zone)
    dsn, ses = PROJECT / 'attendance-board-economic.dsn', PROJECT / 'attendance-board-economic.ses'
    for attempt in range(1, attempts + 1):
        if not pcbnew.ExportSpecctraDSN(board, str(dsn)):
            raise RuntimeError('DSN export failed')
        print(f'Routing with Freerouting (pass {attempt})...')
        command = ['java', '-jar', str(FREEROUTING), '-de', str(dsn), '-do', str(ses), '-mp', '40']
        try:  # route optimisation sometimes runs away; fall back to the plain autorouter result
            subprocess.run(command, check=True, timeout=300)
        except subprocess.TimeoutExpired:
            print('Optimisation took too long; routing again without it')
            subprocess.run(command + ['-mt', '0'], check=True, timeout=600)
        if not pcbnew.ImportSpecctraSES(board, str(ses)):
            raise RuntimeError('SES import failed')
        left = unrouted(board)
        print(f'Unrouted connections: {left}')
        if not left:
            break
    add_gnd_zone(board, gnd, pcbnew.F_Cu)
    add_gnd_zone(board, gnd, pcbnew.B_Cu)


def stitch_ground(board, pitch=5.0):
    """GND vias where both ground pours are present: a grid across the board, plus one next to every
    GND SMD pad, so no pour island is left floating. Vias go only where the filled copper already keeps
    clearance from every other net (the fills also exclude the antenna keep-out)."""
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    gnd = board.FindNet(net_name('GND'))
    fills = {z.GetLayer(): z.GetFilledPolysList(z.GetLayer()) for z in board.Zones() if z.GetNetname() == gnd.GetNetname()}
    radius = pcbnew.FromMM(0.3 + 0.05)
    vias = [v.GetPosition() for v in board.GetTracks() if isinstance(v, pcbnew.PCB_VIA)]

    def fits(p):
        ring = [pcbnew.VECTOR2I(p.x + int(radius * dx), p.y + int(radius * dy))
                for dx, dy in [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (0.7, 0.7), (-0.7, 0.7), (0.7, -0.7), (-0.7, -0.7)]]
        return all(poly.Contains(q) for poly in fills.values() for q in ring)

    def near_via(p, mm):
        limit = pcbnew.FromMM(mm) ** 2
        return any((v.x - p.x) ** 2 + (v.y - p.y) ** 2 < limit for v in vias)

    def add(p):
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(p); via.SetWidth(pcbnew.FromMM(0.6)); via.SetDrill(pcbnew.FromMM(0.3)); via.SetNet(gnd)
        board.Add(via); vias.append(p)

    added = 0
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() != gnd.GetNetname() or pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            c = pad.GetPosition()
            if near_via(c, 2.5):
                continue
            for r in (1.0, 1.4, 1.8, 2.3):
                options = [pcbnew.VECTOR2I(c.x + int(pcbnew.FromMM(r) * dx), c.y + int(pcbnew.FromMM(r) * dy))
                           for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0), (0.7, 0.7), (-0.7, 0.7), (0.7, -0.7), (-0.7, -0.7)]]
                hit = next((q for q in options if not near_via(q, 1.0) and fits(q)), None)
                if hit:
                    add(hit); added += 1
                    break
    steps_x, steps_y = int(W // pitch), int(H // pitch)
    for i in range(1, steps_x + 1):
        for j in range(1, steps_y + 1):
            p = pt(i * pitch - pitch / 2, j * pitch - pitch / 2)
            if not near_via(p, pitch * 0.6) and fits(p):
                add(p); added += 1
    # Any pour island still without a via: search it on a fine grid for a spot both pours cover.
    filler.Fill(board.Zones())
    fills = {z.GetLayer(): z.GetFilledPolysList(z.GetLayer()) for z in board.Zones() if z.GetNetname() == gnd.GetNetname()}
    step = pcbnew.FromMM(0.4)
    for layer, poly in fills.items():
        for k in range(poly.OutlineCount()):
            island = pcbnew.SHAPE_POLY_SET(); island.AddOutline(poly.Outline(k))
            if any(island.Contains(v) for v in vias):
                continue
            box = poly.Outline(k).BBox()
            spot = next((q for y in range(box.GetY(), box.GetBottom(), step) for x in range(box.GetX(), box.GetRight(), step)
                         for q in [pcbnew.VECTOR2I(x, y)] if island.Contains(q) and not near_via(q, 1.0) and fits(q)), None)
            if spot:
                add(spot); added += 1
    print(f'Ground stitching: {added} vias')


def finish(board):
    stitch_ground(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(BOARD_FILE), board)
    print('Zones filled and board saved')


if __name__ == '__main__':
    b = build()
    if '--route' in sys.argv:
        b = pcbnew.LoadBoard(str(BOARD_FILE))
        route(b)
    finish(b)
