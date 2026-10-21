"""Give the H743's inner signal balls a via stack in the pad, down to the inner signal layers.

    nix develop ./dps -c dps/aio/gen/aktualizuj_desku.sh --python dps/aio/gen/fanout.py board.kicad_pcb [--smaz-l2]

Every signal ball of rings 2-4 (not GND, not a supply) gets a microvia L1-L2 and a buried via
L2-L7 at its centre, as the +3.3V balls already have: the escape then leaves on L3 or L6, and the
L2 plane under the BGA keeps only GND's own microvias. A ball that already has a buried via of
its net in the pad only gets what is missing. With --smaz-l2 the copper of these nets on L2 (the old escapes
that ran in the GND plane) goes first, with the microvias at their far ends; the nets then need
routing again from the new stacks. The stacks go into the group "fanout". Nothing is checked
here: run DRC and take off what the new stacks hit (another net's track on L3-L6).
"""
import sys
import pcbnew

MM = 1e6
MICRO, BURY = (0.25, 0.10), (0.33, 0.15)
ROWS = "ABCDEFGHJK"
b = pcbnew.LoadBoard(sys.argv[1])
L1, L2, L7 = (b.GetLayerID(n) for n in ("L1.Top", "L2.GND", "L7.GND"))
u = b.FindFootprintByReference("U301")
balls = []
for p in u.Pads():
    n = p.GetNetname()
    if not n or n == "GND" or n.startswith("+") or n.startswith("unconnected"):
        continue
    r, c = ROWS.index(p.GetNumber()[0]), int(p.GetNumber()[1:]) - 1
    if min(r, c, 9 - r, 9 - c) >= 2:
        balls.append(p)
nets = {p.GetNetCode() for p in balls}

if "--smaz-l2" in sys.argv:
    # pcbnew does not survive iterating the board after a removal: decide first, remove after
    tracks = list(b.GetTracks())
    cut = [t for t in tracks if t.GetNetCode() in nets and t.GetClass() != "PCB_VIA" and t.GetLayer() == L2]
    ids = {t.m_Uuid.AsString() for t in cut}
    l2 = [t for t in tracks if t.GetClass() != "PCB_VIA" and t.GetLayer() == L2 and t.m_Uuid.AsString() not in ids]
    # microvias L1-L2 of these nets that no L2 track touches any more: the far ends of the escapes
    for t in tracks:
        if t.GetClass() == "PCB_VIA" and t.GetNetCode() in nets and t.TopLayer() == L1 and t.BottomLayer() == L2:
            P = t.GetPosition()
            if not any(s.GetNetCode() == t.GetNetCode() and s.HitTest(P) for s in l2):
                cut.append(t)
    for t in cut:
        b.Remove(t)
    print(f"removed {len(cut)} L2 tracks and microvias")

grp = next((g for g in b.Groups() if g.GetName() == "fanout"), None)
if grp is None:
    grp = pcbnew.PCB_GROUP(b)
    grp.SetName("fanout")
    b.Add(grp)
added = []
for p in balls:
    P = p.GetPosition()
    have = [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetCode() == p.GetNetCode()
            and (t.GetPosition() - P).EuclideanNorm() < 1000]
    new = False
    for top, bot, (land, hole), kind in ((L1, L2, MICRO, pcbnew.VIATYPE_MICROVIA), (L2, L7, BURY, pcbnew.VIATYPE_BURIED)):
        if any(t.TopLayer() == top and t.BottomLayer() == bot for t in have):
            continue
        v = pcbnew.PCB_VIA(b)
        v.SetViaType(kind)
        v.SetPosition(P)
        v.SetLayerPair(top, bot)
        v.SetWidth(int(land * MM))
        v.SetDrill(int(hole * MM))
        v.SetNet(p.GetNet())
        b.Add(v)
        grp.AddItem(v)
        new = True
    if new:
        added.append(f"{p.GetNumber()} {p.GetNetname().split('/')[-1]}")
print(f"stacks in {len(added)} balls: {', '.join(added)}")
pcbnew.SaveBoard(sys.argv[1], b)
