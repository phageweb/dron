"""Rough first placement of the parts aktualizuj_desku.py left outside the board.

    nix develop ./dps -c dps/aio/gen/aktualizuj_desku.sh --rozmisti

Not a layout: a start that puts every new part on the board, near what it
connects to, without courtyard overlaps, so the layout begins from something.
- Anchors take the place of the OpenAIO part they replace (H743 where the
  RP2354 was, USB-C, microSD, baro, the SH-6 connector, the pads).
- Every other part goes as close as it fits to the pads it shares a net with,
  searched on a 0.2 mm grid on its preferred side first, then on the other.
Only parts that are still outside the board move, so it can be run again.
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
    "R307": (63.30, 56.23, 90, "B"),     # R3, CC1
    "R308": (63.30, 57.48, -90, "B"),    # R4, CC2
    "J302": (66.81, 65.99, 90, "F"),     # Card1, same footprint
    "U302": (81.23, 67.38, -90, "B"),    # U26 BMP580
    "J201": (80.44, 74.65, 0, "F"),      # U12 SM06B: HD VTX
    # pads on the spots of OpenAIO's small pads
    "TP301": (69.67, 53.23, 0, "F"), "TP302": (71.67, 53.23, 0, "F"), "TP303": (73.67, 53.23, 0, "F"),
    "TP304": (75.70, 53.26, 0, "F"), "TP305": (77.67, 53.26, 0, "F"), "TP306": (79.67, 53.23, 0, "F"),
    "TP307": (84.80, 52.95, 0, "F"), "TP308": (84.80, 54.95, 0, "F"), "TP309": (84.80, 56.90, 0, "F"),
    "TP310": (84.80, 58.90, 0, "F"),
    "TP311": (90.66, 61.73, 0, "F"), "TP312": (90.66, 63.73, 0, "F"), "TP313": (90.66, 65.73, 0, "F"),
    "TP314": (91.16, 61.60, 0, "B"),
    "TP315": (86.74, 61.73, 0, "F"), "TP316": (86.74, 63.73, 0, "F"), "TP317": (86.74, 65.72, 0, "F"),
    "TP318": (86.77, 67.72, 0, "F"), "TP319": (87.06, 70.17, 0, "F"),
    "TP320": (85.06, 70.17, 0, "F"), "TP321": (83.06, 70.17, 0, "F"),
    "TP322": (81.06, 70.17, 0, "F"), "TP323": (81.67, 53.23, 0, "F"),
}
# preferred side for the rest; anything not listed tries the front first
SIDE = {"B": ["C301", "C302", "C303", "C304", "C305", "C306", "C307", "C308", "C309", "C310", "C311", "C312",
              "C313", "R309", "R310", "R311", "R312", "R313", "C320", "C321", "U303", "C318", "C319",
              "U201", "L201", "C201", "C202", "C203", "R201", "R202", "R203", "R204", "R205", "U202", "C204",
              "JP201", "JP202", "R206", "Q301", "R319", "D304", "J303", "J304", "J202"]}
SIDE_OF = {r: s for s, refs in SIDE.items() for r in refs}
# parts tied to the H743 as a whole (its supply), not to one ball
TO_MCU = {f"C{n}" for n in range(301, 314)}
POWER = {"GND", "+3.3V", "+5V", "+BATT", "+4v5", "+10V"}

b = pcbnew.LoadBoard(PCB)
outline = pcbnew.SHAPE_POLY_SET()
b.GetBoardPolygonOutlines(outline, True)
fps = {f.GetReference(): f for f in b.GetFootprints()}
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


# obstacles per side: courtyards of the parts on the board, and U24's pads (through-hole ones on both sides)
obst = {"F": [], "B": []}


def block(f):
    obst[side_of(f)].append(box(f))


for f in fps.values():
    if f in todo or f.GetReference() == "U24":
        continue
    block(f)
for pad in fps["U24"].Pads():
    bb = pad.GetBoundingBox()
    r = (mm(bb.GetLeft()) - 0.2, mm(bb.GetTop()) - 0.2, mm(bb.GetRight()) + 0.2, mm(bb.GetBottom()) + 0.2)
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH or pad.IsOnLayer(pcbnew.F_Cu):
        obst["F"].append(r)
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH or pad.IsOnLayer(pcbnew.B_Cu):
        obst["B"].append(r)


def inside(r, inset=0.4):
    l, t, rr, bt = r
    pts = [(l - inset, t - inset), (rr + inset, t - inset), (l - inset, bt + inset), (rr + inset, bt + inset)]
    return all(outline.Contains(pcbnew.VECTOR2I(MM(x), MM(y))) for x, y in pts)


def free(r, side, gap=0.05):
    l, t, rr, bt = r
    return all(rr + gap <= a or l - gap >= c or bt + gap <= b_ or t - gap >= d for a, b_, c, d in obst[side])


placed = set(fps) - {f.GetReference() for f in todo}
# candidate positions: a 0.2 mm grid over the board
_bb = outline.BBox()
GRID = [(mm(_bb.GetLeft()) + 0.2 * i, mm(_bb.GetTop()) + 0.2 * j)
        for i in range(int(mm(_bb.GetWidth()) / 0.2)) for j in range(int(mm(_bb.GetHeight()) / 0.2))]


def target(f):
    """Mean position of the placed pads this part shares a signal net with."""
    ref = f.GetReference()
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

rest = [f for f in todo if f.GetReference() not in ANCHORS]
failed = []
while rest:
    # the H743's decoupling first (right under it), then big parts, then whatever is most tied to what is placed
    rest.sort(key=lambda f: (f.GetReference() not in TO_MCU, f.GetReference()[0] not in "UJYL", -links(f),
                             f.GetReference()))
    f = rest.pop(0)
    tx, ty = target(f)
    pref = SIDE_OF.get(f.GetReference(), "F")
    best = None
    for side in (pref, "B" if pref == "F" else "F"):
        # the courtyard's offsets from the origin, once per rotation
        shapes = []
        for rot in (0, 90, 180, 270):
            put(f, 0, 0, rot, side)
            shapes.append((rot, box(f)))
        for x, y in sorted(GRID, key=lambda p: (p[0] - tx) ** 2 + (p[1] - ty) ** 2):
            for rot, (l, t_, r_, bt) in shapes:
                r = (x + l, y + t_, x + r_, y + bt)
                if free(r, side) and inside(r):
                    best = (x, y, rot, side)
                    break
            if best:
                break
        if best:
            break
    if best:
        put(f, *best)
        block(f)
        placed.add(f.GetReference())
    else:
        put(f, 110, 40 + 3 * len(failed), 0, "F")
        failed.append(f.GetReference())

if failed:
    print("no room, left outside:", " ".join(failed))
pcbnew.SaveBoard(PCB, b)
print("saved", PCB)
