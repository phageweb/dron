"""The barrier filter: closest safe velocity, and two agents that pass."""

import math
import unittest

from openipc_cinewhoop_demo.velocity_barrier import (
    barrier_half_planes,
    closest_feasible,
    filter_velocity,
    half_planes_body,
    nominal_in_room,
    wall_half_planes,
)

D_SAFE = 0.78


def step(positions, velocities, dt):
    return [(p[0] + v[0] * dt, p[1] + v[1] * dt)
            for p, v in zip(positions, velocities)]


class TestHalfPlanes(unittest.TestCase):
    def test_far_neighbours_do_not_constrain(self):
        self.assertEqual(barrier_half_planes((0, 0), [(5, 0)], D_SAFE), [])

    def test_closing_is_allowed_far_and_forbidden_at_d_safe(self):
        (far,) = barrier_half_planes((0, 0), [(2.0, 0)], D_SAFE)
        (near,) = barrier_half_planes((0, 0), [(D_SAFE, 0)], D_SAFE)
        (inside,) = barrier_half_planes((0, 0), [(0.5, 0)], D_SAFE)
        # Normal points away from the neighbour: -x.
        self.assertAlmostEqual(far[0], -1.0)
        self.assertLess(far[2], -0.25)         # may still close at 2 m
        self.assertAlmostEqual(near[2], 0.0)   # may not close at all
        self.assertGreater(inside[2], 0.0)     # must open the gap


