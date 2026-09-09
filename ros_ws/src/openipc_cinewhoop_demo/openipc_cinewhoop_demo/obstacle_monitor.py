import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan

from openipc_cinewhoop_demo.scan_helpers import nearest_valid_range


class ObstacleMonitor(Node):
    def __init__(self):
        super().__init__("obstacle_monitor")
        self.declare_parameter("scan_topic", "/openipc_cinewhoop/scan/front")
        self.declare_parameter("warn_distance_m", 0.8)
        self.declare_parameter("log_period_s", 0.5)

        self._last_log_time = self.get_clock().now()
        topic = self.get_parameter("scan_topic").value
        self.create_subscription(
            LaserScan,
            topic,
            self._on_scan,
            qos_profile_sensor_data,
        )
        self.get_logger().info(f"Listening for LaserScan on {topic}")

    def _on_scan(self, msg: LaserScan):
        now = self.get_clock().now()
        period = float(self.get_parameter("log_period_s").value)
        if (now - self._last_log_time).nanoseconds / 1e9 < period:
            return
        self._last_log_time = now

        nearest = nearest_valid_range(msg.ranges, msg.range_min, msg.range_max)
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
    finally:
        node.destroy_node()
        rclpy.shutdown()
