"""Normalise the easyeda2kicad symbol library: 'unspecified' pins become 'passive'.

easyeda2kicad leaves pin electrical types unspecified, which makes KiCad's ERC warn on every
connection. Passive is the honest type for these imported parts. Run after adding parts.
"""
from pathlib import Path

from sexpr import Sym, dump, parse

LIB = Path(__file__).resolve().parent.parent / 'libraries/attendance.kicad_sym'


def walk(node, changed):
    for item in node:
        if isinstance(item, list) and item:
            if item[0] == 'pin' and len(item) > 1 and item[1] == 'unspecified':
                item[1] = Sym('passive')
                changed.append(1)
            walk(item, changed)


tree = parse(LIB.read_text(encoding='utf-8'))
changed = []
walk(tree, changed)
LIB.write_text(dump(tree) + '\n', encoding='utf-8')
print(f'{len(changed)} pins set to passive in {LIB.name}')
