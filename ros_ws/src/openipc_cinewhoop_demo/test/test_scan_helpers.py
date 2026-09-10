import math
import unittest

from openipc_cinewhoop_demo.scan_helpers import (
    nearest_valid_range,
    safe_forward_speed,
    scan_is_usable,
    takeoff_needs_retry,
)


class ScanHelpersTest(unittest.TestCase):
    def test_nearest_valid_range_ignores_invalid_values(self):
        self.assertEqual(
            nearest_valid_range([math.inf, math.nan, 1.2, 0.7], 0.1, 5.0),
            0.7,
        )

    def test_nearest_valid_range_rejects_out_of_range_values(self):
        self.assertIsNone(nearest_valid_range([0.01, 6.0], 0.1, 5.0))

    def test_safe_forward_speed_stops_without_a_valid_scan(self):
        self.assertEqual(safe_forward_speed(None, 0.8, 0.5), 0.0)

    def test_safe_forward_speed_stops_below_the_threshold(self):
        self.assertEqual(safe_forward_speed(0.79, 0.8, 0.5), 0.0)

    def test_safe_forward_speed_allows_motion_at_the_threshold(self):
        self.assertEqual(safe_forward_speed(0.8, 0.8, 0.5), 0.5)

    def test_scan_is_unusable_before_any_scan_arrives(self):
        self.assertFalse(scan_is_usable(None, 0.5))

    def test_scan_is_usable_inside_the_timeout(self):
        self.assertTrue(scan_is_usable(0.2, 0.5))

    def test_scan_is_usable_exactly_at_the_timeout(self):
        self.assertTrue(scan_is_usable(0.5, 0.5))

    def test_scan_is_unusable_past_the_timeout(self):
        self.assertFalse(scan_is_usable(0.51, 0.5))

    def test_takeoff_is_given_time_before_it_is_judged(self):
        self.assertFalse(takeoff_needs_retry(0.03, 0.03, 2.9, 3.0, 0.15))

    def test_takeoff_is_retried_when_the_vehicle_never_moved(self):
        self.assertTrue(takeoff_needs_retry(0.03, 0.03, 3.0, 3.0, 0.15))

    def test_takeoff_is_not_retried_once_the_climb_is_visible(self):
        self.assertFalse(takeoff_needs_retry(0.25, 0.03, 3.0, 3.0, 0.15))

    def test_takeoff_is_retried_without_any_altitude_telemetry(self):
        self.assertTrue(takeoff_needs_retry(None, None, 3.0, 3.0, 0.15))

    def test_takeoff_is_retried_when_the_vehicle_sank(self):
        self.assertTrue(takeoff_needs_retry(-0.1, 0.03, 4.0, 3.0, 0.15))
