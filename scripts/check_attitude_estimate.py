#!/usr/bin/env python3
"""Assert ArduPilot's attitude estimate is the attitude the vehicle has.

The demo's floor rejection projects every lidar return into a gravity-aligned
frame using roll and pitch from /ap/pose/filtered. The geometry has unit tests
and `check_leaning_scan.sh` proves the rejection works given an attitude, but
both take that attitude as correct. If AP_DDS reported it in another convention -
a flipped sign, or roll and pitch the other way round - the demo would discard
the ceiling and keep the floor, and every test would still pass.

Checking that in flight means aligning two streams during a transient. Parked on
a slope it is two steady numbers, so this reads three of them:

  * what the world file says the ramp is tilted by
  * what Gazebo says the vehicle's attitude actually is, which differs if it
    slid or never settled
  * what /ap/pose/filtered reports

The ramp is tilted in both axes so that a roll/pitch swap cannot hide.
"""

import math
import re
import subprocess
import sys
from pathlib import Path

import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(
    0, str(ROOT / "ros_ws/src/openipc_cinewhoop_demo"))
from openipc_cinewhoop_demo.scan_helpers import (  # noqa: E402
    roll_pitch_from_quaternion,
)

POSE_TOPIC = "/ap/pose/filtered"
# The vehicle settles onto the ramp rather than starting on it, and a slope is
# not a perfectly rigid contact, so allow a little. A convention error is tens
# of degrees, so this stays decisive.
SETTLE_TOLERANCE_DEG = 2.0
ESTIMATE_TOLERANCE_DEG = 2.0
# Below this the ramp is not doing its job and the comparison proves nothing.
MIN_ANGLE_DEG = 5.0


def ramp_angles(world_path):
    """Roll and pitch the world file asks the vehicle to sit at, in degrees."""
    text = Path(world_path).read_text()
    found = re.search(
        r"<include>.*?<pose>\s*([-\d.eE+ ]+?)\s*</pose>", text, re.S)
    if found is None:
        sys.exit(f"No included model pose in {world_path}")
    parts = [float(v) for v in found.group(1).split()]
    if len(parts) != 6:
        sys.exit(f"Model pose in {world_path} is not x y z r p y: {parts}")
    return math.degrees(parts[3]), math.degrees(parts[4])


def world_name(world_path):
    found = re.search(r'<world\s+name="([^"]+)"', Path(world_path).read_text())
    if found is None:
        sys.exit(f"No <world name=...> in {world_path}")
    return found.group(1)


def truth_angles(world):
    """Roll and pitch Gazebo reports for the model, in degrees.

    Read once rather than streamed: the vehicle is parked, so one sample is the
    whole story, and a vehicle that is not parked fails the settle check below.
    """
    try:
        out = subprocess.run(
            ["gz", "topic", "-e", "-t", f"/world/{world}/pose/info", "-n", "1"],
            capture_output=True, text=True, timeout=20).stdout
    except subprocess.TimeoutExpired:
        sys.exit("Gazebo published no pose within 20 s.")
    for block in re.split(r"\npose \{", out):
        if '"openipc_cinewhoop"' in block:
            found = re.search(r"orientation \{(.*?)\n\}", block, re.S)
            if found is None:
                break
            q = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 0.0}
            q.update({k: float(v) for k, v in
                      re.findall(r"([xyzw]):\s*([-\d.e+]+)", found.group(1))})
            roll, pitch = roll_pitch_from_quaternion(q["x"], q["y"], q["z"], q["w"])
            return math.degrees(roll), math.degrees(pitch)
    sys.exit("Gazebo's pose feed never mentioned the vehicle.")


class PoseReader(Node):
    def __init__(self):
        super().__init__("check_attitude_estimate")
        self.angles = None
        self.create_subscription(
            PoseStamped, POSE_TOPIC, self._keep, qos_profile_sensor_data)

    def _keep(self, msg):
        q = msg.pose.orientation
        roll, pitch = roll_pitch_from_quaternion(q.x, q.y, q.z, q.w)
        self.angles = (math.degrees(roll), math.degrees(pitch))


def estimate_angles():
    rclpy.init()
    node = PoseReader()
    deadline = node.get_clock().now().nanoseconds + 40e9
    while rclpy.ok() and node.angles is None:
        if node.get_clock().now().nanoseconds > deadline:
            node.destroy_node()
            rclpy.shutdown()
            sys.exit(f"Nothing on {POSE_TOPIC} within 40 s.")
        rclpy.spin_once(node, timeout_sec=0.5)
    angles = node.angles
    node.destroy_node()
    rclpy.shutdown()
    return angles


def main():
    world_path = sys.argv[1]
    want_roll, want_pitch = ramp_angles(world_path)
    truth_roll, truth_pitch = truth_angles(world_name(world_path))
    ap_roll, ap_pitch = estimate_angles()

    print(f"  the ramp asks for   roll {want_roll:+6.2f}  pitch {want_pitch:+6.2f} deg")
    print(f"  Gazebo reports      roll {truth_roll:+6.2f}  pitch {truth_pitch:+6.2f} deg")
    print(f"  {POSE_TOPIC:<19} roll {ap_roll:+6.2f}  pitch {ap_pitch:+6.2f} deg")

    if max(abs(want_roll), abs(want_pitch)) < MIN_ANGLE_DEG:
        sys.exit(f"The ramp is nearly level, so matching it proves nothing.")
    if (abs(truth_roll - want_roll) > SETTLE_TOLERANCE_DEG
            or abs(truth_pitch - want_pitch) > SETTLE_TOLERANCE_DEG):
        sys.exit("The vehicle is not sitting where the ramp puts it; it slid or "
                 "never settled, so there is no known attitude to compare against.")
    if (abs(ap_roll - truth_roll) > ESTIMATE_TOLERANCE_DEG
            or abs(ap_pitch - truth_pitch) > ESTIMATE_TOLERANCE_DEG):
        sys.exit(
            f"ArduPilot's estimate is off by roll {ap_roll - truth_roll:+.2f}, "
            f"pitch {ap_pitch - truth_pitch:+.2f} degrees. Swapped or inverted "
            "axes look exactly like this, and the demo's floor rejection trusts "
            "these two numbers.")

    print("  the estimate matches the truth in both axes and both signs")


if __name__ == "__main__":
    main()
