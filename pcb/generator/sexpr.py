"""Minimal S-expression reader/writer for KiCad files."""
import re

TOKEN = re.compile(r'\s*(?:(\()|(\))|("(?:[^"\\]|\\.)*")|([^\s()"]+))')


class Sym(str):
    """An unquoted atom (keyword or number), kept distinct from quoted strings."""


def parse(text):
    stack, current, pos = [], [], 0
    while True:
        match = TOKEN.match(text, pos)
        if not match or match.end() == pos:
            break
        pos = match.end()
        opening, closing, string, atom = match.groups()
        if opening:
            stack.append(current)
            current = []
        elif closing:
            finished, current = current, stack.pop()
            current.append(finished)
        elif string is not None:
            current.append(string[1:-1].replace('\\"', '"').replace('\\\\', '\\'))
        else:
            current.append(Sym(atom))
    return current[0] if len(current) == 1 else current


def quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'


def dump(node, indent=0):
    if not isinstance(node, list):
        if isinstance(node, Sym):
            return str(node)
        if isinstance(node, bool):
            return 'yes' if node else 'no'
        if isinstance(node, (int, float)):
            return format_number(node)
        return quote(node)
    simple = all(not isinstance(item, list) for item in node)
    if simple:
        return '(' + ' '.join(dump(item) for item in node) + ')'
    head = []
    rest = list(node)
    while rest and not isinstance(rest[0], list):
        head.append(dump(rest.pop(0)))
    pad = '\t' * (indent + 1)
    body = '\n'.join(pad + dump(item, indent + 1) for item in rest)
    return '(' + ' '.join(head) + '\n' + body + '\n' + '\t' * indent + ')'


def format_number(value):
    if isinstance(value, int):
        return str(value)
    text = f'{value:.4f}'.rstrip('0').rstrip('.')
    return '0' if text in ('-0', '') else text


def find(node, key):
    """First child list whose head is `key`."""
    for item in node:
        if isinstance(item, list) and item and item[0] == key:
            return item
    return None


def find_all(node, key):
    return [item for item in node if isinstance(item, list) and item and item[0] == key]
