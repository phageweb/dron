"""Route the AIO's unconnected items, on a grid, with the board's own HDI vias.

    nix develop ./dps -c dps/aio/gen/aktualizuj_desku.sh --trasuj [board] [net regex | --smaz]

Takes the unconnected pairs from KiCad's DRC and routes each one, shortest first:
  layers   L1, L3, L6, L8 (L2 and L7 are the GND planes, L4 and L5 the supply planes)
  vias     microvia L1-L2 / L7-L8 on a buried via L2-L7, as on the rest of the board:
           L1-L3/L6 microvia + buried, L3-L6 buried, L8-L3/L6 buried + microvia, L1-L8 all three
  tracks   width and clearance of the net's class (aio.kicad_pro), 45 degree steps of 0.05 mm
A net with a zone on an inner layer (GND on L2/L7, +3.3V and +5V on L5, +BATT on L4...) may
instead end in a via into that zone's fill. Obstacles are the copper of other nets on every layer
a track or via uses, their zone fills included, except GND's (it refills around new copper). A via
may go through the fill of another net (it refills around the via), a track may not. USB CC1/CC2
may use L2: behind J301 there is only the +5V fill.
Before routing, every waiting ball of the BGA's outer ring and every waiting end of its escape gets
a stub 0.8 mm straight out that only its own net may use, so no track walls the ring in.
TRASUJ_PRVNI names a file of nets that go before all others (`--pretrasuj` passes the ones an
earlier pass left).
Per net, RULES set the order (crystal, USB, SD, IMU first), the layers, the cost of a via and
whether the track wants a GND plane right under it (L2 for L1 and L3, L7 for L6 and L8): a step
without one costs REF_COST times more. USB D- follows the D+ just routed, at the class gap.
Each path is pulled straight (any 0/45/90 degree shortcut that fits) before it is built.
Everything placed goes into the group "trasuj": `--smaz` takes it all off again.
A pair that finds no way is reported and left. The wrapper refills the zones before and after.
At the end the SD bus lengths are printed (all of each net's tracks, escape included).
"""
import array, heapq, json, math, os, re, subprocess, sys, tempfile
import pcbnew

PCB = sys.argv[1]
if len(sys.argv) > 2 and sys.argv[2] == "--smaz":
    b = pcbnew.LoadBoard(PCB)
    gone = 0
    for grp in list(b.Groups()):
        if grp.GetName() == "trasuj":
            for it in list(grp.GetItems()):
                b.Remove(it)
                gone += 1
            b.Remove(grp)
    pcbnew.SaveBoard(PCB, b)
    print(f"removed {gone} routed tracks and vias", flush=True)
    os._exit(0)  # the removed items crash swig's cleanup on a normal exit
ONLY = re.compile(sys.argv[2]) if len(sys.argv) > 2 else None

MM = 1e6
STEP, MARGIN = 0.05, 0.03
MICRO = (0.25, 0.10)
BURY = (0.33, 0.15)
HOLE_GAP, EDGE = 0.20, 0.20
TURN_COST, REF_COST = 2.0, 6.0  # grid steps per 45 degrees; factor for a step off the GND plane
REF = {0: 1, 2: 1, 5: 6, 7: 6}    # route layer index -> its GND plane layer index
ALL = [0, 2, 5, 7]
# per net, first match wins: (pattern, order, layers, via cost in grid steps, wants a GND plane)
RULES = [
    (r"HSE_(IN|OUT)$", 0, [0], 0, True),            # crystal: short, top only, no via
    (r"USB_D[PM]$", 1, ALL, 40, True),
    (r"USB_CC[12]$", 1, [0, 1], 10, False),         # behind J301 only the +5V fill and L2: DC, may cut the plane
    (r"SD_(CK|CMD|D[0-3])$", 2, ALL, 40, True),
    (r"IMU", 3, ALL, 40, True),
    (r"^(\+|GND$)", 0.5, ALL, 16, False),           # supplies: short and local, before the signals
    (r"", 4, ALL, 30, True),
]
PAIRS = [("USB_DP", "USB_DM")]                       # the second follows the first


def rule(net):
    for pat, order, layers, via, ref in RULES:
        if re.search(pat, net):
            return order, layers, via, ref
