"""Regressions for unreachable corners, missed entrances and starvation."""

import math
import unittest
import random

from openipc_cinewhoop_demo.grid_helpers import (
    corridor_is_clear, escape_waypoint, navigation_blocked, reachability,
    visible_carrot,
)
from openipc_swarm.allocation import Candidate, allocate, allocate_utility, travel_costs
from openipc_swarm.assignment import Agent, Target
from openipc_swarm.exploration import ExplorationMemory
from openipc_swarm.passages import Reservations


class TestSafeExploration(unittest.TestCase):
    def test_navigation_mask_matches_full_disc_on_random_maps(self):
        rng = random.Random(42)
        cols, rows, radius = 19, 17, 3
        values = [rng.choice([0, 0, 0, -1, 50, 100])
                  for _ in range(cols*rows)]
        actual = navigation_blocked(values, cols, rows, radius)
        expected = set()
        for r in range(rows):
            for c in range(cols):
                if any(not (0 <= c+dc < cols and 0 <= r+dr < rows)
                       or not 0 <= values[(r+dr)*cols+c+dc] < 50
                       for dc in range(-radius, radius+1)
                       for dr in range(-radius, radius+1)
                       if dc*dc+dr*dr <= radius*radius):
                    expected.add((c, r))
        self.assertEqual(actual, expected)

    def test_frontier_is_observed_from_known_clear_floor(self):
        cols = rows = 41
        values = [0 if r < 25 else -1 for r in range(rows) for c in range(cols)]
        targets, _, candidates = allocate(
            'utility', values, cols, rows, [Agent('v1', (20, 10))],
            .1, 0., 0., 4, safe_viewpoints=True)
        self.assertTrue(targets)
        self.assertTrue(candidates)
        blocked = navigation_blocked(values, cols, rows, 4)
        for candidate in candidates:
            self.assertNotIn(candidate.cell, blocked)
            self.assertLessEqual(candidate.cell[1], 20)
        for target in targets.values():
            self.assertTrue(all(cell not in blocked for cell in target.route))
            self.assertIsNotNone(visible_carrot(
                target.route, values, cols, rows, .1, 0., 0., 2., .33335))

    def test_unknown_slots_are_not_routes_for_the_body(self):
        values = [-1] * (30 * 30)
        for r in range(5, 25):
            for c in range(10, 16):
                values[r * 30 + c] = 0
        blocked = navigation_blocked(values, 30, 30, 4)
        distance, _ = reachability(values, 30, 30, (12, 8), 4, blocked=blocked)
        self.assertNotIn((12, 20), distance)

    def test_carrot_does_not_skip_obstacles_near_start(self):
        values = [0] * 900
        values[10 * 30 + 9] = 100
        route = [(c, 10) for c in range(10, 25)]
        self.assertIsNone(visible_carrot(
            route, values, 30, 30, .1, 0., 0., 2., .33))

    def test_empty_carrot_has_no_unchecked_destination(self):
        self.assertIsNone(visible_carrot([], [0]*900, 30, 30, .1, 0., 0., 2., .33))

    def test_exact_corridor_uses_cell_faces_and_actual_pose(self):
        values = [100 if c == 10 else 0 for r in range(30) for c in range(30)]
        # The wall begins at x=1.0, so x=.65 is clear; x=.68 is not.
        self.assertTrue(corridor_is_clear(values, 30, 30, .1, 0., 0.,
                                         (.65, 1.), (.65, 2.), .33335))
        self.assertFalse(corridor_is_clear(values, 30, 30, .1, 0., 0.,
                                          (.68, 1.), (.68, 2.), .33335))

    def test_recovery_leaves_margin_without_approaching_wall(self):
        values = [100 if c == 10 else 0 for r in range(30) for c in range(30)]
        self.assertTrue(corridor_is_clear(values, 30, 30, .1, 0., 0.,
                                         (.8, 1.), (.5, 1.), .33335, .1))
        self.assertFalse(corridor_is_clear(values, 30, 30, .1, 0., 0.,
                                          (.8, 1.), (.85, 1.), .33335, .1))
        self.assertFalse(corridor_is_clear(values, 30, 30, .1, 0., 0.,
                                          (.95, 1.), (.5, 1.), .33335, .1))

    def test_recovery_can_choose_a_direction_outside_the_goal_route(self):
        values = [100 if c == 10 else 0 for r in range(30) for c in range(30)]
        mask = navigation_blocked(values, 30, 30, 4)
        point = escape_waypoint(values, 30, 30, .1, 0., 0., (.8, 1.5),
                                .33335, .1, mask)
        self.assertIsNotNone(point)
        self.assertLess(point[0], .8)
        self.assertTrue(corridor_is_clear(values, 30, 30, .1, 0., 0.,
                                         (.8, 1.5), point, .33335, .1))

    def test_own_cell_beside_a_pillar_is_not_a_carrot(self):
        # World 2, 2026-10-04: 0.35 m off a pillar, 0.32 m off its cell. Only
        # the vehicle's own cell centre was clear, 4 cm away, and the autonomy
        # held on it as reached for 97 s.
        values = [0] * 900
        values[13 * 30 + 18] = 100
        start = (1.48, 1.33)
        route = [(14, 13), (15, 14), (16, 15), (17, 16), (17, 17), (17, 18)]
        near = visible_carrot(route, values, 30, 30, .1, 0., 0., 2., .33335,
                              start_m=start, escape_radius_m=.1)
        self.assertLess(abs(near[0] - start[0]) + abs(near[1] - start[1]), .1)
        self.assertIsNone(visible_carrot(
            route, values, 30, 30, .1, 0., 0., 2., .33335, start_m=start,
            escape_radius_m=.1, min_step_m=.2))
        mask = navigation_blocked(values, 30, 30, 4)
        point = escape_waypoint(values, 30, 30, .1, 0., 0., start, .33335,
                                .1, mask, min_step=.2)
        self.assertGreaterEqual(math.dist(start, point), .2)
        self.assertTrue(corridor_is_clear(values, 30, 30, .1, 0., 0.,
                                         start, point, .33335, .1))

    def test_a_near_route_end_is_still_the_carrot(self):
        values = [0] * 900
        start = (1.48, 1.33)
        point = visible_carrot([(14, 13), (15, 13)], values, 30, 30, .1, 0.,
                               0., 2., .33335, start_m=start, min_step_m=.2)
        self.assertAlmostEqual(point[0], 1.55)

    def test_capsule_cannot_cut_through_a_diagonal_corner(self):
        values = [0] * 900
        values[10*30+10] = 100
        self.assertFalse(corridor_is_clear(values, 30, 30, .1, 0., 0.,
                                          (.5, 1.3), (1.3, .5), .2))


