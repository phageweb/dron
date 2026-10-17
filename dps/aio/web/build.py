#!/usr/bin/env python3
"""Build schema.html: the AIO schematic, sheet by sheet, with clickable blocks.

    nix develop ./dps -c python3 dps/aio/web/build.py

Exports every sheet to SVG with kicad-cli, finds each block's outline from
the symbols it lists in obsah.py, and writes one self-contained page.
"""
import html, json, math, os, re, subprocess, sys, tempfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
AIO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, AIO)
from obsah import LISTY, ZDROJE, STAVY, ODKAZY  # noqa: E402
from tabulky import FUNCTION  # noqa: E402

TOK = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))')


def parse(text):
    stack, cur, pos = [], [], 0
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
            done, cur = cur, stack.pop()
            cur.append(done)
        else:
            cur.append(s if s is not None else a)
    return cur[0]


def find(lst, key):
    return [e for e in lst if isinstance(e, list) and e and e[0] == key]


def first(lst, key):
    r = find(lst, key)
    return r[0] if r else None


def lib_extent(sym):
    """Points of a library symbol's graphics and pin ends, in symbol units (y up)."""
    pts = []

    def walk(x):
        for e in x:
            if not isinstance(e, list):
                continue
            if e[0] == "rectangle":
                for k in ("start", "end"):
                    p = first(e, k)
                    pts.append((float(p[1]), float(p[2])))
            elif e[0] in ("polyline", "bezier"):
                for xy in find(first(e, "pts") or [], "xy"):
                    pts.append((float(xy[1]), float(xy[2])))
            elif e[0] == "circle":
                c, r = first(e, "center"), float(first(e, "radius")[1])
                pts.extend([(float(c[1]) - r, float(c[2]) - r), (float(c[1]) + r, float(c[2]) + r)])
            elif e[0] == "arc":
                for k in ("start", "mid", "end"):
                    p = first(e, k)
                    if p:
                        pts.append((float(p[1]), float(p[2])))
            elif e[0] == "pin":
                at = first(e, "at")
                x, y, a = float(at[1]), float(at[2]), math.radians(float(at[3]))
                ln = float(first(e, "length")[1])
                pts.extend([(x, y), (x + ln * math.cos(a), y + ln * math.sin(a))])
            else:
                walk(e)
    walk(sym)
    return pts


