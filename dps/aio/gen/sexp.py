"""Minimal KiCad S-expression reader/writer."""
import re

TOK = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))')


class Sym(str):
    """A bare atom (not a quoted string)."""


def parse(text):
    stack, cur = [], []
    pos = 0
    while True:
        m = TOK.match(text, pos)
        if not m or m.end() == pos:
            break
        pos = m.end()
        o, c, s, a = m.groups()
        if o:
            stack.append(cur)
            cur = []
        elif c:
            done = cur
            cur = stack.pop()
            cur.append(done)
        elif s is not None:
            cur.append(s.replace('\\"', '"').replace('\\\\', '\\'))
        else:
            cur.append(Sym(a))
    return cur[0]


def dump(x, ind=0):
    if isinstance(x, list):
        simple = all(not isinstance(e, list) for e in x)
        if simple:
            return "(" + " ".join(dump(e) for e in x) + ")"
        head = []
        rest = []
        for e in x:
            (rest if (rest or isinstance(e, list)) else head).append(e)
        pad = "\t" * (ind + 1)
        return ("(" + " ".join(dump(e) for e in head) + "\n"
                + "\n".join(pad + dump(e, ind + 1) for e in rest) + "\n" + "\t" * ind + ")")
    if isinstance(x, Sym):
        return str(x)
    if isinstance(x, (int, float)):
        return fmt(x)
    return '"' + str(x).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def fmt(v):
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def find(lst, key):
    return [e for e in lst if isinstance(e, list) and e and e[0] == key]


def first(lst, key):
    r = find(lst, key)
    return r[0] if r else None
