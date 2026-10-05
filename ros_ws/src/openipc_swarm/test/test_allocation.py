"""Viewpoints along an opening, and four allocators over the same ones.

The fixture that matters is the one the flights kept producing: a single long
opening and three agents. One opening per agent leaves two of them idle; split
into viewpoints, it should give work to more than one.
"""

import itertools
import random
import unittest

from openipc_swarm.allocation import (
    ALLOCATORS,
    Candidate,
    allocate,
    allocate_hungarian,
    allocate_iterative,
    allocate_minpos,
    allocate_utility,
    expected_view,
    hungarian,
    viewpoint_candidates,
)
from openipc_swarm.assignment import Agent

UNKNOWN = -1
FREE = 0
WALL = 100
RESOLUTION_M = 0.1


def long_opening(cols=41, rows=15, known_rows=10):
    """Known floor below `known_rows`, unknown above: one opening 4 m long."""
    return [FREE if row < known_rows else UNKNOWN
            for row in range(rows) for _ in range(cols)]


def place(values, cols, cells, value):
    values = list(values)
    for col, row in cells:
        values[row * cols + col] = value
    return values


def run(method, values, cols, rows, agents, **kwargs):
    return allocate(method, values, cols, rows, agents, RESOLUTION_M, 0.0, 0.0,
                    clearance_cells=1, **kwargs)


class TestViewpoints(unittest.TestCase):
    def test_a_long_opening_gives_several_viewpoints_a_metre_apart(self):
        candidates = viewpoint_candidates(long_opening(), 41, 15,
                                          clearance_cells=1)
        self.assertGreaterEqual(len(candidates), 3)
        self.assertEqual({c.cluster_index for c in candidates}, {0})
        for a, b in itertools.combinations(candidates, 2):
            dist = ((a.cell[0] - b.cell[0]) ** 2
                    + (a.cell[1] - b.cell[1]) ** 2) ** 0.5
            self.assertGreaterEqual(dist, 10.0)

    def test_viewpoints_are_cells_of_the_opening_itself(self):
        for candidate in viewpoint_candidates(long_opening(), 41, 15,
                                              clearance_cells=1):
            self.assertEqual(candidate.cell[1], 9)

    def test_a_wall_hides_what_lies_behind_it(self):
        values = long_opening()
        open_view = expected_view(values, 41, 15, (20, 9), 30, 10, 96)
        walled = place(values, 41, [(c, 10) for c in range(41)], WALL)
        # The unknown row past the wall is still there; none of it is seen.
        self.assertGreater(len(open_view), 50)
        self.assertEqual(expected_view(walled, 41, 15, (20, 9), 30, 10, 96),
                         frozenset())

    def test_slivers_with_nothing_behind_them_are_not_viewpoints(self):
        # One unknown cell in a known room: a frontier of four cells round it,
        # and almost nothing to see. It is how a wall's face shows up.
        values = place([FREE] * (21 * 21), 21, [(10, 10)], UNKNOWN)
        self.assertEqual(
            viewpoint_candidates(values, 21, 21, clearance_cells=1,
                                 min_frontier_cells=1), [])


class TestAllocatorsOnOneLongOpening(unittest.TestCase):
    def test_every_allocator_gives_one_opening_to_more_than_one_agent(self):
        agents = [Agent("v1", (5, 2)), Agent("v2", (20, 2)),
                  Agent("v3", (35, 2))]
        for method in ALLOCATORS:
            with self.subTest(method=method):
                targets, _, _ = run(method, long_opening(), 41, 15, agents)
                self.assertGreaterEqual(len(targets), 2)
                cells = [t.cell for t in targets.values()]
                self.assertEqual(len(cells), len(set(cells)))

    def test_the_point_sent_is_the_cell_costed(self):
        targets, _, _ = run("utility", long_opening(), 41, 15,
                            [Agent("v1", (20, 2))])
        target = targets["v1"]
        self.assertAlmostEqual(target.point_m[0],
                               (target.cell[0] + 0.5) * RESOLUTION_M)
        self.assertAlmostEqual(target.point_m[1],
                               (target.cell[1] + 0.5) * RESOLUTION_M)

    def test_a_covered_room_leaves_everyone_without_a_target(self):
        for method in ALLOCATORS:
            targets, unassigned, _ = run(method, [FREE] * (41 * 15), 41, 15,
                                         [Agent("v1", (5, 2))])
            self.assertEqual(targets, {})
            self.assertEqual(unassigned, ["v1"])

    def test_an_unknown_method_is_refused(self):
        with self.assertRaises(ValueError):
            run("nearest", long_opening(), 41, 15, [Agent("v1", (5, 2))])

    def test_the_last_target_is_kept_against_a_slightly_nearer_one(self):
        # Facing the opening at (26, 2): the viewpoint at (30, 9) is 0.2 m
        # cheaper than the one at (20, 9) it was sent to last time.
        agents = [Agent("v1", (26, 2), 1.5708)]
        fresh, _, _ = run("iterative", long_opening(), 41, 15, agents)
        self.assertEqual(fresh["v1"].cell, (30, 9))
        held, _, _ = run("iterative", long_opening(), 41, 15, agents,
                         previous={"v1": (20, 9)})
        self.assertEqual(held["v1"].cell, (20, 9))

    def test_the_turn_counts(self):
        # Two openings either side, the same distance away: facing one of
        # them decides which it gets.
        cols, rows = 41, 5
        values = [UNKNOWN if col in (0, cols - 1) else FREE
                  for _ in range(rows) for col in range(cols)]
        east, _, _ = run("iterative", values, cols, rows,
                         [Agent("v1", (20, 2), 0.0)], min_gain_cells=1)
        west, _, _ = run("iterative", values, cols, rows,
                         [Agent("v1", (20, 2), 3.14159)], min_gain_cells=1)
        self.assertGreater(east["v1"].cell[0], 20)
        self.assertLess(west["v1"].cell[0], 20)


