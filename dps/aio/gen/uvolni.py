"""Take off the copper that moved parts landed on.

    nix develop ./dps -c dps/aio/gen/aktualizuj_desku.sh --python dps/aio/gen/uvolni.py board.kicad_pcb drc.json REF...

Reads a DRC report (run with zones refilled) and deletes every track and via that it reports
against a pad of one of the named footprints (or an item of a group named @name): clearance, hole clearance, short, solder mask
bridge. Copper of the named parts' own nets that only led to their old places is presun.py's job;
this is the other nets' copper under the new places. Each net it cuts is printed: it needs
routing again. One round; repeat with a fresh DRC until it removes nothing.
"""
import json, sys
import pcbnew

b = pcbnew.LoadBoard(sys.argv[1])
refs = set(sys.argv[3:])
KINDS = {"clearance", "hole_clearance", "shorting_items", "solder_mask_bridge", "tracks_crossing"}
pads = set()
# "@group" names a group instead of a footprint: copper hit by its items goes (the fanout stacks)
for g in b.Groups():
    if "@" + g.GetName() in refs:
        pads |= {i.m_Uuid.AsString() for i in g.GetItems()}
for ref in (r for r in refs if not r.startswith("@")):
    for p in b.FindFootprintByReference(ref).Pads():
        pads.add(p.m_Uuid.AsString())
kill = set()
for v in json.load(open(sys.argv[2]))["violations"]:
    if v["type"] not in KINDS:
        continue
    ids = [i["uuid"] for i in v["items"]]
    if any(i in pads for i in ids):
        kill.update(i for i in ids if i not in pads)
cut = set()
n = 0
for t in list(b.GetTracks()):
    if t.m_Uuid.AsString() in kill:
        cut.add(t.GetNetname())
        b.Remove(t)
        n += 1
print(f"removed {n} tracks and vias: {', '.join(sorted(cut))}")
pcbnew.SaveBoard(sys.argv[1], b)
