"""The arbiter's clipping rules, without ROS in the way."""

import unittest

from openipc_cinewhoop_demo.arbiter import clipped_speed, effective_limit


class TestClippedSpeed(unittest.TestCase):
    def test_a_command_under_the_limit_passes_through(self):
        self.assertAlmostEqual(clipped_speed(0.3, 0.5), 0.3)

    def test_a_command_over_the_limit_is_cut_to_it(self):
        self.assertAlmostEqual(clipped_speed(0.9, 0.5), 0.5)

    def test_reverse_is_clipped_by_magnitude_not_by_value(self):
        # min() would have turned this into -0.5 -> -0.9, a faster reverse.
        self.assertAlmostEqual(clipped_speed(-0.9, 0.5), -0.5)
        self.assertAlmostEqual(clipped_speed(-0.2, 0.5), -0.2)

    def test_a_zero_limit_stops_the_vehicle_in_both_directions(self):
        self.assertEqual(clipped_speed(1.0, 0.0), 0.0)
        self.assertEqual(clipped_speed(-1.0, 0.0), 0.0)

    def test_a_negative_limit_is_treated_as_a_stop(self):
        self.assertEqual(clipped_speed(1.0, -0.5), 0.0)


class TestEffectiveLimit(unittest.TestCase):
    def test_a_fresh_limit_is_used(self):
        self.assertAlmostEqual(
            effective_limit(0.4, age_s=0.2, timeout_s=1.0, fallback_mps=0.25),
            0.4)

    def test_a_stale_limit_falls_back_rather_than_persisting(self):
        self.assertAlmostEqual(
            effective_limit(1.0, age_s=2.0, timeout_s=1.0, fallback_mps=0.25),
            0.25)

    def test_no_limit_yet_falls_back_too(self):
        self.assertAlmostEqual(
            effective_limit(None, None, timeout_s=1.0, fallback_mps=0.25),
            0.25)

    def test_a_fresh_stop_is_honoured_and_not_replaced_by_the_fallback(self):
        # The dangerous confusion: silence means slow, but an explicit stop
        # means stop, and the two must not be collapsed.
        self.assertEqual(
            effective_limit(0.0, age_s=0.1, timeout_s=1.0, fallback_mps=0.25),
            0.0)


if __name__ == "__main__":
    unittest.main()
