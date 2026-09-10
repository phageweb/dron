"""Publish the downward rangefinder as sensor_msgs/msg/Range.

Gazebo can only model a rangefinder as a small lidar, so the bridge delivers a
LaserScan. The real MicoAir MTF-02P is a time-of-flight rangefinder and its
driver publishes Range, and
spec/realna_stavba_dronu/02_rozhrani_sim_real.md requires the logical topic to
carry the same message type on both. This adapter is the simulation half of
that: it owns /openipc_cinewhoop/range/down and consumes the raw scan under a
name no demo node is allowed to know about.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan, Range

from openipc_cinewhoop_demo.scan_helpers import range_reading


class RangeAdapter(Node):
    def __init__(self):
        super().__init__("range_adapter")
        self.declare_parameter("scan_topic", "/openipc_cinewhoop/range/down_raw")
        self.declare_parameter("range_topic", "/openipc_cinewhoop/range/down")
        # MicoAir give the MTF-02P's laser a 2 degree emitting angle. The
        # simulated fan spans the same angle, so this reports the sensor rather
        # than describing hardware the simulation does not have.
        self.declare_parameter("field_of_view_rad", 0.035)

        range_topic = self.get_parameter("range_topic").value
        scan_topic = self.get_parameter("scan_topic").value
        self._pub = self.create_publisher(Range, range_topic, 10)
        self.create_subscription(
            LaserScan, scan_topic, self._on_scan, qos_profile_sensor_data)
        self.get_logger().info(f"Converting {scan_topic} into Range on {range_topic}")

    def _on_scan(self, msg: LaserScan):
        out = Range()
        out.header = msg.header
        # A laser time-of-flight sensor is INFRARED here; Range offers only
        # ULTRASOUND and INFRARED, and the MTF-02P is not an ultrasonic sensor.
        out.radiation_type = Range.INFRARED
        out.field_of_view = float(self.get_parameter("field_of_view_rad").value)
        out.min_range = msg.range_min
        out.max_range = msg.range_max
        out.range = range_reading(msg.ranges, msg.range_min, msg.range_max)
        self._pub.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = RangeAdapter()
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
