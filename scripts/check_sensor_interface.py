#!/usr/bin/env python3
"""Assert the bridged sensors present the interface the real drone will present.

A Gazebo sensor stamps its messages with its own scoped name unless the model
sets `gz_frame_id`, and that name is not a link in the URDF. Nothing fails
loudly when it happens: the topic carries data, `ros2 topic echo` looks healthy,
and only RViz and any TF-using consumer quietly find nothing to transform. The
real drone's drivers publish URDF link names, so the mismatch is also a
simulation-only behaviour, which is exactly what the transition checklist in
spec/realna_stavba_dronu/02_rozhrani_sim_real.md forbids.

The check subscribes to each sensor topic, takes the frame from the first
message, and asks TF whether it can be transformed into the fixed frame RViz
uses. That is the property that matters, rather than a string comparison.

It also compares the rangefinder's declared field of view against the width of
the simulated fan behind it, because those two live in different files and a
Range that describes a cone the sensor does not have is a quiet lie, and it
reads gravity off the IMU, which is the cheapest way to catch an axis flip.
"""

import sys

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.time import Time
from sensor_msgs.msg import CameraInfo, Imu, LaserScan, Range
from tf2_ros import Buffer, TransformListener

FIXED_FRAME = "base_link"

TOPICS = {
    "/openipc_cinewhoop/scan/front": LaserScan,
    "/openipc_cinewhoop/range/down": Range,
    "/openipc_cinewhoop/imu": Imu,
    "/openipc_cinewhoop/camera/camera_info": CameraInfo,
}

RANGE_TOPIC = "/openipc_cinewhoop/range/down"
RAW_SCAN_TOPIC = "/openipc_cinewhoop/range/down_raw"
IMU_TOPIC = "/openipc_cinewhoop/imu"
GRAVITY = 9.80665


class FrameCheck(Node):
    def __init__(self):
        super().__init__("check_sensor_frames")
        self._frames = {}
        self._range = None
        self._raw_scan = None
        self._imu = None
        self._buffer = Buffer()
        self._listener = TransformListener(self._buffer, self)
        for topic, msg_type in TOPICS.items():
            self.create_subscription(
                msg_type, topic,
                lambda msg, topic=topic: self._frames.setdefault(
                    topic, msg.header.frame_id),
                qos_profile_sensor_data)
        self.create_subscription(
            Range, RANGE_TOPIC, self._keep_range, qos_profile_sensor_data)
        self.create_subscription(
            LaserScan, RAW_SCAN_TOPIC, self._keep_raw_scan, qos_profile_sensor_data)
        self.create_subscription(
            Imu, IMU_TOPIC, self._keep_imu, qos_profile_sensor_data)

    def _keep_range(self, msg):
        self._range = msg

    def _keep_raw_scan(self, msg):
        self._raw_scan = msg

    def _keep_imu(self, msg):
        self._imu = msg

    def gravity_points_up(self):
        """A resting REP 103 accelerometer reads +g on z, not -g.

        The model carries a second IMU for exactly this reason: the one
        ArduPilot reads is rolled into the aircraft convention, and bridging it
        gave ROS an inverted y and z that only real hardware would have exposed.
        """
        if self._imu is None:
            return None, f"  {IMU_TOPIC}: no message to check gravity against"
        a = self._imu.linear_acceleration
        if abs(a.z - GRAVITY) > 0.5 or abs(a.x) > 0.5 or abs(a.y) > 0.5:
            return False, (
                f"  {IMU_TOPIC}: at rest reads ({a.x:.2f}, {a.y:.2f}, {a.z:.2f}) "
                f"m/s^2, not (0, 0, +{GRAVITY:.2f}); the axes are not REP 103")
        return True, f"  {IMU_TOPIC}: gravity reads +{a.z:.2f} m/s^2 on z, as REP 103 wants"

    def field_of_view_matches(self):
        """Compare the declared cone with the fan the simulation actually casts."""
        if self._range is None or self._raw_scan is None:
            return None, (
                f"  {RANGE_TOPIC}: no message from {RAW_SCAN_TOPIC} to compare with")
        fan = self._raw_scan.angle_max - self._raw_scan.angle_min
        declared = self._range.field_of_view
        if abs(fan - declared) > 0.01:
            return False, (
                f"  {RANGE_TOPIC}: declares a {declared:.3f} rad cone while "
                f"{RAW_SCAN_TOPIC} spans {fan:.3f} rad")
        return True, f"  {RANGE_TOPIC}: {declared:.3f} rad cone matches the fan"

    def missing(self):
        return [t for t in TOPICS if t not in self._frames]

    def report(self):
        """Return (ok, lines) for every topic that produced a message."""
        ok = True
        lines = []
        for topic, frame in sorted(self._frames.items()):
            if not frame:
                ok = False
                lines.append(f"  {topic}: empty frame_id")
                continue
            # Time() means "latest available", which is what a static transform
            # answers; the sensor stamp would drag sim-time skew in for nothing.
            if self._buffer.can_transform(FIXED_FRAME, frame, Time()):
                lines.append(f"  {topic}: {frame} -> {FIXED_FRAME} ok")
            else:
                ok = False
                lines.append(
                    f"  {topic}: {frame} is not in the TF tree under {FIXED_FRAME}")
        return ok, lines


def main():
    rclpy.init()
    node = FrameCheck()
    timeout = 40.0
    deadline = node.get_clock().now().nanoseconds / 1e9 + timeout
    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.2)
            # Every condition has to hold at once, or the loop can leave while
            # the rangefinder pair is still one message short and report a
            # failure that is only slow discovery.
            settled = (not node.missing()
                       and node.report()[0]
                       and node.field_of_view_matches()[0] is True
                       and node.gravity_points_up()[0] is True)
            if settled:
                break
            if node.get_clock().now().nanoseconds / 1e9 > deadline:
                break

        missing = node.missing()
        ok, lines = node.report()
        for passed, line in (node.field_of_view_matches(), node.gravity_points_up()):
            lines.append(line)
            if passed is not True:
                ok = False
        print("\n".join(lines))
        for topic in missing:
            print(f"  {topic}: no message within {timeout:.0f} s")
        if missing or not ok:
            print("Sensor interface check FAILED.", file=sys.stderr)
            return 1
        print("Every bridged sensor matches the interface spec.")
        return 0
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    sys.exit(main())
