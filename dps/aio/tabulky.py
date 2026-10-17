#!/usr/bin/env python3
"""Regenerate the tables in NAVRH.md from the schematic.

    nix develop ./dps -c python3 dps/aio/tabulky.py

Exports the netlist with kicad-cli and rewrites everything between the
<!-- tabulky:NAME --> and <!-- /tabulky:NAME --> markers in NAVRH.md.
"""
import collections, os, re, subprocess, tempfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
DOC = os.path.join(HERE, "NAVRH.md")

# What each H743 signal does in ArduPilot (hwdef MicoAir743v2) and where it goes.
FUNCTION = {
    "MOTOR1": "PWM1, TIM1_CH4, BIDIR DShot", "MOTOR2": "PWM2, TIM1_CH3", "MOTOR3": "PWM3, TIM1_CH2, BIDIR DShot",
    "MOTOR4": "PWM4, TIM1_CH1", "PWM5": "PWM5, TIM3_CH4, GPIO 54", "LIDAR_PWM": "PWM6, TIM3_CH3, GPIO 55",
    "PWM7": "PWM7, TIM4_CH1, GPIO 56", "VTX_EN": "PWM8 jako GPIO 57 (RELAYn_PIN 57)", "PWM9": "PWM9, TIM15_CH1, GPIO 58",
    "PWM10": "PWM10, TIM15_CH2, GPIO 59", "PWM11": "PWM11, TIM4_CH3, GPIO 60 (LED pad)",
    "IMU_SPI.SCK": "SPI3_SCK", "IMU_SPI.MOSI": "SPI3_MOSI", "IMU_SPI.MISO": "SPI3_MISO", "IMU_CS": "BMI270_CS",
    "IMU_INT": "DRDY3_BMI270", "IMU2_SCK": "SPI2_SCK", "IMU2_MISO": "SPI2_MISO", "IMU2_MOSI": "SPI2_MOSI",
    "IMU2_ACC_CS": "BMI088_A_CS", "IMU2_GYR_CS": "BMI088_G_CS", "IMU2_ACC_INT": "DRDY2_BMI088_A",
    "IMU2_GYR_INT": "DRDY1_BMI088_G", "VBAT_SENSE": "ADC1 ch10, BATT_VOLTAGE_SENS",
    "ESC_CURRENT": "ADC1 ch11, BATT_CURRENT_SENS", "SDA": "I2C2_SDA (bus 0)", "SCL": "I2C2_SCL (bus 0)",
    "EXT_SDA": "I2C1_SDA (bus 1)", "EXT_SCL": "I2C1_SCL (bus 1)", "UART1_TX": "USART1_TX, SERIAL1",
    "UART1_RX": "USART1_RX, SERIAL1", "VTX_TX": "USART2_TX, SERIAL2", "VTX_RX": "USART2_RX, SERIAL2",
    "GPS_TX": "USART3_TX, SERIAL3", "GPS_RX": "USART3_RX, SERIAL3", "FLOW_TX": "UART4_TX, SERIAL4",
    "FLOW_RX": "UART4_RX, SERIAL4", "UART5_TX": "UART5_TX, SERIAL5", "LIDAR_TX": "UART5_RX, SERIAL5",
    "RC_TX": "USART6_TX, SERIAL6", "RC_RX": "USART6_RX, SERIAL6", "UART7_TX": "UART7_TX, SERIAL7",
    "UART7_RX": "UART7_RX, SERIAL7", "UART8_TX": "UART8_TX, SERIAL8", "UART8_RX": "UART8_RX, SERIAL8",
    "USB_DM": "OTG_FS_DM, SERIAL0", "USB_DP": "OTG_FS_DP, SERIAL0", "SWDIO": "SWD", "SWCLK": "SWD",
    "SD_CK": "SDMMC1_CK", "SD_CMD": "SDMMC1_CMD", "SD_D0": "SDMMC1_D0", "SD_D1": "SDMMC1_D1",
    "SD_D2": "SDMMC1_D2", "SD_D3": "SDMMC1_D3", "LED_R": "LED_RED, GPIO 0", "LED_G": "LED_GREEN, GPIO 1",
    "LED_B": "LED_BLUE, GPIO 2", "BUZZER": "BUZZER, GPIO 61", "HSE_IN": "OSC_IN, 8 MHz", "HSE_OUT": "OSC_OUT",
    "BOOT0": "BOOT0", "NRST": "reset", "PDR_ON": "napěťový dozor", "VCAP": "výstup LDO jádra",
}


