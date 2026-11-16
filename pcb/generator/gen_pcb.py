"""Generate the PCB (placement, outline, rules, zones) from design.py, then optionally autoroute.

Run with KiCad's Python:  <KiCad>/bin/python.exe gen_pcb.py [--route]
Coordinates below are board millimetres seen from the FRONT (user side): x right, y down,
board 70 x 110 mm. 'B' parts are on the back (all SMT, assembled by JLCPCB); the front carries
only the TFT socket and the R307 lead pads. The TFT and R307 themselves sit on the front.
"""
import subprocess
import sys
from pathlib import Path

import pcbnew
import footprints
import symbols
from design import COMPONENTS
from gen_schematic import symbol_footprint

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent / 'attendance-board'
BOARD_FILE = PROJECT / 'attendance-board.kicad_pcb'
FREEROUTING = Path.home() / 'AppData/Local/Programs/Freerouting/freerouting-cli.exe'
OX, OY = 100.0, 50.0           # board origin on the KiCad page
W, H, CORNER = 70.0, 110.0, 3.0


def pt(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))


# ---------------------------------------------------------------- placement (x, y, rotation, side)
# The centre of each part's real extent (courtyard plus pads) goes to (x, y). U1 is placed by origin.
PLACE = {
    # mounting holes
    'H1': (4, 4, 0, 'F'), 'H2': (66, 4, 0, 'F'), 'H3': (4, 106, 0, 'F'), 'H4': (66, 106, 0, 'F'),
    # left of ESP32: programming and auto-reset (ESP32 TX/RX/IO0 are on this side when mounted on the back)
    'J9': (4.5, 19.5, 0, 'B'), 'JP1': (10, 28.5, 0, 'B'),
    'R22': (10, 12.5, 90, 'B'), 'R23': (12.5, 12.5, 90, 'B'),
    'R20': (17, 9.5, 0, 'B'), 'Q4': (17, 14, 0, 'B'),
    'R21': (11, 20.5, 90, 'B'), 'Q5': (17, 20.5, 0, 'B'),
    'R19': (22, 18.5, 90, 'B'), 'SW2': (19, 26.5, 0, 'B'),
    'R25': (22, 10.5, 90, 'B'), 'R26': (24, 14, 90, 'B'),
    # right of ESP32: EN, decoupling, 3.3 V regulator, power LED
    'C19': (47.5, 9.5, 90, 'B'), 'C20': (50, 9.5, 90, 'B'),
    'R18': (53, 9.5, 90, 'B'), 'C21': (55.5, 9.5, 90, 'B'), 'SW1': (61, 11.5, 0, 'B'),
    'C10': (49, 16, 0, 'B'), 'C11': (54, 16.5, 0, 'B'), 'U4': (62, 21, 90, 'B'), 'C9': (67.5, 14.5, 90, 'B'),
    'R5': (48, 21.5, 90, 'B'), 'LED5': (48, 25.5, 90, 'B'), 'TP3': (53, 22, 0, 'B'),
    # middle left: RTC with coin cell
    'BT1': (13.5, 42, 0, 'B'), 'U2': (8.5, 58, 0, 'B'), 'C22': (15, 55.5, 0, 'B'), 'C23': (15, 58.5, 0, 'B'),
    'R24': (15, 61.5, 0, 'B'),
    # TFT backlight switch
    'Q2': (30, 34.5, 0, 'B'), 'R27': (30, 30.5, 0, 'B'), 'R28': (34, 30.5, 0, 'B'),
    # left edge: I2C and tamper connectors with the tamper pull-up and filter
    'J8': (4.5, 69, 90, 'B'), 'J7': (4.5, 91.5, 90, 'B'),
    'R30': (11, 86.5, 90, 'B'), 'R31': (13.5, 86.5, 90, 'B'), 'C25': (16, 86.5, 90, 'B'),
    # front: TFT socket and R307 lead pads (just above the sensor); sensor connector on the back
    'J5': (35, 61, 90, 'F'), 'J11': (35, 66.5, 90, 'F'),
    'J4': (35, 71.5, 0, 'B'), 'JP2': (25, 75, 0, 'B'), 'C24': (44, 75, 0, 'B'),
    # status LEDs
    'LED1': (19, 79.5, 90, 'B'), 'R33': (19, 83.5, 90, 'B'), 'LED2': (22, 79.5, 90, 'B'), 'R34': (22, 83.5, 90, 'B'),
    'TP4': (16, 75, 0, 'B'),
    # battery: charger, protection, boost, switch-over (right middle)
    'J3': (65, 31, 90, 'B'), 'J10': (66.5, 46, 90, 'B'), 'TP5': (63, 41, 0, 'B'),
    'C12': (40, 30, 0, 'B'), 'C13': (40, 33, 0, 'B'), 'U5': (46.5, 32.5, 0, 'B'), 'R6': (46.5, 37.5, 0, 'B'),
    'R7': (39, 39, 0, 'B'), 'LED3': (43, 39, 0, 'B'), 'R8': (39, 42, 0, 'B'), 'LED4': (43, 42, 0, 'B'),
    'R9': (47.5, 41, 90, 'B'),
    'R10': (55, 31, 0, 'B'), 'U6': (55, 35, 0, 'B'), 'C14': (51.5, 35, 90, 'B'), 'R11': (55, 39, 0, 'B'),
    'Q3': (59, 39, 0, 'B'),
    'U7': (55, 47.5, 0, 'B'), 'L2': (60, 47.5, 0, 'B'), 'R12': (51, 46, 0, 'B'), 'R13': (51, 49, 0, 'B'),
    'C15': (60, 53, 0, 'B'), 'C16': (55.5, 52, 90, 'B'), 'C17': (53, 52, 90, 'B'), 'U9': (48.5, 52.5, 0, 'B'),
    'R16': (64, 53, 90, 'B'), 'R17': (66.5, 53, 90, 'B'), 'C18': (66.5, 57.5, 90, 'B'),
    # buzzer group (right, below the battery block)
    'BZ1': (62.5, 66, 0, 'B'), 'Q6': (54.5, 63, 0, 'B'), 'R32': (54.5, 66.5, 0, 'B'), 'D6': (54.5, 70, 0, 'B'),
    'TP2': (49, 70, 0, 'B'),
    # 5 V rail, external-power OR and sense (lower right)
    'C7': (57, 85, 0, 'B'), 'C8': (52, 85, 90, 'B'),
    'D4': (47, 80, 0, 'B'), 'D5': (57, 80, 0, 'B'), 'C6': (64, 80, 90, 'B'),
    'R14': (62.5, 87, 90, 'B'), 'R15': (65, 87, 90, 'B'),
    'U8': (47, 106, 0, 'B'), 'U10': (63.5, 99.5, 0, 'B'),
    'J2': (55, 106.5, 0, 'B'), 'R2': (53.5, 100, 90, 'B'), 'R3': (56, 100, 90, 'B'), 'C5': (60.5, 100, 90, 'B'),
    # 12 V input and buck converter (bottom left)
    'J1': (21, 103, 0, 'B'), 'F1': (10, 100.5, 90, 'B'), 'Q1': (13, 94, 0, 'B'), 'R1': (13, 90.5, 0, 'B'),
    'D2': (18, 92, 0, 'B'), 'D3': (24.8, 92, 0, 'B'), 'TP1': (28, 97.5, 0, 'B'),
    'C1': (35, 83, 0, 'B'), 'C2': (30, 93, 90, 'B'),
    'U3': (34, 93, 0, 'B'), 'D1': (39.5, 95, 90, 'B'), 'L1': (47, 95, 0, 'B'),
    'C3': (35.5, 104.5, 0, 'B'), 'C4': (46, 101.5, 0, 'B'),
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
        if drill < 0.05:
            pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
            pad.SetDrillSize(pcbnew.VECTOR2I(0, 0))
            pad.SetLayerSet(pcbnew.PAD.SMDMask())
        elif ref == 'U1' and drill < 0.3:
            fp.Remove(pad)


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
    print('OVERLAPS:', ' '.join(found) if found else 'none')
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
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    zone.SetThermalReliefGap(pcbnew.FromMM(0.3))
    zone.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.4))
    board.Add(zone)


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
            ns.SetNetclassPatternAssignment(net, name)
    ns.RecomputeEffectiveNetclasses()


