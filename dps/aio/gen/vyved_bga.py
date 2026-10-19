"""Escape the H743's BGA (U301), as planned in NAVRH.md, chapter 7.

    nix develop ./dps -c dps/aio/gen/aktualizuj_desku.sh --vyved

Per ball, by ring (0 = the outer row of the 10 x 10 grid):
  GND                 microvia L1-L2 in the pad, into the L2 plane
  +3.3V               microvia L1-L2 + buried via L2-L7 in the pad, into the L5 zone
  signal, ring 0      nothing: it leaves on L1 when routed
  signal, ring 1      L1 track out between two ring 0 balls
  signal, ring 2-3    in BURIED: microvia + buried via in the pad, track out on L3 (else L6).
                      The others: microvia in the pad, track out on L2, microvia back up to L1
                      outside the BGA. L3 under the BGA carries OpenAIO's ESC copper, the
                      buried vias fit only at the balls in BURIED (checked 18. 10.).
Every track is found on a 0.05 mm grid around the BGA, against the copper already on that
layer (other nets only; zones are left out, they refill around new copper). A ball whose
escape finds no way is reported and left for hand routing. The tracks end outside the BGA;
the rest is routed by hand. The wrapper refills the zones afterwards. A ball that already has
copper of its net on it is left alone, so after a ball changes its net only it is done again.
"""
import heapq, math, sys
import pcbnew

PCB = sys.argv[1]
REF = "U301"
BURIED = {"C3", "C4", "C8", "D3", "F3", "D5", "H5"}

MM = 1e6
TRACK, CLEAR = 0.09, 0.09            # line standard, aio.kicad_dru
MICRO = (0.25, 0.10)                 # land, laser hole
BURY = (0.33, 0.15)
STEP, SPAN, MARGIN = 0.05, 7.0, 0.03  # grid pitch, half width of the grid, rounding margin
PITCH = 0.8
BOX = 4.1                            # a track leaves the BGA past this, from its centre
TURN = 3.0                           # cost of a 45 degree turn, in grid steps

b = pcbnew.LoadBoard(PCB)
L = {n: b.GetLayerID(n) for n in ("L1.Top", "L2.GND", "L3.Signal", "L6.Signal_5V", "L7.GND")}
L1, L2, L3, L6, L7 = L.values()
INNER = [b.GetLayerID(n) for n in ("L2.GND", "L3.Signal", "L4.BATT", "L5.Rails", "L6.Signal_5V", "L7.GND")]
fp = b.FindFootprintByReference(REF)
C = fp.GetPosition()
cx, cy = C.x / MM, C.y / MM
N = int(2 * SPAN / STEP) + 1


def cell(x, y):
    return round((x - cx + SPAN) / STEP), round((y - cy + SPAN) / STEP)


def xy(i, j):
    return cx - SPAN + i * STEP, cy - SPAN + j * STEP


def segdist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    ll = dx * dx + dy * dy
    t = 0 if ll == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / ll))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


# copper per layer, as (net, kind, data, reach) with reach the copper's own half size, mm
copper = {l: [] for l in (L1, *INNER)}


def add(layer, net, kind, data, reach):
    if layer in copper:
        copper[layer].append((net, kind, data, reach))


holes = []  # (x, y, radius, net, on-L1) of every drilled or lasered hole, mm
HOLE_GAP = 0.20  # hole to hole, line standard

for t in b.GetTracks():
    net = t.GetNetCode()
    if t.GetClass() == "PCB_VIA":
        holes.append((t.GetPosition().x / MM, t.GetPosition().y / MM, t.GetDrillValue() / MM / 2, net, t.IsOnLayer(L1)))
        for l in copper:
            if t.IsOnLayer(l):
                add(l, net, "c", (t.GetPosition().x / MM, t.GetPosition().y / MM), t.GetWidth(l) / MM / 2)
    else:
        s, e = t.GetStart(), t.GetEnd()
        add(t.GetLayer(), net, "s", (s.x / MM, s.y / MM, e.x / MM, e.y / MM), t.GetWidth() / MM / 2)
