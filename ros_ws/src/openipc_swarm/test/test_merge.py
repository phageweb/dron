"""Merging three maps into one, and counting where they disagreed."""

import unittest

from openipc_swarm.merge import (
    UNKNOWN,
    GeometryMismatch,
    conflict_fraction,
    merge_grids,
)

FREE = 0
OCCUPIED = 100


class TestMerge(unittest.TestCase):
    def test_unknown_loses_to_anything(self):
        merged, conflicts = merge_grids([[UNKNOWN, FREE], [FREE, UNKNOWN]])
        self.assertEqual(merged, [FREE, FREE])
        self.assertEqual(conflicts, 0)

    def test_nobody_has_seen_it_stays_unknown(self):
        merged, _ = merge_grids([[UNKNOWN], [UNKNOWN], [UNKNOWN]])
        self.assertEqual(merged, [UNKNOWN])

    def test_occupied_beats_free_and_is_counted(self):
        merged, conflicts = merge_grids([[FREE], [OCCUPIED]])
        self.assertEqual(merged, [OCCUPIED])
        self.assertEqual(conflicts, 1)

    def test_agreement_is_not_a_conflict(self):
        merged, conflicts = merge_grids([[OCCUPIED], [OCCUPIED], [OCCUPIED]])
        self.assertEqual(conflicts, 0)
        merged, conflicts = merge_grids([[FREE], [FREE]])
        self.assertEqual(conflicts, 0)

    def test_one_conflict_per_cell_however_many_disagree(self):
        _, conflicts = merge_grids([[FREE], [OCCUPIED], [OCCUPIED], [FREE]])
        self.assertEqual(conflicts, 1)

    def test_mismatched_geometry_is_refused_rather_than_aligned(self):
        with self.assertRaises(GeometryMismatch):
            merge_grids([[FREE, FREE], [FREE]])

    def test_no_grids_at_all_is_refused(self):
        with self.assertRaises(GeometryMismatch):
            merge_grids([])

    def test_a_room_merges_into_more_than_either_agent_saw(self):
        # Two agents, each having seen half a four-cell room.
        first = [FREE, FREE, UNKNOWN, UNKNOWN]
        second = [UNKNOWN, UNKNOWN, FREE, OCCUPIED]
        merged, conflicts = merge_grids([first, second])
        self.assertEqual(merged, [FREE, FREE, FREE, OCCUPIED])
        self.assertEqual(conflicts, 0)
        self.assertEqual(sum(1 for v in merged if v == UNKNOWN), 0)


class TestConflictFraction(unittest.TestCase):
    def test_measured_against_shared_cells_not_the_whole_map(self):
        # Four cells; only two were seen by both, and one of those conflicts.
        first = [FREE, OCCUPIED, FREE, UNKNOWN]
        second = [FREE, FREE, UNKNOWN, UNKNOWN]
        _, conflicts = merge_grids([first, second])
        self.assertEqual(conflicts, 1)
        self.assertAlmostEqual(conflict_fraction(conflicts, [first, second]), 0.5)

    def test_no_shared_cells_is_no_fraction_rather_than_a_crash(self):
        first = [FREE, UNKNOWN]
        second = [UNKNOWN, FREE]
        self.assertEqual(conflict_fraction(0, [first, second]), 0.0)


if __name__ == "__main__":
    unittest.main()
