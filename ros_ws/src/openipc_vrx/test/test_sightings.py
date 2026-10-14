import csv
import tempfile
import unittest

from openipc_vrx.sightings import Sightings, where


class Clock:
    def __init__(self):
        self.t = 1_800_000_000.0

    def __call__(self):
        return self.t


def rows(s):
    s.file.flush()
    with open(s.path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


class SightingsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.clock = Clock()
        self.s = Sightings(self.dir.name, gone_after=3.0, clock=self.clock)
        self.snaps = []

    def tearDown(self):
        if not self.s.file.closed:
            self.s.file.close()
        self.dir.cleanup()

    def step(self, found, dt=0.1):
        self.clock.t += dt
        return self.s.update(found, 1920, self.snaps.append)

    def test_one_line_when_seen_and_one_when_gone(self):
        person = [("person", 0.8, 100, 0, 300, 500)]
        for _ in range(30):                     # 3 s in view, ten pictures a second
            self.step(person)
        for _ in range(20):                     # not seen for 2 s: still counts as there
            self.step([])
        self.assertEqual([r["udalost"] for r in rows(self.s)], ["objeveno"])
        for _ in range(15):                     # past 3 s without it: gone
            self.step([])
        r = rows(self.s)
        self.assertEqual([x["udalost"] for x in r], ["objeveno", "zmizelo"])
        self.assertEqual(r[0]["co"], "person")
        self.assertEqual(r[0]["kde_v_obraze"], "vlevo 10 %")
        self.assertEqual(float(r[1]["trvani_s"]), 2.9)
        self.assertEqual(len(self.snaps), 1)
        self.assertTrue(r[0]["snimek"].endswith("_001_person.jpg"))

    def test_a_short_miss_does_not_split_the_sighting(self):
        self.step([("chair", 0.6, 1500, 0, 1700, 300)])
        self.step([], dt=1.0)
        self.step([("chair", 0.7, 1500, 0, 1700, 300)])
        self.assertEqual([r["udalost"] for r in rows(self.s)], ["objeveno"])

    def test_most_at_once_and_best_score_are_kept(self):
        self.step([("person", 0.5, 0, 0, 10, 10)])
        self.step([("person", 0.9, 900, 0, 1000, 10), ("person", 0.6, 0, 0, 10, 10)])
        self.step([], dt=5.0)
        gone = rows(self.s)[-1]
        self.assertEqual(gone["pocet"], "2")
        self.assertEqual(gone["jistota"], "0.90")
        self.assertEqual(gone["kde_v_obraze"], "uprostred 49 %")

    def test_close_writes_what_is_still_in_view(self):
        self.step([("cup", 0.5, 1800, 0, 1900, 10)])
        self.s.close()
        with open(self.s.path, encoding="utf-8") as f:
            self.assertEqual([r["udalost"] for r in csv.DictReader(f)], ["objeveno", "zmizelo"])

    def test_where_thirds(self):
        self.assertTrue(where(0, 100, 1920).startswith("vlevo"))
        self.assertTrue(where(900, 1000, 1920).startswith("uprostred"))
        self.assertTrue(where(1800, 1900, 1920).startswith("vpravo"))


if __name__ == "__main__":
    unittest.main()