WINDOW = float(os.environ.get("TRASUJ_OKNO", 4.0))  # mm around a pair
NODES = int(os.environ.get("TRASUJ_UZLY", 1500000))  # search limit per pair
# nets that go before all the others (one name per line): the ones an earlier pass left
FIRST = set(open(os.environ["TRASUJ_PRVNI"]).read().split("\n")) - {""} if os.environ.get("TRASUJ_PRVNI") else set()
GREED = 1.5  # weighted A*: the pull towards the goal, against the extra cost of a step off the plane

with tempfile.TemporaryDirectory() as tmp:
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "-o", f"{tmp}/d.json", PCB],
                   check=True, capture_output=True)
    pairs = json.load(open(f"{tmp}/d.json"))["unconnected_items"]

b = pcbnew.LoadBoard(PCB)
LN = ["L1.Top", "L2.GND", "L3.Signal", "L4.BATT", "L5.Rails", "L6.Signal_5V", "L7.GND", "L8.Bottom"]
LID = [b.GetLayerID(n) for n in LN]
ROUTE = [0, 2, 5, 7]                  # indexes into LN that carry tracks
GND = b.FindNet("GND").GetNetCode()

bb = b.GetBoardEdgesBoundingBox()
X0, Y0 = bb.GetX() / MM, bb.GetY() / MM
NX, NY = int(bb.GetWidth() / MM / STEP) + 2, int(bb.GetHeight() / MM / STEP) + 2


def cell(x, y):
    return round((x - X0) / STEP), round((y - Y0) / STEP)


def xy(i, j):
    return X0 + i * STEP, Y0 + j * STEP


def segdist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    ll = dx * dx + dy * dy
    t = 0 if ll == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / ll))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


# net classes
pro = json.load(open(re.sub(r"\.kicad_pcb$", ".kicad_pro", PCB)))
CLASS = {c["name"]: (c["track_width"], c["clearance"]) for c in pro["net_settings"]["classes"]}


def klass(net):
    ni = b.FindNet(net) if isinstance(net, str) else net
    name = ni.GetNetClassName() if ni else "Default"
    return CLASS.get(name, CLASS["Default"])


net_clear = {}
for code, ni in b.GetNetsByNetcode().items():
    net_clear[code] = klass(ni)[1]

# copper of other nets, per layer index: (net, kind, data, reach, clearance)
copper = [[] for _ in LN]
holes = []  # (x, y, r)
for t in b.GetTracks():
    net = t.GetNetCode() or -1
    cl = net_clear.get(net, 0.09)
    if t.GetClass() == "PCB_VIA":
        p = t.GetPosition()
        holes.append((p.x / MM, p.y / MM, t.GetDrillValue() / MM / 2))
        for k, l in enumerate(LID):
            if t.IsOnLayer(l):
                copper[k].append((net, "c", (p.x / MM, p.y / MM), t.GetWidth(l) / MM / 2, cl))
    else:
        s, e = t.GetStart(), t.GetEnd()
        if t.GetLayer() in LID:
            copper[LID.index(t.GetLayer())].append(
                (net, "s", (s.x / MM, s.y / MM, e.x / MM, e.y / MM), t.GetWidth() / MM / 2, cl))
HOLE_CLEAR = pro["board"]["design_settings"]["rules"].get("min_hole_clearance", 0.25)
pads_of = {}
for f in b.GetFootprints():
    for p in f.Pads():
        q = p.GetPosition()
        net = p.GetNetCode() or -1  # copper without a net is in everyone's way
        cl = net_clear.get(net, 0.09)
        pads_of.setdefault(net, []).append(p)
        for k, l in enumerate(LID):
            if p.IsOnLayer(l):
                copper[k].append((net, "p", p.GetEffectivePolygon(l, pcbnew.ERROR_INSIDE), 0, cl))
        if p.HasHole():
            holes.append((q.x / MM, q.y / MM, p.GetDrillSize().x / MM / 2))
            npth = p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH
            for k in range(len(LN)):
                copper[k].append((-1 if npth else net, "c", (q.x / MM, q.y / MM), p.GetDrillSize().x / MM / 2,
                                  HOLE_CLEAR))
