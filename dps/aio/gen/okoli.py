"""What copper lies around a point on one layer: the first question when a connection will not route.

    nix develop ./dps -c dps/aio/gen/aktualizuj_desku.sh --okoli dps/aio/aio.kicad_pcb L1.Top 73.1 69.2 0.4

Prints every track, via and pad on the layer whose edge is closer than the radius (mm) to the point,
with its net, the gap to its edge, and for tracks and vias the group ("trasuj" = placed by the router,
"rucne" = by hand, empty = OpenAIO or the BGA escape).
"""
import math, sys
import pcbnew

b = pcbnew.LoadBoard(sys.argv[1])
L = b.GetLayerID(sys.argv[2])
x, y, R = map(float, sys.argv[3:6])
P = pcbnew.VECTOR2I(int(x * 1e6), int(y * 1e6))


def segd(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    ll = dx * dx + dy * dy
    t = 0 if ll == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / ll))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


for t in b.GetTracks():
    if not t.IsOnLayer(L):
        continue
    g = t.GetParentGroup().GetName() if t.GetParentGroup() else ""
    if t.GetClass() == "PCB_VIA":
        p = t.GetPosition()
        d = math.hypot(p.x / 1e6 - x, p.y / 1e6 - y) - t.GetWidth(L) / 2e6
        if d < R:
            print(f"via {t.GetNetname():28} at {p.x / 1e6:.3f}, {p.y / 1e6:.3f}  "
                  f"{b.GetLayerName(t.TopLayer())}-{b.GetLayerName(t.BottomLayer())}  gap {d:.3f}  [{g}]")
    else:
        s, e = t.GetStart(), t.GetEnd()
        d = segd(x, y, s.x / 1e6, s.y / 1e6, e.x / 1e6, e.y / 1e6) - t.GetWidth() / 2e6
        if d < R:
            print(f"trk {t.GetNetname():28} {s.x / 1e6:.3f}, {s.y / 1e6:.3f} -> {e.x / 1e6:.3f}, {e.y / 1e6:.3f}  "
                  f"w {t.GetWidth() / 1e6}  gap {d:.3f}  [{g}]")
for f in b.GetFootprints():
    for p in f.Pads():
        if p.IsOnLayer(L):
            sh = p.GetEffectivePolygon(L, pcbnew.ERROR_INSIDE)
            d = 0 if sh.Contains(P) else math.sqrt(sh.SquaredDistance(P)) / 1e6
            if d < R:
                print(f"pad {f.GetReference()}.{p.GetNumber()} {p.GetNetname():28} gap {d:.3f}")
