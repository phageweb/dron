"""Narrow passages and who may be in them."""

import unittest

from openipc_swarm.passages import (
    Reservations,
    half_width_for,
    passages,
    passages_on,
)

FREE, WALL = 0, 100


def two_rooms(door_rows=(9, 10, 11), cols=41, rows=21, wall_col=20,
              wall_thick=3):
    """Two rooms side by side, a wall `wall_thick` thick between, one door."""
    values = []
    for row in range(rows):
        for col in range(cols):
            edge = row in (0, rows - 1) or col in (0, cols - 1)
            in_wall = wall_col <= col < wall_col + wall_thick
            values.append(WALL if edge or (in_wall and row not in door_rows)
                          else FREE)
    return values


class TestPassages(unittest.TestCase):
    def test_the_half_width_follows_d_safe(self):
        # 0.78 m apart plus 0.25 m of wall each side: 1.28 m, 7 cells each way.
        self.assertEqual(half_width_for(0.78, 0.25, 0.1), 7)

    def test_a_door_is_a_passage_and_the_rooms_are_not(self):
        found = passages(two_rooms(), 41, 21, half_width_cells=3)
        self.assertEqual(len(found), 1)
        (cells,) = found.values()
        self.assertTrue(all(20 <= c < 23 for c, _ in cells))

    def test_the_corners_of_a_room_are_not_passages(self):
        found = passages(two_rooms(door_rows=()), 41, 21, half_width_cells=3)
        self.assertEqual(found, {})

    def test_a_route_through_the_door_meets_it(self):
        found = passages(two_rooms(), 41, 21, half_width_cells=3)
        route = [(c, 10) for c in range(5, 35)]
        self.assertEqual(passages_on(route, found), list(found))
        self.assertEqual(passages_on([(c, 3) for c in range(2, 18)], found), [])


class TestReservations(unittest.TestCase):
    def setUp(self):
        self.found = passages(two_rooms(), 41, 21, half_width_cells=3)
        (self.door,) = self.found
        self.through = [(c, 10) for c in range(5, 35)]

    def test_one_holder_and_the_others_kept_out(self):
        r = Reservations()
        r.update(0.0, self.found, {"v1": self.through, "v2": self.through},
                 {"v1": (5, 10), "v2": (35, 10)})
        self.assertEqual(r.holder(self.door), "v1")
        self.assertEqual(r.blocked_for("v1"), set())
        self.assertEqual(r.blocked_for("v2"), self.found[self.door])

    def test_released_once_through_and_no_longer_needed(self):
        r = Reservations(margin_cells=2)
        r.update(0.0, self.found, {"v1": self.through}, {"v1": (5, 10)})
        r.update(1.0, self.found, {"v1": [(30, 10), (31, 10)]}, {"v1": (21, 10)})
        self.assertEqual(r.holder(self.door), "v1")      # still in the door
        r.update(2.0, self.found, {"v1": [(30, 10), (31, 10)]}, {"v1": (30, 10)})
        self.assertIsNone(r.holder(self.door))

    def test_a_lost_holder_is_not_assumed_outside_after_timeout(self):
        r = Reservations(max_hold_s=10.0)
        r.update(0.0, self.found, {"v1": self.through}, {"v1": (5, 10)})
        r.update(5.0, self.found, {}, {})
        self.assertEqual(r.holder(self.door), "v1")
        r.update(11.0, self.found, {}, {})
        self.assertEqual(r.holder(self.door), "v1")


if __name__ == "__main__":
    unittest.main()