zone_fill = {}  # (net, layer index) -> filled polygons, for the zone targets
for z in b.Zones():
    if z.GetIsRuleArea():
        for k, l in enumerate(LID):
            if z.GetLayerSet().Contains(l):
                copper[k].append((-1, "p", z.Outline(), 0, 0))
        continue
    net = z.GetNetCode()
    for k, l in enumerate(LID):
        if not z.IsOnLayer(l) or not z.HasFilledPolysForLayer(l):
            continue
        fill = z.GetFilledPolysList(l)
        zone_fill.setdefault((net, k), []).append(fill)
        if net != GND and (k in ROUTE or k == 1):
            # "f": a via may go through it (the fill refills around), a track may not
            copper[k].append((net, "f", fill, 0, net_clear.get(net, 0.09)))

outline = pcbnew.SHAPE_POLY_SET()
b.GetBoardPolygonOutlines(outline, True)
inner = pcbnew.SHAPE_POLY_SET(outline)
inner.Inflate(-int((EDGE + 0.2) * MM), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, int(0.005 * MM))
INSIDE = array.array("b", [0]) * (NX * NY)  # 1 where copper may go: inside the outline, off the edge
for i in range(NX):
    for j in range(NY):
        x, y = xy(i, j)
        INSIDE[i * NY + j] = inner.Contains(pcbnew.VECTOR2I(int(x * MM), int(y * MM)))

hole_buckets = {}
for hx, hy, hr in holes:
    hole_buckets.setdefault((int(hx), int(hy)), []).append((hx, hy, hr))


def add_hole(x, y, r):
    hole_buckets.setdefault((int(x), int(y)), []).append((x, y, r))


def holes_near(x, y):
    for a in (int(x) - 1, int(x), int(x) + 1):
        for c in (int(y) - 1, int(y), int(y) + 1):
            yield from hole_buckets.get((a, c), ())


U301 = b.FindFootprintByReference("U301").GetPosition()
BGA = (U301.x / MM, U301.y / MM, 4.6)  # the escape owns the area under the BGA: no plane demand there


def raster(polys):
    """Cells inside any of the polygons (even-odd per polygon), by scanline over their edges."""
    m = array.array("b", [0]) * (NX * NY)
    for poly in polys:
        rows = {}
        chains = [poly.Outline(n) for n in range(poly.OutlineCount())]
        chains += [poly.Hole(n, h) for n in range(poly.OutlineCount()) for h in range(poly.HoleCount(n))]
        for ch in chains:
            pts = [(ch.CPoint(q).x / MM, ch.CPoint(q).y / MM) for q in range(ch.PointCount())]
            for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
                if y1 == y2:
                    continue
                j0 = math.ceil((min(y1, y2) - Y0) / STEP)
                j1 = math.ceil((max(y1, y2) - Y0) / STEP) - 1
                for j in range(max(0, j0), min(NY - 1, j1) + 1):
                    y = Y0 + j * STEP
                    rows.setdefault(j, []).append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
        for j, xs in rows.items():
            xs.sort()
            for xa, xb in zip(xs[::2], xs[1::2]):
                for i in range(max(0, math.ceil((xa - X0) / STEP)), min(NX - 1, int((xb - X0) / STEP)) + 1):
                    m[i * NY + j] = 1
    return m


plane_masks = {}


def has_plane(k):
    """Mask of the cells of route layer k with GND fill right under (or above) them."""
    if k not in plane_masks:
        m = raster(zone_fill.get((GND, REF[k]), []))
        bx, by, r = BGA
        for i in range(max(0, int((bx - r - X0) / STEP)), min(NX, int((bx + r - X0) / STEP) + 1)):
            for j in range(max(0, int((by - r - Y0) / STEP)), min(NY, int((by + r - Y0) / STEP) + 1)):
                m[i * NY + j] = 1
        plane_masks[k] = m
    return plane_masks[k]


def blocking(k, keep, clear, fills):
    """Grid over the board: 0 free, a net code whose copper is within reach, -1 several or outside.
    Without fills, the zone fills of other nets are left out (the grid for vias)."""
    g = array.array("i", [0]) * (NX * NY)
    for n in range(NX * NY):
        if not INSIDE[n]:
            g[n] = -1
    for net, kind, data, reach, cl in copper[k]:
        if fills or kind != "f":
            mark(g, net, kind, data, reach + max(cl, clear) + keep)
    return g


