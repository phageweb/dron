"""Update aio.kicad_pcb from the schematic without the GUI, like F8 (Update PCB from Schematic).

    nix develop ./dps -c dps/aio/gen/aktualizuj_desku.sh [--dry-run]

Footprints are matched to symbols by their UUID path. The script
- removes footprints whose symbol is gone (the sheets dropped from OpenAIO),
- adds the new ones from lib.pretty or KiCad's library, outside the board on the
  right, one row per sheet,
- sets every pad's net from the netlist,
- renames the tracks, vias and zones of a net that only changed its name (the old
  name sat on the kept pads that now carry exactly one new name), and deletes those
  of nets left on nothing we keep.
Close the board in KiCad first: it would save its own copy over this one.
"""
import collections, os, subprocess, sys, tempfile
import xml.etree.ElementTree as ET
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
AIO = os.path.dirname(HERE)
PCB = f"{AIO}/aio.kicad_pcb"
DRY = "--dry-run" in sys.argv
FPDIR = os.environ["KICAD10_FOOTPRINT_DIR"]

with tempfile.TemporaryDirectory() as tmp:
    subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadxml", "-o", f"{tmp}/n.xml",
                    f"{AIO}/aio.kicad_sch"], check=True, capture_output=True)
    root = ET.parse(f"{tmp}/n.xml").getroot()



def netname(name):
    """The netlist writes '/' inside generated names; the board keeps KiCad's {slash} escape there."""
    for head in ("unconnected-(", "Net-("):
        if name.startswith(head):
            return head + name[len(head):].replace("/", "{slash}")
    return name


comps = {}
for c in root.iter("comp"):
    props = {p.get("name") for p in c.iter("property")}
    if "exclude_from_board" in props:   # OpenAIO's test points that exist only in the schematic
        continue
    path = (c.find("sheetpath").get("tstamps") + c.find("tstamps").text).rstrip("/")
    fields = {f.get("name"): f.text or "" for f in c.iter("field")}
    comps[path] = dict(ref=c.get("ref"), fp=c.findtext("footprint"), value=c.findtext("value"),
                       sheet=c.find("sheetpath").get("names"), fields=fields,
                       no_bom="exclude_from_bom" in props, dnp="dnp" in props)
pad_net = {}
for n in root.iter("net"):
    for node in n.iter("node"):
        pad_net[(node.get("ref"), node.get("pin"))] = netname(n.get("name"))
new_nets = {netname(n.get("name")) for n in root.iter("net")}

b = pcbnew.LoadBoard(PCB)
fps = {f.GetPath().AsString().rstrip("/"): f for f in b.GetFootprints()}
drop = [f for p, f in fps.items() if p not in comps]
add = [p for p in comps if p not in fps]
keep = {p: f for p, f in fps.items() if p in comps}
print(f"footprints: {len(keep)} kept, {len(drop)} removed, {len(add)} added")

# old net name -> new names, read on the kept pads before they change
moves = collections.defaultdict(set)
for f in keep.values():
    ref = comps[f.GetPath().AsString().rstrip("/")]["ref"]
    for pad in f.Pads():
        new = pad_net.get((ref, pad.GetNumber()))
        if pad.GetNetname() and new:
            moves[pad.GetNetname()].add(new)

nets = {}


def net(name):
    if name not in nets:
        item = b.FindNet(name)
        if item is None:
            item = pcbnew.NETINFO_ITEM(b, name)
            b.Add(item)
        nets[name] = item
    return nets[name]


for f in drop:
    b.Remove(f)

# new footprints, outside the board on the right, one row per sheet
x0, y = pcbnew.FromMM(100), pcbnew.FromMM(40)
gap = pcbnew.FromMM(1.5)
rows = collections.defaultdict(list)
for p in add:
    rows[comps[p]["sheet"]].append(p)
for sheet, paths in sorted(rows.items()):
    x, height = x0, 0
    for p in sorted(paths, key=lambda p: comps[p]["ref"]):
        c = comps[p]
        lib, name = c["fp"].split(":", 1)
        libdir = f"{AIO}/lib.pretty" if lib == "lib" else f"{FPDIR}/{lib}.pretty"
        f = pcbnew.FootprintLoad(libdir, name)
        assert f is not None, c["fp"]
        f.SetFPIDAsString(c["fp"])
        f.SetPath(pcbnew.KIID_PATH(p))
        f.SetReference(c["ref"])
        f.SetValue(c["value"])
        f.GetField(pcbnew.FIELD_T_DATASHEET).SetText(c["fields"].get("Datasheet", ""))
        for k, v in c["fields"].items():
            if k not in ("Reference", "Value", "Footprint", "Datasheet", "Description") and v:
                f.SetField(k, v)
        f.SetBoardOnly(False)
        f.SetExcludedFromBOM(c["no_bom"])
        f.SetDNP(c["dnp"])
        box = f.GetBoundingBox(False)
        # place by the bounding box's top-left corner, so neighbours never overlap
        f.SetPosition(pcbnew.VECTOR2I(x + f.GetPosition().x - box.GetLeft(), y + f.GetPosition().y - box.GetTop()))
        x += box.GetWidth() + gap
        height = max(height, box.GetHeight())
        b.Add(f)
        keep[p] = f
    y += height + gap

for p, f in keep.items():
    ref = comps[p]["ref"]
    f.SetExcludedFromBOM(comps[p]["no_bom"])
    f.SetDNP(comps[p]["dnp"])
    for pad in f.Pads():
        name = pad_net.get((ref, pad.GetNumber()))
        if name:
            pad.SetNet(net(name))
        else:   # pads the symbol has no pin for (mounting tabs, the slot's shield)
            pad.SetNetCode(0)

# copper on nets that are gone: renamed when unambiguous, removed when orphaned
renamed, removed, unclear = collections.Counter(), collections.Counter(), collections.Counter()
items = list(b.GetTracks()) + list(b.Zones())
for t in items:
    old = t.GetNetname()
    if not old or old in new_nets:
        continue
    to = moves.get(old, set())
    if len(to) == 1:
        t.SetNet(net(next(iter(to))))
        renamed[f"{old} -> {next(iter(to))}"] += 1
    elif not to:
        b.Remove(t)
        removed[old] += 1
    else:
        unclear[f"{old} -> {sorted(to)}"] += 1
print("renamed:", *[f"  {k}: {v}" for k, v in sorted(renamed.items())], sep="\n")
print(f"removed copper of {len(removed)} nets, {sum(removed.values())} items")
if unclear:
    print("UNCLEAR, left as is:", *[f"  {k}: {v}" for k, v in sorted(unclear.items())], sep="\n")

if not DRY:
    b.BuildConnectivity()
    pcbnew.SaveBoard(PCB, b)
    print("saved", PCB)
