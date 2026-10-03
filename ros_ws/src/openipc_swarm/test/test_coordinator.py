"""The coordinator's arithmetic, and the one piece of wiring that moves frames."""

import unittest

import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import OccupancyGrid
from rclpy.parameter import Parameter

from openipc_swarm.coordinator import Coordinator, velocity_from
from openipc_swarm.merge import UNKNOWN


class TestVelocityFrom(unittest.TestCase):
    def test_the_first_pose_gives_no_velocity(self):
        self.assertEqual(velocity_from(None, 1.0, (0.0, 0.0, 1.0)),
                         (0.0, 0.0, 0.0))

    def test_a_metre_in_a_second_is_a_metre_per_second(self):
        previous = (1.0, (0.0, 0.0, 1.0))
        self.assertEqual(velocity_from(previous, 2.0, (1.0, 0.0, 1.0)),
                         (1.0, 0.0, 0.0))

    def test_two_poses_at_the_same_instant_do_not_divide_by_zero(self):
        previous = (1.0, (0.0, 0.0, 1.0))
        self.assertEqual(velocity_from(previous, 1.0, (5.0, 0.0, 1.0)),
                         (0.0, 0.0, 0.0))

    def test_a_tiny_interval_is_treated_as_no_interval(self):
        # A 0.1 ms gap would turn millimetres of noise into metres per second,
        # and the filter would brake the swarm for a rounding error.
        previous = (1.0, (0.0, 0.0, 1.0))
        self.assertEqual(velocity_from(previous, 1.0001, (0.001, 0.0, 1.0)),
                         (0.0, 0.0, 0.0))

    def test_it_differences_every_axis(self):
        previous = (0.0, (1.0, 2.0, 3.0))
        self.assertEqual(velocity_from(previous, 2.0, (3.0, 6.0, 9.0)),
                         (1.0, 2.0, 3.0))


class TestCoordinatorFrames(unittest.TestCase):
    """The node, not the module: the first swarm flight's bug was wiring."""

    @classmethod
    def setUpClass(cls):
        rclpy.init()

    @classmethod
    def tearDownClass(cls):
        rclpy.try_shutdown()

    def node(self, offsets):
        overrides = [Parameter("agents", value=["v1", "v2"])]
        if offsets is not None:
            overrides.append(Parameter("start_offsets", value=offsets))
        node = Coordinator(parameter_overrides=overrides)
        self.addCleanup(node.destroy_node)
        return node

    def test_it_will_not_start_without_offsets(self):
        with self.assertRaises(ValueError):
            self.node(None)

    def test_two_agents_at_their_own_origins_are_two_places(self):
        node = self.node([0.5, -2.0, 0.5, 2.0])
        for name in ("v1", "v2"):
            msg = PoseStamped()
            msg.pose.position.z = 1.0
            node._pose_handler(name)(msg)
        fresh = node._state.fresh(node._now())
        self.assertEqual(fresh["v1"][0], (0.5, -2.0, 1.0))
        self.assertEqual(fresh["v2"][0], (0.5, 2.0, 1.0))

    def test_a_map_is_moved_by_its_own_agents_offset(self):
        node = self.node([0.0, 0.0, 0.2, -0.1])
        grid = OccupancyGrid()
        grid.info.width, grid.info.height, grid.info.resolution = 4, 3, 0.1
        grid.data = [UNKNOWN] * 12
        grid.data[1 * 4 + 1] = 100          # col 1, row 1
        self.assertEqual(node._in_room("v1", grid).index(100), 1 * 4 + 1)
        self.assertEqual(node._in_room("v2", grid).index(100), 0 * 4 + 3)


if __name__ == "__main__":
    unittest.main()
