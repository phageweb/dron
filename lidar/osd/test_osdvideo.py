#!/usr/bin/env python3
"""osdvideo.py on real VRX pictures.

vrx_frames.npz: the frame rows of three pictures from the VRX recording of
14. 10. 2026 (old alphabet), the three frames of turn 13, and one picture
without the rows.

    python3 lidar/osd/test_osdvideo.py      # needs numpy
"""

import itertools
import random
import sys
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import osdscan as O  # noqa: E402
import osdvideo as V  # noqa: E402


class RealPictures(unittest.TestCase):
    def setUp(self):
        z = np.load(HERE / "vrx_frames.npz")
        self.strips, self.texts, self.codes = z["strips"], list(z["texts"]), list(z["codes"])

    def test_strip_size(self):
        self.assertEqual(self.strips.shape[1:], (V.STRIP[1] - V.STRIP[0], V.WIDTH))

    def test_reads_the_turn(self):
        dec = V.VideoDecoder(V.Glyphs.load(V.GLYPHS_ARDU), V.OLD_ALPHABET)
        out = [dec.feed(s) for s in self.strips[:3]]
        self.assertEqual([dec.read(s) for s in self.strips[:3]], self.texts)
        self.assertEqual(out[:2], [None, None])
        self.assertEqual(list(out[2]), self.codes)
        self.assertEqual(dec.read(self.strips[3]), "")

    def test_lookalikes_need_the_crc(self):
        # In the old alphabet s-y have the same glyph as b, d, f, h, j, l, n;
        # the frames still read only because the CRC picks among them. The
        # text is in ALPHABET, where those symbols are < > [ ] % @ /.
        twins = {O.ALPHABET[V.OLD_ALPHABET.index(c)] for c in V.LOOKALIKE}
        self.assertTrue(any(c in twins for t in self.texts for c in t))

    def test_learning_keeps_reading(self):
        g = V.Glyphs.load(V.GLYPHS_ARDU)
        dec = V.VideoDecoder(g, V.OLD_ALPHABET, learn=True)
        for _ in range(3):
            for s in self.strips[:3]:
                dec.read(s)
        self.assertEqual(dec.stats["unread"], 0)


class Alphabet(unittest.TestCase):
    def test_every_symbol_has_a_glyph(self):
        g = V.Glyphs.load()
        for c in O.ALPHABET:
            self.assertIn(c, g.chars)

    def test_glyphs_differ(self):
        g = V.Glyphs.load()
        T = np.array([g.tmpl[g.index(c)] for c in O.ALPHABET])
        d = ((T[:, None] - T[None]) ** 2).sum(-1) + np.eye(len(T)) * 1e9
        i, j = np.unravel_index(d.argmin(), d.shape)
        self.assertGreater(d[i, j], 3.0, f"{O.ALPHABET[i]!r} and {O.ALPHABET[j]!r} look alike")


class GF2(unittest.TestCase):
    def test_against_brute_force(self):
        rnd = random.Random(1)
        for n in (3, 8, 12, 18):
            cols = [rnd.getrandbits(16) for _ in range(n)]
            target = rnd.getrandbits(16)
            if n > 10:
                target = 0
                for k in range(n):
                    if rnd.random() < 0.5:
                        target ^= cols[k]
            want = set()
            for bits in itertools.product((0, 1), repeat=n):
                v = 0
                for b, c in zip(bits, cols):
                    if b:
                        v ^= c
                if v == target:
                    want.add(sum(b << k for k, b in enumerate(bits)))
            self.assertEqual(set(V._gf2_solutions(target, cols, limit=1 << 20)), want)


if __name__ == "__main__":
    unittest.main()
