"""Regression tests for acceptance gates and the reference pin migration (no KiCad needed)."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from automat import Build
from kontrola import better, firmware_errors, signature, summarize, valid
import micoair

HERE = Path(__file__).parent


class Gates(unittest.TestCase):
    def setUp(self):
        self.drc = dict(violations=[], unconnected_items=[{}] * 22, schematic_parity=[])
        self.erc = dict(sheets=[])
        self.allowed = dict(erc=[], parity=[])

    def score(self):
        return summarize(self.drc, self.erc, self.allowed)

    def test_zero_ratsnest_does_not_hide_drc_error(self):
        before = self.score()
        self.drc["unconnected_items"] = []
        self.drc["violations"].append(dict(type="shorting_items", severity="error"))
        self.assertFalse(better(self.score(), before))

    def test_equal_or_worse_result_is_not_progress(self):
        before = self.score()
        self.assertFalse(better(self.score(), before))
        self.drc["unconnected_items"].append({})
        self.assertFalse(better(self.score(), before))
        self.drc["unconnected_items"] = [{}] * 21
        self.assertTrue(better(self.score(), before))

    def test_same_count_of_different_erc_error_is_rejected(self):
        v = dict(type="pin_not_driven", severity="error", description="Input not driven",
                 items=[dict(uuid="pin-1", description="C37 Pin 1")])
        self.allowed["erc"] = [signature(v, "/ESC1/")]
        self.erc["sheets"] = [dict(path="/ESC1/", violations=[v])]
        self.assertTrue(valid(self.score()))
        v["items"][0]["uuid"] = "another-pin"
        self.assertFalse(valid(self.score()))

    def test_same_uuid_in_another_sheet_is_not_the_same_exception(self):
        v = dict(type="pin_not_driven", severity="error", description="Input not driven", items=[])
        self.allowed["erc"] = [signature(v, "/ESC1/")]
        self.erc["sheets"] = [dict(path="/ESC2/", violations=[v])]
        self.assertEqual(self.score()["unexpected_erc"], 1)

    def test_parity_warning_cannot_be_ignored(self):
        self.drc["schematic_parity"] = [dict(type="net_conflict", severity="warning",
                                                 description="wrong net", items=[])]
        self.assertFalse(valid(self.score()))

    def test_exceptions_are_not_broad_check_type_allowances(self):
        data = json.loads((HERE / "vyjimky.json").read_text())
        self.assertEqual(len(data["erc"]), 18)
        self.assertEqual(len(data["parity"]), 14)
        for key in ("erc", "parity"):
            for value in data[key]:
                _, kind, description, items = json.loads(value)
                self.assertTrue(kind and description and items)


class Reference(unittest.TestCase):
    def setUp(self):
        self.hw = micoair.hwdef((HERE.parent / "hwdef/Pavo20AIO/hwdef.dat").read_text())
        self.pins = {name: dict(pin=pin, ball="unused") for name, pin in micoair.PINS.items()}

    def test_reference_firmware_matches_all_declared_signals(self):
        self.assertEqual(firmware_errors(self.pins, self.hw), [])
        self.assertIn("define HAL_BATT_CURR_SCALE 50.0", self.hw)
        self.assertIn("define HAL_BATT_VOLT_SCALE 11.0", self.hw)
        self.assertIn("APJ_BOARD_ID 25026", self.hw)

    def test_uart_and_spi_miswiring_is_detected(self):
        for signal in ("GPS_RX", "RC_TX", "LIDAR_TX", "IMU_SPI.MISO", "IMU2_SCK", "MOTOR2"):
            with self.subTest(signal=signal):
                pins = copy.deepcopy(self.pins)
                pins[signal]["pin"] = "PA8"
                self.assertTrue(firmware_errors(pins, self.hw))

    def test_duplicate_gpio_is_rejected(self):
        self.assertIn("duplicate GPIO PB3", firmware_errors(self.pins, self.hw + "\nPB3 SPI1_SCK SPI1\n"))

    def test_analog_switch_pin_names(self):
        self.assertEqual(micoair.gpio("PC2_C"), "PC2")
        self.assertEqual(micoair.gpio("PC14-OSC32_IN"), "PC14")

    def test_remap_preserves_power_and_removes_old_assignment(self):
        names = {str(i): pin for i, pin in enumerate(micoair.PINS.values())}
        names["POWER"] = "VDD"
        balls = {"OLD": "IMU_SPI.MISO", "POWER": "+3.3V"}
        result = micoair.remap(balls, names)
        self.assertEqual(result["POWER"], "+3.3V")
        self.assertNotIn("OLD", result)
        self.assertEqual(len(set(micoair.PINS.values())), len(micoair.PINS))
        self.assertEqual(set(result.values()) - {"+3.3V"}, set(micoair.PINS))


class Checkpoints(unittest.TestCase):
    def build(self, path):
        obj = Build(SimpleNamespace(output=Path(path), source=HERE.parent, profile="current", passes=1))
        obj.project.mkdir()
        obj.board.write_text("original")
        obj.save = lambda: None
        return obj

    def test_tool_failure_restores_board(self):
        with tempfile.TemporaryDirectory() as path:
            obj = self.build(path)

            def fail(*args, **kwargs):
                obj.board.write_text("partially modified")
                raise RuntimeError("tool failed")

            obj.script = fail
            with self.assertRaisesRegex(RuntimeError, "tool failed"):
                obj.route({}, dict(unconnected=22))
            self.assertEqual(obj.board.read_text(), "original")

    def test_short_and_bad_stitching_restore_last_valid_escape(self):
        with tempfile.TemporaryDirectory() as path:
            obj = self.build(path)
            erc = dict(sheets=[])
            report = dict(violations=[], unconnected_items=[], schematic_parity=[])
            baseline = dict(drc_errors=0, unconnected=22, unexpected_erc=0, unexpected_parity=0)

            def script(name, *args, **kwargs):
                obj.board.write_text(name)

            def drc(label):
                obj.history.append({})
                result = copy.deepcopy(report)
                if label != "escape":
                    result["violations"] = [dict(type="shorting_items", severity="error")]
                return result

            obj.script, obj.drc = script, drc
            obj.route(erc, baseline)
            self.assertEqual(obj.board.read_text(), "vyved_bga.py")


if __name__ == "__main__":
    unittest.main()