class TestExplorationMemory(unittest.TestCase):
    def setUp(self):
        self.memory = ExplorationMemory(overdue_s=30, stalled_s=10)
        self.agents = [Agent('v1', (0, 0))]
        self.candidates = [Candidate((10, 0), 0, frozenset(range(20))),
                           Candidate((50, 0), 1, frozenset(range(20, 40)))]
        self.routes = {('v1', j): [(i, 0) for i in range(c.cell[0]+1)]
                       for j, c in enumerate(self.candidates)}
        self.costs = {('v1', 0): 1., ('v1', 1): 8.}

    def adjust(self, now):
        return self.memory.costs(now, self.candidates, self.costs,
                                 self.agents, self.routes, .1)

    def test_assignment_alone_does_not_reset_age(self):
        self.adjust(0)
        t = Target(1, (50, 0), (5., 0.), 8.)
        t.route = self.routes['v1', 1]
        self.memory.assigned(5, {'v1': t}, .1)
        self.assertEqual(self.memory.regions[1]['since'], 0)

    def test_visited_near_region_yields_to_old_remote_region(self):
        self.adjust(0)
        self.agents[0].cell = (10, 0)
        adjusted = self.adjust(31)
        chosen = allocate_utility(['v1'], adjusted, self.candidates, .01, 2., 10)
        self.assertEqual(chosen, {'v1': 1})

    def test_stalled_pair_is_retried_after_cooldown(self):
        self.adjust(0)
        t = Target(1, (50, 0), (5., 0.), 8.)
        t.route = self.routes['v1', 1]
        self.memory.assigned(0, {'v1': t}, .1)
        self.assertNotIn(('v1', 1), self.adjust(11))
        self.memory.assigned(11, {}, .1)
        self.assertNotIn(('v1', 1), self.adjust(20))
        self.assertIn(('v1', 1), self.adjust(37))

    def test_shorter_route_keeps_assignment_alive(self):
        self.adjust(0)
        t = Target(1, (50, 0), (5., 0.), 8.)
        t.route = self.routes['v1', 1]
        self.memory.assigned(0, {'v1': t}, .1)
        self.routes['v1', 1] = self.routes['v1', 1][5:]
        self.assertIn(('v1', 1), self.adjust(9))
        self.assertIn(('v1', 1), self.adjust(15))
        self.assertNotIn(('v1', 0), self.adjust(15))

    def test_a_late_agent_keeps_its_region_against_an_overdue_one(self):
        self.adjust(0)
        t = Target(0, (10, 0), (1., 0.), 1.)
        t.route = self.routes['v1', 0]
        self.memory.assigned(0, {'v1': t}, .1, present={'v1'})
        # One tick with v1's state late: not planned, not given up.
        self.memory.assigned(1, {}, .1, present=set())
        self.routes['v1', 0] = self.routes['v1', 0][5:]
        adjusted = self.adjust(31)
        self.assertIn(('v1', 0), adjusted)
        self.assertNotIn(('v1', 1), adjusted)

    def test_frontier_drift_preserves_age(self):
        self.adjust(0)
        self.candidates[1].cell = (52, 1)
        self.adjust(20)
        self.assertEqual(self.memory.regions[1]['since'], 0)

    def test_arrived_view_does_not_keep_claiming_the_agent(self):
        self.agents[0].cell = (10, 0)
        self.assertIn(('v1', 0), self.adjust(0))
        self.assertNotIn(('v1', 0), self.adjust(3))
        self.assertIn(('v1', 1), self.adjust(3))
        # A changed view is fresh work, not a permanent spatial blacklist.
        self.candidates[0].seen = frozenset(range(21))
        self.assertIn(('v1', 0), self.adjust(4))