class TestAllocators(unittest.TestCase):
    def test_hungarian_beats_iterative_where_greedy_is_wrong(self):
        # v1 is cheapest at 0, but v2 can only usefully go to 0.
        costs = {("v1", 0): 1.0, ("v1", 1): 2.0,
                 ("v2", 0): 2.0, ("v2", 1): 10.0}
        self.assertEqual(allocate_iterative(["v1", "v2"], costs),
                         {"v1": 0, "v2": 1})
        self.assertEqual(allocate_hungarian(["v1", "v2"], costs, [0, 0], 0.0),
                         {"v1": 1, "v2": 0})

    def test_hungarian_lets_an_agent_wait_rather_than_go_where_it_cannot(self):
        costs = {("v1", 0): 1.0, ("v2", 0): 0.5}
        self.assertEqual(allocate_hungarian(["v1", "v2"], costs, [0], 0.0),
                         {"v2": 0})

    def test_minpos_sends_the_second_agent_where_it_is_second(self):
        # v1 is nearest everywhere, so v2 ranks second everywhere and goes
        # to the nearest it can have.
        costs = {("v1", 0): 1.0, ("v1", 1): 1.5, ("v1", 2): 3.0,
                 ("v2", 0): 4.0, ("v2", 1): 2.0, ("v2", 2): 3.5}
        self.assertEqual(allocate_minpos(["v1", "v2"], costs),
                         {"v1": 0, "v2": 1})
        # With a third agent nearer to 1, v2 is second only at 2.
        costs.update({("v3", 0): 5.0, ("v3", 1): 0.5, ("v3", 2): 9.0})
        chosen = allocate_minpos(["v1", "v2", "v3"], costs)
        self.assertEqual(chosen, {"v1": 0, "v2": 2, "v3": 1})

    def test_utility_does_not_send_two_agents_to_look_at_the_same_thing(self):
        same = frozenset((c, 0) for c in range(40))
        other = frozenset((c, 5) for c in range(30))
        candidates = [Candidate((0, 0), 0, same), Candidate((1, 0), 0, same),
                      Candidate((9, 9), 1, other)]
        costs = {("v1", 0): 1.0, ("v1", 1): 1.1, ("v1", 2): 6.0,
                 ("v2", 0): 1.1, ("v2", 1): 1.0, ("v2", 2): 6.0}
        chosen = allocate_utility(["v1", "v2"], costs, candidates, 0.01,
                                  2.0, min_gain_cells=10)
        self.assertEqual(sorted(chosen.values())[-1], 2)
        # The iterative method has no idea and sends both to the same view.
        self.assertEqual(sorted(allocate_iterative(["v1", "v2"], costs)
                                .values()), [0, 1])

    def test_utility_leaves_an_agent_idle_rather_than_duplicate(self):
        same = frozenset((c, 0) for c in range(40))
        candidates = [Candidate((0, 0), 0, same), Candidate((1, 0), 0, same)]
        costs = {("v1", 0): 1.0, ("v2", 1): 1.0}
        self.assertEqual(len(allocate_utility(["v1", "v2"], costs, candidates,
                                              0.01, 2.0, 10)), 1)


class TestHungarian(unittest.TestCase):
    def test_matches_brute_force(self):
        rng = random.Random(4)
        for _ in range(200):
            n = rng.randint(1, 4)
            m = rng.randint(n, 6)
            matrix = [[rng.uniform(-5, 10) for _ in range(m)] for _ in range(n)]
            columns = hungarian(matrix)
            self.assertEqual(len(set(columns)), n)
            best = min(sum(matrix[i][p[i]] for i in range(n))
                       for p in itertools.permutations(range(m), n))
            self.assertAlmostEqual(
                sum(matrix[i][columns[i]] for i in range(n)), best)

    def test_more_rows_than_columns_is_refused(self):
        with self.assertRaises(ValueError):
            hungarian([[1.0], [2.0]])


if __name__ == "__main__":
    unittest.main()
