"""Write the schematic of dps/aio: the OpenAIO sheets we keep, the root, the VTX
sheet and the H743 sheet. Every sheet is rewritten on each run, with stable
UUIDs, so the schematic is edited here and not in KiCad.

    ./dps/check.sh                                    # clones OpenAIO into external/
    nix develop ./dps -c python3 dps/aio/gen/gen_aio.py [OUT]

The board, its rules, the project file and the footprint library are copied
from OpenAIO only when missing: they are edited in KiCad from then on."""
import copy, glob, math, os, re, shutil, sys, uuid
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sexp import parse, dump, find, first, Sym

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(HERE)
ROOTDIR = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = f"{ROOTDIR}/external/opendrone/OpenAIO/hardware"


def _stock_dir():
    """KiCad's own symbols: $KICAD_SYMBOL_DIR, or the store path the nix kicad-cli wrapper points at."""
    if os.environ.get("KICAD_SYMBOL_DIR"):
        return os.environ["KICAD_SYMBOL_DIR"]
    cli = os.path.realpath(shutil.which("kicad-cli"))
    store = re.search(r"/nix/store/[a-z0-9]+-kicad-symbols[^/:\"\s]*", open(cli, errors="ignore").read()).group(0)
    return f"{store}/share/kicad/symbols"


STOCK = _stock_dir()
PROJ = "aio"
S = Sym
YES, NO = S("yes"), S("no")
_n = 0


def uid():
    """UUID of wires, labels and texts: by order, nothing outside the schematic refers to them."""
    global _n
    _n += 1
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"dron/dps/aio/{_n}"))