for f in b.GetFootprints():
    for p in f.Pads():
        q = p.GetPosition()
        if abs(q.x / MM - cx) > SPAN + 3 or abs(q.y / MM - cy) > SPAN + 3:
            continue
        for l in copper:
            if not p.IsOnLayer(l):
                continue
            if p.GetShape(l) == pcbnew.PAD_SHAPE_CIRCLE:
                add(l, p.GetNetCode(), "c", (q.x / MM, q.y / MM), p.GetSize(l).x / MM / 2)
            else:
                add(l, p.GetNetCode(), "p", p.GetEffectivePolygon(l, pcbnew.ERROR_INSIDE), 0)
        if p.HasHole():
            holes.append((q.x / MM, q.y / MM, p.GetDrillSize().x / MM / 2, p.GetNetCode(), True))
            for l in copper:
                add(l, p.GetNetCode(), "c", (q.x / MM, q.y / MM), p.GetDrillSize().x / MM / 2)


def blocking(layer, keep):
    """Grid of the nets whose copper is within `keep` mm of each cell: 0 none, a net code, or -1 several."""
    g = [0] * (N * N)
    for net, kind, data, reach in copper[layer]:
        r = reach + keep
        if kind == "c":
            x0, y0, x1, y1 = data[0] - r, data[1] - r, data[0] + r, data[1] + r
        elif kind == "s":
            x0, y0 = min(data[0], data[2]) - r, min(data[1], data[3]) - r
            x1, y1 = max(data[0], data[2]) + r, max(data[1], data[3]) + r
        else:
            bb = data.BBox()
            x0, y0 = bb.GetX() / MM - r, bb.GetY() / MM - r
            x1, y1 = bb.GetRight() / MM + r, bb.GetBottom() / MM + r
        i0, j0 = cell(x0, y0)
        i1, j1 = cell(x1, y1)
        for i in range(max(0, i0), min(N - 1, i1) + 1):
            for j in range(max(0, j0), min(N - 1, j1) + 1):
                x, y = xy(i, j)
                if kind == "c":
                    hit = math.hypot(x - data[0], y - data[1]) < r
                elif kind == "s":
                    hit = segdist(x, y, *data) < r
                else:
                    hit = data.Collide(pcbnew.VECTOR2I(int(x * MM), int(y * MM)), int(r * MM))
                if hit:
                    k = i * N + j
                    g[k] = net if g[k] in (0, net) else -1
    return g


def free(g, i, j, net):
    v = g[i * N + j]
    return v == 0 or v == net


TRK = TRACK / 2 + CLEAR + MARGIN       # how far a track centre keeps from other copper
VIA_MICRO = MICRO[0] / 2 + CLEAR + MARGIN
VIA_BURY = BURY[0] / 2 + CLEAR + MARGIN
grids = {}


def grid(layer, keep):
    if (layer, keep) not in grids:
        grids[(layer, keep)] = blocking(layer, keep)
    return grids[(layer, keep)]


def claim(layer, net, kind, data, reach):
    """Add new copper, and mark it in every grid already built for that layer."""
    copper[layer].append((net, kind, data, reach))
    for (l, keep), g in grids.items():
        if l != layer:
            continue
        r = reach + keep
        pts = [data[:2]] if kind == "c" else [data[:2], data[2:]]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        i0, j0 = cell(min(xs) - r, min(ys) - r)
        i1, j1 = cell(max(xs) + r, max(ys) + r)
        for i in range(max(0, i0), min(N - 1, i1) + 1):
            for j in range(max(0, j0), min(N - 1, j1) + 1):
                x, y = xy(i, j)
                d = math.hypot(x - data[0], y - data[1]) if kind == "c" else segdist(x, y, *data)
                if d < r:
                    k = i * N + j
                    g[k] = net if g[k] in (0, net) else -1


def track_fits(layer, net, a, z):
    g = grid(layer, TRK)
    n = max(1, int(math.hypot(z[0] - a[0], z[1] - a[1]) / (STEP / 2)))
    return all(free(g, *cell(a[0] + (z[0] - a[0]) * k / n, a[1] + (z[1] - a[1]) * k / n), net) for k in range(n + 1))


def via_fits(x, y, net, layers_keep):
    i, j = cell(x, y)
    hole = (MICRO if layers_keep[-1][1] == VIA_MICRO else BURY)[1] / 2
    if any(math.hypot(x - hx, y - hy) < hole + hr + HOLE_GAP for hx, hy, hr, _, _ in holes):
        return False
    return all(free(grid(l, k), i, j, net) for l, k in layers_keep)


