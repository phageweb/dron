"""Three agents, and no two of them sent to the same opening.

The fixture is a corridor: five rows of known free floor with unknown space off
both ends, so there are exactly two frontiers and they are as far apart as the
room allows. That makes the assignment's job unambiguous and its failure -
sending both agents to the same end - visible.
"""

import unittest

from openipc_swarm.assignment import Agent, assign_targets, work_overlap

UNKNOWN = -1
FREE = 0

COLS, ROWS = 21, 5
RESOLUTION_M = 0.1
ORIGIN_X_M = 0.0
ORIGIN_Y_M = 0.0


def corridor():
    """Free floor in columns 1..19, unknown at both ends."""
    values = []
    for row in range(ROWS):
        for col in range(COLS):
            values.append(UNKNOWN if col in (0, COLS - 1) else FREE)
    return values


class TestAssignment(unittest.TestCase):
    def test_two_agents_take_one_end_each(self):
        agents = [Agent("v1", (2, 2)), Agent("v2", (18, 2))]
        assignment, unassigned = assign_targets(
            corridor(), COLS, ROWS, agents, RESOLUTION_M,
            ORIGIN_X_M, ORIGIN_Y_M, clearance_cells=1)
        self.assertEqual(unassigned, [])
        self.assertEqual(len(assignment), 2)
        self.assertNotEqual(assignment["v1"].cluster_index,
                            assignment["v2"].cluster_index)
        # Each took the end it was standing next to.
        self.assertLess(assignment["v1"].cell[0], COLS // 2)
        self.assertGreater(assignment["v2"].cell[0], COLS // 2)

    def test_no_opening_is_given_to_two_agents(self):
        # Three agents, two openings: somebody must go without, and nobody may
        # be sent where another agent is already going.
        agents = [Agent("v1", (2, 2)), Agent("v2", (18, 2)), Agent("v3", (10, 2))]
        assignment, unassigned = assign_targets(
            corridor(), COLS, ROWS, agents, RESOLUTION_M,
            ORIGIN_X_M, ORIGIN_Y_M, clearance_cells=1)
        self.assertEqual(len(unassigned), 1)
        taken = [target.cluster_index for target in assignment.values()]
        self.assertEqual(len(taken), len(set(taken)))

    def test_the_nearer_agent_gets_the_nearer_opening(self):
        # v3 stands next to the left end and v1 in the middle, so the left
        # opening should go to v3 even though v1 is listed first.
        agents = [Agent("v1", (10, 2)), Agent("v3", (2, 2))]
        assignment, _ = assign_targets(
            corridor(), COLS, ROWS, agents, RESOLUTION_M,
            ORIGIN_X_M, ORIGIN_Y_M, clearance_cells=1)
        self.assertLess(assignment["v3"].cell[0], assignment["v1"].cell[0])

    def test_a_fully_known_map_leaves_everyone_unassigned(self):
        # No unknown cells means no frontiers: the room is covered, and that
        # is a normal end state rather than a failure.
        values = [FREE] * (COLS * ROWS)
        agents = [Agent("v1", (2, 2)), Agent("v2", (18, 2))]
        assignment, unassigned = assign_targets(
            values, COLS, ROWS, agents, RESOLUTION_M,
            ORIGIN_X_M, ORIGIN_Y_M, clearance_cells=1)
        self.assertEqual(assignment, {})
        self.assertEqual(sorted(unassigned), ["v1", "v2"])

    def test_targets_carry_a_point_in_metres_not_only_a_cell(self):
        agents = [Agent("v1", (2, 2))]
        assignment, _ = assign_targets(
            corridor(), COLS, ROWS, agents, RESOLUTION_M,
            ORIGIN_X_M, ORIGIN_Y_M, clearance_cells=1)
        x, y = assignment["v1"].point_m
        self.assertGreaterEqual(x, 0.0)
        self.assertLessEqual(x, COLS * RESOLUTION_M)
        self.assertGreater(assignment["v1"].cost_m, 0.0)


class TestWorkOverlap(unittest.TestCase):
    def test_no_overlap_when_each_cell_had_one_first_seer(self):
        self.assertEqual(work_overlap({(0, 0): ["v1"], (1, 0): ["v2"]}), 0.0)

    def test_overlap_counts_cells_two_agents_reached_together(self):
        seen = {(0, 0): ["v1"], (1, 0): ["v1", "v2"],
                (2, 0): ["v2"], (3, 0): ["v1", "v3"]}
        self.assertAlmostEqual(work_overlap(seen), 0.5)

    def test_the_same_agent_twice_is_not_an_overlap(self):
        self.assertEqual(work_overlap({(0, 0): ["v1", "v1"]}), 0.0)

    def test_nothing_seen_is_no_overlap_rather_than_a_crash(self):
        self.assertEqual(work_overlap({}), 0.0)


if __name__ == "__main__":
    unittest.main()
