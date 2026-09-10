import math

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan

from openipc_cinewhoop_demo.scan_helpers import nearest_in_sector, scan_is_usable


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

        self._last_log_time = self.get_clock().now()
        self._started_at = self.get_clock().now()
        self._last_scan_time = None
        self._silent_logged = False
        topic = self.get_parameter("scan_topic").value
        self.create_subscription(
            LaserScan,
            topic,
            self._on_scan,
            qos_profile_sensor_data,
        )
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
        if scan_is_usable(silent_for, timeout) or self._silent_logged:
            return
        what = "yet" if self._last_scan_time is None else "any more"
        self.get_logger().warning(
            f"No front lidar scan {what} after {silent_for:.1f} s")
        self._silent_logged = True

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
            msg.range_min, msg.range_max, sector)
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
