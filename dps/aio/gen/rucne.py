"""Copper placed by hand, where the router cannot find the way and the way is known.

    nix develop ./dps -c dps/aio/gen/aktualizuj_desku.sh --rucne [board]

Everything goes into the group "rucne"; a run first takes the old group off, so it can be repeated.
  USB-C J301   the second pads of D+ (A6, B6) and D- (B7, A7). On L1 the two jumpers would cross
               and right behind the pads is the +5V fill, so each runs on L2 between two microvias
               in its pads. D- at the outer end of the pads, D+ 0.34 mm further in: clear of each
               other and of the +5V buried vias at x 64.57 and 64.97.
"""
import sys
import pcbnew

PCB = sys.argv[1]
MM = 1e6
MICRO = (0.25, 0.10)

b = pcbnew.LoadBoard(PCB)
for grp in list(b.Groups()):
    if grp.GetName() == "rucne":
        for it in list(grp.GetItems()):
            b.Remove(it)
        b.Remove(grp)
group = pcbnew.PCB_GROUP(b)
group.SetName("rucne")
b.Add(group)
L1, L2 = b.GetLayerID("L1.Top"), b.GetLayerID("L2.GND")


def pt(x, y):
    return pcbnew.VECTOR2I(int(x * MM), int(y * MM))


def via(net, x, y):
    v = pcbnew.PCB_VIA(b)
    v.SetViaType(pcbnew.VIATYPE_MICROVIA)
    v.SetPosition(pt(x, y))
    v.SetLayerPair(L1, L2)
    v.SetWidth(int(MICRO[0] * MM))
    v.SetDrill(int(MICRO[1] * MM))
    v.SetNet(b.FindNet(net))
    b.Add(v)
    group.AddItem(v)


def track(net, layer, a, z, width=0.09):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(pt(*a))
    t.SetEnd(pt(*z))
    t.SetWidth(int(width * MM))
    t.SetLayer(layer)
    t.SetNet(b.FindNet(net))
    b.Add(t)
    group.AddItem(t)


def jumper(net, x, y1, y2):
    """Microvia in a pad at (x, y1), one at (x, y2), a straight track on L2 between them."""
    via(net, x, y1)
    via(net, x, y2)
    track(net, L2, (x, y1), (x, y2))


J301 = b.FindFootprintByReference("J301")
pads = {p.GetNumber(): p for p in J301.Pads()}
y = {n: pads[n].GetPosition().y / MM for n in ("A6", "B6", "A7", "B7")}
jumper("/MCU H743/USB_DM", 63.78, y["B7"], y["A7"])
jumper("/MCU H743/USB_DP", 64.12, y["A6"], y["B6"])

pcbnew.SaveBoard(PCB, b)
print(f"placed {len(group.GetItems())} items by hand", flush=True)