def mark(g, net, kind, data, r):
    if kind == "c":
        x0, y0, x1, y1 = data[0] - r, data[1] - r, data[0] + r, data[1] + r
    elif kind == "s":
        x0, y0 = min(data[0], data[2]) - r, min(data[1], data[3]) - r
        x1, y1 = max(data[0], data[2]) + r, max(data[1], data[3]) + r
    else:
        bx = data.BBox()
        x0, y0 = bx.GetX() / MM - r, bx.GetY() / MM - r
        x1, y1 = bx.GetRight() / MM + r, bx.GetBottom() / MM + r
        grown = pcbnew.SHAPE_POLY_SET(data)
        grown.Inflate(int(r * MM), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, int(0.005 * MM))
    i0, j0 = cell(x0, y0)
    i1, j1 = cell(x1, y1)
    for i in range(max(0, i0), min(NX - 1, i1) + 1):
        for j in range(max(0, j0), min(NY - 1, j1) + 1):
            x, y = xy(i, j)
            if kind == "c":
                hit = math.hypot(x - data[0], y - data[1]) < r
            elif kind == "s":
                hit = segdist(x, y, *data) < r
            else:
                hit = grown.Contains(pcbnew.VECTOR2I(int(x * MM), int(y * MM)))
            if hit:
                k = i * NY + j
                v = g[k]
                g[k] = net if v in (0, net) else -1


grids = {}


def grid(k, keep, clear, fills=True):
    key = (k, round(keep, 4), round(clear, 4), fills)
    if key not in grids:
        grids[key] = blocking(k, keep, clear, fills)
    return grids[key]


def claim(k, net, kind, data, reach, clear):
    copper[k].append((net, kind, data, reach, clear))
    for (gk, keep, gclear, fills), g in grids.items():
        if gk == k and (fills or kind != "f"):
            mark(g, net, kind, data, reach + max(clear, gclear) + keep)


def free(g, i, j, net):
    v = g[i * NY + j]
    return v == 0 or v == net


def stack(a, z):
    """The vias that take a track from route layer index a to z: [(top, bottom, (land, hole))]."""
    lo, hi = min(a, z), max(a, z)
    vias = [(1, 6, BURY)] if (lo, hi) != (0, 1) else []
    if lo == 0:
        vias.insert(0, (0, 1, MICRO))
    if hi == 7:
        vias.append((6, 7, MICRO))
    return vias


def stack_fits(x, y, net, vias, clear):
    i, j = cell(x, y)
    for top, bot, (land, hole) in vias:
        if any(math.hypot(x - hx, y - hy) < hole / 2 + hr + HOLE_GAP for hx, hy, hr in holes_near(x, y)):
            return False
        for k in range(top, bot + 1):
            if not free(grid(k, land / 2 + MARGIN, clear, False), i, j, net):
                return False
    return True


def plane_vias(k, pk):
    """The vias from route layer index k down or up into plane layer index pk."""
    if k == 0:
        return [(0, 1, MICRO)] + ([] if pk == 1 else [(1, 6, BURY)])
    if k == 7:
        return ([] if pk == 6 else [(1, 6, BURY)]) + [(6, 7, MICRO)]
    return [(1, 6, BURY)]


DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]


b.BuildConnectivity()
conn = b.GetConnectivity()


def item_cells(uuid):
    """Route-layer cells of an unconnected item and of all copper already connected to it, and the
    plane layers that copper already reaches (a via through them)."""
    item = b.ResolveItem(pcbnew.KIID(uuid), True) if hasattr(b, "ResolveItem") else b.GetItem(pcbnew.KIID(uuid))
    if item is None:
        return [], set(), []
    item = item.Cast() if hasattr(item, "Cast") else item
    out, planes, anchors = set(), set(), []
    for o in [item] + list(conn.GetConnectedItems(item)):
        o = o.Cast() if hasattr(o, "Cast") else o
        cls = o.GetClass()
        if cls == "PCB_VIA" or cls == "PAD":
            on = {k for k in (1, 3, 4, 6) if o.IsOnLayer(LID[k])}
            planes |= on
            anchors += [(k, o.GetPosition()) for k in on]
            p = o.GetPosition()
            out |= {(k, *cell(p.x / MM, p.y / MM)) for k in ROUTE if o.IsOnLayer(LID[k])}
        elif cls in ("PCB_TRACK", "PCB_ARC") and o.GetLayer() in LID and LID.index(o.GetLayer()) in ROUTE:
            k = LID.index(o.GetLayer())
            s, e = o.GetStart(), o.GetEnd()
            ax, ay, bx, by = s.x / MM, s.y / MM, e.x / MM, e.y / MM
            n = max(1, int(math.hypot(bx - ax, by - ay) / STEP))
            out |= {(k, *cell(ax + (bx - ax) * t / n, ay + (by - ay) * t / n)) for t in range(n + 1)}
    return sorted(out), planes, anchors