def sheet_boxes(path, want_path=None):
    """ref -> (x0, y0, x1, y1) in sheet mm, plus sheet symbols -> (name, box)."""
    d = parse(open(path).read())
    libs = {s[1]: s for s in first(d, "lib_symbols")[1:]}
    boxes, sheets = {}, []
    for s in find(d, "symbol"):
        lib = libs.get(first(s, "lib_id")[1])
        at = first(s, "at")
        X, Y, rot = float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0
        ref = None
        for inst in find(s, "instances"):
            for proj in find(inst, "project"):
                for p in find(proj, "path"):
                    if want_path is None or p[1] == want_path:
                        ref = first(p, "reference")[1]
        if not ref or ref.startswith("#") or lib is None:
            continue
        mir = first(s, "mirror")
        c, sn = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        xs, ys = [], []
        for px, py in lib_extent(lib):
            if mir and mir[1] == "x":
                py = -py
            if mir and mir[1] == "y":
                px = -px
            rx, ry = px * c - py * sn, px * sn + py * c
            xs.append(X + rx)
            ys.append(Y - ry)
        if xs:
            boxes[ref] = (min(xs), min(ys), max(xs), max(ys))
    rects = []
    for r in find(d, "rectangle"):
        s0, s1 = first(r, "start"), first(r, "end")
        x0, y0, x1, y1 = float(s0[1]), float(s0[2]), float(s1[1]), float(s1[2])
        rects.append((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
    boxes["__rects__"] = rects
    for sh in find(d, "sheet"):
        at, size = first(sh, "at"), first(sh, "size")
        name = [p[2] for p in find(sh, "property") if p[1] == "Sheetname"][0]
        x, y = float(at[1]), float(at[2])
        sheets.append((name, (x, y, x + float(size[1]), y + float(size[2]))))
    return boxes, sheets


def union(bs, margin):
    return [min(b[0] for b in bs) - margin, min(b[1] for b in bs) - margin,
            max(b[2] for b in bs) + margin, max(b[3] for b in bs) + margin]


def short(net):
    return re.sub(r"^/(?:[^/]+/)*", "", net) if net.startswith("/") else net


def main():
    out_html = os.path.join(HERE, "schema.html")
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["kicad-cli", "sch", "export", "svg", "--exclude-drawing-sheet", "-o", tmp,
                        os.path.join(AIO, "aio.kicad_sch")], check=True, capture_output=True)
        subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadxml", "-o",
                        os.path.join(tmp, "n.xml"), os.path.join(AIO, "aio.kicad_sch")],
                       check=True, capture_output=True)
        svgs = {f: open(os.path.join(tmp, f)).read() for f in os.listdir(tmp) if f.endswith(".svg")}
        nl = ET.parse(os.path.join(tmp, "n.xml")).getroot()

    values = {c.get("ref"): c.findtext("value") for c in nl.find("components")}
    nets_of = {}
    members = {}
    for n in nl.find("nets"):
        refs = [x.get("ref") for x in n.findall("node")]
        members[n.get("name")] = refs
        for x in n.findall("node"):
            nets_of.setdefault(x.get("ref"), {})[x.get("pin")] = (n.get("name"), x.get("pinfunction") or "")

    # path of the ESC1 instance, to read ESC1's references from the shared sheet
    root = parse(open(os.path.join(AIO, "aio.kicad_sch")).read())
    root_uuid = first(root, "uuid")[1]
    esc1 = [first(s, "uuid")[1] for s in find(root, "sheet")
            if [p[2] for p in find(s, "property") if p[1] == "Sheetname"][0] == "ESC1"][0]

    data = {"listy": [], "zdroje": ZDROJE, "stavy": STAVY}
    svg_out = {}
    for L in LISTY:
        want = f"/{root_uuid}/{esc1}" if L["id"] == "esc" else None
        boxes, sheets = sheet_boxes(os.path.join(AIO, L["soubor"]), want)
        bloky = []
        for b in L["bloky"]:
            if "rect" in b:
                x, y, w, h = b["rect"]
                box = [x, y, x + w, y + h]
            elif "ramecek" in b:   # the frame the sheet's authors drew around this ref
                r0 = boxes[b["ramecek"]]
                cx, cy = (r0[0] + r0[2]) / 2, (r0[1] + r0[3]) / 2
                inside = [r for r in boxes["__rects__"] if r[0] <= cx <= r[2] and r[1] <= cy <= r[3]]
                assert inside, (L["id"], b["id"])
                box = list(min(inside, key=lambda r: (r[2] - r[0]) * (r[3] - r[1])))
            else:
                missing = [r for r in b["refs"] if r not in boxes]
                assert not missing, (L["id"], b["id"], missing)
                box = union([boxes[r] for r in b["refs"]], 3.2)
            parts = [{"ref": r, "val": values.get(r, "")} for r in b.get("refs", [])]
            bb = dict(b, box=[round(v, 2) for v in box], dily=parts)
            bb.pop("refs", None)
            bb.pop("rect", None)
            bb.pop("ramecek", None)
            if b.get("piny"):
                rows = []
                for ball, (net, func) in nets_of["U301"].items():
                    pin = func.rsplit("_", 1)[0]
                    s = short(net)
                    if s.startswith("unconnected"):
                        rows.append([ball, pin, "", "", "nezapojeno"])
                        continue
                    others = sorted({r for r in members[net] if r != "U301"})
                    goes = (f"napájecí síť ({len(others)} dílů)" if len(others) > 12
                            else ", ".join(others) or "jen štítek")
                    rows.append([ball, pin, s, FUNCTION.get(s, ""), goes])
                key = lambda r: (r[1][:2] if r[1].startswith("P") else "~",
                                 int(re.sub(r"\D", "", r[1][2:]) or 0), r[1])
                bb["piny"] = sorted(rows, key=key)
            bloky.append(bb)
        odkazy = []
        if L["id"] == "koren":
            for name, (x0, y0, x1, y1) in sheets:
                odkazy.append({"nazev": name, "cil": ODKAZY[name], "box": [x0 - 1.5, y0 - 3, x1 + 1.5, y1 + 3]})
        svg = svgs[L["svg"]]
        svg = re.sub(r"<\?xml.*?\?>|<!DOCTYPE.*?>|<title>.*?</title>|<desc>.*?</desc>", "", svg, flags=re.S)
        svg = re.sub(r">\s+<", "><", svg)
        svg_out[L["id"]] = svg.strip()
        vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', svg).group(1).split()]
        data["listy"].append({k: L[k] for k in ("id", "nazev", "soubor", "uvod")} |
                             {"bloky": bloky, "odkazy": odkazy, "viewBox": vb})

    tpl = open(os.path.join(HERE, "sablona.html")).read()
    templates = "\n".join(f'<template id="svg-{k}">{v}</template>' for k, v in svg_out.items())
    page = (tpl.replace("/*DATA*/", "const DATA = " + json.dumps(data, ensure_ascii=False) + ";")
               .replace("<!--SVG-->", templates))
    open(out_html, "w").write(page)
    print(out_html, f"{len(page) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
