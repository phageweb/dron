"""Rough first placement of the parts aktualizuj_desku.py left outside the board.

    nix develop ./dps -c dps/aio/gen/aktualizuj_desku.sh --rozmisti [--znovu]

Not a layout: a start that puts every new part on the board, near what it
connects to, without courtyard overlaps, so the layout begins from something.
- Anchors take the place of the OpenAIO part they replace (H743 where the
  RP2354 was, USB-C, microSD, baro, the SH-6 connector, the pads).
- Every other part goes as close as it fits to the pads it shares a net with,
  searched on a 0.1 mm grid on its preferred side first, then on the other.
- The loose pads go in blocks of three per row, as the pad field on MicoAir743-AIO.
Only parts that are still outside the board move, so it can be run again;
--znovu first puts every part of the new sheets back outside and starts over.
"""
import math, sys
import pcbnew

PCB = sys.argv[1]
mm, MM = pcbnew.ToMM, pcbnew.FromMM
CX, CY = 75.37, 60.91   # board centre (U24)

# ref: (x, y, rotation, side) -- the place of the OpenAIO part it replaces
ANCHORS = {
    # H743 where the RP2354A was; turned 180 so the USB and SDMMC balls (columns 7-10) face USB-C and the slot
    "U301": (75.90, 64.10, 180, "F"),
    "J301": (61.88, 55.51, -90, "F"),    # USB1, same footprint
    "J302": (66.81, 65.99, 90, "F"),     # Card1, same footprint
    "U302": (81.23, 67.38, -90, "B"),    # U26 BMP580
    # pads on the spots of OpenAIO's small pads
    "TP301": (69.67, 53.23, 0, "F"), "TP302": (71.67, 53.23, 0, "F"), "TP303": (73.67, 53.23, 0, "F"),
    "TP304": (75.70, 53.26, 0, "F"), "TP305": (77.67, 53.26, 0, "F"), "TP306": (79.67, 53.23, 0, "F"),

}
# preferred side for the rest; anything not listed tries the front first
SIDE = {"B": ["C301", "C302", "C303", "C304", "C305", "C306", "C307", "C308", "C309", "C310", "C311", "C312",
              "C313", "R309", "R310", "R311", "R312", "R313", "C320", "C321", "U303", "C318", "C319",
              "U201", "L201", "C201", "C202", "C203", "R201", "R202", "R203", "R204",
              "JP202", "R206", "Q301", "R319", "J304", "J305"]}
SIDE_OF = {r: s for s, refs in SIDE.items() for r in refs}
# side-entry SH1.0 connectors as on MicoAir743-AIO, on the edge stretches the motor and battery pads leave
# free, where no kept OpenAIO part is in the way (found by a search over the board).
# (x, y, side, direction the opening faces)
CONN = {"J201": (80.0, 73.5, "F", (0, 1)),    # DJI VTX: front bottom, where OpenAIO's SH-6 was
        "J303": (88.5, 65.5, "F", (1, 0)),    # GPS: front right, below motor 4
        "J305": (88.0, 65.5, "B", (1, 0)),    # UART1+UART6: back right
        "J304": (81.0, 73.5, "B", (0, 1))}    # UART4: back bottom
EDGE = {}
# the loose pads in one block, three per row, as the pad field on MicoAir743-AIO
PAD_BLOCKS = [["TP320", "TP321", "TP322", "TP323", "TP313", "TP314"],             # 5V GND BZ+ BZ- TX8 RX8
              ["TP315", "TP316", "TP317", "TP318", "TP319", "TP201", "TP202"]]    # PWM5 7 9 10 11, LD06 TX, PWM
PADS = [r for blk in PAD_BLOCKS for r in blk]
PAD_PITCH = (1.3, 1.7)
# parts tied to the H743 as a whole (its supply), not to one ball
TO_MCU = {f"C{n}" for n in range(301, 314)}
# supply capacitors of other ICs: placed right after the big parts, next to their IC (they share only power nets)
DECAP_OF = {"C201": "U201", "C203": "L201", "C317": "U302", "C318": "U303", "C319": "U303"}
POWER = {"GND", "+3.3V", "+5V", "+BATT", "+4v5", "+10V"}

b = pcbnew.LoadBoard(PCB)
outline = pcbnew.SHAPE_POLY_SET()
b.GetBoardPolygonOutlines(outline, True)
fps = {f.GetReference(): f for f in b.GetFootprints()}
if "--znovu" in sys.argv or "--ven" in sys.argv:   # every part of the new sheets back outside the board
    for f in fps.values():
        if f.GetSheetname() in ("/MCU H743/", "/VTX a LD06/"):
            f.SetPosition(pcbnew.VECTOR2I(MM(120), f.GetPosition().y))
    if "--ven" in sys.argv:
        pcbnew.SaveBoard(PCB, b)
        raise SystemExit("new parts moved outside the board")
todo = [f for f in fps.values() if mm(f.GetPosition().x) > 95]
print(f"placing {len(todo)} parts")


def side_of(f):
    return "B" if f.IsFlipped() else "F"