class TestFilter(unittest.TestCase):
    def test_a_safe_command_passes_untouched(self):
        planes = barrier_half_planes((0, 0), [(2.5, 0)], D_SAFE)
        self.assertEqual(filter_velocity((0.3, 0.0), planes), ((0.3, 0.0), "free"))

    def test_the_closing_part_is_removed_and_the_rest_kept(self):
        planes = barrier_half_planes((0, 0), [(D_SAFE, 0)], D_SAFE)
        v = closest_feasible((0.4, 0.3), planes)
        assert v is not None
        self.assertAlmostEqual(v[0], 0.0)
        self.assertAlmostEqual(v[1], 0.3)

    def test_two_neighbours_give_the_corner(self):
        planes = barrier_half_planes((0, 0), [(D_SAFE, 0), (0, D_SAFE)], D_SAFE)
        v = closest_feasible((0.4, 0.4), planes)
        assert v is not None
        self.assertAlmostEqual(v[0], 0.0)
        self.assertAlmostEqual(v[1], 0.0)

    def test_never_faster_than_asked(self):
        planes = barrier_half_planes((0, 0), [(0.9, 0.1)], D_SAFE)
        v, _ = filter_velocity((0.5, 0.0), planes)
        self.assertLessEqual(math.hypot(*v), 0.5 + 1e-9)

    def test_head_on_agents_pass_each_other_by_the_right(self):
        # The case the scalar limit cannot solve: two agents flying at each
        # other along one line, each wanting the other's position.
        positions = [(-1.5, 0.0), (1.5, 0.0)]
        goals = [(1.5, 0.0), (-1.5, 0.0)]
        closest = 10.0
        for _ in range(600):
            velocities = []
            for i, me in enumerate(positions):
                other = positions[1 - i]
                to_goal = (goals[i][0] - me[0], goals[i][1] - me[1])
                d = math.hypot(*to_goal)
                nominal = ((0.4 * to_goal[0] / d, 0.4 * to_goal[1] / d)
                           if d > 0.05 else (0.0, 0.0))
                planes = barrier_half_planes(me, [other], D_SAFE)
                velocities.append(filter_velocity(nominal, planes)[0])
            positions = step(positions, velocities, 0.05)
            closest = min(closest, math.dist(*positions))
        self.assertGreater(closest, D_SAFE - 0.05)
        # Both got past: each is now on the side it was heading to.
        self.assertGreater(positions[0][0], 0.5)
        self.assertLess(positions[1][0], -0.5)

    def test_three_and_four_agents_swap_through_the_centre(self):
        # Every agent heads for the point opposite it, so they all meet in
        # the middle at once - the arrangement in which a barrier filter with
        # no rule for choosing a side stands still for good.
        for n in (3, 4):
            positions = [(1.5 * math.cos(2 * math.pi * i / n),
                          1.5 * math.sin(2 * math.pi * i / n)) for i in range(n)]
            goals = [(-x, -y) for x, y in positions]
            closest = 10.0
            for _ in range(1200):
                velocities = []
                for i, me in enumerate(positions):
                    to_goal = (goals[i][0] - me[0], goals[i][1] - me[1])
                    d = math.hypot(*to_goal)
                    nominal = ((0.4 * to_goal[0] / d, 0.4 * to_goal[1] / d)
                               if d > 0.05 else (0.0, 0.0))
                    planes = barrier_half_planes(
                        me, [o for j, o in enumerate(positions) if j != i],
                        D_SAFE)
                    velocities.append(filter_velocity(nominal, planes)[0])
                positions = step(positions, velocities, 0.05)
                closest = min([closest] + [
                    math.dist(positions[i], positions[j])
                    for i in range(n) for j in range(i)])
            with self.subTest(agents=n):
                self.assertGreater(closest, D_SAFE - 0.02)
                for p, g in zip(positions, goals):
                    self.assertLess(math.dist(p, g), 0.1)

    def test_with_latency_and_lag_a_head_on_pair_stays_apart(self):
        # The vehicle as flown: commands 0.4 s late, velocity following them
        # with a 0.35 s lag, half-planes refreshed every 0.2 s. At gamma 2
        # this model closes a head-on pair to 0.36 m; the flight did 0.39.
        dt, delay, tau, period = 0.02, 0.4, 0.35, 0.2
        positions = [(0.0, -1.8), (0.0, 1.8)]
        goals = [(0.0, 1.8), (0.0, -1.8)]
        velocities = [(0.0, 0.0)] * 2
        queue, commands, planes = [], [(0.0, 0.0)] * 2, [[], []]
        closest = 10.0
        for k in range(int(40 / dt)):
            if k % int(period / dt) == 0:
                planes = [barrier_half_planes(positions[i], [positions[1 - i]],
                                              D_SAFE) for i in range(2)]
            wanted = []
            for i, me in enumerate(positions):
                to_goal = (goals[i][0] - me[0], goals[i][1] - me[1])
                d = math.hypot(*to_goal)
                nominal = ((0.5 * to_goal[0] / d, 0.5 * to_goal[1] / d)
                           if d > 0.05 else (0.0, 0.0))
                wanted.append(filter_velocity(nominal, planes[i])[0])
            queue.append(wanted)
            if len(queue) > int(delay / dt):
                commands = queue.pop(0)
            velocities = [(v[0] + (c[0] - v[0]) * dt / tau,
                           v[1] + (c[1] - v[1]) * dt / tau)
                          for v, c in zip(velocities, commands)]
            positions = step(positions, velocities, dt)
            closest = min(closest, math.dist(*positions))
        self.assertGreater(closest, D_SAFE)
        for p, g in zip(positions, goals):
            self.assertLess(math.dist(p, g), 0.3)


def corridor_scan(y_body, yaw, half_width, n=360):
    """A 360° scan of two walls at room y = ±half_width, from an agent at
    room height y_body facing `yaw`, sensor at the body centre."""
    ranges = []
    for k in range(n):
        bearing = -math.pi + 2 * math.pi * k / n
        direction = math.sin(yaw + bearing)
        if abs(direction) < 1e-6:
            ranges.append(float("inf"))
            continue
        wall = half_width if direction > 0 else -half_width
        ranges.append((wall - y_body) / direction)
    return ranges, -math.pi, 2 * math.pi / n