def netlist():
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "aio.xml")
        subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadxml", "-o", out,
                        os.path.join(HERE, "aio.kicad_sch")], check=True, capture_output=True)
        return ET.parse(out).getroot()


def short(net):
    return re.sub(r"^/(?:[^/]+/)*", "", net) if net.startswith("/") else net


def main():
    t = netlist()
    comps = {}
    for c in t.find("components"):
        f = {x.get("name"): x.text or "" for x in c.findall("fields/field")}
        comps[c.get("ref")] = dict(value=c.findtext("value"), fp=(c.findtext("footprint") or "").split(":")[-1],
                                   lcsc=f.get("LCSC", ""), sheet=c.find("sheetpath").get("names"))
    pins = collections.defaultdict(dict)
    nets = collections.defaultdict(list)
    for n in t.find("nets"):
        name = n.get("name")
        for x in n.findall("node"):
            pins[x.get("ref")][x.get("pin")] = (name, x.get("pinfunction") or "")
            nets[name].append(x.get("ref"))

    tables = {}

    # bill of materials, per sheet
    by = collections.defaultdict(list)
    for ref, c in comps.items():
        by[c["sheet"]].append(ref)
    key = lambda r: (re.sub(r"\d+", "", r), int(re.sub(r"\D", "", r) or 0))
    out = []
    for sheet in sorted(by, key=lambda s: (s != "/", s)):
        refs = sorted(by[sheet], key=key)
        out.append(f"\n**{sheet}** ({len(refs)} dílů)\n")
        out.append("| Ref | Hodnota | Pouzdro | LCSC |")
        out.append("| --- | --- | --- | --- |")
        for r in refs:
            c = comps[r]
            out.append(f"| {r} | {c['value']} | {c['fp']} | {c['lcsc'] or '—'} |")
    tables["kusovnik"] = "\n".join(out)

    # H743 pin map
    out = ["| Kulička | Pin | Síť | Funkce (hwdef MicoAir743v2) | Kam vede |", "| --- | --- | --- | --- | --- |"]
    rows = []
    for ball, (net, func) in pins["U301"].items():
        pin = func.rsplit("_", 1)[0]
        s = short(net)
        if s.startswith("unconnected"):
            s, goes = "—", "nezapojeno"
        else:
            others = sorted({r for r in nets[net] if r != "U301"}, key=key)
            if len(others) > 12:
                goes = f"napájecí síť ({len(others)} dílů)"
            else:
                goes = ", ".join(others) if others else "jen štítek, čeká na zapojení"
        rows.append((pin, ball, s, FUNCTION.get(s, ""), goes))
    order = lambda r: (r[0][:2] if r[0].startswith("P") else "~", int(re.sub(r"\D", "", r[0][2:]) or 0), r[0])
    for pin, ball, s, f, goes in sorted(rows, key=order):
        out.append(f"| {ball} | {pin} | {s} | {f} | {goes} |")
    tables["piny"] = "\n".join(out)

    # nets crossing sheets
    out = ["| Síť | Listy | Součástky |", "| --- | --- | --- |"]
    for name, refs in sorted(nets.items(), key=lambda kv: short(kv[0])):
        sheets = sorted({comps[r]["sheet"] for r in refs})
        if len(sheets) > 1 and short(name) not in ("GND",):
            rs = sorted(set(refs), key=key)
            shown = ", ".join(rs[:10]) + (f" … (+{len(rs) - 10})" if len(rs) > 10 else "")
            out.append(f"| {short(name)} | {', '.join(sheets)} | {shown} |")
    tables["site"] = "\n".join(out)

    doc = open(DOC).read()
    for k, v in tables.items():
        doc, n = re.subn(rf"(<!-- tabulky:{k} -->).*?(<!-- /tabulky:{k} -->)",
                         lambda m: f"{m.group(1)}\n{v}\n{m.group(2)}", doc, flags=re.S)
        assert n == 1, k
    open(DOC, "w").write(doc)
    print("NAVRH.md: tabulky", ", ".join(tables))


if __name__ == "__main__":
    main()
