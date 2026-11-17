"""Load footprints for design.py components (standard and project libraries)."""
from pathlib import Path

import pcbnew
from symbols import KICAD

PROJECT_FP = Path(__file__).resolve().parent.parent.parent / 'libraries/attendance.pretty'


def library_path(lib):
    return str(PROJECT_FP if lib == 'attendance' else KICAD / f'share/kicad/footprints/{lib}.pretty')


def load(fp_id):
    lib, name = fp_id.split(':', 1)
    fp = pcbnew.FootprintLoad(library_path(lib), name)
    if fp is None:
        raise FileNotFoundError(fp_id)
    return fp


def courtyard_size(fp):
    """Width and height (mm) of the courtyard, falling back to pads + graphics."""
    for layer in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
        poly = fp.GetCourtyard(layer)
        if poly.OutlineCount():
            box = poly.BBox()
            return pcbnew.ToMM(box.GetWidth()), pcbnew.ToMM(box.GetHeight())
    box = fp.GetBoundingBox(False)
    return pcbnew.ToMM(box.GetWidth()), pcbnew.ToMM(box.GetHeight())


if __name__ == '__main__':
    from design import COMPONENTS
    from gen_schematic import symbol_footprint  # noqa: F401 (footprint defaults come from the schematic step)
    import symbols as syms
    seen = {}
    for comp in COMPONENTS.values():
        fp_id = comp['footprint'] or symbol_footprint(syms.load(comp['symbol']))
        seen.setdefault(fp_id, []).append(comp['ref'])
    for fp_id, refs in sorted(seen.items()):
        w, h = courtyard_size(load(fp_id))
        print(f'{w:6.1f} x {h:5.1f}  {fp_id}  [{" ".join(refs)}]')
