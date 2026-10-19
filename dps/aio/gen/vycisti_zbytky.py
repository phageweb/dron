"""Remove OpenAIO's dead-end copper: what is left of the routes to the old RP2354 core.

    nix develop ./dps -c dps/aio/gen/aktualizuj_desku.sh --zbytky [old.kicad_pcb]

Only on nets without a zone (a via into a zone is not a dead end, and this does not look at
zones), and only copper that is also in `old.kicad_pcb` (default: the board in git HEAD), so
the BGA escape of vyved_bga.py, whose ends wait for routing, stays. What goes:
  a via that touches nothing of its net but at most one pad (a via only in a pad leads nowhere),
  copper that reaches no pad of its net at all.
OpenAIO's half routes, from a part to where the RP2354 was, stay: routing goes on from their ends.
One round per run (pcbnew does not survive iterating the board after a removal); the wrapper
repeats it until a round removes nothing.
"""
import math, re, subprocess, sys
import pcbnew

PCB = sys.argv[1]
if len(sys.argv) > 2:
    text = open(sys.argv[2]).read()
else:
    root = subprocess.run(["git", "rev-parse", "--show-toplevel"], check=True, capture_output=True,
                          text=True, cwd=sys.path[0]).stdout.strip()
    text = subprocess.run(["git", "show", "HEAD:dps/aio/aio.kicad_pcb"], check=True, capture_output=True,
                          text=True, cwd=root).stdout
# read as text: pcbnew does not survive loading a second board
old = set(re.findall(r'\n\t\((?:segment|arc|via)\b.*?\(uuid "([^"]+)"\)', text, re.S))

b = pcbnew.LoadBoard(PCB)
zoned = {z.GetNetCode() for z in b.Zones() if not z.GetIsRuleArea()}
MM = 1e6


def segdist(p, a, z):
    dx, dy = z.x - a.x, z.y - a.y
    ll = dx * dx + dy * dy
    t = 0 if ll == 0 else max(0, min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / ll))
    return math.hypot(p.x - a.x - t * dx, p.y - a.y - t * dy)


def touches_point(item, p, layer):
    """Does the copper of `item` on `layer` cover the point p?"""
    if not item.IsOnLayer(layer):
        return False
    if item.GetClass() == "PCB_VIA":
        return math.hypot(p.x - item.GetPosition().x, p.y - item.GetPosition().y) <= item.GetWidth(layer) / 2
    if item.GetClass() == "PCB_TRACK":
        return segdist(p, item.GetStart(), item.GetEnd()) <= item.GetWidth() / 2
    return item.HitTest(p)  # pad


pads = {}
for f in b.GetFootprints():
    for p in f.Pads():
        pads.setdefault(p.GetNetCode(), []).append(p)
removed = {}
b.BuildConnectivity()
conn = b.GetConnectivity()
by_net = {}
for t in b.GetTracks():
    by_net.setdefault(t.GetNetCode(), []).append(t)
doomed = []
for net, items in by_net.items():
    if net == 0 or net in zoned:
        continue
    for t in items:
        if t.m_Uuid.AsString() not in old:
            continue
        if not any(i.GetClass() == "PAD" for i in conn.GetConnectedItems(t)):
            doomed.append(t)
        elif t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            near = [o for o in items + pads.get(net, []) if o is not t and any(
                touches_point(o, p, l) for l in t.GetLayerSet().Seq() if o.IsOnLayer(l))]
            if all(o.GetClass() == "PAD" for o in near) and len(near) <= 1:
                doomed.append(t)
for t in doomed:
    k = (t.GetNetname(), t.GetClass())
    removed[k] = removed.get(k, 0) + 1
    b.Remove(t)
for (net, cls), n in sorted(removed.items()):
    print(f"{net}: {n} {'vias' if cls == 'PCB_VIA' else 'tracks'}")
print(f"removed {sum(removed.values())} dead-end tracks and vias")
if removed:
    pcbnew.SaveBoard(PCB, b)
