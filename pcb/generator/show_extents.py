"""Print board-relative extents (mm) of the given references. Usage: show_extents.py J3 U4 ..."""
import sys

import pcbnew
from gen_pcb import BOARD_FILE, OX, OY, extent

board = pcbnew.LoadBoard(str(BOARD_FILE))
for ref in sys.argv[1:]:
    fp = board.FindFootprintByReference(ref)
    x0, y0, x1, y1 = (pcbnew.ToMM(v) for v in extent(fp))
    side = 'B' if fp.IsFlipped() else 'F'
    print(f'{ref:5} {side}  x {x0 - OX:6.2f} .. {x1 - OX:6.2f}   y {y0 - OY:6.2f} .. {y1 - OY:6.2f}')
