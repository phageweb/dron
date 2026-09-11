"""Put the flight controller's position estimate into TF, as map -> base_link.

Until this existed the TF tree had no root in the world. robot_state_publisher
serves base_link and everything bolted to it, so the tree knew where the lidar
was relative to the airframe and nothing knew where the airframe was. That is
why RViz cannot draw the occupancy map: the grid is stamped in a `map` frame
that no transform reaches, and a frame nothing connects is a frame nothing can
place anything in.

The pose is taken from `/ap/pose/filtered` and used as the transform directly.
That message's own `header.frame_id` says `base_link`, and it is simply wrong:
AP_DDS fills the body from `get_relative_position_NED_home` swapped into ENU, so
the content is where base_link is relative to home - a world-fixed frame - and a
pose saying where base_link is cannot itself be expressed in base_link, or it
would be zero for ever. Anything that believed the label would pin every mapped
return to the vehicle. The label is therefore ignored, deliberately and here
rather than silently.

REP 105 wants map -> odom -> base_link, with odom continuous and map corrected in
jumps. There is one estimate here and no second source to correct it with, so the
two frames would be the same transform written twice. The cost of collapsing them
is real and worth naming: when the EKF resets or the position jumps, base_link
teleports, where a separate odom frame would have absorbed the jump into
map -> odom and left odom -> base_link smooth. Nothing downstream depends on that
smoothness today.
"""

import rclpy
from geometry_msgs.msg import PoseStamped, TransformStamped
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from tf2_ros import TransformBroadcaster


class PoseTfBroadcaster(Node):
    def __init__(self):
        super().__init__("pose_tf_broadcaster")
        self.declare_parameter("pose_topic", "/ap/pose/filtered")
        self.declare_parameter("frame_id", "map")
        self.declare_parameter("child_frame_id", "base_link")

        self._frame = self.get_parameter("frame_id").value
        self._child = self.get_parameter("child_frame_id").value
        self._broadcaster = TransformBroadcaster(self)
        self._announced = False

        topic = self.get_parameter("pose_topic").value
        self.create_subscription(
            PoseStamped, topic, self._on_pose, qos_profile_sensor_data)
        self.get_logger().info(
            f"Broadcasting {self._frame} -> {self._child} from {topic}")

    def _on_pose(self, msg: PoseStamped):
        # No timer and no repeat of the last transform. A pose that stops
        # arriving has to become a gap in TF, not a transform that goes on
        # asserting where the vehicle was: a consumer meeting a gap refuses to
        # transform, which is the answer an unknown position deserves, while one
        # meeting a stale transform draws the map somewhere confidently wrong.
        if not self._announced:
            self.get_logger().info(
                f"First pose in; AP_DDS stamps these '{msg.header.frame_id}', "
                "which describes where base_link is rather than the frame it is "
                "in, so the frame is taken from this node's parameters instead.")
            self._announced = True

        transform = TransformStamped()
        # The pose's own stamp, not this node's clock. TF is looked up by time,
        # and restamping a measurement with the moment it was handled makes
        # every consumer's interpolation wrong by the handling delay.
        #
        # That was nearly changed, and the measurement is worth keeping. This
        # simulation runs two clocks: Gazebo's /clock, and every sensor message
        # the bridge carries, count seconds from when the simulator started,
        # while AP_DDS stamps this pose with ArduPilot's UTC - 22.3 s against
        # 1789156172 in the same instant. So a consumer on sim time sees this
        # transform 56 years in the future and can look it up at "latest" and at
        # no particular time at all. A consumer on the wall clock is fine, and
        # measurably so: 20 lookups out of 20 at a stamp half a second old. That
        # is why sitl_gazebo.launch.py puts RViz on the wall clock rather than
        # why this node restamps anything.
        transform.header.stamp = msg.header.stamp
        transform.header.frame_id = self._frame
        transform.child_frame_id = self._child
        transform.transform.translation.x = msg.pose.position.x
        transform.transform.translation.y = msg.pose.position.y
        transform.transform.translation.z = msg.pose.position.z
        transform.transform.rotation = msg.pose.orientation
        self._broadcaster.sendTransform(transform)


def main(args=None):
    rclpy.init(args=args)
    node = PoseTfBroadcaster()
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
