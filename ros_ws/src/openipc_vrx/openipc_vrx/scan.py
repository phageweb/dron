"""A turn decoded from the OSD as the fields of a sensor_msgs/LaserScan.

The OSD carries 144 sectors of 2.5 degrees in the lidar's own convention:
sector i is centred on (i + 0.5) * 2.5 degrees, measured from the front
clockwise seen from above. ROS measures counter-clockwise, so the sectors
are reversed: ranges[k] is sector 143 - k, at angle_min + k * increment.
Kept free of rclpy so it can be tested without ROS.
"""

import math

from . import osdscan

INCREMENT = math.radians(osdscan.BIN_DEG)
ANGLE_MIN = INCREMENT / 2
ANGLE_MAX = ANGLE_MIN + (osdscan.BINS - 1) * INCREMENT
RANGE_MIN = osdscan.DMIN / 1000.0
RANGE_MAX = osdscan.DMAX / 1000.0


def ranges_from_codes(codes):
    """144 OSD codes -> ranges in metres, ROS order; no return is +inf (REP 117)."""
    if len(codes) != osdscan.BINS:
        raise ValueError(f"a turn has {osdscan.BINS} sectors, got {len(codes)}")
    return [osdscan.distance(v) / 1000.0 if v else math.inf for v in reversed(codes)]


def sector_angle_ros(i):
    """ROS angle (rad, counter-clockwise, -pi..pi) of the centre of OSD sector i."""
    a = -math.radians((i + 0.5) * osdscan.BIN_DEG)
    return math.atan2(math.sin(a), math.cos(a))
