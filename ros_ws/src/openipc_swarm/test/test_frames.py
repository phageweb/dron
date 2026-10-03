"""Moving poses, grids and targets between an agent's frame and the room."""

import unittest

from openipc_swarm.frames import (
    offset_in_cells,
    parse_offsets,
    shift_grid,
    to_agent,
    to_room,
)
from openipc_swarm.merge import UNKNOWN


class TestParseOffsets(unittest.TestCase):
    def test_pairs_the_values_with_the_names_in_order(self):
        self.assertEqual(
            parse_offsets(["v1", "v2"], [0.5, -2.0, 0.5, 0.0]),
            {"v1": (0.5, -2.0), "v2": (0.5, 0.0)})

    def test_a_missing_offset_is_refused_not_taken_as_zero(self):
        # Zero is what the first swarm flight used without knowing it.
        with self.assertRaises(ValueError):
            parse_offsets(["v1", "v2", "v3"], [])
        with self.assertRaises(ValueError):
            parse_offsets(["v1", "v2"], [0.5, -2.0, 0.5])


class TestFrames(unittest.TestCase):
    def test_three_agents_reporting_one_point_are_three_places(self):
        # The measured case: each drifted +0.73 m from its own start.
        offsets = parse_offsets(["v1", "v2", "v3"],
                                [0.5, -2.0, 0.5, 0.0, 0.5, 2.0])
        local = (0.73, 0.04, 1.1)
        placed = [to_room(local, offsets[n]) for n in ("v1", "v2", "v3")]
        self.assertEqual([p[1] for p in placed], [-1.96, 0.04, 2.04])
        self.assertTrue(all(abs(p[0] - 1.23) < 1e-9 for p in placed))

    def test_a_target_goes_back_where_it_came_from(self):
        offset = (0.5, -2.0)
        room = to_room((1.0, 1.5, 0.9), offset)
        self.assertEqual(to_agent(room[:2], offset), (1.0, 1.5))

    def test_height_is_not_moved(self):
        self.assertEqual(to_room((0.0, 0.0, 1.2), (0.5, 2.0))[2], 1.2)


class TestOffsetInCells(unittest.TestCase):
    def test_the_generated_starts_are_whole_cells(self):
        self.assertEqual(offset_in_cells((0.5, -2.0), 0.10), (5, -20))
        self.assertEqual(offset_in_cells((0.5, 2.0), 0.10), (5, 20))

    def test_a_fraction_of_a_cell_is_refused(self):
        with self.assertRaises(ValueError):
            offset_in_cells((0.55, 0.0), 0.10)


class TestShiftGrid(unittest.TestCase):
    # 3 wide, 2 high, row-major:  row 0: 1 2 3   row 1: 4 5 6
    GRID = [1, 2, 3, 4, 5, 6]

    def test_no_shift_is_the_same_grid(self):
        self.assertEqual(shift_grid(self.GRID, 3, 2, 0, 0), self.GRID)

    def test_a_positive_column_shift_moves_towards_higher_x(self):
        self.assertEqual(shift_grid(self.GRID, 3, 2, 1, 0),
                         [UNKNOWN, 1, 2, UNKNOWN, 4, 5])

    def test_a_negative_row_shift_moves_towards_lower_y(self):
        self.assertEqual(shift_grid(self.GRID, 3, 2, 0, -1),
                         [4, 5, 6, UNKNOWN, UNKNOWN, UNKNOWN])

    def test_a_shift_past_the_edge_leaves_nothing_known(self):
        self.assertEqual(shift_grid(self.GRID, 3, 2, 3, 0), [UNKNOWN] * 6)

    def test_a_cell_lands_where_its_room_position_is(self):
        # A wall an agent standing at y=+2 m sees 1 m to its left is at
        # y=+3 m in the room; in a 0.1 m grid that is 20 rows further up.
        width, height = 4, 40
        local = [UNKNOWN] * (width * height)
        local[10 * width + 1] = 100        # row 10: local y = origin + 1.05
        room = shift_grid(local, width, height, *offset_in_cells((0.0, 2.0), 0.10))
        self.assertEqual(room.index(100), 30 * width + 1)

    def test_a_grid_of_the_wrong_size_is_refused(self):
        with self.assertRaises(ValueError):
            shift_grid([0] * 5, 3, 2, 0, 0)


if __name__ == "__main__":
    unittest.main()