def has_via(pad):
    """A via of the pad's own net already touching the pad."""
    q, r = pad.GetPosition(), pad.GetSize(L1).x / MM / 2
    return any(n == pad.GetNetCode() and top and math.hypot(q.x / MM - hx, q.y / MM - hy) < r + BURY[0] / 2
               for hx, hy, _, n, top in holes)


DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]


def route(layer, net, start, goal):
    """Cheapest 45-degree path on the layer's grid from `start` (mm) to a cell where goal(i, j)."""
    g = grid(layer, TRK)
    si, sj = cell(*start)
    heap = [(0.0, si, sj, -1)]
    best = {(si, sj, -1): 0.0}
    prev = {}
    while heap:
        cost, i, j, d = heapq.heappop(heap)
        if cost > best.get((i, j, d), 1e9):
            continue
        if goal(i, j):
            path = [(i, j)]
            key = (i, j, d)
            while key in prev:
                key = prev[key]
                path.append(key[:2])
            return [xy(*p) for p in reversed(path)]
        for nd, (di, dj) in enumerate(DIRS):
            ni, nj = i + di, j + dj
            if not (0 <= ni < N and 0 <= nj < N) or not free(g, ni, nj, net):
                continue
            step = math.hypot(di, dj)
            turn = 0 if d < 0 or d == nd else TURN * min((nd - d) % 8, (d - nd) % 8)
            nc = cost + step + turn
            if nc < best.get((ni, nj, nd), 1e9):
                best[(ni, nj, nd)] = nc
                prev[(ni, nj, nd)] = (i, j, d)
                heapq.heappush(heap, (nc, ni, nj, nd))
    return None


def outside(i, j):
    x, y = xy(i, j)
    return max(abs(x - cx), abs(y - cy)) >= BOX


def corners(path):
    """Keep only the points where the direction changes."""
    out = [path[0]]
    for a, m, z in zip(path, path[1:], path[2:]):
        if (round((m[0] - a[0]) / STEP), round((m[1] - a[1]) / STEP)) != \
           (round((z[0] - m[0]) / STEP), round((z[1] - m[1]) / STEP)):
            out.append(m)
    out.append(path[-1])
    return out


def put_track(layer, ni, pts):
    for a, z in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(int(a[0] * MM), int(a[1] * MM)))
        t.SetEnd(pcbnew.VECTOR2I(int(z[0] * MM), int(z[1] * MM)))
        t.SetWidth(int(TRACK * MM))
        t.SetLayer(layer)
        t.SetNet(ni)
        b.Add(t)
        claim(layer, ni.GetNetCode(), "s", (a[0], a[1], z[0], z[1]), TRACK / 2)


def put_via(x, y, ni, top, bottom):
    kind, (land, hole) = (pcbnew.VIATYPE_MICROVIA, MICRO) if (top, bottom) in ((L1, L2),) \
        else (pcbnew.VIATYPE_BURIED, BURY)
    v = pcbnew.PCB_VIA(b)
    v.SetViaType(kind)
    v.SetPosition(pcbnew.VECTOR2I(int(x * MM), int(y * MM)))
    v.SetLayerPair(top, bottom)
    v.SetWidth(int(land * MM))
    v.SetDrill(int(hole * MM))
    v.SetNet(ni)
    b.Add(v)
    holes.append((x, y, hole / 2, ni.GetNetCode(), top == L1))
    for l in copper:
        if v.IsOnLayer(l):
            claim(l, ni.GetNetCode(), "c", (x, y), land / 2)


# balls, by ring
balls = []
xs = sorted({round(p.GetPosition().x / MM, 2) for p in fp.Pads()})
ys = sorted({round(p.GetPosition().y / MM, 2) for p in fp.Pads()})
for p in fp.Pads():
    if p.GetNetname().startswith("unconnected") or not p.GetNetname():
        continue
    q = p.GetPosition()
    i, j = xs.index(round(q.x / MM, 2)), ys.index(round(q.y / MM, 2))
    balls.append((min(i, 9 - i, j, 9 - j), p.GetNumber(), p, q.x / MM, q.y / MM))
balls.sort(key=lambda r: (-r[0], r[1]))  # inner rings first: they have the fewest ways out