class TestWalls(unittest.TestCase):
    def test_a_wall_beside_is_one_plane_pointing_away(self):
        # Wall 0.5 m to the right (body -y), nothing else in range.
        ranges = [float("inf")] * 360
        ranges[90] = 0.5                    # bearing -90°
        (plane,) = wall_half_planes(ranges, -math.pi, math.radians(1.0),
                                    0.05, 12.0, sensor_offset=(0.0, 0.0))
        self.assertAlmostEqual(plane[0], 0.0, places=6)
        self.assertAlmostEqual(plane[1], 1.0, places=6)
        self.assertAlmostEqual(plane[2], -0.2, places=6)  # may close at 0.2

    def test_far_returns_and_bad_values_give_nothing(self):
        ranges = [5.0, float("nan"), 0.01] + [float("inf")] * 357
        self.assertEqual(wall_half_planes(ranges, -math.pi,
                                          math.radians(1.0), 0.05, 12.0), [])

    def test_the_right_hand_rule_stops_at_a_wall_on_the_right(self):
        # Neighbour straight ahead at d_safe, wall 0.3 m to the right: the
        # right-hand rule may not push the agent into it.
        planes = barrier_half_planes((0, 0), [(D_SAFE, 0)], D_SAFE)
        ranges = [float("inf")] * 360
        ranges[90] = 0.30
        walls = wall_half_planes(ranges, -math.pi, math.radians(1.0), 0.05,
                                 12.0, sensor_offset=(0.0, 0.0))
        v, _ = filter_velocity((0.4, 0.0), planes, 0.25, walls=walls)
        self.assertGreaterEqual(v[1], -1e-9)

    def test_a_wall_never_slows_what_the_autonomy_asked(self):
        # Flying straight at a wall 0.35 m ahead is the autonomy's call.
        planes = barrier_half_planes((0, 0), [(0, 1.0)], D_SAFE)
        ranges = [float("inf")] * 360
        ranges[180] = 0.35
        walls = wall_half_planes(ranges, -math.pi, math.radians(1.0), 0.05,
                                 12.0, sensor_offset=(0.0, 0.0))
        v, action = filter_velocity((0.3, 0.0), planes, 0.25, walls=walls)
        self.assertEqual(action, "free")
        self.assertEqual(v, (0.3, 0.0))

    def test_head_on_in_a_corridor_never_touches_the_walls(self):
        # Two agents meet head on in a corridor 1.4 m wide. The right-hand
        # rule moves both towards their right walls; the walls hold them
        # 0.3 m off while the barrier still keeps them apart; without them
        # the agents come to 0.19 m of the walls.
        half_width = 0.7
        positions = [(-1.5, 0.0), (1.5, 0.0)]
        goals = [(1.5, 0.0), (-1.5, 0.0)]
        closest_pair, closest_wall = 10.0, 10.0
        for _ in range(1200):
            velocities = []
            for i, me in enumerate(positions):
                yaw = 0.0 if i == 0 else math.pi
                to_goal = (goals[i][0] - me[0], goals[i][1] - me[1])
                d = math.hypot(*to_goal)
                nominal = ((0.4 * to_goal[0] / d, 0.4 * to_goal[1] / d)
                           if d > 0.05 else (0.0, 0.0))
                planes = half_planes_body(
                    barrier_half_planes(me, [positions[1 - i]], D_SAFE), yaw)
                scan = corridor_scan(me[1], yaw, half_width)
                walls = wall_half_planes(*scan, 0.05, 12.0,
                                         sensor_offset=(0.0, 0.0))
                body = half_planes_body([(nominal[0], nominal[1], 0.0)], yaw)
                v, _ = filter_velocity((body[0][0], body[0][1]), planes,
                                       0.25, walls=walls)
                velocities.append(nominal_in_room(v, yaw))
            positions = step(positions, velocities, 0.05)
            closest_pair = min(closest_pair, math.dist(*positions))
            closest_wall = min([closest_wall]
                               + [half_width - abs(p[1]) for p in positions])
        self.assertGreater(closest_pair, D_SAFE - 0.05)
        self.assertGreater(closest_wall, 0.30 - 0.02)
        self.assertGreater(positions[0][0], 0.5)
        self.assertLess(positions[1][0], -0.5)


class TestFrames(unittest.TestCase):
    def test_body_frame_round_trip(self):
        planes = [(1.0, 0.0, -0.2)]
        yaw = math.pi / 2       # facing +y in the room
        (body,) = half_planes_body(planes, yaw)
        # The room's +x is the agent's right, body -y.
        self.assertAlmostEqual(body[0], 0.0)
        self.assertAlmostEqual(body[1], -1.0)
        room = nominal_in_room((1.0, 0.0), yaw)
        self.assertAlmostEqual(room[0], 0.0)
        self.assertAlmostEqual(room[1], 1.0)


if __name__ == "__main__":
    unittest.main()