def stable(key):
    """UUID of sheets, symbols and pins, by name: the board links footprints to them, so adding or
    removing a part must not shift the others."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"dron/dps/aio/id/{key}"))


def font(*extra):
    return [S("effects"), [S("font"), [S("size"), 1.27, 1.27]], *extra]


root_src = parse(open(f"{SRC}/OpenAIO.kicad_sch").read())
ROOT = first(root_src, "uuid")[1]
power_src = parse(open(f"{SRC}/fc_power.kicad_sch").read())
LIB = {s[1]: s for s in first(root_src, "lib_symbols")[1:]}
LIB.update({s[1]: s for s in first(power_src, "lib_symbols")[1:]})
_stock = {}


def stock(lib, name):
    if lib not in _stock:
        _stock[lib] = {s[1]: s for s in find(parse(open(f"{STOCK}/{lib}.kicad_sym").read()), "symbol")}
    s = copy.deepcopy(_stock[lib][name])
    s[1] = f"{lib}:{name}"
    return s


for lib, name in [("Sensor_Energy", "INA226"), ("Connector_Generic", "Conn_01x06"),
                  ("Connector_Generic", "Conn_01x04"), ("Jumper", "SolderJumper_2_Open"),
                  ("power", "PWR_FLAG"), ("Power_Management", "TPS22810DRV")]:
    LIB[f"{lib}:{name}"] = stock(lib, name)


def pins_of(sym):
    out = {}

    def walk(x):
        for e in x:
            if isinstance(e, list):
                if e[0] == "pin":
                    at = first(e, "at")
                    out[first(e, "number")[1]] = (float(at[1]), float(at[2]), float(at[3]), first(e, "name")[1])
                else:
                    walk(e)
    walk(sym)
    return out


def pin_xy(sym, x, y, rot):
    c, s = round(math.cos(math.radians(rot))), round(math.sin(math.radians(rot)))
    for num, (px, py, ang, name) in pins_of(sym).items():
        rx, ry = px * c - py * s, px * s + py * c
        yield num, name, x + rx, y - ry, (ang + rot) % 360


def outward(angle):
    a = math.radians(angle)
    return round(-math.cos(a)), round(math.sin(a))


LABEL_ANG = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}
GND_ROT = {(0, 1): 0, (1, 0): 90, (0, -1): 180, (-1, 0): 270}
RAIL_ROT = {(0, -1): 0, (-1, 0): 90, (0, 1): 180, (1, 0): 270}
RAILS = {"GND": "lib:GND", "+5V": "lib:+5V", "+3.3V": "lib:+3.3V", "+BATT": "lib:+BATT"}
# power nets made inside fc_power; a global label of the same name joins them
GLOBALS = {"+4v5", "+10V", "+1.8V_GYRO", "+5V_USB"}


class Sheet:
    def __init__(self, path):
        self.items, self.path, self.pwr, self.used = [], path, 0, set()
        self.hier = set()

    def wire(self, a, b, bus=False):
        self.items.append([S("bus" if bus else "wire"), [S("pts"), [S("xy"), *a], [S("xy"), *b]],
                           [S("stroke"), [S("width"), 0], [S("type"), S("default")]], [S("uuid"), uid()]])

    def text(self, s, x, y, size=1.27):
        self.items.append([S("text"), s, [S("exclude_from_sim"), NO], [S("at"), x, y, 0],
                           [S("effects"), [S("font"), [S("size"), size, size]], [S("justify"), S("left"), S("bottom")]],
                           [S("uuid"), uid()]])

    def label(self, net, x, y, d):
        ang = LABEL_ANG[d]
        just = {0: "left", 180: "right", 90: "left", 270: "right"}[ang]
        if net in self.hier:
            self.items.append([S("hierarchical_label"), net, [S("shape"), S("bidirectional")], [S("at"), x, y, ang],
                               font([S("justify"), S(just)]), [S("uuid"), uid()]])
        elif net in RAILS or net in GLOBALS:
            self.items.append([S("global_label"), net, [S("shape"), S("passive")], [S("at"), x, y, ang],
                               [S("fields_autoplaced"), YES], font([S("justify"), S(just)]), [S("uuid"), uid()],
                               [S("property"), "Intersheetrefs", "${INTERSHEET_REFS}", [S("at"), x, y, 0],
                                [S("hide"), YES], font([S("justify"), S(just)])]])
        else:
            self.items.append([S("label"), net, [S("at"), x, y, ang],
                               font([S("justify"), S(just), S("bottom")]), [S("uuid"), uid()]])

    def attach(self, net, px, py, d, rail_ends):
        ex, ey = px + d[0] * 2.54, py + d[1] * 2.54
        self.wire((px, py), (ex, ey), bus="{" in net)
        if net in RAILS and d[0] == 0:
            key = (net, d, ey)
            near = [x0 for (k, x0) in rail_ends if k == key and abs(x0 - ex) <= 5.08]
            if near:
                self.wire((near[0], ey), (ex, ey))
                return
            rail_ends.append((key, ex))
            self.pwr += 1
            rot = (GND_ROT if net == "GND" else RAIL_ROT)[d]
            self.place(f"#PWR{self.path[-4:]}{self.pwr:03d}", RAILS[net], net, "", "", ex, ey, rot=rot, power=True,
                       ref_at=(ex, ey), val_at=(ex, ey + d[1] * 5.08))
        else:
            self.label(net, ex, ey, d)

    def prop(self, name, value, x, y, hide=False, justify=None):
        e = [S("property"), name, value, [S("at"), x, y, 0]]
        if hide:
            e.append([S("hide"), YES])
        e += [[S("show_name"), NO], [S("do_not_autoplace"), NO],
              font([S("justify"), S(justify)]) if justify else font()]
        return e

    def place(self, ref, lib_id, value, fp, lcsc, x, y, rot=0, dnp=False, power=False, ref_at=None, val_at=None):
        sym = LIB[lib_id]
        if lib_id in ("lib:R", "lib:C") and not ref_at:
            ref_at, val_at = (x + 2.54, y - 1.27), (x + 2.54, y + 1.27)
        ref_at = ref_at or (x, y - 6.35)
        val_at = val_at or (x, y + 6.35)
        just = "left" if lib_id in ("lib:R", "lib:C") else None
        e = [S("symbol"), [S("lib_id"), lib_id], [S("at"), x, y, rot], [S("unit"), 1], [S("body_style"), 1],
             [S("exclude_from_sim"), NO], [S("in_bom"), NO if power else YES], [S("on_board"), NO if power else YES],
             [S("in_pos_files"), NO if power else YES], [S("dnp"), YES if dnp else NO],
             [S("uuid"), stable(f"{self.path}/{ref}")],
             self.prop("Reference", ref, *ref_at, hide=power, justify=just),
             self.prop("Value", value, *val_at, justify=just),
             self.prop("Footprint", fp, x, y, hide=True), self.prop("Datasheet", "", x, y, hide=True)]
        if lcsc:
            e.append(self.prop("LCSC", lcsc, x, y, hide=True))
        for num in pins_of(sym):
            e.append([S("pin"), num, [S("uuid"), stable(f"{self.path}/{ref}/{num}")]])
        e.append([S("instances"), [S("project"), PROJ, [S("path"), self.path, [S("reference"), ref], [S("unit"), 1]]]])
        self.items.append(e)

    def part(self, ref, lib_id, value, fp, lcsc, x, y, nets, rot=0, dnp=False):
        self.place(ref, lib_id, value, fp, lcsc, x, y, rot=rot, dnp=dnp, power=lib_id == "power:PWR_FLAG")
        ends = []
        pins = list(pin_xy(LIB[lib_id], x, y, rot))
        assert {p[0] for p in pins} == set(nets), (ref, sorted(nets), sorted(p[0] for p in pins))
        for num, _, sx, sy, ang in pins:
            if nets[num] == "":   # joined by placement: the pin touches another part's pin
                continue
            if nets[num] is None:
                self.items.append([S("no_connect"), [S("at"), sx, sy], [S("uuid"), uid()]])
            else:
                self.attach(nets[num], sx, sy, outward(ang), ends)

    def write(self, fname, title, page_uuid, paper="A3", comments=()):
        tb = [S("title_block"), [S("title"), title], [S("date"), "2026-10-17"], [S("rev"), "A"]]
        for i, c in enumerate(comments, 1):
            tb.append([S("comment"), i, c])
        used = set()

        def walk(x):
            for e in x:
                if isinstance(e, list):
                    if e[0] == "lib_id":
                        used.add(e[1])
                    walk(e)
        walk(self.items)
        sch = [S("kicad_sch"), [S("version"), 20260306], [S("generator"), "eeschema"],
               [S("generator_version"), "10.0"], [S("uuid"), page_uuid], [S("paper"), paper], tb,
               [S("lib_symbols"), *[LIB[k] for k in sorted(used)]], *self.items]
        if self.path == "/" + ROOT:
            sch.append([S("sheet_instances"), [S("path"), "/", [S("page"), "1"]]])
        sch.append([S("embedded_fonts"), NO])
        with open(f"{OUT}/{fname}", "w") as f:
            f.write(dump(sch) + "\n")


os.makedirs(OUT, exist_ok=True)
CERN = "Převzato z OpenAIO (CERN-OHL-S-2.0), https://github.com/OpenDrone-hw/OpenAIO"

# ------------------------------------------------------------------ copied sheets
for f in ["esc_channel.kicad_sch", "fc_power.kicad_sch", "fc_imu.kicad_sch"]:
    s = open(f"{SRC}/{f}").read().replace('(project "OpenAIO"', f'(project "{PROJ}"')
    open(f"{OUT}/{f}", "w").write(s)
shutil.copy(f"{SRC}/lib.kicad_sym", OUT)
# edited in KiCad after the first run: copied only when missing
for a, b in [("fp-lib-table", "fp-lib-table"), ("sym-lib-table", "sym-lib-table"),
             ("OpenAIO.kicad_pcb", "aio.kicad_pcb"), ("OpenAIO.kicad_dru", "aio.kicad_dru")]:
    if not os.path.exists(f"{OUT}/{b}"):
        s = open(f"{SRC}/{a}").read()
        if b.endswith("lib-table"):   # no KiCad-Library submodule: lib/ has every part used
            s = "\n".join(l for l in s.splitlines() if "KiCad-Library" not in l) + "\n"
        open(f"{OUT}/{b}", "w").write(s)
os.makedirs(f"{OUT}/lib.pretty", exist_ok=True)
for fp in glob.glob(f"{SRC}/lib.pretty/*.kicad_mod"):
    if not os.path.exists(f"{OUT}/lib.pretty/{os.path.basename(fp)}"):
        shutil.copy(fp, f"{OUT}/lib.pretty")

# ------------------------------------------------------------------ root
root = Sheet("/" + ROOT)
src_syms = {[p[2] for p in find(s, "property") if p[1] == "Reference"][0]: s for s in find(root_src, "symbol")}
src_sheets = {[p[2] for p in find(s, "property") if p[1] == "Sheetname"][0]: s for s in find(root_src, "sheet")}

ROOT_NETS = {
    "Rsense2": {"1": "CSA+", "2": "+BATT"},
    "U25": {"1": "GND", "2": "GND", "3": "+3.3V", "4": "CSA+", "5": "+BATT", "6": "ESC_CURRENT"},
    "C104": {"1": "+3.3V", "2": "GND"},
    "TP13": {"1": "ESC_CURRENT"},
    "TP20": {"1": "MOTOR1"}, "TP21": {"1": "MOTOR2"}, "TP22": {"1": "MOTOR3"}, "TP23": {"1": "MOTOR4"},
}
PHASE = {"12": "1A", "13": "1B", "14": "1C", "15": "2A", "16": "2B", "17": "2C",
         "18": "3C", "19": "3B", "20": "3A", "21": "4C", "22": "4B", "23": "4A"}
ROOT_NETS["U24"] = {n: ({"1": "CSA+", "2": "GND", "11": "GND"} | PHASE).get(n) for n in pins_of(LIB["lib:AIO_outline"])}

ROOT_PLACE = {"U24": (60.96, 101.6), "Rsense2": (40.64, 50.8), "U25": (68.58, 50.8), "C104": (104.14, 50.8),
              "TP13": (124.46, 50.8), "TP20": (304.8, 40.64), "TP21": (304.8, 81.28), "TP22": (304.8, 121.92),
              "TP23": (304.8, 162.56)}


def reloc(block, x, y):
    """Move a copied symbol or sheet, its fields and its pins, to (x, y)."""
    b = copy.deepcopy(block)
    at = first(b, "at")
    dx, dy = x - float(at[1]), y - float(at[2])

    def walk(e):
        for c in e:
            if isinstance(c, list):
                if c[0] == "at" and c is not at:
                    c[1], c[2] = float(c[1]) + dx, float(c[2]) + dy
                elif c[0] != "instances":
                    walk(c)
    walk(b)
    at[1], at[2] = x, y
    for inst in find(b, "instances"):
        for proj in find(inst, "project"):
            proj[1] = PROJ
    return b


for ref, (x, y) in ROOT_PLACE.items():
    blk = reloc(src_syms[ref], x, y)
    root.items.append(blk)
    rot = float(first(blk, "at")[3])
    ends = []
    for num, _, sx, sy, ang in pin_xy(LIB[first(blk, "lib_id")[1]], x, y, rot):
        net = ROOT_NETS[ref][num]
        if net is None:
            root.items.append([S("no_connect"), [S("at"), sx, sy], [S("uuid"), uid()]])
        else:
            root.attach(net, sx, sy, outward(ang), ends)


def sheet_pins(sh):
    for p in find(sh, "pin"):
        at = first(p, "at")
        yield p[1], float(at[1]), float(at[2]), float(at[3])


def attach_sheet(sh, nets):
    for name, x, y, ang in sheet_pins(sh):
        d = (1, 0) if ang == 0 else (-1, 0)
        net = nets.get(name, name)
        if net is None:
            root.items.append([S("no_connect"), [S("at"), x, y], [S("uuid"), uid()]])
        else:
            root.attach(net, x, y, d, [])


page = 2
for name, (x, y) in {"ESC1": (241.3, 35.56), "ESC2": (241.3, 76.2), "ESC3": (241.3, 116.84),
                     "ESC4": (241.3, 157.48), "Power": (30.48, 175.26), "IMU": (127, 208.28)}.items():
    sh = reloc(src_sheets[name], x, y)
    if name == "Power":   # the CURR pin has no label inside fc_power
        sh[:] = [e for e in sh if not (isinstance(e, list) and e[0] == "pin")]
    for inst in find(sh, "instances"):
        for proj in find(inst, "project"):
            first(proj, "path")[2:] = [[S("page"), str(page)]]
    page += 1
    root.items.append(sh)
    if name.startswith("ESC"):
        i = name[-1]
        attach_sheet(sh, {"A": f"{i}A", "B": f"{i}B", "C": f"{i}C", "dshot": f"MOTOR{i}"})
    elif name == "IMU":
        attach_sheet(sh, {"CLKIN": None, "CS": "IMU_CS", "GYRO_INT": "IMU_INT", "SPI1{SCK,MOSI,MISO}": "IMU_SPI{SCK,MOSI,MISO}"})


def new_sheet(name, fname, x, y, w, pins_left, pins_right, page):
    su = stable(f"sheet/{name}")
    h = 2.54 * (max(len(pins_left), len(pins_right)) + 2)
    sh = [S("sheet"), [S("at"), x, y], [S("size"), w, h], [S("exclude_from_sim"), NO], [S("in_bom"), YES],
          [S("on_board"), YES], [S("dnp"), NO], [S("fields_autoplaced"), YES],
          [S("stroke"), [S("width"), 0.1524], [S("type"), S("solid")]], [S("fill"), [S("color"), 0, 0, 0, 0]],
          [S("uuid"), su],
          [S("property"), "Sheetname", name, [S("at"), x, y - 0.7116, 0], font([S("justify"), S("left"), S("bottom")])],
          [S("property"), "Sheetfile", fname, [S("at"), x, y + h + 0.5884, 0], font([S("justify"), S("left"), S("top")])]]
    for i, p in enumerate(pins_left):
        sh.append([S("pin"), p, S("bidirectional"), [S("at"), x, y + 2.54 * (i + 2), 180], [S("uuid"), uid()],
                   font([S("justify"), S("left")])])
    for i, p in enumerate(pins_right):
        sh.append([S("pin"), p, S("bidirectional"), [S("at"), x + w, y + 2.54 * (i + 2), 0], [S("uuid"), uid()],
                   font([S("justify"), S("right")])])
    sh.append([S("instances"), [S("project"), PROJ, [S("path"), "/" + ROOT, [S("page"), str(page)]]]])
    root.items.append(sh)
    attach_sheet(sh, {})
    return su


VTX_IF = ["VTX_EN", "VTX_TX", "VTX_RX", "RC_RX", "LIDAR_TX", "LIDAR_PWM"]
MCU_LEFT = ["IMU_SPI{SCK,MOSI,MISO}", "IMU_CS", "IMU_INT", "ESC_CURRENT"]
MCU_RIGHT = ["MOTOR1", "MOTOR2", "MOTOR3", "MOTOR4", "VTX_EN", "VTX_TX", "VTX_RX", "RC_RX", "LIDAR_TX", "LIDAR_PWM"]
vtx_uuid = new_sheet("VTX a LD06", "vtx.kicad_sch", 236.22, 210.82, 40.64, VTX_IF, [], 8)
mcu_uuid = new_sheet("MCU H743", "mcu_h743.kicad_sch", 132.08, 101.6, 50.8, MCU_LEFT, MCU_RIGHT, 9)

for i, net in enumerate(["+BATT", "CSA+", "+4v5", "+10V", "+1.8V_GYRO"]):
    root.place(f"#FLG{i + 1:02d}", "power:PWR_FLAG", "PWR_FLAG", "", "", 30.48 + 15.24 * i, 251.46, power=True,
               ref_at=(30.48 + 15.24 * i, 248), val_at=(30.48 + 15.24 * i, 248.92))
    root.attach(net, 30.48 + 15.24 * i, 251.46, (0, 1) if net in RAILS else (1, 0), [])

root.text("Baterie a motory: U24 = obrys desky s pady (OpenAIO). Obrys 35,4 mm, díry ⌀3 na 25,5: rám Pavo20 má 26 × 26, M2 projde s vůlí 0,15 mm.", 20.32, 25.4, 1.8)
root.text("Proud všech ESC: Rsense2 0,2 mΩ + INA186A3 (100 V/V) = 20 mV/A → ESC_CURRENT do ADC H743.", 20.32, 33.02, 1.8)
root.text("Převzato beze změny: 4× esc_channel (OpenESC kanál), fc_power (10 V budiče + 5 V + 3,3 V + 1,8 V gyro), fc_imu (BMI270).\nNové: vtx.kicad_sch (spínaných 10 V pro HD VTX, LD06), mcu_h743.kicad_sch (H743, senzory, microSD, USB, konektory, LED, bzučák).", 20.32, 236.22, 1.8)
root.write("aio.kicad_sch", "AIO H743 pro Pavo20 Pro", ROOT, comments=[CERN, "Licence: CERN-OHL-S-2.0"])

# ------------------------------------------------------------------ VTX sheet
v = Sheet(f"/{ROOT}/{vtx_uuid}")
v.hier = set(VTX_IF)
R0201, C0201 = "lib:R_0201_0603Metric", "lib:C_0201_0603Metric"
# VTX switched on the +10V rail of fc_power, as OpenAIO feeds its VTX connector from it [Z1], through a load switch
# (a second buck did not fit). TPS22810DRV: 2.7-18 V, 3 A, 79 mOhm at 12 V; thermal pad to GND as on TI's EVM.
# CT 4.7 nF: ~0.8 ms rise at 10 V (datasheet table 2), inrush into ~70 uF of VTX input ~0.9 A. QOD on VOUT
# empties the VTX's capacitors when it is switched off.
v.part("C201", "lib:C", "1uF 25V", "lib:C_0402_1005Metric", "", 50.8, 50.8, {"1": "+10V", "2": "GND"})
v.part("U201", "Power_Management:TPS22810DRV", "TPS22810DRVR", "lib:WSON-6-1EP_2x2mm_P0.65mm_EP1x1.6mm", "", 88.9, 50.8,
       {"1": "+10V_VTX", "2": "+10V_VTX", "3": "CT_VTX", "4": "GND", "5": "EN_VTX", "6": "+10V", "7": "GND"})
v.part("C202", "lib:C", "4.7nF", C0201, "", 114.3, 50.8, {"1": "CT_VTX", "2": "GND"})
v.part("C203", "lib:C", "22uF", "lib:C_0603_1608Metric", "C2762594", 165.1, 50.8, {"1": "+10V_VTX", "2": "GND"})
v.part("R203", "lib:R", "1k", R0201, "", 50.8, 81.28, {"1": "VTX_EN", "2": "EN_VTX"})
v.part("R204", "lib:R", "100k", R0201, "C270364", 63.5, 81.28, {"1": "EN_VTX", "2": "GND"})
v.part("J201", "Connector_Generic:Conn_01x06", "HD VTX",
       "Connector_JST:JST_SH_SM06B-SRSS-TB_1x06-1MP_P1.00mm_Horizontal", "C160405", 203.2, 116.84,
       {"1": "+10V_VTX", "2": "GND", "3": "VTX_TX", "4": "VTX_RX", "5": "GND", "6": "VTX_SBUS"})
# LD06 on pads as on MicoAir (no room for the ZH1.5 connector): its 5V and GND go to TP320/TP321
v.part("TP201", "lib:TestPoint", "LD06 TX", "lib:Pad_1.0x1.4mm", "", 203.2, 162.56, {"1": "LIDAR_TX"})
v.part("TP202", "lib:TestPoint", "LD06 PWM", "lib:Pad_1.0x1.4mm", "", 215.9, 162.56, {"1": "LIDAR_PWM"})
v.part("R206", "lib:R", "0R", R0201, "", 231.14, 162.56, {"1": "LIDAR_PWM", "2": "GND"})
# J201 pin 6 (SBUS from a DJI unit) and the XR1 Nano's TX both want the receiver's RX (UART5, SERIAL6): open by default
v.part("JP202", "Jumper:SolderJumper_2_Open", "SBUS z DJI", "Jumper:SolderJumper-2_P1.3mm_Open_Pad1.0x1.5mm", "",
       238.76, 132.08, {"1": "VTX_SBUS", "2": "RC_RX"})
v.text("Spínaných 10 V pro HD VTX: spínač TPS22810 na +10V z fc_power (U3, LMR51430 3 A),\nze které OpenAIO napájí VTX i budiče ESC. Spíná se jen VTX, +10V pro budiče zůstává.\nDimenzováno na DJI O3/O4 (12–16 W ≈ 1,6 A, spínač 3 A). CT 4,7 nF: náběh ~0,8 ms.", 38.1, 20.32, 1.8)
v.text("EN: výchozí vypnuto (R204), MCU spíná přes VTX_EN\n(RELAYn_PIN, RELAYn_DEFAULT 1).", 99.06, 83.82)
v.text("Bez měření proudu VTX, jako MicoAir: INA226 a bočník se na desku nevešly (18. 10.).", 182.88, 20.32, 1.8)
v.text("HD VTX, pinout DJI jako MicoAir: 1 napájení, 2 GND, 3 TX2, 4 RX2, 5 GND, 6 SBUS z DJI. Pro Lite+ redukce 6P → 4P.\nJP202 rozpojená: RX přijímače (UART5, SERIAL6) patří přijímači na J305. Zapájet jen pro DJI s SBUS a bez přijímače.", 177.8, 101.6, 1.8)
v.text("LD06/D500 na pady jako u MicoAiru (ZH1.5 se nevešel): TP201 Tx lidaru, TP202 PWM, 5V a GND na TP320/TP321 (rozběh 540 mA).\nPWM uzemněn přes R206; bez něj ho řídí MCU přes LIDAR_PWM.", 177.8, 152.4, 1.8)
v.write("vtx.kicad_sch", "VTX a LD06", uid(), comments=["Napájení VTX z +10V jako OpenAIO (CERN-OHL-S-2.0)", "Licence: CERN-OHL-S-2.0"])

# ------------------------------------------------------------------ MCU sheet
# Pin map: hwdef MicoAir743v2 (same MCU, ArduPilot target exists). Balls: KiCad
# stock symbol STM32H743VIHx. Supply and decoupling: ST AN4938 rev 6, sec. 2.2.
rp_src = parse(open(f"{SRC}/fc_rp2350a.kicad_sch").read())
LIB.update({s[1]: s for s in first(rp_src, "lib_symbols")[1:] if s[1] in ("lib:TYPE-C16PQTWT", "lib:DMN1150UFB-7B")})
imu_src = parse(open(f"{SRC}/fc_imu.kicad_sch").read())
LIB.update({s[1]: s for s in first(imu_src, "lib_symbols")[1:] if s[1] == "lib:LSM6DSV16XTR"})
bb_src = parse(open(f"{SRC}/fc_blackbox.kicad_sch").read())
LIB.update({s[1]: s for s in first(bb_src, "lib_symbols")[1:] if s[1] == "lib:TF-021B-H265"})
for _lib, _name in [("Sensor_Pressure", "BMP280"), ("Device", "Crystal_GND24"),
                     ("Transistor_FET", "Q_NMOS_GSD"), ("Device", "D")]:
    LIB[f"{_lib}:{_name}"] = stock(_lib, _name)
_h7 = {s[1]: s for s in find(parse(open(f"{STOCK}/MCU_ST_STM32H7.kicad_sym").read()), "symbol")}
_mcu = copy.deepcopy(_h7["STM32H743V_G-I_Hx"])
_der = {p[1]: p for p in find(_h7["STM32H743VIHx"], "property")}


def _ren(x):
    for e in x:
        if isinstance(e, list):
            if e[0] == "symbol" and isinstance(e[1], str) and e[1].startswith("STM32H743V_G-I_Hx_"):
                e[1] = "STM32H743VIHx" + e[1][len("STM32H743V_G-I_Hx"):]
            _ren(e)


_ren(_mcu)
_mcu[1] = "MCU_ST_STM32H7:STM32H743VIHx"
_mcu[:] = [_der.get(e[1], e) if isinstance(e, list) and e and e[0] == "property" else e for e in _mcu]
LIB["MCU_ST_STM32H7:STM32H743VIHx"] = _mcu

m = Sheet(f"/{ROOT}/{mcu_uuid}")
m.hier = set(MCU_LEFT + MCU_RIGHT)
H743 = {
    # supply (AN4938 2.2): every VDD-type pin on +3.3V, VCAP1+VCAP2 joined
    "D2": "+3.3V", "F5": "+3.3V", "K1": "+3.3V", "F4": "+3.3V", "F6": "+3.3V", "B2": "+3.3V", "H1": "+3.3V",
    "C2": "GND", "E4": "GND", "E5": "GND", "E6": "GND", "J1": "GND", "G1": "GND",
    "E7": "VCAP", "F8": "VCAP", "F7": "PDR_ON", "D5": "BOOT0", "E1": "NRST",
    "C1": "HSE_IN", "D1": "HSE_OUT",
    # hwdef MicoAir743v2, except three UARTs (19. 10.): our board's edge is MicoAir's mirrored, so GPS and the
    # receiver take the UARTs whose balls face the connectors (bottom edge); SERIAL_ORDER keeps MicoAir's numbers
    "G7": "MOTOR1", "K6": "MOTOR2", "H6": "MOTOR3", "K5": "MOTOR4",            # PE14 PE13 PE11 PE9, TIM1
    # both IMUs sit above the BGA (19. 10.): BMI270 on SPI1 (free, MicoAir's OSD) instead of SPI3, whose
    # balls face down; the ICM's SCK, CS and DRDY on balls of the top rows
    "H3": "IMU_SPI.SCK", "K3": "IMU_SPI.MOSI", "J3": "IMU_SPI.MISO",           # PA5 PA7 PA6, SPI1
    "G3": "IMU_CS", "G4": "IMU_INT",                                          # PA4 PC4, BMI270
    "J8": "IMU2_SCK", "E2": "IMU2_MISO", "F3": "IMU2_MOSI",                   # PB13 PC2_C PC3_C, SPI2
    "K8": "IMU2_CS", "J6": "IMU2_INT",                                       # PB12 PE12, ICM-42688-P
    "F1": "VBAT_SENSE", "F2": "ESC_CURRENT",                                  # PC0 PC1, ADC1
    "K7": "SDA", "J7": "SCL",                                                 # PB11 PB10, I2C2 = bus 0
    "A4": "EXT_SDA", "B4": "EXT_SCL",                                         # PB9 PB8, I2C1 = bus 1
    "C9": "UART1_TX", "D10": "UART1_RX",                                      # PA9 PA10, SERIAL1
    "J2": "VTX_TX", "K2": "VTX_RX",                                           # PA2 PA3, USART2 = SERIAL2
    "C4": "GPS_TX", "D4": "GPS_RX",                                           # PE1 PE0, UART8 = SERIAL3
    "G2": "FLOW_TX", "H2": "FLOW_RX",                                         # PA0 PA1, UART4 = SERIAL4
    "K9": "UART3_TX", "J9": "LIDAR_TX",                                       # PD8 PD9, USART3 = SERIAL5
    "B5": "RC_TX", "C5": "RC_RX",                                             # PB6 PB5, UART5 = SERIAL6
    "J5": "UART7_TX", "H5": "UART7_RX",                                       # PE8 PE7, SERIAL8
    "C10": "USB_DM", "B10": "USB_DP",                                         # PA11 PA12, OTG_FS
    "A10": "SWDIO", "A9": "SWCLK",                                            # PA13 PA14
    "C8": "SD_CK", "B7": "SD_CMD", "F9": "SD_D0", "E9": "SD_D1", "B9": "SD_D2", "B8": "SD_D3",  # SDMMC1
    "B3": "LED_R", "A3": "LED_G", "C3": "LED_B", "G8": "BUZZER",              # PE3 PE2 PE4 PD15
    "J4": "LIDAR_PWM", "J10": "VTX_EN",                                       # PB0 = PWM6, PD13 = PWM8
    "K4": "PWM5", "K10": "PWM7", "D3": "PWM9", "E3": "PWM10", "H8": "PWM11",  # PB1 PD12 PE5 PE6 PD14
}
_balls = pins_of(LIB["MCU_ST_STM32H7:STM32H743VIHx"])
H743.update({b: None for b in _balls if b not in H743})
R0201, C0201, C0402 = "lib:R_0201_0603Metric", "lib:C_0201_0603Metric", "lib:C_0402_1005Metric"
TP = "lib:Pad_1.0x1.4mm"
m.part("U301", "MCU_ST_STM32H7:STM32H743VIHx", "STM32H743VIH6", "Package_BGA:TFBGA-100_8x8mm_Layout10x10_P0.8mm",
       "", 200.66, 139.7, H743)
cap = [("C301", "100n", C0201, "C76939", "+3.3V"), ("C302", "100n", C0201, "C76939", "+3.3V"),
       ("C303", "100n", C0201, "C76939", "+3.3V"), ("C304", "4.7uF", C0402, "C23733", "+3.3V"),
       ("C305", "4.7uF", C0402, "C23733", "+3.3V"), ("C306", "2.2uF", C0402, "", "VCAP"),
       ("C307", "2.2uF", C0402, "", "VCAP"), ("C308", "100n", C0201, "C76939", "+3.3V"),
       ("C309", "1uF", C0402, "", "+3.3V"), ("C310", "100n", C0201, "C76939", "+3.3V"),
       ("C311", "1uF", C0402, "", "+3.3V"), ("C312", "100n", C0201, "C76939", "+3.3V"),
       ("C313", "100n", C0201, "C76939", "NRST")]
for i, (ref, val, fp, lcsc, net) in enumerate(cap):
    m.part(ref, "lib:C", val, fp, lcsc, 30.48 + 12.7 * i, 40.64, {"1": net, "2": "GND"})
m.part("R301", "lib:R", "10k", R0201, "", 30.48, 236.22, {"1": "+3.3V", "2": "PDR_ON"})
m.part("R302", "lib:R", "10k", R0201, "", 43.18, 236.22, {"1": "BOOT0", "2": "GND"})
m.part("R303", "lib:R", "100k", R0201, "C270364", 63.5, 236.22, {"1": "+BATT", "2": "VBAT_SENSE"})
m.part("R304", "lib:R", "10k", R0201, "", 76.2, 236.22, {"1": "VBAT_SENSE", "2": "GND"})
m.part("C314", "lib:C", "100n", C0201, "C76939", 88.9, 236.22, {"1": "VBAT_SENSE", "2": "GND"})
m.part("R305", "lib:R", "2.2k", R0201, "", 109.22, 236.22, {"1": "+3.3V", "2": "SDA"})
m.part("R306", "lib:R", "2.2k", R0201, "", 121.92, 236.22, {"1": "+3.3V", "2": "SCL"})
m.part("J301", "lib:TYPE-C16PQTWT", "TYPE-C 16P QTWT", "lib:USB-TYPE-C-SMD_TYPE-C-16P-QTWT", "C5187472",
       317.5, 66.04, {"A4": "+5V_USB", "A9": "+5V_USB", "0": "GND", "A1": "GND", "A12": "GND",
                      "A5": "USB_CC1", "B5": "USB_CC2", "A6": "USB_DP", "B6": "USB_DP",
                      "A7": "USB_DM", "B7": "USB_DM", "A8": None, "B8": None})
m.part("R307", "lib:R", "5.1k", R0201, "C270344", 350.52, 99.06, {"1": "USB_CC1", "2": "GND"})
m.part("R308", "lib:R", "5.1k", R0201, "C270344", 363.22, 99.06, {"1": "USB_CC2", "2": "GND"})
# HSE: YXC X32258MOB4SI, 8 MHz, CL 12 pF, ESR 180 ohm. Load caps per AN4938/AN2867:
# CL = C/2 + Cstray, ~5 pF stray -> C = 14 pF, nearest E12 15 pF.
m.part("Y301", "Device:Crystal_GND24", "8MHz 12pF X32258MOB4SI", "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
       "C2682775", 101.6, 71.12, {"1": "HSE_IN", "3": "HSE_OUT", "2": "GND", "4": "GND"})
m.part("C322", "lib:C", "15pF C0G", C0402, "", 88.9, 86.36, {"1": "HSE_IN", "2": "GND"})
m.part("C323", "lib:C", "15pF C0G", C0402, "", 114.3, 86.36, {"1": "HSE_OUT", "2": "GND"})
# baro: SPL06-001 and DPS310 share the BMP280 package and pinout; I2C, CSB and SDO high -> 0x77
m.part("U302", "Sensor_Pressure:BMP280", "SPL06-001 / DPS310", "Package_LGA:Bosch_LGA-8_2x2.5mm_P0.65mm_ClockwisePinNumbering",
       "C2684428", 360.68, 200.66, {"1": "GND", "7": "GND", "8": "+3.3V", "6": "+3.3V", "2": "+3.3V", "5": "+3.3V",
                                    "3": "SDA", "4": "SCL"})
# ICM-42688-P on SPI2 (MicoAir has a BMI088 there; its 4.5 x 3 mm did not fit the board). The LGA-14 2.5 x 3 mm
# footprint and symbol are OpenAIO's "universal IMU" (BMI270, LSM6, TDK), same pins as on the IMU sheet.
# Datasheet DS-000347 table 9: RESV 2, 3, 10, 11 NC or GND, RESV 7 GND, FSYNC (9) to GND when unused;
# table 10: VDD 100 nF + 2.2 uF, VDDIO 10 nF.
m.part("U303", "lib:LSM6DSV16XTR", "ICM-42688-P", "lib:LGA-14_L3.0-W2.5-P0.50-BR", "", 289.56, 200.66,
       {"1": "IMU2_MISO", "2": "GND", "3": "GND", "4": "IMU2_INT", "5": "+3.3V", "6": "GND", "7": "GND",
        "8": "+3.3V", "9": "GND", "10": "GND", "11": "GND", "12": "IMU2_CS", "13": "IMU2_SCK", "14": "IMU2_MOSI"})
# microSD on SDMMC1 (MicoAir); slot from OpenAIO Card1
m.part("J302", "lib:TF-021B-H265", "TF-021B-H265", "lib:TF-SMD_TF-021B-H265", "C498185", 271.78, 116.84,
       {"1": "SD_D2", "2": "SD_D3", "3": "SD_CMD", "4": "+3.3V", "5": "SD_CK", "6": "GND", "7": "SD_D0",
        "8": "SD_D1", "9": "GND", "10": "GND"})
for i, (ref, val, fp, lcsc, a, b) in enumerate([
        ("R309", "47k", R0201, "", "+3.3V", "SD_CMD"), ("R310", "47k", R0201, "", "+3.3V", "SD_D0"),
        ("R311", "47k", R0201, "", "+3.3V", "SD_D1"), ("R312", "47k", R0201, "", "+3.3V", "SD_D2"),
        ("R313", "47k", R0201, "", "+3.3V", "SD_D3"), ("C320", "100n", C0201, "C76939", "+3.3V", "GND"),
        ("C321", "4.7uF", C0402, "C23733", "+3.3V", "GND"), ("C318", "100n", C0201, "C76939", "+3.3V", "GND"),
        ("C319", "2.2uF", C0201, "", "+3.3V", "GND"), ("C324", "10n", C0201, "", "+3.3V", "GND"),
        ("C317", "100n", C0201, "C76939", "+3.3V", "GND")]):
    m.part(ref, "lib:R" if ref[0] == "R" else "lib:C", val, fp, lcsc, 147.32 + 12.7 * i, 236.22, {"1": a, "2": b})
for i, (ref, net) in enumerate([("TP301", "BOOT0"), ("TP302", "+3.3V"), ("TP303", "SWDIO"), ("TP304", "SWCLK"),
                                ("TP305", "NRST"), ("TP306", "GND")]):
    m.part(ref, "lib:TestPoint", net, TP, "", 304.8 + 12.7 * i, 152.4, {"1": net})
m.text("""MCU STM32H743VIH6 (TFBGA-100), jako MicoAir. Piny podle hwdef MicoAir743v2, kuličky podle symbolu KiCad.
Napájení podle ST AN4938 kap. 2.2: 100 nF na každý VDD + 4,7 µF; VDDLDO 4,7 µF; VCAP1+VCAP2 spojené, 2× 2,2 µF;
VDDA 100 nF + 1 µF; VDD33USB z VDD, 100 nF + 1 µF; VBAT na VDD + 100 nF; PDR_ON 10k na VDD; BOOT0 10k na GND.
Plný popis a zdroje: dps/aio/NAVRH.md""", 30.48, 22.86, 1.8)
def fields_right(sheet, ref, x, y, rot):
    """Reference and Value of a symbol placed at `rot` 90 or 270, to its right and reading horizontally."""
    sym = next(e for e in sheet.items if e[0] == "symbol" and
               any(p[1] == "Reference" and p[2] == ref for p in find(e, "property")))
    for p in find(sym, "property"):
        if p[1] in ("Reference", "Value"):
            p[3][1:] = [x + 2.54, y + (-1.27 if p[1] == "Reference" else 1.27), 360 - rot]
            first(p, "effects").append([S("justify"), S("left")])


# RGB LED: ArduPilot drives GPIO_LED_RGB active low (HAL_GPIO_LED_ON 0), so anodes on 3.3 V.
# XINGLIGHT XL-1005 0402; G and B as in OpenAIO, blue with its 75R. ~3-5 mA each, pin limit 20 mA.
for i, (ref, col, val, lcsc, r, rv, net) in enumerate([
        ("D301", "R", "XL-1005SURC", "C965790", "R316", "330R", "LED_R"),
        ("D302", "G", "XL-1005UGC", "C965793", "R317", "150R", "LED_G"),
        ("D303", "B", "XL-1005UBC", "C22355736", "R318", "75R", "LED_B")]):
    x = 30.48 + 17.78 * i
    m.part(r, "lib:R", rv, R0201, "", x, 180.34, {"1": "+3.3V", "2": ""})
    m.part(ref, "lib:LED", val, "lib:LED_0402_1005Metric", lcsc, x, 187.96, {"2": "", "1": net}, rot=90)
    fields_right(m, ref, x, 187.96, 90)
# buzzer: BUZZ_ON_LVL 1 (active high), external 5 V active buzzer on pads, low side switch.
# AP1606 (OpenAIO's Q1): N-MOSFET, Vgs(th) 1.2 V, 700 mA, DFN 1.0 x 0.6 mm; a SOT-23 did not fit on the board.
m.part("Q301", "lib:DMN1150UFB-7B", "AP1606", "lib:DFN-3L_L1.0-W0.6-P0.65-BR", "C2849580", 96.52, 198.12,
       {"1": "BUZZER", "2": "GND", "3": "BZ-"})
m.part("R319", "lib:R", "100k", R0201, "C270364", 81.28, 205.74, {"1": "BUZZER", "2": "GND"})
m.part("TP322", "lib:TestPoint", "BZ+", TP, "", 127, 182.88, {"1": "+5V"})
m.part("TP323", "lib:TestPoint", "BZ-", TP, "", 139.7, 182.88, {"1": "BZ-"})
m.text("""RGB LED aktivní v nule (ArduPilot GPIO_LED_RGB), ~3–5 mA.
Bzučák: aktivní 5 V (piezo) na padech BZ+/BZ−, BUZZ_ON_LVL 1, bez diody jako MicoAir.
R319 drží Q301 vypnutý, dokud MCU nenastaví PD15.""", 30.48, 167.64, 1.27)
m.text("""Y301: CL 12 pF, C = 2 × (CL − Cstray) = 2 × (12 − 5) = 14 → 15 pF [AN4938, AN2867].
gm_crit = 4·ESR·(2πf)²·(C0+CL)² ≈ 0,5 mA/V (ESR 180 Ω, C0 ≤ 5 pF) < Gmcritmax 1,5 mA/V [DS12110].""", 60.96, 106.68, 1.27)
m.text("""U302: SPL06-001 a DPS310 mají stejné pouzdro i piny (jako BMP280).
CSB a SDO na 3,3 V → I2C, adresa 0x77. Osadit podle skladu JLC.""", 330.2, 177.8, 1.27)
m.text("""U303 ICM-42688-P na SPI2 (MicoAir tu má BMI088, 4,5 × 3 mm se nevešel).
Pouzdro LGA-14 2,5 × 3 jako BMI270. INT1 = data ready, RESV a FSYNC na GND.
VDD 100 nF + 2,2 µF (C318, C319), VDDIO 10 nF (C324) podle DS-000347.""", 266.7, 177.8, 1.27)
m.text("""J302 microSD na SDMMC1, pull-upy 47k na CMD a D0–D3 (SD: 10–100k).""", 251.46, 96.52, 1.27)
# the IMU SPI bus: hierarchical bus label; members join the IMU_SPI.* labels on the MCU pins by name
m.items.append([S("hierarchical_label"), "IMU_SPI{SCK,MOSI,MISO}", [S("shape"), S("bidirectional")],
                [S("at"), 243.84, 167.64, 180], font([S("justify"), S("right")]), [S("uuid"), uid()]])
m.wire((243.84, 167.64), (251.46, 167.64), bus=True)
m.items.append([S("label"), "IMU_SPI{SCK,MOSI,MISO}", [S("at"), 246.38, 167.64, 0],
                font([S("justify"), S("left"), S("bottom")]), [S("uuid"), uid()]])
# peripherals: connectors as on MicoAir743-AIO (ArduPilot hwdef/MicoAir743-AIO, ports picture), SH1.0 side entry.
# MicoAir's tables list pin 6 first: its README says pin 1 of the DJI connector is 12 V, the last row.
m.part("J303", "Connector_Generic:Conn_01x06", "GPS (SERIAL3+I2C1)", "Connector_JST:JST_SH_SM06B-SRSS-TB_1x06-1MP_P1.00mm_Horizontal",
       "C160405", 50.8, 266.7, {"1": "GND", "2": "+5V", "3": "GPS_TX", "4": "GPS_RX", "5": "EXT_SCL", "6": "EXT_SDA"})
m.part("R314", "lib:R", "4.7k", R0201, "", 76.2, 266.7, {"1": "+3.3V", "2": "EXT_SCL"})
m.part("R315", "lib:R", "4.7k", R0201, "", 88.9, 266.7, {"1": "+3.3V", "2": "EXT_SDA"})
m.part("J304", "Connector_Generic:Conn_01x04", "UART4 (MTF-02P)", "Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal",
       "", 119.38, 266.7, {"1": "GND", "2": "+5V", "3": "FLOW_TX", "4": "FLOW_RX"})
m.part("J305", "Connector_Generic:Conn_01x06", "SERIAL1+SERIAL6 (RX, telemetrie)",
       "Connector_JST:JST_SH_SM06B-SRSS-TB_1x06-1MP_P1.00mm_Horizontal", "C160405", 297.18, 266.7,
       {"1": "GND", "2": "+5V", "3": "UART1_TX", "4": "UART1_RX", "5": "RC_TX", "6": "RC_RX"})
# pads: UART7 (Bluetooth or spare), free PWM, 5V and GND (also for the LD06)
for i, (ref, val, net) in enumerate([
        ("TP313", "UART7 TX", "UART7_TX"), ("TP314", "UART7 RX", "UART7_RX"), ("TP315", "PWM5", "PWM5"),
        ("TP316", "PWM7", "PWM7"), ("TP317", "PWM9", "PWM9"), ("TP318", "PWM10", "PWM10"), ("TP319", "PWM11", "PWM11"),
        ("TP320", "5V", "+5V"), ("TP321", "GND", "GND")]):
    m.part(ref, "lib:TestPoint", val, TP, "", 147.32 + 15.24 * i, 264.16, {"1": net})
m.text("""Konektory jako MicoAir743-AIO (SH1.0, boční), pin 1 = GND:
J303 GPS: 1 GND, 2 5V, 3 TX, 4 RX (UART8 = SERIAL3), 5 SCL, 6 SDA (kompas na I2C1, pull-upy R314/R315).
J304 UART4 (MTF-02P): 1 GND, 2 5V, 3 TX4, 4 RX4.  J305: 1 GND, 2 5V, 3 TX1, 4 RX1 (USART1 = SERIAL1), 5 TX, 6 RX (přijímač, UART5 = SERIAL6).
GPS a přijímač jsou na UARTech, jejichž kuličky míří ke konektorům (obvod desky je zrcadlo MicoAiru); čísla SERIALn jako MicoAir.
Kabely od MicoAiru tak sedí. Pin 1 před prvním zapnutím ověřit multimetrem proti kabelu.""", 30.48, 287.02, 1.27)
m.place("#FLG301", "power:PWR_FLAG", "PWR_FLAG", "", "", 317.5, 30.48, power=True, ref_at=(317.5, 27), val_at=(317.5, 27.94))
m.attach("+5V_USB", 317.5, 30.48, (1, 0), [])   # USB VBUS comes in from the connector
# +5V is made in fc_power; ERC wants a flag on a sheet where the rail has other pins too
m.place("#FLG302", "power:PWR_FLAG", "PWR_FLAG", "", "", 332.74, 30.48, power=True, ref_at=(332.74, 27), val_at=(332.74, 27.94))
m.attach("+5V", 332.74, 30.48, (0, 1), [])
m.write("mcu_h743.kicad_sch", "MCU STM32H743", uid())

# project file from OpenAIO with the new name
import json
if not os.path.exists(f"{OUT}/{PROJ}.kicad_pro"):
    pro = json.load(open(f"{SRC}/OpenAIO.kicad_pro"))
    pro["meta"]["filename"] = f"{PROJ}.kicad_pro"
    pro["sheets"] = [[ROOT, "Root"]]
    json.dump(pro, open(f"{OUT}/{PROJ}.kicad_pro", "w"), indent=2)
print("ok")