def route(net, starts, goals, width, clear, planes, here, there, layers, via_cost, ref, follow=None):
    """A* over the allowed route layers. planes: {inner layer index: fill islands} that are also a
    goal. ref: a step off the GND plane costs REF_COST. follow: {layer: cells} a step outside costs more."""
    keep = width / 2 + MARGIN
    g = {k: grid(k, keep, clear) for k in layers}
    pm = {k: has_plane(k) for k in layers} if ref else None
    starts = [s for s in starts if s[0] in layers]
    goalset = {s for s in goals if s[0] in layers}
    # the window and the pull: around the two points KiCad pairs, not the whole of both clusters
    (ai, aj), (zi, zj) = cell(*here), cell(*there)
    ci, cj = (ai + zi) / 2, (aj + zj) / 2
    span = max(abs(ai - zi), abs(aj - zj)) / 2 + WINDOW / STEP
    starts = [s for s in starts if abs(s[1] - ci) <= span and abs(s[2] - cj) <= span]

    def h(i, j):
        return GREED * math.hypot(i - zi, j - zj)

    def plane_hit(k, i, j):
        x, y = xy(i, j)
        r = BURY[0] / 2
        around = [pcbnew.VECTOR2I(int((x + dx) * MM), int((y + dy) * MM))
                  for dx, dy in ((0, 0), (r, 0), (-r, 0), (0, r), (0, -r))]
        for pk, isl in planes.items():
            vias = plane_vias(k, pk)
            if any(all(f.Contains(p) and f.Outline(n).PointInside(p) for p in around) for f, n in isl) and \
                    stack_fits(x, y, net, vias, clear):
                return vias
        return None

    heap = [(h(i, j), 0.0, k, i, j, -1) for k, i, j in starts]
    best = {(k, i, j): 0.0 for k, i, j in starts}
    prev = {}
    seen = 0
    while heap:
        _, cost, k, i, j, d = heapq.heappop(heap)
        if cost > best.get((k, i, j), 1e18):
            continue
        seen += 1
        if seen > NODES:
            return None
        node = (k, i, j)
        if node in goalset:
            return walk(prev, node), None
        if planes and (i + j) % 2 == 0:
            vias = plane_hit(k, i, j)
            if vias:
                return walk(prev, node), vias
        for nd, (di, dj) in enumerate(DIRS):
            ni, nj = i + di, j + dj
            if abs(ni - ci) > span or abs(nj - cj) > span or not (0 <= ni < NX and 0 <= nj < NY):
                continue
            if not free(g[k], ni, nj, net):
                continue
            turn = 0 if d < 0 or d == nd else TURN_COST * min((nd - d) % 8, (d - nd) % 8)
            step = math.hypot(di, dj)
            if pm and not pm[k][ni * NY + nj]:
                step *= REF_COST
            if follow is not None and (ni * NY + nj) not in follow.get(k, ()):
                step *= 1.6
            nc = cost + step + turn
            if nc < best.get((k, ni, nj), 1e18):
                best[(k, ni, nj)] = nc
                prev[(k, ni, nj)] = node
                heapq.heappush(heap, (nc + h(ni, nj), nc, k, ni, nj, nd))
        x, y = xy(i, j)
        for nk in layers:
            if nk == k:
                continue
            nc = cost + via_cost * len(stack(k, nk))
            if nc < best.get((nk, i, j), 1e18) and stack_fits(x, y, net, stack(k, nk), clear):
                best[(nk, i, j)] = nc
                prev[(nk, i, j)] = node
                heapq.heappush(heap, (nc + h(i, j), nc, nk, i, j, -1))
    return None


def walk(prev, node):
    path = [node]
    while node in prev:
        node = prev[node]
        path.append(node)
    return path[::-1]


