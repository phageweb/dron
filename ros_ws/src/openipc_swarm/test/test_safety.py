"""The safety filter, against the three approaches that actually happen.

The last test is the one that matters: a stepped simulation with the measured
braking behaviour of the machine, asserting that the pair never comes closer
than `d_safe`. That is K1 from `spec/roj/01_zadani_mapovani.md`, and it is the
only criterion in the swarm task with no tolerance.
"""

import math
import unittest

from openipc_swarm.safety import (
    AgentMotion,
    closest_approach,
    backoff_limit,
    braking_distance_m,
    deadlock_backoff,
    deadlock_backoffs,
    escape_limit,
    leads_away,
    speed_for_room,
    separation,
    speed_limits,
)

# From M1 re-measured on 2026-09-20, on the Pavo20 that actually loads: d_safe
# 1.56 m at 1 m/s, and the room a stop takes is the latency plus the braking
# distance, 1.00 * 0.408 + 1.001. The earlier 1.30 m and 0.77 m were the
# CineLog's, flown under a Pavo20 label - see workflow/troubleshooting.md.
D_SAFE_M = 1.56
STOPPING_ROOM_M = 0.408 + 1.001
MAX_SPEED_MPS = 1.0
# Deceleration implied by M1: 1.001 m from 1.0 m/s is v^2 / 2s = 0.50 m/s^2.
DECELERATION_MPS2 = 0.50


class TestSeparation(unittest.TestCase):
    def test_distance_is_three_dimensional(self):
        a = AgentMotion("v1", (0.0, 0.0, 1.0))
        b = AgentMotion("v2", (3.0, 4.0, 1.0))
        self.assertAlmostEqual(separation(a, b), 5.0)
        c = AgentMotion("v3", (0.0, 0.0, 3.0))
        self.assertAlmostEqual(separation(a, c), 2.0)

    def test_closest_approach_sees_the_middle_of_a_pass(self):
        # Crossing paths: far apart at both ends of the horizon, close in it.
        a = AgentMotion("v1", (-4.0, 0.0, 1.0), (4.0, 0.0, 0.0))
        b = AgentMotion("v2", (0.5, -4.0, 1.0), (0.0, 4.0, 0.0))
        at_end = separation(a, b, 2.0)
        nearest = closest_approach(a, b, 2.0)
        self.assertLess(nearest, at_end)