def build():
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(2)
    configure_rules(board)
    nets = {}
    for comp in COMPONENTS.values():
        for net in comp['pins'].values():
            if net != 'NC' and net not in nets:
                nets[net] = pcbnew.NETINFO_ITEM(board, net)
                board.Add(nets[net])

    unplaced, unmatched = [], []
    for ref, comp in COMPONENTS.items():
        fp = footprints.load(footprint_id(comp))
        fp.SetParent(board)
        repair_footprint(ref, fp)
        fp.SetReference(ref)
        fp.SetValue(comp['value'])
        if comp['lcsc']:
            field = pcbnew.PCB_FIELD(fp, fp.GetNextFieldOrdinal(), 'LCSC')
            field.SetText(comp['lcsc']); field.SetVisible(False); field.SetLayer(pcbnew.F_Fab)
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
            elif number and net is None and pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                unmatched.append(f'{ref}.{number}')
        board.Add(fp)
        if ref == 'U1':
            tighten_esp32_courtyard(fp)
            fp.SetPosition(pt(35, 13.3))   # module top edge at y = 0.5: antenna at the board edge
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
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
    # Front silkscreen: where the TFT and R307 sit, so the enclosure can follow the board.
    add_outline(board, 17.5, 8.0, 52.5, 64.0, pcbnew.F_SilkS)
    add_text(board, '1.8in TFT (header at bottom)', 35, 36, pcbnew.F_SilkS)
    add_outline(board, 7.0, 68.0, 63.0, 90.0, pcbnew.F_SilkS)
    add_text(board, 'R307 fingerprint sensor', 35, 79, pcbnew.F_SilkS)
    add_text(board, 'ATTENDANCE BOARD v0.1  2026-11', 35, 107.5, pcbnew.B_SilkS, 1.0, mirrored=True)
    add_text(board, 'LiPo +', 65, 25.5, pcbnew.B_SilkS, 0.9, mirrored=True)
    add_gnd_zone(board, nets['GND'], pcbnew.F_Cu)
    add_gnd_zone(board, nets['GND'], pcbnew.B_Cu)
    pcbnew.SaveBoard(str(BOARD_FILE), board)
    print(f'Wrote {BOARD_FILE.name}: {len(COMPONENTS)} footprints, {len(nets)} nets')
    if unplaced:
        print('NOT PLACED:', ' '.join(unplaced))
    if unmatched:
        print('pads without a net in design.py:', ' '.join(unmatched))
    return board


def route(board):
    dsn, ses = PROJECT / 'attendance-board.dsn', PROJECT / 'attendance-board.ses'
    if not pcbnew.ExportSpecctraDSN(board, str(dsn)):
        raise RuntimeError('DSN export failed')
    print('Routing with Freerouting...')
    subprocess.run([str(FREEROUTING), '-de', str(dsn), '-do', str(ses), '-mp', '40'], check=True)
    if not pcbnew.ImportSpecctraSES(board, str(ses)):
        raise RuntimeError('SES import failed')


def finish(board):
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(BOARD_FILE), board)
    print('Zones filled and board saved')


if __name__ == '__main__':
    b = build()
    if '--route' in sys.argv:
        b = pcbnew.LoadBoard(str(BOARD_FILE))
        route(b)
    finish(b)