groups = [g for g in b.Groups() if g.GetName() == "trasuj"]
group = groups[0] if groups else pcbnew.PCB_GROUP(b)
if not groups:
    group.SetName("trasuj")
    b.Add(group)
placed = {}  # net code -> [(layer index, (x, y), (x, y))] of the tracks placed in this run


def straight(a, z):
    di, dj = z[0] - a[0], z[1] - a[1]
    return di == 0 or dj == 0 or abs(di) == abs(dj)


def clear_run(k, a, z, net, g, pm):
    """Every cell of the straight run a-z is free (and on the plane, if pm)."""
    n = max(abs(z[0] - a[0]), abs(z[1] - a[1]))
    for t in range(n + 1):
        i = a[0] + (z[0] - a[0]) * t // n if n else a[0]
        j = a[1] + (z[1] - a[1]) * t // n if n else a[1]
        if not free(g, i, j, net) or (pm and not pm[i * NY + j]):
            return False
    return True


def pull(k, cells, net, width, clear, ref):
    """Shortcuts along a run of grid cells: from each kept point, the farthest point of the run
    that a straight 0/45/90 degree track reaches without hitting anything (or leaving the plane)."""
    g = grid(k, width / 2 + MARGIN, clear)
    pm = has_plane(k) if ref else None
    out, a = [cells[0]], 0
    while a < len(cells) - 1:
        z = a + 1
        for c in range(min(len(cells) - 1, a + 400), a + 1, -1):
            if straight(cells[a], cells[c]) and clear_run(k, cells[a], cells[c], net, g, pm):
                z = c
                break
        out.append(cells[z])
        a = z
    return out


def build(ni, path, end_vias, width, clear, ref):
    """Tracks and vias of a found path: one track per straight run, vias where the layer changes."""
    net = ni.GetNetCode()
    run = [path[0]]

    def flush():
        cells = [(i, j) for _, i, j in run]
        k = run[0][0]
        keep = [xy(*c) for c in pull(k, cells, net, width, clear, ref)] if len(cells) > 1 else [xy(*cells[0])]
        for a, z in zip(keep, keep[1:]):
            if a == z:
                continue
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(pcbnew.VECTOR2I(int(a[0] * MM), int(a[1] * MM)))
            t.SetEnd(pcbnew.VECTOR2I(int(z[0] * MM), int(z[1] * MM)))
            t.SetWidth(int(width * MM))
            t.SetLayer(LID[k])
            t.SetNet(ni)
            b.Add(t)
            group.AddItem(t)
            placed.setdefault(net, []).append((k, a, z))
            claim(k, net, "s", (a[0], a[1], z[0], z[1]), width / 2, clear)

    for node in path[1:]:
        if node[0] != run[-1][0]:
            flush()
            put_vias(ni, *xy(node[1], node[2]), stack(run[-1][0], node[0]), clear)
            run = [node]
        else:
            run.append(node)
    flush()
    if end_vias:
        put_vias(ni, *xy(path[-1][1], path[-1][2]), end_vias, clear)


def put_vias(ni, x, y, vias, clear):
    for top, bot, (land, hole) in vias:
        v = pcbnew.PCB_VIA(b)
        v.SetViaType(pcbnew.VIATYPE_MICROVIA if (top, bot) in ((0, 1), (6, 7)) else pcbnew.VIATYPE_BURIED)
        v.SetPosition(pcbnew.VECTOR2I(int(x * MM), int(y * MM)))
        v.SetLayerPair(LID[top], LID[bot])
        v.SetWidth(int(land * MM))
        v.SetDrill(int(hole * MM))
        v.SetNet(ni)
        b.Add(v)
        group.AddItem(v)
        add_hole(x, y, hole / 2)
        for k in range(top, bot + 1):
            claim(k, ni.GetNetCode(), "c", (x, y), land / 2, clear)


def islands(net, anchors):
    """{plane layer index: [(fill, outline index)]} of the fill islands that the anchors sit in.
    The other side cannot be in any of them already, or the pair would be connected."""
    out = {}
    for k, p in anchors:
        for fill in zone_fill.get((net, k), []):
            for n in range(fill.OutlineCount()):
                if fill.Outline(n).PointInside(p) and (fill, n) not in out.get(k, []):
                    out.setdefault(k, []).append((fill, n))
    return out