class TestSpeedLimits(unittest.TestCase):
    def test_far_apart_is_left_alone(self):
        agents = [AgentMotion("v1", (0.0, 0.0, 1.0), (0.5, 0.0, 0.0)),
                  AgentMotion("v2", (8.0, 0.0, 1.0), (0.0, 0.0, 0.0))]
        limits, interventions = speed_limits(
            agents, D_SAFE_M, MAX_SPEED_MPS, STOPPING_ROOM_M)
        self.assertEqual(interventions, [])
        self.assertEqual(set(limits.values()), {MAX_SPEED_MPS})

    def test_head_on_closes_to_a_stop(self):
        agents = [AgentMotion("v1", (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
                  AgentMotion("v2", (3.0, 0.0, 1.0), (-1.0, 0.0, 0.0))]
        limits, interventions = speed_limits(
            agents, D_SAFE_M, MAX_SPEED_MPS, STOPPING_ROOM_M)
        self.assertEqual(len(interventions), 1)
        self.assertEqual(interventions[0].action, "stop")
        self.assertEqual(limits["v1"], 0.0)
        self.assertEqual(limits["v2"], 0.0)

    def test_both_of_a_pair_are_limited_not_one(self):
        # A standing agent is limited too: it is half of the pair, and the
        # filter has no way to make the moving one give way on its own.
        agents = [AgentMotion("v1", (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
                  AgentMotion("v2", (3.2, 0.0, 1.0), (0.0, 0.0, 0.0))]
        limits, _ = speed_limits(
            agents, D_SAFE_M, MAX_SPEED_MPS, STOPPING_ROOM_M)
        self.assertLess(limits["v1"], MAX_SPEED_MPS)
        self.assertEqual(limits["v1"], limits["v2"])

    def test_catching_up_from_behind_is_caught(self):
        agents = [AgentMotion("v1", (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
                  AgentMotion("v2", (3.4, 0.0, 1.0), (0.2, 0.0, 0.0))]
        _, interventions = speed_limits(
            agents, D_SAFE_M, MAX_SPEED_MPS, STOPPING_ROOM_M)
        self.assertTrue(interventions)

    def test_three_converging_on_one_point(self):
        agents = [
            AgentMotion("v1", (-3.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
            AgentMotion("v2", (3.0, 0.0, 1.0), (-1.0, 0.0, 0.0)),
            AgentMotion("v3", (0.0, 3.0, 1.0), (0.0, -1.0, 0.0)),
        ]
        limits, interventions = speed_limits(
            agents, D_SAFE_M, MAX_SPEED_MPS, STOPPING_ROOM_M)
        self.assertEqual(len(interventions), 3)  # every pair
        for name in ("v1", "v2", "v3"):
            self.assertLess(limits[name], MAX_SPEED_MPS)

    def test_the_limit_tightens_as_they_close(self):
        def limit_at(gap):
            agents = [AgentMotion("v1", (0.0, 0.0, 1.0), (0.5, 0.0, 0.0)),
                      AgentMotion("v2", (gap, 0.0, 1.0), (-0.5, 0.0, 0.0))]
            limits, _ = speed_limits(
                agents, D_SAFE_M, MAX_SPEED_MPS, STOPPING_ROOM_M)
            return limits["v1"]

        # Closing at 1 m/s between them, so the 2 s prediction is 2 m ahead of
        # the present gap: these three are inside the band, near its top,
        # middle and bottom.
        self.assertGreater(limit_at(5.5), limit_at(5.0))
        self.assertGreater(limit_at(5.0), limit_at(4.6))


class TestDeadlock(unittest.TestCase):
    def test_one_of_two_stopped_agents_is_told_to_back_off(self):
        agents = [AgentMotion("v2", (0.0, 0.0, 1.0)),
                  AgentMotion("v1", (1.0, 0.0, 1.0))]
        limits = {"v1": 0.0, "v2": 0.0}
        self.assertEqual(deadlock_backoff(agents, limits, 2.0), "v1")

    def test_nobody_backs_off_when_they_are_apart(self):
        agents = [AgentMotion("v1", (0.0, 0.0, 1.0)),
                  AgentMotion("v2", (5.0, 0.0, 1.0))]
        limits = {"v1": 0.0, "v2": 0.0}
        self.assertIsNone(deadlock_backoff(agents, limits, 2.0))

    def test_every_jam_gets_a_backer(self):
        # Flight 5 of 2026-10-03: v1 freed every tick, v2 and v3 frozen.
        agents = [AgentMotion("v1", (0.0, 0.0, 1.0)),
                  AgentMotion("v2", (1.0, 0.0, 1.0)),
                  AgentMotion("v3", (6.0, 0.0, 1.0)),
                  AgentMotion("v4", (7.0, 0.0, 1.0))]
        limits = {n: 0.0 for n in ("v1", "v2", "v3", "v4")}
        self.assertEqual(deadlock_backoffs(agents, limits, 2.0), ["v1", "v3"])

    def test_a_chain_is_one_group(self):
        agents = [AgentMotion("v1", (0.0, 0.0, 1.0)),
                  AgentMotion("v2", (1.5, 0.0, 1.0)),
                  AgentMotion("v3", (3.0, 0.0, 1.0))]
        limits = {n: 0.0 for n in ("v1", "v2", "v3")}
        self.assertEqual(deadlock_backoffs(agents, limits, 2.0), ["v1"])

    def test_two_backers_share_the_room_between_them(self):
        agents = [AgentMotion("v1", (0.0, 0.0, 1.0)),
                  AgentMotion("v3", (2.0, 0.0, 1.0))]
        alone = backoff_limit(agents, {}, "v1", 0.78, 0.408, 0.5)
        shared = backoff_limit(agents, {}, "v1", 0.78, 0.408, 0.5,
                               also_moving=["v3"])
        self.assertLess(shared, alone)


class TestK1OnSyntheticTrajectories(unittest.TestCase):
    """The filter has to hold d_safe against a machine that obeys it late.

    The agents here do not jump to their commanded speed; they decelerate at
    the rate M1 measured, which is the whole reason the stop is ordered a
    stopping room early. Running this with an instant-response model would
    prove nothing about the real one.
    """

    def _fly(self, starts, velocities, seconds=20.0, dt=0.05):
        agents = [AgentMotion(name, position, velocity)
                  for name, position, velocity in zip(
                      ("v1", "v2", "v3"), starts, velocities)]
        wanted = {a.name: math.dist((0, 0, 0), a.velocity) for a in agents}
        heading = {a.name: tuple(v / max(wanted[a.name], 1e-9)
                                 for v in a.velocity) for a in agents}
        closest = float("inf")
        for _ in range(int(seconds / dt)):
            limits, _ = speed_limits(
                agents, D_SAFE_M, MAX_SPEED_MPS, STOPPING_ROOM_M)
            for agent in agents:
                speed = math.dist((0, 0, 0), agent.velocity)
                target = min(limits[agent.name], wanted[agent.name])
                # Obey with the machine's own lag rather than instantly.
                if speed > target:
                    speed = max(target, speed - DECELERATION_MPS2 * dt)
                else:
                    speed = min(target, speed + DECELERATION_MPS2 * dt)
                agent.velocity = tuple(h * speed for h in heading[agent.name])
                agent.position = tuple(p + v * dt for p, v
                                       in zip(agent.position, agent.velocity))
            for index, first in enumerate(agents):
                for second in agents[index + 1:]:
                    closest = min(closest, separation(first, second))
        return closest

    def test_head_on_at_full_speed_never_breaks_d_safe(self):
        closest = self._fly(
            starts=[(-5.0, 0.0, 1.0), (5.0, 0.0, 1.0)],
            velocities=[(1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)])
        self.assertGreaterEqual(closest, D_SAFE_M)

    def test_catch_up_never_breaks_d_safe(self):
        closest = self._fly(
            starts=[(0.0, 0.0, 1.0), (4.0, 0.0, 1.0)],
            velocities=[(1.0, 0.0, 0.0), (0.25, 0.0, 0.0)])
        self.assertGreaterEqual(closest, D_SAFE_M)

    def test_three_at_one_point_never_break_d_safe(self):
        closest = self._fly(
            starts=[(-4.0, 0.0, 1.0), (4.0, 0.0, 1.0), (0.0, 4.0, 1.0)],
            velocities=[(1.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, -1.0, 0.0)])
        self.assertGreaterEqual(closest, D_SAFE_M)


class TestSpeedForRoom(unittest.TestCase):
    def test_no_room_is_no_speed(self):
        self.assertEqual(speed_for_room(0.0, 0.408, 0.5), 0.0)
        self.assertEqual(speed_for_room(-0.2, 0.408, 0.5), 0.0)

    def test_plenty_of_room_is_the_cap(self):
        self.assertEqual(speed_for_room(5.0, 0.408, 0.5), 0.5)

    def test_the_speed_found_stops_inside_the_room(self):
        for room in (0.05, 0.2, 0.4, 0.6):
            v = speed_for_room(room, 0.408, 0.5)
            self.assertGreater(v, 0.0)
            self.assertLessEqual(v * 0.408 + braking_distance_m(v), room + 1e-9)
            # and not needlessly slower than that
            faster = v + 0.01
            self.assertGreater(faster * 0.408 + braking_distance_m(faster), room)


class TestBackoffLimit(unittest.TestCase):
    def test_the_measured_deadlock_gets_moving(self):
        # v2 and v3 as the second swarm flight left them: 1.39 m apart,
        # under a 1.41 m stop line, both stopped.
        agents = [AgentMotion("v2", (2.95, -1.75, 1.0), (0.0, 0.0, 0.0)),
                  AgentMotion("v3", (3.45, -0.45, 1.0), (0.0, 0.0, 0.0))]
        limit = backoff_limit(agents, {"v2": 0.0, "v3": 0.0}, "v2",
                              d_safe_m=0.78, latency_s=0.408,
                              max_speed_mps=0.5)
        self.assertGreater(limit, 0.0)
        self.assertLess(limit, 0.5)

    def test_at_d_safe_it_stays_put(self):
        agents = [AgentMotion("v1", (0.0, 0.0, 1.0), (0.0, 0.0, 0.0)),
                  AgentMotion("v2", (0.78, 0.0, 1.0), (0.0, 0.0, 0.0))]
        self.assertEqual(backoff_limit(agents, {}, "v1", 0.78, 0.408, 0.5),
                         0.0)

    def test_the_nearest_neighbour_sets_the_limit(self):
        far = [AgentMotion("v1", (0.0, 0.0, 1.0), (0, 0, 0)),
               AgentMotion("v2", (1.3, 0.0, 1.0), (0, 0, 0))]
        near = far + [AgentMotion("v3", (0.0, 0.9, 1.0), (0, 0, 0))]
        self.assertLess(backoff_limit(near, {}, "v1", 0.78, 0.408, 0.5),
                        backoff_limit(far, {}, "v1", 0.78, 0.408, 0.5))


class TestSpeedDependentTerms(unittest.TestCase):
    """d_safe has to follow the speed, or it stops a room-sized swarm dead."""

    def test_the_measured_points_come_back_unchanged(self):
        from openipc_swarm.safety import braking_distance_m
        self.assertAlmostEqual(braking_distance_m(0.25), 0.174)
        self.assertAlmostEqual(braking_distance_m(0.50), 0.426)
        self.assertAlmostEqual(braking_distance_m(1.00), 1.001)

    def test_between_them_it_interpolates(self):
        from openipc_swarm.safety import braking_distance_m
        middle = braking_distance_m(0.75)
        self.assertGreater(middle, 0.426)
        self.assertLess(middle, 1.001)

    def test_a_crawl_still_costs_something_to_stop(self):
        from openipc_swarm.safety import braking_distance_m
        self.assertGreater(braking_distance_m(0.1), 0.0)
        self.assertLess(braking_distance_m(0.1), 0.174)

    def test_the_stop_line_at_half_a_metre_per_second_fits_the_room(self):
        # The failure this exists for: at 1 m/s the stop line is about 3 m,
        # and three machines in a room 8 by 6 m are never that far apart, so
        # the filter ordered a permanent stop. At the 0.5 m/s they fly it has
        # to be something a room can hold.
        from openipc_swarm.safety import separation_terms
        d_safe, room = separation_terms(0.5, 0.06107, 0.012, 0.408)
        self.assertLess(d_safe + room, 1.5)
        fast_safe, fast_room = separation_terms(1.0, 0.06107, 0.012, 0.408)
        self.assertGreater(fast_safe + fast_room, 2.5)


class TestSlowBand(unittest.TestCase):
    def test_a_pair_standing_in_the_band_is_left_alone(self):
        agents = [AgentMotion("v1", (0.0, 0.0, 1.0), (0.0, 0.0, 0.0)),
                  AgentMotion("v2", (1.9, 0.0, 1.0), (0.0, 0.0, 0.0))]
        limits, interventions = speed_limits(agents, 0.78, 0.5, 0.63)
        self.assertEqual(limits, {"v1": 0.5, "v2": 0.5})
        self.assertEqual(interventions, [])

    def test_hover_jitter_is_not_closing(self):
        agents = [AgentMotion("v1", (0.0, 0.0, 1.0), (0.004, 0.0, 0.0)),
                  AgentMotion("v2", (1.46, 0.0, 1.0), (-0.003, 0.0, 0.0))]
        limits, _ = speed_limits(agents, 0.78, 0.5, 0.63)
        self.assertEqual(limits, {"v1": 0.5, "v2": 0.5})

    def test_a_pair_closing_in_the_band_is_slowed(self):
        agents = [AgentMotion("v1", (0.0, 0.0, 1.0), (0.3, 0.0, 0.0)),
                  AgentMotion("v2", (1.9, 0.0, 1.0), (0.0, 0.0, 0.0))]
        limits, _ = speed_limits(agents, 0.78, 0.5, 0.63)
        self.assertLess(limits["v1"], 0.5)

    def test_a_pair_separating_in_the_band_is_left_alone(self):
        agents = [AgentMotion("v1", (0.0, 0.0, 1.0), (-0.3, 0.0, 0.0)),
                  AgentMotion("v2", (1.9, 0.0, 1.0), (0.0, 0.0, 0.0))]
        limits, _ = speed_limits(agents, 0.78, 0.5, 0.63)
        self.assertEqual(limits["v1"], 0.5)


class TestEscapeInsideDSafe(unittest.TestCase):
    """v1 and v3, 0.67 m apart under a 0.78 m d_safe, for 899 ticks."""

    def pair(self):
        return [AgentMotion("v1", (0.0, 0.0, 1.0)),
                AgentMotion("v3", (0.67, 0.0, 1.0))]

    def test_a_target_away_lets_it_move(self):
        limit = escape_limit(self.pair(), "v1", (-2.0, 0.5), 0.78, 0.146,
                             0.408, 0.5)
        self.assertGreater(limit, 0.0)
        self.assertLessEqual(limit, 0.5)

    def test_a_target_towards_the_other_does_not(self):
        self.assertEqual(escape_limit(self.pair(), "v1", (3.0, 0.0), 0.78,
                                      0.146, 0.408, 0.5), 0.0)

    def test_no_target_no_move(self):
        self.assertEqual(escape_limit(self.pair(), "v1", None, 0.78, 0.146,
                                      0.408, 0.5), 0.0)

    def test_it_still_stops_short_of_contact(self):
        limit = escape_limit(self.pair(), "v1", (-2.0, 0.0), 0.78, 0.146,
                             0.408, 0.5)
        self.assertLessEqual(limit * 0.408 + braking_distance_m(limit),
                             0.67 - 0.146 + 1e-9)

    def test_away_means_away_from_every_close_neighbour(self):
        me = AgentMotion("v1", (0.0, 0.0, 1.0))
        east = AgentMotion("v2", (0.5, 0.0, 1.0))
        north = AgentMotion("v3", (0.0, 0.5, 1.0))
        self.assertTrue(leads_away(me, (-1.0, -1.0), [east, north]))
        self.assertFalse(leads_away(me, (-1.0, 1.0), [east, north]))

    def test_the_one_headed_away_backs_off(self):
        agents = self.pair()
        limits = {"v1": 0.0, "v3": 0.0}
        self.assertEqual(
            deadlock_backoffs(agents, limits, 1.41, preferred=["v3"]), ["v3"])


if __name__ == "__main__":
    unittest.main()