# keep the way straight out on L1 free for each ring 0 signal ball: nothing else may take it
for ring, num, pad, x, y in balls:
    if ring == 0 and pad.GetNetname() not in ("GND", "+3.3V"):
        dx, dy = x - cx, y - cy
        ux, uy = (math.copysign(1, dx), 0) if abs(dx) >= abs(dy) else (0, math.copysign(1, dy))
        reach = BOX + 0.6 - max(abs(dx), abs(dy))
        copper[L1].append((pad.GetNetCode(), "s", (x, y, x + ux * reach, y + uy * reach), TRACK / 2))

# a ball that has copper of its net on it is escaped already (an earlier run, or OpenAIO's vias): only the
# others get an escape, so after a ball changes its net only that ball is done again
def escaped(pad):
    code = pad.GetNetCode()
    for t in b.GetTracks():
        if t.GetNetCode() != code:
            continue
        pts = [t.GetPosition()] if t.GetClass() == "PCB_VIA" else [t.GetStart(), t.GetEnd()]
        if any(pad.HitTest(p) for p in pts) and t.IsOnLayer(L1):
            return True
    return False


balls = [r for r in balls if not escaped(r[2])]
if not balls:
    print("the BGA is escaped already, nothing done")
    sys.exit(0)

done, left = [], []
micro_keep = [(L1, VIA_MICRO), (L2, VIA_MICRO)]
stack_keep = micro_keep + [(l, VIA_BURY) for l in INNER]
for ring, num, pad, x, y in balls:
    ni, net = pad.GetNet(), pad.GetNetname()
    code = pad.GetNetCode()
    if ring == 0 and net not in ("GND", "+3.3V"):
        continue

    def spot(keep, ni=ni, code=code, x=x, y=y):
        """Where the via goes: in the pad, else in a gap between four balls with a short L1 track."""
        if via_fits(x, y, code, keep):
            return x, y, ""
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            vx, vy = x + dx * PITCH / 2, y + dy * PITCH / 2
            if via_fits(vx, vy, code, keep) and track_fits(L1, code, (x, y), (vx, vy)):
                put_track(L1, ni, [(x, y), (vx, vy)])
                return vx, vy, " (dogbone)"
        return None

    def stack(at):
        put_via(at[0], at[1], ni, L1, L2)
        put_via(at[0], at[1], ni, L2, L7)

    def via_l2(code=code, ni=ni, net=net, num=num):
        at = spot(micro_keep)
        if not at:
            return f"{num} {net}: no room for the microvia"

        def up(i, j):
            return outside(i, j) and via_fits(*xy(i, j), code, micro_keep)
        path = route(L2, code, at[:2], up)
        if not path:
            return f"{num} {net}: no way out on L2"
        put_via(at[0], at[1], ni, L1, L2)
        put_track(L2, ni, corners(path))
        put_via(*path[-1], ni, L1, L2)
        done.append(f"{num} {net}: L2{at[2]}, up at {path[-1][0]:.2f}, {path[-1][1]:.2f}")

    if net in ("GND", "+3.3V") and has_via(pad):
        done.append(f"{num} {net}: has a via of OpenAIO already")
    elif net == "GND":
        at = spot(micro_keep)
        if at:
            put_via(at[0], at[1], ni, L1, L2)
            done.append(f"{num} GND: microvia into L2{at[2]}")
        else:
            left.append(f"{num} GND: no room for the microvia")
    elif net == "+3.3V":
        at = spot(stack_keep)
        if at:
            stack(at)
            done.append(f"{num} +3.3V: microvia + buried via into L5{at[2]}")
        else:
            left.append(f"{num} +3.3V: no room for the buried via, to L1")
    elif ring == 1:
        path = route(L1, code, (x, y), outside)
        if path:
            put_track(L1, ni, corners(path))
            done.append(f"{num} {net}: L1")
        else:
            left.append(f"{num} {net}: no way out on L1")
    else:
        at = spot(stack_keep) if num in BURIED else None
        for layer in (L3, L6) if at else ():
            path = route(layer, code, at[:2], outside)
            if path:
                stack(at)
                put_track(layer, ni, corners(path))
                done.append(f"{num} {net}: buried via{at[2]}, {b.GetLayerName(layer)}")
                break
        else:
            why = via_l2()
            if why:
                left.append(why)

print("\n".join(done))
print(f"-- {len(done)} escaped, {len(left)} left for hand routing:")
print("\n".join(left))
pcbnew.SaveBoard(PCB, b)
