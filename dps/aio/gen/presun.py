"""Move named footprints to explicit places, and take off the copper that led to their old pads.

    nix develop ./dps -c dps/aio/gen/aktualizuj_desku.sh --python dps/aio/gen/presun.py board.kicad_pcb moves.json

moves.json: {"U8": [x, y, rot], "J303": ["+0", "+1.9", null], ...}; mm and degrees, a string with a
sign is relative to the present place, null keeps the rotation. The side never changes.
Before a part moves, every track and via of its pads' nets that touches one of its pads goes, and
then what that leaves hanging, along the net, up to a pad of another part or a zone: copper of
GND and of a net with a zone of its own (+3.3V, +5V...) only as far as the first via, which is
where such a net reaches its plane. Nothing else changes. Prints what moved and what went;
routing it again is the router's job.
"""
import json, sys
import pcbnew

MM = 1e6
b = pcbnew.LoadBoard(sys.argv[1])
moves = json.load(open(sys.argv[2]))


def val(v, now):
    if isinstance(v, str) and v[:1] in "+-":
        return now + float(v)
    return float(v)


zoned = {z.GetNetname() for z in b.Zones() if not z.GetIsRuleArea()}
gone = set()
for ref in moves:
    f = b.FindFootprintByReference(ref)
    pads = [p for p in f.Pads() if p.GetNetname()]
    # the copper touching the pads, then along the net what is left without another anchor
    todo = []
    for t in b.GetTracks():
        for p in pads:
            if t.GetNetCode() == p.GetNetCode() and t.m_Uuid.AsString() not in gone and \
                    (t.HitTest(p.GetPosition()) or any(p.HitTest(q) for q in
                     ((t.GetStart(), t.GetEnd()) if t.GetClass() != "PCB_VIA" else (t.GetPosition(),)))):
                todo.append(t)
    while todo:
        t = todo.pop()
        key = t.m_Uuid.AsString()
        if key in gone:
            continue
        gone.add(key)
        if t.GetClass() == "PCB_VIA" and t.GetNetname() in zoned:
            continue  # the way into the plane: a via of a zoned net ends the walk here
        ends = (t.GetPosition(),) if t.GetClass() == "PCB_VIA" else (t.GetStart(), t.GetEnd())
        for e in ends:
            # another part's pad holds this end: stop
            held = any(p.HitTest(e) for fp in b.GetFootprints() if fp.GetReference() not in moves
                       for p in fp.Pads() if p.GetNetCode() == t.GetNetCode())
            if held:
                continue
            for u in b.GetTracks():
                if u.GetNetCode() != t.GetNetCode() or u.m_Uuid.AsString() in gone:
                    continue
                if u.GetClass() == "PCB_VIA":
                    if u.HitTest(e) and (u.IsOnLayer(t.GetLayer()) if t.GetClass() != "PCB_VIA" else True):
                        todo.append(u)
                elif (u.GetStart() == e or u.GetEnd() == e) and \
                        (t.GetClass() == "PCB_VIA" and t.IsOnLayer(u.GetLayer()) or u.GetLayer() == t.GetLayer()):
                    todo.append(u)
    x0, y0 = f.GetPosition().x / MM, f.GetPosition().y / MM
    x, y, rot = moves[ref]
    x, y = val(x, x0), val(y, y0)
    if rot is not None:
        f.SetOrientationDegrees(float(rot))
    f.SetPosition(pcbnew.VECTOR2I(int(round(x * MM)), int(round(y * MM))))
    print(f"{ref}: ({x0:.2f}; {y0:.2f}) -> ({x:.2f}; {y:.2f}) {f.GetOrientationDegrees():.0f} deg")

removed = 0
for t in list(b.GetTracks()):
    if t.m_Uuid.AsString() in gone:
        b.Remove(t)
        removed += 1
print(f"removed {removed} tracks and vias")
pcbnew.SaveBoard(sys.argv[1], b)
