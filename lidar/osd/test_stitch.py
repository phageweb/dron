#!/usr/bin/env python3
"""stitch.py on a made-up flat whose walk is known.

Turns are ray-cast in an L-shaped room with a table, from a path that turns
by up to 90 degrees between turns, the way a walk with the drone in hand
does. With the heading given, the path has to come back to within a few
centimetres; the angle conventions (lidar and yaw both clockwise) are what
this pins down.

    python3 lidar/osd/test_stitch.py      # needs numpy
"""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stitch  # noqa: E402

# walls as segments, mm: an L of 5 x 4 m with a 2 x 1.5 m notch, and a table
WALLS = [((0, 0), (5000, 0)), ((5000, 0), (5000, 2500)), ((5000, 2500), (3000, 2500)),
         ((3000, 2500), (3000, 4000)), ((3000, 4000), (0, 4000)), ((0, 4000), (0, 0)),
         ((1200, 1200), (2000, 1200)), ((2000, 1200), (2000, 1700)), ((2000, 1700), (1200, 1700)),
         ((1200, 1700), (1200, 1200))]


def ray(x, y, ang):
    """Distance from (x, y) along heading ang (clockwise from +y) to the nearest wall."""
    dx, dy = np.sin(ang), np.cos(ang)
    best = np.inf
    for (ax, ay), (bx, by) in WALLS:
        ex, ey = bx - ax, by - ay
        den = dx * ey - dy * ex
        if abs(den) < 1e-9:
            continue
        t = ((ax - x) * ey - (ay - y) * ex) / den
        u = ((ax - x) * dy - (ay - y) * dx) / den
        if t > 0 and 0 <= u <= 1:
            best = min(best, t)
    return best


def turn(x, y, heading_deg, t):
    pts = []
    for i in range(144):
        a = (i + 0.5) * 2.5
        d = ray(x, y, np.radians(heading_deg + a))
        if d < 12000:
            pts += [a, d, 200]
    return {"t_ns": int(t * 1e9), "pts": pts, "yaw": heading_deg % 360}


class Walk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = np.random.default_rng(3)
        path = [(600 + 3500 * f, 600 + 400 * np.sin(4 * f)) for f in np.linspace(0, 1, 20)]
        x1, y1 = path[-1]
        path += [(x1 + (2500 - x1) * f, y1 + (3400 - y1) * f) for f in np.linspace(0, 1, 13)[1:]]
        heads = np.cumsum(rng.uniform(-90, 90, len(path)))
        cls.true = np.array(path)
        cls.turns = [turn(x, y, h, i * 0.5) for i, ((x, y), h) in enumerate(zip(path, heads))]

    def test_path_with_the_heading(self):
        _, poses, fits, yaw = stitch.stitch(self.turns, dmin=100)
        self.assertTrue(yaw)
        got = poses[:, :2] - poses[0, :2]
        want = self.true - self.true[0]
        err = np.hypot(*(got - want).T)
        self.assertLess(err.max(), 60, err.round())
        self.assertGreater(min(fits), 0.9)

    def test_png(self):
        placed, poses, _, _ = stitch.stitch(self.turns[:5], dmin=100)
        img = stitch.draw(placed, poses, size=200)
        out = Path(__file__).with_name(".test_map.png")
        stitch.write_png(out, img)
        self.assertTrue(out.read_bytes().startswith(b"\x89PNG"))
        out.unlink()


if __name__ == "__main__":
    unittest.main()
