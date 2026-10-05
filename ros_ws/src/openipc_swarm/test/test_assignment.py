"""Three agents, and no two of them sent to the same opening.

The fixture is a corridor: five rows of known free floor with unknown space off
both ends, so there are exactly two frontiers and they are as far apart as the
room allows. That makes the assignment's job unambiguous and its failure -
sending both agents to the same end - visible.
"""

import math
import unittest

from openipc_swarm.assignment import (
    Agent,
    assign_targets,
    spread_targets,
    work_overlap,
)

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
        # The centre of the very cell the cost was computed for.
        col, row = assignment["v1"].cell
        self.assertAlmostEqual(x, (col + 0.5) * RESOLUTION_M)
        self.assertAlmostEqual(y, (row + 0.5) * RESOLUTION_M)
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


class TestSpreadTargets(unittest.TestCase):
    """Where an agent goes when R5 has no opening left for it."""

    def room(self, cols=30, rows=30):
        return [FREE] * (cols * rows)

    def spread(self, agents, names, taken=(), spread_m=1.5, cols=30, rows=30):
        return spread_targets(self.room(cols, rows), cols, rows, agents,
                              taken, names, RESOLUTION_M, ORIGIN_X_M,
                              ORIGIN_Y_M, clearance_cells=1, spread_m=spread_m)

    def test_it_moves_away_from_the_agent_next_to_it(self):
        agents = [Agent("v1", (15, 15)), Agent("v2", (16, 15))]
        target = self.spread(agents, ["v2"])["v2"]
        self.assertGreaterEqual(math.dist(target.cell, (15, 15)), 15 - 1e-9)

    def test_far_enough_is_enough(self):
        # Already 2 m from the other agent with spread at 1.5 m: stay put
        # rather than cross the room for distance that buys nothing.
        agents = [Agent("v1", (5, 15)), Agent("v2", (25, 15))]
        target = self.spread(agents, ["v2"])["v2"]
        self.assertEqual(target.cell, (25, 15))

    def test_two_spreading_agents_do_not_pick_the_same_corner(self):
        agents = [Agent("v1", (15, 15)), Agent("v2", (14, 15)),
                  Agent("v3", (16, 15))]
        chosen = self.spread(agents, ["v2", "v3"])
        self.assertGreaterEqual(
            math.dist(chosen["v2"].cell, chosen["v3"].cell), 15 - 1e-9)

    def test_an_assigned_opening_counts_as_taken(self):
        agents = [Agent("v1", (2, 15)), Agent("v2", (15, 15))]
        target = self.spread(agents, ["v2"], taken=[(28, 15)])["v2"]
        self.assertGreaterEqual(math.dist(target.cell, (28, 15)), 15 - 1e-9)

    def test_only_the_named_agents_get_one(self):
        agents = [Agent("v1", (15, 15)), Agent("v2", (16, 15))]
        self.assertEqual(list(self.spread(agents, ["v1"])), ["v1"])

    def test_away_is_never_past_a_close_neighbour(self):
        # v2 west of v3 and close: whatever v2 is sent to must be west of it,
        # even though the far east of the room is further from everyone.
        agents = [Agent("v1", (2, 2)), Agent("v2", (10, 15)),
                  Agent("v3", (20, 15))]
        target = spread_targets(self.room(), 30, 30, agents, (), ["v2"],
                                RESOLUTION_M, 0.0, 0.0, clearance_cells=1,
                                spread_m=3.0, close_m=1.41)["v2"]
        self.assertLess(target.cell[0], 10)

    def test_it_never_targets_a_wall(self):
        cols = rows = 12
        values = self.room(cols, rows)
        for row in range(rows):
            values[row * cols + 6] = 100
        chosen = spread_targets(values, cols, rows,
                                [Agent("v1", (2, 6)), Agent("v2", (3, 6))],
                                (), ["v2"], RESOLUTION_M, 0.0, 0.0,
                                clearance_cells=1, spread_m=2.0)
        self.assertLess(chosen["v2"].cell[0], 5)

    def test_the_route_runs_from_the_agent_to_the_place(self):
        # The coordinator steers along it (`carrot`), so it has to be there
        # and has to be walkable: start on the agent, end on the target,
        # one cell per step.
        agents = [Agent("v1", (15, 15)), Agent("v2", (16, 15))]
        target = self.spread(agents, ["v2"])["v2"]
        self.assertEqual(target.route[0], (16, 15))
        self.assertEqual(target.route[-1], target.cell)
        for a, b in zip(target.route, target.route[1:]):
            self.assertLessEqual(max(abs(a[0] - b[0]), abs(a[1] - b[1])), 1)


if __name__ == "__main__":
    unittest.main()