def beside(net, gap):
    """{layer: cells} at the pair's centre spacing from the tracks just placed for `net`."""
    out = {}
    for k, a, z in placed.get(net, []):
        r = gap + 0.06
        i0, j0 = cell(min(a[0], z[0]) - r, min(a[1], z[1]) - r)
        i1, j1 = cell(max(a[0], z[0]) + r, max(a[1], z[1]) + r)
        for i in range(max(0, i0), min(NX - 1, i1) + 1):
            for j in range(max(0, j0), min(NY - 1, j1) + 1):
                if abs(segdist(*xy(i, j), a[0], a[1], z[0], z[1]) - gap) <= 0.04:
                    out.setdefault(k, set()).add(i * NY + j)
    return out


# the pairs: by rule order, the first of a pair before its partner, then shortest first
todo = []
for u in pairs:
    a, z = u["items"][0], u["items"][1]
    net = re.search(r"\[(.*?)\]", a["description"]).group(1)
    if ONLY and not ONLY.search(net):
        continue
    d = math.hypot(a["pos"]["x"] - z["pos"]["x"], a["pos"]["y"] - z["pos"]["y"])
    second = any(net.endswith(q) for _, q in PAIRS)
    todo.append((net not in FIRST, rule(net)[0], second, d, net, a, z))
todo.sort(key=lambda r: r[:4])

# the BGA's ways out: a track routed along the edge of the ball array walls in the outer ring
# (PDR_ON along the top row did, 19. 10.). Every waiting ball of ring 0 and every waiting end of
# an escape gets a stub straight out from the array, which only its own net may use
EXIT = 0.8
HALF = 3.6  # centre to the outer balls


def exit_from(code, x, y):
    dx, dy = x - BGA[0], y - BGA[1]
    if max(abs(dx), abs(dy)) > HALF + 1.0:
        return
    ux, uy = ((1 if dx > 0 else -1), 0) if abs(dx) >= abs(dy) else (0, (1 if dy > 0 else -1))
    copper[0].append((code, "s", (x, y, x + ux * EXIT, y + uy * EXIT), 0.045, 0.09))


for *_, net, a, z in todo:
    items = (a, z)
    code = b.FindNet(net).GetNetCode()
    for it in items:
        o = b.ResolveItem(pcbnew.KIID(it["uuid"]), True) if hasattr(b, "ResolveItem") else \
            b.GetItem(pcbnew.KIID(it["uuid"]))
        o = o.Cast() if o is not None and hasattr(o, "Cast") else o
        if o is None:
            continue
        if o.GetClass() == "PAD" and o.GetParentFootprint().GetReference() == "U301":
            p = o.GetPosition()
            x, y = p.x / MM, p.y / MM
            if max(abs(x - BGA[0]), abs(y - BGA[1])) > HALF - 0.1:
                exit_from(code, x, y)
        elif o.GetClass() == "PCB_TRACK" and o.GetLayer() == LID[0]:
            ends = [(q.x / MM, q.y / MM) for q in (o.GetStart(), o.GetEnd())]
            x, y = max(ends, key=lambda e: max(abs(e[0] - BGA[0]), abs(e[1] - BGA[1])))
            if HALF + 0.1 < max(abs(x - BGA[0]), abs(y - BGA[1])):
                exit_from(code, x, y)

done, left = [], []
for *_, d, net, a, z in todo:
    ni = b.FindNet(net)
    code = ni.GetNetCode()
    width, clear = klass(ni)
    _, layers, via_cost, ref = rule(net)
    follow = None
    for p1, p2 in PAIRS:
        if net.endswith(p2):
            first = b.FindNet(net[: -len(p2)] + p1)
            follow = beside(first.GetNetCode(), width + clear) if first else None
    starts, _, anchors_a = item_cells(a["uuid"])
    goals, _, anchors_z = item_cells(z["uuid"])
    if not starts or not goals:
        left.append(f"{net}: {a['description']} / {z['description']}: item not found")
        continue
    pa, pz = (a["pos"]["x"], a["pos"]["y"]), (z["pos"]["x"], z["pos"]["y"])
    # a plane is a goal only in a fill island that the other side reaches already
    # (a net can have several separate fills on one layer)
    opts = (layers, via_cost, ref, follow)
    found = None
    # a wide class (supplies) necks down to the line minimum where the full width does not fit
    for w in dict.fromkeys((width, CLASS["Default"][0])):
        found = route(code, starts, goals, w, clear, islands(code, anchors_z), pa, pz, *opts) or \
            route(code, goals, starts, w, clear, islands(code, anchors_a), pz, pa, *opts)
        if found:
            width = w
            break
    if found:
        path, end_vias = found
        build(ni, path, end_vias, width, clear, ref)
        how = "into its plane" if end_vias else ""
        done.append(f"{net}: {d:.1f} mm {how}")
    else:
        left.append(f"{net}: {d:.1f} mm, no way ({a['description']} / {z['description']})")

