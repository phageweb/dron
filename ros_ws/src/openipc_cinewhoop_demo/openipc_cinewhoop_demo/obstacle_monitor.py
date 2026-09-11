import math

import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan, Range

from openipc_cinewhoop_demo.scan_helpers import (
    compensation_height,
    nearest_in_sector,
    reading_is_fresh,
    roll_pitch_from_quaternion,
)


class ObstacleMonitor(Node):
    def __init__(self):
        super().__init__("obstacle_monitor")
        self.declare_parameter("scan_topic", "/openipc_cinewhoop/scan/front")
        self.declare_parameter("warn_distance_m", 0.8)
        self.declare_parameter("log_period_s", 0.5)
        self.declare_parameter("scan_timeout_s", 1.0)
        # Same reason as the autonomy node: the sensor sweeps the whole circle,
        # so the monitor has to be told which part of it counts as "ahead".
        self.declare_parameter("forward_sector_deg", 60.0)
        # And for the same reason again, the same compensation: the lidar leans
        # with the airframe, so its forward beams find the floor as soon as the
        # nose drops. A monitor without this reports the floor as the nearest
        # obstacle while the autonomy node correctly ignores it, which is worse
        # than either behaviour on its own - the two would disagree in flight.
        self.declare_parameter("range_topic", "/openipc_cinewhoop/range/down")
        self.declare_parameter("pose_topic", "/ap/pose/filtered")
        self.declare_parameter("ground_margin_m", 0.25)
        # Neither the attitude nor the height arrives with the scan, so both can
        # go stale while the lidar stays healthy. Rejecting the floor with an
        # attitude the vehicle no longer holds is worse than not rejecting it.
        self.declare_parameter("compensation_timeout_s", 0.5)

        self._last_log_time = self.get_clock().now()
        self._started_at = self.get_clock().now()
        self._last_scan_time = None
        self._silent_logged = False
        self._roll = 0.0
        self._pitch = 0.0
        self._height = None
        self._pose_time = None
        self._range_time = None
        self._blind_reason = None
        topic = self.get_parameter("scan_topic").value
        self.create_subscription(
            LaserScan,
            topic,
            self._on_scan,
            qos_profile_sensor_data,
        )
        self.create_subscription(
            PoseStamped, self.get_parameter("pose_topic").value,
            self._on_pose, qos_profile_sensor_data)
        self.create_subscription(
            Range, self.get_parameter("range_topic").value,
            self._on_range, qos_profile_sensor_data)
        # A monitor that simply goes quiet when its sensor dies is worse than
        # no monitor, so silence is reported rather than left to be noticed.
        self.create_timer(0.2, self._check_alive)
        self.get_logger().info(f"Listening for LaserScan on {topic}")

    def _silent_for_s(self):
        """Seconds since the last scan, or since startup while none has come."""
        reference = self._last_scan_time or self._started_at
        return (self.get_clock().now() - reference).nanoseconds / 1e9

    def _check_alive(self):
        timeout = float(self.get_parameter("scan_timeout_s").value)
        silent_for = self._silent_for_s()
        if reading_is_fresh(silent_for, timeout) or self._silent_logged:
            return
        what = "yet" if self._last_scan_time is None else "any more"
        self.get_logger().warning(
            f"No front lidar scan {what} after {silent_for:.1f} s")
        self._silent_logged = True

    def _age_s(self, stamp):
        if stamp is None:
            return None
        return (self.get_clock().now() - stamp).nanoseconds / 1e9

    def _on_pose(self, msg: PoseStamped):
        q = msg.pose.orientation
        self._roll, self._pitch = roll_pitch_from_quaternion(q.x, q.y, q.z, q.w)
        self._pose_time = self.get_clock().now()

    def _on_range(self, msg: Range):
        # Outside the sensor's window the reading means "no detection", and an
        # unknown height must not start discarding real obstacles.
        self._height = (msg.range
                        if msg.min_range <= msg.range <= msg.max_range
                        else None)
        self._range_time = self.get_clock().now()

    def _rejection_height(self):
        """The height to drop floor returns with, saying so when there is none."""
        height, reason, detail = compensation_height(
            self._age_s(self._pose_time), self._age_s(self._range_time),
            float(self.get_parameter("compensation_timeout_s").value),
            self._height)
        if reason != self._blind_reason:
            if reason:
                self.get_logger().warning(
                    f"Not rejecting floor returns: {reason}{detail}")
            else:
                self.get_logger().info("Rejecting floor returns again")
            self._blind_reason = reason
        return height

    def _on_scan(self, msg: LaserScan):
        now = self.get_clock().now()
        self._last_scan_time = now
        self._silent_logged = False
        period = float(self.get_parameter("log_period_s").value)
        if (now - self._last_log_time).nanoseconds / 1e9 < period:
            return
        self._last_log_time = now

        sector = math.radians(
            float(self.get_parameter("forward_sector_deg").value))
        nearest = nearest_in_sector(
            msg.ranges, msg.angle_min, msg.angle_increment,
            msg.range_min, msg.range_max, sector,
            self._roll, self._pitch, self._rejection_height(),
            float(self.get_parameter("ground_margin_m").value))
        if nearest is None:
            self.get_logger().warning("No valid front lidar range")
            return

        warn_distance = float(self.get_parameter("warn_distance_m").value)
        if nearest < warn_distance:
            self.get_logger().warning(f"Obstacle close: {nearest:.2f} m")
        else:
            self.get_logger().info(f"Nearest obstacle: {nearest:.2f} m")


def main(args=None):
    rclpy.init(args=args)
    node = ObstacleMonitor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        # Ctrl-C and a TERM to the process group are how these nodes are always
        # stopped, so a traceback on the way out is noise, not information.
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
