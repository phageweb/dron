import math
import unittest

from openipc_vrx import osdscan
from openipc_vrx.scan import ANGLE_MIN, INCREMENT, ranges_from_codes, sector_angle_ros


class ScanTest(unittest.TestCase):
    def test_sector_lands_at_its_ros_angle(self):
        # One return in every tested sector; it must come out where ROS
        # puts the same direction (counter-clockwise from the front).
        for i in (0, 1, 35, 36, 71, 72, 108, 143):
            codes = [0] * osdscan.BINS
            codes[i] = osdscan.code(2000)
            ranges = ranges_from_codes(codes)
            k = next(j for j, r in enumerate(ranges) if math.isfinite(r))
            got = ANGLE_MIN + k * INCREMENT
            want = sector_angle_ros(i)
            diff = math.atan2(math.sin(got - want), math.cos(got - want))
            self.assertAlmostEqual(diff, 0.0, places=9, msg=f"sector {i}")

    def test_right_side_is_negative_angle(self):
        # Clockwise 90 degrees in the lidar's convention is the right side,
        # which is -90 degrees in ROS.
        i = round(90 / osdscan.BIN_DEG - 0.5)
        self.assertAlmostEqual(sector_angle_ros(i), -math.radians((i + 0.5) * osdscan.BIN_DEG))
        self.assertLess(sector_angle_ros(i), 0)

    def test_ranges_in_metres_and_inf_for_no_return(self):
        codes = [0] * osdscan.BINS
        codes[10] = osdscan.code(1500)
        ranges = ranges_from_codes(codes)
        self.assertEqual(sum(math.isfinite(r) for r in ranges), 1)
        r = next(r for r in ranges if math.isfinite(r))
        self.assertAlmostEqual(r, 1.5, delta=0.02)

    def test_wrong_length_refused(self):
        with self.assertRaises(ValueError):
            ranges_from_codes([0] * 10)


if __name__ == "__main__":
    unittest.main()