print("\n".join(done))
print(f"-- {len(done)} routed, {len(left)} left:")
print("\n".join(left))
pcbnew.SaveBoard(PCB, b)


def path_length(net, pa, pz):
    """Length along the copper of `net` from pad pa to pad pz (Dijkstra over its tracks; a via
    joins its layers, a track end on another track's side joins it there)."""
    tracks = [t for t in b.GetTracks() if t.GetNetCode() == net and t.GetClass() == "PCB_TRACK"]
    vias = [t for t in b.GetTracks() if t.GetNetCode() == net and t.GetClass() == "PCB_VIA"]
    edges = {}

    def link(u, v, w):
        edges.setdefault(u, []).append((v, w))
        edges.setdefault(v, []).append((u, w))

    def node(l, p):
        return (str(l), round(p[0], 3), round(p[1], 3))
    ends = []
    for t in tracks:
        a, z = (t.GetStart().x / MM, t.GetStart().y / MM), (t.GetEnd().x / MM, t.GetEnd().y / MM)
        link(node(t.GetLayer(), a), node(t.GetLayer(), z), math.dist(a, z))
        ends += [(t.GetLayer(), a), (t.GetLayer(), z)]
    for l, p in ends:
        for t in tracks:
            a, z = (t.GetStart().x / MM, t.GetStart().y / MM), (t.GetEnd().x / MM, t.GetEnd().y / MM)
            if t.GetLayer() == l and p not in (a, z) and segdist(*p, *a, *z) <= t.GetWidth() / MM / 2:
                link(node(l, p), node(l, a), math.dist(p, a))
                link(node(l, p), node(l, z), math.dist(p, z))
        for v in vias:
            q = (v.GetPosition().x / MM, v.GetPosition().y / MM)
            if v.IsOnLayer(l) and math.dist(p, q) <= v.GetWidth(l) / MM / 2:
                link(node(l, p), ("via", round(q[0], 3), round(q[1], 3)), math.dist(p, q))

    def touching(pad):
        hit = [node(l, p) for l, p in ends if pad.IsOnLayer(l) and
               pad.HitTest(pcbnew.VECTOR2I(int(p[0] * MM), int(p[1] * MM)))]
        return hit + [("via", round(v.GetPosition().x / MM, 3), round(v.GetPosition().y / MM, 3))
                      for v in vias if pad.HitTest(v.GetPosition()) and
                      any(v.IsOnLayer(l) and pad.IsOnLayer(l) for l in LID)]
    src, dst = set(touching(pa)), set(touching(pz))
    dist = {n: 0.0 for n in src}
    heap = [(0.0, n) for n in src]
    while heap:
        d, n = heapq.heappop(heap)
        if n in dst:
            return d
        if d > dist.get(n, 1e18):
            continue
        for m, w in edges.get(n, []):
            if d + w < dist.get(m, 1e18):
                dist[m] = d + w
                heapq.heappush(heap, (d + w, m))
    return None


# the SD bus, from the H743's ball to the slot's pad
slot = b.FindFootprintByReference("J302")
length = {}
for p in fp.Pads() if (fp := b.FindFootprintByReference("U301")) else []:
    m = re.search(r"SD_(CK|CMD|D[0-3])$", p.GetNetname())
    if not m:
        continue
    to = [q for q in slot.Pads() if q.GetNetCode() == p.GetNetCode()]
    length[m.group(1)] = path_length(p.GetNetCode(), p, to[0]) if to else None
if length:
    print("SD lengths, ball to slot: " + ", ".join(
        f"{n} {v:.1f} mm" if v is not None else f"{n} not connected" for n, v in sorted(length.items())))
    got = [v for v in length.values() if v is not None]
    if len(got) > 1:
        print(f"SD spread {max(got) - min(got):.1f} mm")
