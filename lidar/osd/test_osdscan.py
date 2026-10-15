#!/usr/bin/env python3
"""Tests for the OSD scan link: the Lua encoder against the Python decoder.

    python3 lidar/osd/test_osdscan.py        (needs `lua` 5.3+ on PATH for the Lua part)

1. Real D500 bytes (the LidarCam test sample) go through the Lua parser and
   encoder; the frames must equal the Python encoder's for the same turns,
   and decode back to the same codes.
2. A recorded session goes through code -> frame -> decode, and the distance
   that comes out is compared with the one that went in.
"""

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import osdscan as o  # noqa: E402
from lidar_web import PACKET_LEN, parse_packet  # noqa: E402

SAMPLE = ROOT / "android/lidarcam/app/src/test/resources/d500_sample.bin"
SESSIONS = HERE.parent / "sessions"

LUA_HARNESS = r"""
SCAN_OSD_TEST = true
local M = dofile(arg[1])
local f = io.open(arg[2], "rb"); local data = f:read("a"); f:close()
local n = 0
local parse = M.new_parser(function(bins)
  n = n + 1
  for part = 0, M.PARTS - 1 do io.write(M.frame(n, part, bins), "\n") end
end)
local bad = 0
for i = 1, #data, 100 do bad = parse(data:sub(i, i + 99)) end
io.write("bad ", bad, "\n")
for _, w in ipairs(M.layout(M.frame(1, 0, (function() local t = {} for i = 1, M.BINS do t[i] = 80 * i end return t end)()))) do
  io.write("layout ", w[1], " ", w[2], " ", w[3], "\n")
end
for _, a in ipairs({ { 0, 0, 0 }, { 359.99, 10, -20 }, { 123.4, -60, 60 }, { -90, 3, -3 } }) do
  local t = M.attitude(math.rad(a[1]), math.rad(a[2]), math.rad(a[3]))
  io.write("att ", a[1], " ", a[2], " ", a[3], " ", table.concat(t, " "), "\n")
end
"""


