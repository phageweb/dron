#!/usr/bin/env python3
"""Assert that a leaning vehicle's front scan is the floor, and is rejected.

`scan_helpers` learned to drop returns that are really the ground, because the
LD06 is bolted to the airframe and leaning points its forward beams downwards.
That was written against unit tests. The flying check, `check_forward_flight.sh`,
cruises at 1 m with a gentle attitude, so the floor stays out of range there and
the rejection is never exercised by anything Gazebo produced.

This runs against `leaning_test.sdf`, where the model is held static at 30
degrees nose-down, 0.60 m up. It reads the scan the simulated lidar actually
publishes and asserts both halves of the property:

  * the raw forward sector is inside the demo's stop threshold, so an
    uncompensated vehicle would stop dead for the floor
  * with the attitude and the measured height applied, nothing in that sector
    is left, so the compensated vehicle has no obstacle to stop for

The second without the first would pass over an empty scan, which is why the
raw reading is asserted rather than only printed.
"""

import math
import sys

import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan, Range

from openipc_cinewhoop_demo.scan_helpers import (
    height_from_slant_range,
    nearest_in_sector,
    roll_pitch_from_quaternion,
)

SCAN_TOPIC = "/openipc_cinewhoop/scan/front"
RANGE_TOPIC = "/openipc_cinewhoop/range/down"
POSE_TOPIC = "/ap/pose/filtered"

# simple_indoor_autonomy's own defaults: 0.80 m of wanted clearance plus the
# 0.60 m it takes to stop from 0.5 m/s. A return closer than this is one the
# demo stops for.
STOP_THRESHOLD_M = 0.80 + 0.60
FORWARD_SECTOR_DEG = 60.0
GROUND_MARGIN_M = 0.25
# Nothing useful can be said about a scan taken while the vehicle is level; the
# whole point is the lean, so a pose that is not leaning is a setup failure.
MIN_PITCH_DEG = 20.0
# How far the corrected height may sit from where Gazebo says the sensor is.
# The simulated rangefinder quantises to its 0.01 m range resolution and reads
# the nearest point of a 2 degree cone rather than a single ray, so a centimetre
# is the most the simulator can be held to.
HEIGHT_TOLERANCE_M = 0.015


class LeaningScanCheck(Node):
    def __init__(self):
        super().__init__("check_leaning_scan")
        self.scan = None
        self.slant = None
        self.pose = None
        self.create_subscription(
            LaserScan, SCAN_TOPIC, self._keep_scan, qos_profile_sensor_data)
        self.create_subscription(
            Range, RANGE_TOPIC, self._keep_range, qos_profile_sensor_data)
        self.create_subscription(
            PoseStamped, POSE_TOPIC, self._keep_pose, qos_profile_sensor_data)

    def _keep_scan(self, msg):
        self.scan = msg

    def _keep_range(self, msg):
        self.slant = (msg.range
                      if msg.min_range <= msg.range <= msg.max_range
                      else None)

    def _keep_pose(self, msg):
        q = msg.pose.orientation
        self.pose = roll_pitch_from_quaternion(q.x, q.y, q.z, q.w)

    def complete(self):
        return self.scan is not None and self.slant is not None and self.pose


def main():
    # Where the simulator says the downward sensor is, in metres above the floor
    # surface, passed in by the shell that has Gazebo to ask. Optional so the
    # check still runs, with that one assertion skipped, without it.
    true_height = float(sys.argv[1]) if len(sys.argv) > 1 else None

    rclpy.init()
    node = LeaningScanCheck()
    deadline = node.get_clock().now().nanoseconds + 40e9
    while rclpy.ok() and not node.complete():
        if node.get_clock().now().nanoseconds > deadline:
            missing = [name for name, value in
                       (("scan", node.scan), ("range", node.slant),
                        ("pose", node.pose)) if value is None]
            node.destroy_node()
            rclpy.shutdown()
            sys.exit(f"No {', '.join(missing)} within 40 s.")
        rclpy.spin_once(node, timeout_sec=0.5)

    scan, slant = node.scan, node.slant
    roll, pitch = node.pose
    node.destroy_node()
    rclpy.shutdown()

    # The sensor measures along its own axis, so leaning it reports the slant to
    # the floor and not the height above it. Undo that before anything uses it
    # as a height, and check the result against where the simulator says the
    # sensor really is rather than against the formula that produced it.
    height = height_from_slant_range(slant, roll, pitch)

    sector = math.radians(FORWARD_SECTOR_DEG)
    raw = nearest_in_sector(
        scan.ranges, scan.angle_min, scan.angle_increment,
        scan.range_min, scan.range_max, sector)
    compensated = nearest_in_sector(
        scan.ranges, scan.angle_min, scan.angle_increment,
        scan.range_min, scan.range_max, sector,
        roll, pitch, height, GROUND_MARGIN_M)

    print(f"  attitude: roll {math.degrees(roll):.1f} deg, "
          f"pitch {math.degrees(pitch):.1f} deg (nose down is positive)")
    print(f"  rangefinder: {slant:.3f} m of slant, {height:.3f} m of height"
          + (f", truth {true_height:.3f} m" if true_height is not None else ""))
    print(f"  nearest in the forward {FORWARD_SECTOR_DEG:.0f} deg sector: "
          f"raw {raw if raw is None else f'{raw:.3f} m'}, "
          f"compensated {compensated if compensated is None else f'{compensated:.3f} m'}")

    if true_height is not None and abs(height - true_height) > HEIGHT_TOLERANCE_M:
        sys.exit(f"The corrected height is {height:.3f} m where the simulator "
                 f"puts the sensor {true_height:.3f} m above the floor. The "
                 f"raw reading was {slant:.3f} m; if that is the closer of the "
                 "two, the lean is not being undone.")
    if true_height is not None and abs(slant - true_height) <= HEIGHT_TOLERANCE_M:
        sys.exit(f"The raw reading {slant:.3f} m already matches the true "
                 f"{true_height:.3f} m, so this attitude does not exercise the "
                 "slant correction and the check proves nothing about it.")

    if math.degrees(pitch) < MIN_PITCH_DEG:
        sys.exit(f"The vehicle is only pitched {math.degrees(pitch):.1f} deg; "
                 "this check needs it leaning to mean anything.")
    if raw is None:
        sys.exit("The raw forward sector is empty, so the lidar is not seeing "
                 "the floor and there is nothing here to reject.")
    if raw >= STOP_THRESHOLD_M:
        sys.exit(f"The raw forward sector reports {raw:.3f} m, past the "
                 f"{STOP_THRESHOLD_M:.2f} m the demo stops at. An uncompensated "
                 "vehicle would not have stopped for this, so the check proves "
                 "nothing; lean it further or fly it lower.")
    if compensated is not None:
        sys.exit(f"The floor survived compensation as an obstacle at "
                 f"{compensated:.3f} m.")

    print("  the floor would have stopped the demo; compensation removed it")


if __name__ == "__main__":
    main()
