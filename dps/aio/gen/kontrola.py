"""Machine-readable KiCad gates shared by the automatic build and its tests."""
from collections import Counter
import json
import re
import xml.etree.ElementTree as ET

import micoair


def signature(v, sheet=""):
    # Positions are deliberately not part of the exception: moving a symbol does
    # not change the known pin-type issue. Pin descriptions, UUIDs and sheet are.
    return json.dumps([sheet, v["type"], v["description"], sorted(
        (i["uuid"], i["description"]) for i in v.get("items", []))], ensure_ascii=False)


def unexpected(violations, allowed):
    remaining = Counter(allowed)
    out = []
    for sheet, v in violations:
        key = signature(v, sheet)
        if remaining[key]:
            remaining[key] -= 1
        else:
            out.append(v)
    return out


def summarize(drc, erc, exceptions):
    errors = [v for v in drc["violations"] if v["severity"] == "error"]
    parity = unexpected((("", v) for v in drc["schematic_parity"]), exceptions["parity"])
    erc_errors = unexpected(((s["path"], v) for s in erc["sheets"] for v in s["violations"]
                             if v["severity"] == "error"), exceptions["erc"])
    return dict(drc_errors=len(errors), unconnected=len(drc["unconnected_items"]),
                unexpected_parity=len(parity), unexpected_erc=len(erc_errors),
                warnings=dict(Counter(v["type"] for v in drc["violations"] if v["severity"] == "warning")))


def valid(s):
    return not any(s[k] for k in ("drc_errors", "unexpected_parity", "unexpected_erc"))


def better(candidate, baseline):
    return valid(candidate) and candidate["unconnected"] < baseline["unconnected"]


def net_pins(netlist):
    root = ET.parse(netlist).getroot()
    out = {}
    for net in root.iter("net"):
        for node in net.findall("node"):
            if node.get("ref") == "U301":
                name = net.get("name").rsplit("/", 1)[-1]
                if not name.startswith(("unconnected-", "Net-")):
                    out[name] = dict(ball=node.get("pin"), pin=micoair.gpio(node.get("pinfunction", "")))
    return out


def reference_diff(pins):
    return [dict(signal=signal, expected=pin, actual=pins.get(signal))
            for signal, pin in micoair.PINS.items() if pins.get(signal, {}).get("pin") != pin]


def firmware_errors(pins, hwdef):
    lines = [line.split("#", 1)[0].split() for line in hwdef.splitlines()]
    declared = {}
    errors = []
    for words in lines:
        if words and re.fullmatch(r"P[A-K]\d+", words[0]):
            if words[0] in declared:
                errors.append(f"duplicate GPIO {words[0]}")
            declared[words[0]] = words[1:]
    # Derive UART functions from SERIAL_ORDER, not from historic net names.
    order = next(w[1:] for w in lines if w and w[0] == "SERIAL_ORDER")
    functions = {"IMU_CS": "BMI270_CS", "IMU_INT": "DRDY3_BMI270", "IMU2_CS": "ICM42688_CS",
                 "IMU2_INT": "DRDY1_ICM42688", "VBAT_SENSE": "BATT_VOLTAGE_SENS",
                 "ESC_CURRENT": "BATT_CURRENT_SENS", "SCL": "I2C2_SCL", "SDA": "I2C2_SDA",
                 "EXT_SCL": "I2C1_SCL", "EXT_SDA": "I2C1_SDA", "USB_DM": "OTG_FS_DM",
                 "USB_DP": "OTG_FS_DP", "SWDIO": "JTMS-SWDIO", "SWCLK": "JTCK-SWCLK",
                 "LED_R": "LED_RED", "LED_G": "LED_GREEN", "LED_B": "LED_BLUE", "BUZZER": "BUZZER"}
    for number, prefix in ((1, "UART1"), (2, "VTX"), (3, "GPS"), (4, "FLOW"), (6, "RC")):
        for direction in ("TX", "RX"):
            functions[f"{prefix}_{direction}"] = f"{order[number]}_{direction}"
    functions["LIDAR_TX"] = order[5] + "_RX"  # TX from the sensor is RX on the MCU
    for signal in ("UART3_TX", "UART5_TX"):
        if signal in pins:
            functions[signal] = order[5] + "_TX"
    for prefix in ("UART7", "UART8"):
        for direction in ("TX", "RX"):
            if f"{prefix}_{direction}" in pins:
                functions[f"{prefix}_{direction}"] = order[8] + "_" + direction
    devices = {w[1]: w[2] for w in lines if w and w[0] == "SPIDEV"}
    for prefix, dev in (("IMU_SPI.", "bmi270"), ("IMU2_", "icm42688")):
        for signal in ("SCK", "MISO", "MOSI"):
            functions[prefix + signal] = devices.get(dev, "MISSING") + "_" + signal
    for signal in ("CK", "CMD", "D0", "D1", "D2", "D3"):
        functions["SD_" + signal] = "SDMMC1_" + signal
    for signal, function in functions.items():
        pin = pins.get(signal, {}).get("pin")
        if not pin or not declared.get(pin) or declared[pin][0] != function:
            errors.append(f"{signal}: schematic {pin}, hwdef expects {function}, found {declared.get(pin)}")
    for signal, number in (("MOTOR1", 1), ("MOTOR2", 2), ("MOTOR3", 3), ("MOTOR4", 4),
                           ("PWM5", 5), ("LIDAR_PWM", 6), ("PWM7", 7), ("VTX_EN", 8),
                           ("PWM9", 9), ("PWM10", 10), ("PWM11", 11)):
        if f"PWM({number})" not in declared.get(pins.get(signal, {}).get("pin"), []):
            errors.append(f"{signal}: PWM({number}) does not match hwdef")
    return errors