def python_turns(data):
    """Turns of the sample as bin -> min distance, the way the Lua bins them."""
    turns, bins, last = [], {}, None
    i = 0
    while True:
        i = data.find(b"\x54\x2c", i)
        if i < 0 or len(data) - i < PACKET_LEN:
            break
        p = parse_packet(data[i:i + PACKET_LEN])
        if p is None:
            i += 1
            continue
        i += PACKET_LEN
        for a, d, _ in p[1]:
            if last is not None and a < last - 180:
                turns.append(bins)
                bins = {}
            last = a
            if d > 0:
                b = int(a // o.BIN_DEG) % o.BINS
                bins[b] = min(d, bins.get(b, d))
    return turns


class Codec(unittest.TestCase):
    def test_roundtrip_all_codes(self):
        for start in range(0, 512, o.PER_PART):
            codes = [(start + k) % 512 for k in range(o.BINS)]
            for part in range(o.PARTS):
                text = o.encode(7, part, codes)
                self.assertEqual(len(text), o.FRAME_CHARS)
                self.assertEqual(o.decode(text), (7, part, codes[part * o.PER_PART:(part + 1) * o.PER_PART]))

    def test_one_wrong_character_is_caught(self):
        text = o.encode(3, 1, list(range(o.BINS)))
        for k in range(len(text)):
            for ch in "0Zz+":
                if ch != text[k]:
                    self.assertIsNone(o.decode(text[:k] + ch + text[k + 1:]))

    def test_quantisation_error(self):
        for d in range(o.DMIN, o.DMAX, 7):
            back = o.distance(o.code(d))
            self.assertLess(abs(back - d) / d, 0.006, d)

    def test_attitude_roundtrip(self):
        for yaw, roll, pitch in ((0, 0, 0), (359.9, 10.5, -20.3), (123.45, -47, 46)):
            text = o.encode(5, 2, list(range(o.BINS)), (yaw, roll, pitch))
            y, r, p = o.decode_full(text)[3]
            self.assertLess(abs((y - yaw + 180) % 360 - 180), 360 / 4096)
            self.assertLessEqual(abs(r - roll), 0.75)
            self.assertLessEqual(abs(p - pitch), 0.75)

    def test_reads_v1_frames(self):
        codes = list(range(o.BINS))
        v1 = o.encode(4, 1, codes, att=None)
        self.assertEqual(len(v1), o.FRAME_CHARS_V1)
        self.assertEqual(o.decode_full(v1), (4, 1, codes[o.PER_PART:2 * o.PER_PART], None))
        self.assertEqual(o.decode(v1 + " " * o.ATT_CHARS)[0], 4)    # as a screen reads it

    def test_assembler_keeps_the_attitude(self):
        codes = list(range(o.BINS))
        a = o.Assembler()
        for part in range(o.PARTS):
            a.add(o.encode(9, part, codes, (90, 3, -1.5)))
        self.assertEqual(a.attitude, (90.0, 3.0, -1.5))

    def test_assembler_needs_all_three_parts(self):
        codes = list(range(o.BINS))
        a = o.Assembler()
        self.assertIsNone(a.add(o.encode(1, 0, codes)))
        self.assertIsNone(a.add(o.encode(1, 0, codes)))      # redrawn
        self.assertIsNone(a.add(o.encode(1, 2, codes)))
        self.assertEqual(a.add(o.encode(1, 1, codes)), codes)
        self.assertIsNone(a.add(o.encode(2, 0, codes)))
        self.assertIsNone(a.add(o.encode(3, 0, codes)))      # turn 2 lost a part
        self.assertEqual(a.stats["incomplete"], 1)


@unittest.skipUnless(shutil.which("lua"), "no lua on PATH")
class LuaAgainstPython(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        h = HERE / ".lua_harness.lua"
        h.write_text(LUA_HARNESS)
        try:
            out = subprocess.run(["lua", str(h), str(HERE / "scan_osd.lua"), str(SAMPLE)],
                                 capture_output=True, text=True, check=True).stdout
        finally:
            h.unlink()
        lines = out.splitlines()
        cls.frames = [ln for ln in lines if not ln.startswith(("bad ", "layout ", "att "))]
        cls.att = [ln.split()[1:] for ln in lines if ln.startswith("att ")]
        cls.bad = int(next(ln for ln in lines if ln.startswith("bad "))[4:])
        cls.layout = [ln.split(" ", 3)[1:] for ln in lines if ln.startswith("layout ")]
        cls.turns = python_turns(SAMPLE.read_bytes())

    def test_same_turns(self):
        self.assertGreater(len(self.turns), 0)
        self.assertEqual(len(self.frames), o.PARTS * len(self.turns))
        self.assertEqual(self.bad, 0)

    def test_lua_attitude_equals_python(self):
        self.assertEqual(len(self.att), 4)
        for row in self.att:
            yaw, roll, pitch = map(float, row[:3])
            self.assertEqual(list(map(int, row[3:])), o.attitude(yaw, roll, pitch), row)

    def test_lua_frames_equal_python(self):
        for n, bins in enumerate(self.turns, start=1):
            codes = [o.code(bins.get(b, 0)) for b in range(o.BINS)]
            for part in range(o.PARTS):
                lua = self.frames[(n - 1) * o.PARTS + part]
                self.assertEqual(lua, o.encode(n, part, codes), (n, part))
                self.assertEqual(o.decode(lua)[2], codes[part * o.PER_PART:(part + 1) * o.PER_PART])

    def test_layout_reads_back(self):
        screen = {}
        for col, row, text in self.layout:
            self.assertLessEqual(len(text), 30)
            for k, ch in enumerate(text):
                screen[(int(row), int(col) + k)] = ch
        codes = [o.code(80 * i) for i in range(1, o.BINS + 1)]
        self.assertEqual(o.frame_from_screen(screen), o.encode(1, 0, codes))


@unittest.skipUnless(SESSIONS.exists() and any(SESSIONS.glob("*/lidar.jsonl")), "no sessions")
class RecordedSession(unittest.TestCase):
    def test_what_arrives(self):
        errs, kept, total = [], 0, 0
        for path in SESSIONS.glob("*/lidar.jsonl"):
            for line in path.read_text().splitlines():
                pts = json.loads(line)["pts"]
                bins = {}
                for a, d in zip(pts[0::3], pts[1::3]):
                    total += 1
                    if d > 0:
                        b = int(a // o.BIN_DEG) % o.BINS
                        bins[b] = min(d, bins.get(b, d))
                codes = [o.code(bins.get(b, 0)) for b in range(o.BINS)]
                out = sum((o.decode(o.encode(0, p, codes))[2] for p in range(o.PARTS)), [])
                for b, d in bins.items():
                    if d <= o.DMAX:
                        errs.append(abs(o.distance(out[b]) - d))
                        kept += 1
        errs.sort()
        print(f"\n  {total} points -> {kept} bins, distance error median "
              f"{errs[len(errs) // 2]:.1f} mm, 95 % {errs[int(len(errs) * 0.95)]:.1f} mm, "
              f"max {errs[-1]:.1f} mm", file=sys.stderr)
        self.assertLess(errs[int(len(errs) * 0.95)], 40)


if __name__ == "__main__":
    unittest.main()
