"""Remove the OpenAIO copper the new parts landed on.

    nix develop ./dps -c dps/aio/gen/aktualizuj_desku.sh --vycisti

Runs DRC, and deletes every track and via that DRC reports against a pad or the
keepout of a part from the new sheets (MCU, VTX): clearance, hole clearance,
short, solder mask bridge, keepout, and tracks left dangling. One round per run;
the wrapper repeats it until a round removes nothing. Zones are refilled by DRC.
Copper between kept parts stays.
What it removed is what needs routing again.
"""
import json, subprocess, sys, tempfile
import pcbnew

PCB = sys.argv[1]
NEW = ("/MCU H743/", "/VTX a LD06/")
TYPES = {"clearance", "hole_clearance", "shorting_items", "solder_mask_bridge", "items_not_allowed"}


def drc():
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["kicad-cli", "pcb", "drc", "--severity-all", "--refill-zones", "--format", "json",
                        "-o", f"{tmp}/d.json", PCB], check=True, capture_output=True)
        return json.load(open(f"{tmp}/d.json"))["violations"]


# one round per process: pcbnew does not survive loading the board a second time
b = pcbnew.LoadBoard(PCB)
new_items = set()
for f in b.GetFootprints():
    if f.GetSheetname() in NEW:
        new_items.add(str(f.m_Uuid.AsString()))
        for p in f.Pads():
            new_items.add(str(p.m_Uuid.AsString()))
        for z in f.Zones():
            new_items.add(str(z.m_Uuid.AsString()))
tracks = {str(t.m_Uuid.AsString()): t for t in b.GetTracks()}
doomed = set()
for v in drc():
    uuids = [i["uuid"] for i in v["items"]]
    if v["type"] in TYPES and any(u in new_items for u in uuids):
        doomed |= {u for u in uuids if u in tracks}
    elif v["type"] == "track_dangling":
        doomed |= {u for u in uuids if u in tracks}
# the battery current path is never cut here, whatever DRC says: it is reported instead.
# Ground stitching may go: the GND planes on L2 and L7 carry it.
KEEP = {"/CSA+", "+BATT"}
spared = {u for u in doomed if tracks[u].GetNetname() in KEEP}
for u in spared:
    t = tracks[u]
    print(f"kept {t.GetNetname()} at {pcbnew.ToMM(t.GetPosition().x):.2f}, {pcbnew.ToMM(t.GetPosition().y):.2f}")
doomed -= spared
for u in doomed:
    b.Remove(tracks[u])
if doomed:
    pcbnew.SaveBoard(PCB, b)
print(f"removed {len(doomed)} tracks and vias")
