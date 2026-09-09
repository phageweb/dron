import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path
from rclpy.node import Node


class TrajectoryPublisher(Node):
    def __init__(self):
        super().__init__("trajectory_publisher")
        self.declare_parameter("pose_topic", "/ap/pose/filtered")
        self.declare_parameter("path_topic", "/openipc_cinewhoop/path")
        self.declare_parameter("max_points", 2000)

        self._path = Path()
        self._path.header.frame_id = "map"
        pose_topic = self.get_parameter("pose_topic").value
        path_topic = self.get_parameter("path_topic").value
        self._pub = self.create_publisher(Path, path_topic, 10)
        self.create_subscription(PoseStamped, pose_topic, self._on_pose, 10)
        self.get_logger().info(f"Building path from {pose_topic} to {path_topic}")

    def _on_pose(self, msg: PoseStamped):
        self._path.header = msg.header
        self._path.poses.append(msg)
        max_points = int(self.get_parameter("max_points").value)
        if len(self._path.poses) > max_points:
            self._path.poses = self._path.poses[-max_points:]
        self._pub.publish(self._path)


def main(args=None):
    rclpy.init(args=args)
    node = TrajectoryPublisher()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