def put(f, x, y, rot, side):
    if side_of(f) != side:
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    f.SetOrientationDegrees(rot)
    f.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))


def box(f):
    cy = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)
    bb = cy.BBox() if cy.OutlineCount() else f.GetBoundingBox(False)
    return mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())


# obstacles per side: courtyards of the parts on the board, and U24's pads (through-hole ones on both sides),
# kept in 1 mm cells so a check looks only at its neighbourhood
class Cells:
    def __init__(self):
        self.cells = {}

    def _keys(self, r):
        for i in range(int(r[0] // 1), int(r[2] // 1) + 1):
            for j in range(int(r[1] // 1), int(r[3] // 1) + 1):
                yield i, j

    def append(self, r):
        for k in self._keys(r):
            self.cells.setdefault(k, []).append(r)

    def near(self, r):
        seen = set()
        for k in self._keys(r):
            for q in self.cells.get(k, ()):
                if id(q) not in seen:
                    seen.add(id(q))
                    yield q


obst = {"F": Cells(), "B": Cells()}


def block(f):
    """A placed part: its courtyard, and its pads (some library courtyards are smaller than the pads);
    holes block both sides."""
    obst[side_of(f)].append(box(f))
    for pad in f.Pads():
        bb = pad.GetBoundingBox()
        r = (mm(bb.GetLeft()) - 0.1, mm(bb.GetTop()) - 0.1, mm(bb.GetRight()) + 0.1, mm(bb.GetBottom()) + 0.1)
        if pad.HasHole():
            obst["F"].append(r)
            obst["B"].append(r)
        else:
            obst["B" if pad.IsOnLayer(pcbnew.B_Cu) else "F"].append(r)


for f in fps.values():
    if f in todo or f.GetReference() == "U24":
        continue
    block(f)
# copper on the outer layers that stays: pads must not land on it. That is the copper of nets no new part is on
# (inside the ESCs, the battery path). Ground stitching, the supply rails and the nets of the new parts are routed
# again around the new parts, so they are not in the way.
REROUTE = {"GND", "+3.3V", "+4v5", "+5V", "+5V_USB", "+10V", "+1.8V_GYRO"}
for f in fps.values():
    if f.GetSheetname() in ("/MCU H743/", "/VTX a LD06/"):
        REROUTE |= {p.GetNetname() for p in f.Pads()}
REROUTE -= {"/CSA+", "+BATT"}
for t in b.GetTracks():
    if t.GetNetname() in REROUTE:
        continue
    for side, layer in (("F", pcbnew.F_Cu), ("B", pcbnew.B_Cu)):
        if not t.IsOnLayer(layer):
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            w = mm(t.GetWidth(layer)) / 2 + 0.1
            pts = [t.GetPosition()]
        else:
            w = mm(t.GetWidth()) / 2 + 0.1
            a, z = t.GetStart(), t.GetEnd()
            n = max(1, int(mm((z - a).EuclideanNorm()) / 0.3))
            pts = [pcbnew.VECTOR2I(a.x + (z.x - a.x) * k // n, a.y + (z.y - a.y) * k // n) for k in range(n + 1)]
        for p in pts:
            obst[side].append((mm(p.x) - w, mm(p.y) - w, mm(p.x) + w, mm(p.y) + w))
for pad in fps["U24"].Pads():
    bb = pad.GetBoundingBox()
    r = (mm(bb.GetLeft()) - 0.2, mm(bb.GetTop()) - 0.2, mm(bb.GetRight()) + 0.2, mm(bb.GetBottom()) + 0.2)
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH or pad.IsOnLayer(pcbnew.F_Cu):
        obst["F"].append(r)
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH or pad.IsOnLayer(pcbnew.B_Cu):
        obst["B"].append(r)


def inside(r, inset=0.25):
    """The rectangle (with inset of margin) lies on the board."""
    l, t, rr, bt = r
    pts = [(l - inset, t - inset), (rr + inset, t - inset), (l - inset, bt + inset), (rr + inset, bt + inset)]
    return all(outline.Contains(pcbnew.VECTOR2I(MM(x), MM(y))) for x, y in pts)


def free(r, side, gap=0.0):
    l, t, rr, bt = r
    return all(rr + gap <= a or l - gap >= c or bt + gap <= b_ or t - gap >= d for a, b_, c, d in obst[side].near(r))


placed = set(fps) - {f.GetReference() for f in todo}
# candidate positions: a 0.1 mm grid over the board
_bb = outline.BBox()
GRID = [(mm(_bb.GetLeft()) + 0.1 * i, mm(_bb.GetTop()) + 0.1 * j)
        for i in range(int(mm(_bb.GetWidth()) / 0.1)) for j in range(int(mm(_bb.GetHeight()) / 0.1))]


def target(f):
    """Mean position of the placed pads this part shares a signal net with."""
    ref = f.GetReference()
    if ref in EDGE:
        return EDGE[ref]
    if ref in DECAP_OF and DECAP_OF[ref] in placed:
        p = fps[DECAP_OF[ref]].GetPosition()
        return mm(p.x), mm(p.y)
    if ref in TO_MCU and "U301" in placed:
        p = fps["U301"].GetPosition()
        return mm(p.x), mm(p.y)
    nets = {p.GetNetname() for p in f.Pads()} - POWER - {""}
    pts = [(mm(p.GetPosition().x), mm(p.GetPosition().y))
           for r in placed if r != "U24" for p in fps[r].Pads() if p.GetNetname() in nets]
    if not pts:   # power only: next to the nearest placed IC of the same sheet
        ics = [fps[r] for r in placed if r[0] == "U" and fps[r].GetSheetname() == f.GetSheetname()]
        if not ics:
            return CX, CY
        p = ics[0].GetPosition()
        return mm(p.x), mm(p.y)
    return sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts)


def links(f):
    nets = {p.GetNetname() for p in f.Pads()} - POWER - {""}
    return sum(1 for r in placed for p in fps[r].Pads() if p.GetNetname() in nets)


for ref, (x, y, rot, side) in ANCHORS.items():
    f = fps[ref]
    put(f, x, y, rot, side)
    block(f)
    placed.add(ref)


def opening(f):
    """Unit vector the opening of a side-entry SH connector faces: from its signal pads to its mounting pads."""
    sig = [p.GetPosition() for p in f.Pads() if p.GetNumber() != "MP"]
    mp = [p.GetPosition() for p in f.Pads() if p.GetNumber() == "MP"]
    dx = sum(p.x for p in mp) / len(mp) - sum(p.x for p in sig) / len(sig)
    dy = sum(p.y for p in mp) / len(mp) - sum(p.y for p in sig) / len(sig)
    return (round(dx / max(abs(dx), abs(dy))), round(dy / max(abs(dx), abs(dy))))


for ref, (x, y, side, d) in CONN.items():
    f = fps[ref]
    for rot in (0, 90, 180, 270):
        put(f, x, y, rot, side)
        if opening(f) == d:
            break
    else:
        raise SystemExit(f"{ref}: no rotation opens towards {d}")
    block(f)
    placed.add(ref)

rest = [f for f in todo if f.GetReference() not in ANCHORS and f.GetReference() not in CONN
        and f.GetReference() not in PADS]
failed = []


def place_one(f):
    tx, ty = target(f)
    pref = SIDE_OF.get(f.GetReference(), "F")
    for side in (pref, "B" if pref == "F" else "F"):
        # the courtyard's offsets from the origin, once per rotation
        shapes = []
        for rot in (0, 90, 180, 270):
            put(f, 0, 0, rot, side)
            shapes.append((rot, box(f)))
        for x, y in sorted(GRID, key=lambda p: (p[0] - tx) ** 2 + (p[1] - ty) ** 2):
            for rot, (l, t_, r_, bt) in shapes:
                r = (x + l, y + t_, x + r_, y + bt)
                if free(r, side) and inside(r, -1.0 if f.GetReference() in EDGE else 0.25):
                    put(f, x, y, rot, side)
                    block(f)
                    placed.add(f.GetReference())
                    return True
    put(f, 110, 40 + 8 * len(failed), 0, "F")
    failed.append(f.GetReference())
    return False


def place_pads(refs):
    """A pad block: the nearest spot to the board centre where the whole grid is free, on either side."""
    pads = [fps[r] for r in refs if fps[r] in todo]
    cols = 3
    rows = (len(pads) + cols - 1) // cols
    px, py = PAD_PITCH
    put(pads[0], 0, 0, 0, "F")
    l, t_, r_, bt = box(pads[0])
    for side in ("B", "F"):
        for x, y in sorted(GRID, key=lambda p: (p[0] - CX) ** 2 + (p[1] - CY) ** 2):
            r = (x + l, y + t_, x + r_ + px * (cols - 1), y + bt + py * (rows - 1))
            if free(r, side) and inside(r):
                for k, f in enumerate(pads):
                    put(f, x + px * (k % cols), y + py * (k // cols), 0, side)
                    block(f)
                    placed.add(f.GetReference())
                return True
    rest.extend(pads)   # no room for the block: one by one with the rest
    return False


def by_links(fs):
    return sorted(fs, key=lambda f: (-links(f), f.GetReference()))


# the H743's decoupling right under it, then the big parts and their supply capacitors, the pad blocks,
# the rest by what they tie to
for f in [f for f in rest if f.GetReference() in TO_MCU]:
    place_one(f)
rest = [f for f in rest if f.GetReference() not in TO_MCU]
big = [f for f in rest if f.GetReference()[0] in "UJYLQ"]
rest = [f for f in rest if f not in big]
while big:
    f = by_links(big).pop(0)
    big.remove(f)
    place_one(f)
for f in [f for f in rest if f.GetReference() in DECAP_OF]:
    place_one(f)
rest = [f for f in rest if f.GetReference() not in DECAP_OF]
for blk in PAD_BLOCKS:
    if not place_pads(blk):
        print("pad block", blk[0], "did not fit, its pads go one by one")
while rest:
    f = by_links(rest).pop(0)
    rest.remove(f)
    place_one(f)

if failed:
    print("no room, left outside:", " ".join(failed))
pcbnew.SaveBoard(PCB, b)
print("saved", PCB)
