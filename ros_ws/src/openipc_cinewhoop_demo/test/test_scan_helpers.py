import math
import unittest

from openipc_cinewhoop_demo.scan_helpers import nearest_valid_range, safe_forward_speed


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
