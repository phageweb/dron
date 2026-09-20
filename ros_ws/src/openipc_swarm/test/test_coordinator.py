"""The one piece of the coordinator that is arithmetic rather than wiring."""

import unittest

from openipc_swarm.coordinator import velocity_from


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


if __name__ == "__main__":
    unittest.main()
