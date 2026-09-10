#!/usr/bin/env python3
"""Stand in for ArduPilot so the autonomy node can be driven without a simulator.

Serves the four services and three topics the node needs, all under names the
caller chooses, and reports which of them the node actually used. That is what
proves the service-name parameters are honoured: `ros2 node info` does not list
service clients, so introspection cannot answer it.
"""
import argparse
import math
import sys

import rclpy
from ardupilot_msgs.msg import Status
from ardupilot_msgs.srv import ArmMotors, ModeSwitch, Takeoff
from geometry_msgs.msg import PoseStamped, TwistStamped
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from std_srvs.srv import Trigger


class FakeArduPilot(Node):
    def __init__(self, args):
        super().__init__("fake_ardupilot")
        self.seen = set()
        self.cmd_vel_seen = 0
        self.forward_seen = 0.0
        self._altitude = 0.0
        self._armed = False
        self._range = args.range_m

        self.create_service(Trigger, args.prearm_service, self._on_prearm)
        self.create_service(ModeSwitch, args.mode_service, self._on_mode)
        self.create_service(ArmMotors, args.arm_service, self._on_arm)
        self.create_service(Takeoff, args.takeoff_service, self._on_takeoff)

        self._scan_pub = self.create_publisher(
            LaserScan, args.scan_topic, qos_profile_sensor_data)
        self._pose_pub = self.create_publisher(
            PoseStamped, args.pose_topic, qos_profile_sensor_data)
        self._status_pub = self.create_publisher(
            Status, args.status_topic, qos_profile_sensor_data)
        self.create_subscription(
            TwistStamped, args.cmd_vel_topic, self._on_cmd_vel, 10)

        self.create_timer(0.05, self._publish)

    def _on_prearm(self, request, response):
        self.seen.add("prearm")
        response.success = True
        response.message = "fake"
        return response

    def _on_mode(self, request, response):
        self.seen.add("mode")
        response.status = True
        response.curr_mode = request.mode
        return response

    def _on_arm(self, request, response):
        self.seen.add("arm")
        self._armed = request.arm
        response.result = True
        return response

    def _on_takeoff(self, request, response):
        self.seen.add("takeoff")
        # Climb instantly, so the node's retry is not what is under test here.
        self._altitude = request.alt
        response.status = True
        return response

    def _on_cmd_vel(self, msg: TwistStamped):
        self.seen.add("cmd_vel")
        self.cmd_vel_seen += 1
        self.forward_seen = max(self.forward_seen, msg.twist.linear.x)

    def _publish(self):
        now = self.get_clock().now().to_msg()

        scan = LaserScan()
        scan.header.stamp = now
        scan.header.frame_id = "front_lidar_link"
        scan.angle_min = -0.5236
        scan.angle_max = 0.5236
        scan.angle_increment = 0.01745
        scan.range_min = 0.10
        scan.range_max = 8.0
        scan.ranges = [self._range] * 61
        self._scan_pub.publish(scan)

        pose = PoseStamped()
        pose.header.stamp = now
        pose.header.frame_id = "base_link"
        pose.pose.position.z = self._altitude
        self._pose_pub.publish(pose)

        status = Status()
        status.header.stamp = now
        status.armed = self._armed
        status.flying = self._altitude > 0.1
        self._status_pub.publish(status)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prearm-service", default="/ap/prearm_check")
    parser.add_argument("--mode-service", default="/ap/mode_switch")
    parser.add_argument("--arm-service", default="/ap/arm_motors")
    parser.add_argument("--takeoff-service", default="/ap/experimental/takeoff")
    parser.add_argument("--scan-topic", default="/openipc_cinewhoop/scan/front")
    parser.add_argument("--pose-topic", default="/ap/pose/filtered")
    parser.add_argument("--status-topic", default="/ap/status")
    parser.add_argument("--cmd-vel-topic", default="/ap/cmd_vel")
    parser.add_argument("--range-m", type=float, default=5.0,
                        help="range every beam reports; above the stop threshold "
                             "the node should cruise, below it should hold")
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument("--expect-forward", action="store_true",
                        help="also require a non-zero forward velocity command")
    args = parser.parse_args()

    rclpy.init()
    node = FakeArduPilot(args)
    wanted = {"prearm", "mode", "arm", "takeoff", "cmd_vel"}
    deadline = node.get_clock().now().nanoseconds / 1e9 + args.timeout_s
    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.1)
            if wanted <= node.seen and (not args.expect_forward
                                        or node.forward_seen > 0.0):
                break
            if node.get_clock().now().nanoseconds / 1e9 > deadline:
                break
    finally:
        missing = sorted(wanted - node.seen)
        print("used:", ", ".join(sorted(node.seen)) or "nothing")
        print(f"cmd_vel messages: {node.cmd_vel_seen}, "
              f"peak forward: {node.forward_seen:.2f} m/s")
        node.destroy_node()
        rclpy.shutdown()
    if missing:
        print("never used:", ", ".join(missing), file=sys.stderr)
        return 1
    if args.expect_forward and node.forward_seen <= 0.0:
        print("the node never commanded forward motion", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
