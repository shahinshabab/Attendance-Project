"""Load KiCad symbols (standard and project libraries), flatten `extends`, and list pins."""
import copy
import os
from pathlib import Path

from sexpr import Sym, find, find_all, parse

KICAD = Path(os.environ.get('KICAD_DIR', Path(os.environ['LOCALAPPDATA']) / 'Programs/KiCad/10.0'))
STD_SYMBOLS = KICAD / 'share/kicad/symbols'
PROJECT_LIB = Path(__file__).resolve().parent.parent / 'libraries/attendance.kicad_sym'

_cache = {}


def _library(name):
    if name not in _cache:
        path = PROJECT_LIB if name == 'attendance' else STD_SYMBOLS / f'{name}.kicad_sym'
        tree = parse(path.read_text(encoding='utf-8'))
        _cache[name] = {item[1]: item for item in find_all(tree, 'symbol')}
    return _cache[name]


def load(lib_id):
    """Return a flattened symbol definition named `lib:name`, ready for a schematic's lib_symbols."""
    lib, name = lib_id.split(':', 1)
    symbols = _library(lib)
    node = copy.deepcopy(symbols[name])
    parent_ref = find(node, 'extends')
    if parent_ref:
        parent = copy.deepcopy(symbols[parent_ref[1]])
        # Child properties override the parent's; units and graphics come from the parent.
        child_props = {p[1]: p for p in find_all(node, 'property')}
        merged = [Sym('symbol'), name]
        for item in parent[2:]:
            if isinstance(item, list) and item and item[0] == 'property' and item[1] in child_props:
                merged.append(child_props.pop(item[1]))
            elif isinstance(item, list) and item and item[0] == 'symbol':
                unit = copy.deepcopy(item)
                unit[1] = unit[1].replace(parent_ref[1], name, 1)
                merged.append(unit)
            else:
                merged.append(item)
        merged.extend(child_props.values())
        node = merged
    node[1] = lib_id
    return node


def pins(symbol):
    """Pins of a flattened symbol: list of dicts with number, name, x, y, angle (symbol coordinates, Y up)."""
    result = []

    def walk(item):
        for child in item:
            if isinstance(child, list) and child:
                if child[0] == 'pin':
                    at = find(child, 'at')
                    result.append({'number': find(child, 'number')[1], 'name': find(child, 'name')[1],
                                   'type': str(child[1]), 'x': float(at[1]), 'y': float(at[2]),
                                   'angle': float(at[3]) if len(at) > 3 else 0.0})
                elif child[0] == 'symbol':
                    walk(child)
    walk(symbol)
    return result


if __name__ == '__main__':
    import sys
    for lib_id in sys.argv[1:]:
        found = pins(load(lib_id))
        print(lib_id, f'({len(found)} pins)')
        print('   ' + ', '.join(f"{p['number']}:{p['name']}" for p in sorted(found, key=lambda p: (len(p['number']), p['number']))))