class TestDoorAdmission(unittest.TestCase):
    def test_reservation_search_finds_an_alternative_route(self):
        values = [0] * (21 * 21)
        forbidden = {(10, r) for r in range(8, 13)}
        routes = {}
        costs = travel_costs(values, 21, 21, [Agent('v1', (5, 10))],
                             [Candidate((15, 10), 0, frozenset())],
                             .1, 0., 0., 1, forbidden={'v1': forbidden},
                             routes=routes)
        self.assertIn(('v1', 0), costs)
        self.assertTrue(forbidden.isdisjoint(routes['v1', 0]))
        self.assertGreater(len(routes['v1', 0]), 11)

    def test_first_tick_admits_only_one_contender(self):
        reservations = Reservations()
        door = {(5, 5): {(5, 5), (5, 6)}}
        routes = {'v1': [(4, 5), (5, 5), (6, 5)],
                  'v2': [(6, 5), (5, 5), (4, 5)]}
        reservations.update(0, door, routes, {'v1': (4, 5), 'v2': (6, 5)})
        self.assertEqual(sum(reservations.permitted(n, r)
                             for n, r in routes.items()), 1)

    def test_timeout_never_releases_an_occupied_door(self):
        reservations = Reservations(max_hold_s=1)
        door = {(5, 5): {(5, 5), (5, 6)}}
        reservations.update(0, door, {'v1': [(5, 5)]}, {'v1': (5, 5)})
        reservations.update(5, door, {'v2': [(5, 5)]},
                            {'v1': (5, 5), 'v2': (9, 5)})
        self.assertEqual(reservations.holder((5, 5)), 'v1')
