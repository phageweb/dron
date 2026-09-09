import rclpy
from geometry_msgs.msg import TwistStamped
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan

from openipc_cinewhoop_demo.scan_helpers import nearest_valid_range, safe_forward_speed


class SimpleIndoorAutonomy(Node):
    def __init__(self):
        super().__init__("simple_indoor_autonomy")
        self.declare_parameter("scan_topic", "/openipc_cinewhoop/scan/front")
        self.declare_parameter("cmd_vel_topic", "/ap/cmd_vel")
        self.declare_parameter("forward_speed_mps", 0.5)
        self.declare_parameter("stop_distance_m", 0.8)

        self._nearest = None
        self._last_scan_time = None

        scan_topic = self.get_parameter("scan_topic").value
        cmd_topic = self.get_parameter("cmd_vel_topic").value
        self.create_subscription(
            LaserScan,
            scan_topic,
            self._on_scan,
            qos_profile_sensor_data,
        )
        self._cmd_pub = self.create_publisher(TwistStamped, cmd_topic, 10)
        self.create_timer(0.1, self._tick)
        self.get_logger().info(
            "Demo autonomy publishing velocity only; ArduPilot arm/takeoff wiring is a future step."
        )

    def _on_scan(self, msg: LaserScan):
        self._nearest = nearest_valid_range(msg.ranges, msg.range_min, msg.range_max)
        self._last_scan_time = self.get_clock().now()

    def _tick(self):
        cmd = TwistStamped()
        cmd.header.stamp = self.get_clock().now().to_msg()
        cmd.header.frame_id = "base_link"

        cmd.twist.linear.x = safe_forward_speed(
            self._nearest,
            float(self.get_parameter("stop_distance_m").value),
            float(self.get_parameter("forward_speed_mps").value),
        )

        self._cmd_pub.publish(cmd)


def main(args=None):
    rclpy.init(args=args)
    node = SimpleIndoorAutonomy()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
