"""Stitch the islands of the GND fill that nothing ties to the rest of GND.

    nix develop ./dps -c dps/aio/gen/aktualizuj_desku.sh --prosij [board]

New copper cuts the GND fill on L1, L3, L6 and L8 into pieces; KiCad keeps a piece that has no
via, pad or track of GND in it as an island and reports it unconnected. Islands and what ties
them (GND vias, holes, pads and tracks) are joined in a union-find; the group with the largest
area is the main GND. Every other island gets a via into a GND plane, as the router would place
it: microvia L1-L2 or L7-L8 from the outer layers, a buried via L2-L7 from L3 and L6. The via
goes where its land fits inside the island and keeps the clearance to all copper of other nets
on the layers it touches (fills of other nets refill around it). Vias go into the group "trasuj".
"""
import math, sys
import pcbnew

PCB = sys.argv[1]
MM = 1e6
MICRO = (0.25, 0.10)
BURY = (0.33, 0.15)
CLEAR, HOLE_GAP, STEP = 0.12, 0.25, 0.05  # the widest class clearance (Analog, RF)

b = pcbnew.LoadBoard(PCB)
LN = ["L1.Top", "L2.GND", "L3.Signal", "L4.BATT", "L5.Rails", "L6.Signal_5V", "L7.GND", "L8.Bottom"]
LID = [b.GetLayerID(n) for n in LN]
GND = b.FindNet("GND").GetNetCode()


def pt(x, y):
    return pcbnew.VECTOR2I(int(x * MM), int(y * MM))


# the islands: (layer index, fill, outline index)
isl = []
for z in b.Zones():
    if z.GetIsRuleArea() or z.GetNetCode() != GND:
        continue
    for k, l in enumerate(LID):
        if z.IsOnLayer(l) and z.HasFilledPolysForLayer(l):
            f = z.GetFilledPolysList(l)
            for n in range(f.OutlineCount()):
                isl.append((k, f, n))
parent = list(range(len(isl)))


def find(a):
    while parent[a] != a:
        parent[a] = parent[parent[a]]
        a = parent[a]
    return a


def union(a, c):
    parent[find(a)] = find(c)


def inside(i, p):
    k, f, n = isl[i]
    if not f.Outline(n).PointInside(p):
        return False
    return not any(f.Hole(n, h).PointInside(p) for h in range(f.HoleCount(n)))


by_layer = {}
for i, (k, f, n) in enumerate(isl):
    by_layer.setdefault(k, []).append(i)


def islands_at(k, p):
    return [i for i in by_layer.get(k, []) if inside(i, p)]


# what ties islands: GND vias and holes across their layers, GND pads and tracks within a layer
ties = []
for t in b.GetTracks():
    if t.GetNetCode() != GND:
        continue
    if t.GetClass() == "PCB_VIA":
        ties.append([i for k, l in enumerate(LID) if t.IsOnLayer(l) for i in islands_at(k, t.GetPosition())])
    elif t.GetLayer() in LID:
        k = LID.index(t.GetLayer())
        ties.append(islands_at(k, t.GetStart()) + islands_at(k, t.GetEnd()))
for fp in b.GetFootprints():
    for p in fp.Pads():
        if p.GetNetCode() == GND:
            ties.append([i for k, l in enumerate(LID) if p.IsOnLayer(l) for i in islands_at(k, p.GetPosition())])
for tie in ties:
    for i in tie[1:]:
        union(tie[0], i)

area = {}
for i, (k, f, n) in enumerate(isl):
    area[find(i)] = area.get(find(i), 0) + abs(f.Outline(n).Area()) / MM / MM
main = max(area, key=area.get)
loose = [i for i in range(len(isl)) if find(i) != main]
print(f"{len(isl)} GND islands, {len(loose)} apart from the main GND")

# other copper, for the clearance check of a new via: per layer index (net, shape)
other = [[] for _ in LN]
holes = []
for t in b.GetTracks():
    if t.GetClass() == "PCB_VIA":
        holes.append((t.GetPosition(), t.GetDrillValue() / MM / 2))
    if t.GetNetCode() == GND:
        continue
    for k, l in enumerate(LID):
        if t.IsOnLayer(l):
            other[k].append(t.GetEffectiveShape(l))
for fp in b.GetFootprints():
    for p in fp.Pads():
        if p.HasHole():
            holes.append((p.GetPosition(), p.GetDrillSize().x / MM / 2))
        if p.GetNetCode() == GND:
            continue
        for k, l in enumerate(LID):
            if p.IsOnLayer(l):
                other[k].append(p.GetEffectiveShape(l))


def fits(x, y, top, bot, land, hole):
    p = pt(x, y)
    for h, r in holes:
        if math.hypot(h.x / MM - x, h.y / MM - y) < hole / 2 + r + HOLE_GAP:
            return False
    for k in range(top, bot + 1):
        for sh in other[k]:
            if sh.Collide(p, int((land / 2 + CLEAR) * MM)):
                return False
    return True


def stitch(i):
    k, f, n = isl[i]
    top, bot, (land, hole) = {0: (0, 1, MICRO), 7: (6, 7, MICRO)}.get(k, (1, 6, BURY))
    plane = {0: 1, 1: 6, 6: 1, 7: 6}.get(k, 1)  # a GND plane the via reaches, not the island's own
    ol = f.Outline(n)
    bb = ol.BBox()
    # the land, and its clearance to the fill's edge, inside the island
    r = land / 2 + 0.02
    best = None
    x = bb.GetX() / MM
    while x <= bb.GetRight() / MM:
        y = bb.GetY() / MM
        while y <= bb.GetBottom() / MM:
            ring = [pt(x + r * math.cos(a), y + r * math.sin(a)) for a in [q * math.pi / 4 for q in range(8)]]
            if all(inside(i, q) for q in ring + [pt(x, y)]) and \
                    any(find(j) == main for j in islands_at(plane, pt(x, y))) and \
                    fits(x, y, top, bot, land, hole):
                best = (x, y)
                break
            y += STEP
        if best:
            break
        x += STEP
    if not best:
        return None
    v = pcbnew.PCB_VIA(b)
    v.SetViaType(pcbnew.VIATYPE_MICROVIA if land == MICRO[0] else pcbnew.VIATYPE_BURIED)
    v.SetPosition(pt(*best))
    v.SetLayerPair(LID[top], LID[bot])
    v.SetWidth(int(land * MM))
    v.SetDrill(int(hole * MM))
    v.SetNet(b.FindNet("GND"))
    b.Add(v)
    group.AddItem(v)
    holes.append((pt(*best), hole / 2))
    return best


groups = [g for g in b.Groups() if g.GetName() == "trasuj"]
group = groups[0] if groups else pcbnew.PCB_GROUP(b)
if not groups:
    group.SetName("trasuj")
    b.Add(group)
for i in loose:
    k, f, n = isl[i]
    a = abs(f.Outline(n).Area()) / MM / MM
    got = stitch(i)
    where = f"via at {got[0]:.2f}, {got[1]:.2f}" if got else "no place for a via"
    print(f"{LN[k]} island of {a:.2f} mm2: {where}")
pcbnew.SaveBoard(PCB, b)
