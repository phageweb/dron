"""The one node allowed to write /ap/cmd_vel when the swarm is flying.

Guarantee G9 in `spec/roj/02_vrstva_drona.md`, and the agent's half of the seam
decided in `spec/roj/08_rozhodnuti.md` R19. The coordinator sends a speed
limit; this clips the autonomy's own command with it and passes the result to
the autopilot. It never invents a direction and never decides where to go.

Why the clipping lives here and not in the coordinator: `simple_indoor_autonomy`
is the node that stops for walls, refuses to fly on a stale scan, rejects floor
returns and lands on a flat battery. A coordinator that published `/ap/cmd_vel`
itself would be bypassing all of that, and the first bug in it would be a
machine flown into a wall by the layer that exists to prevent collisions. With
the arbiter in between, the worst a wrong limit can do is make the vehicle
slow or stop.

It is opt-in, and deliberately so. With no arbiter running the autonomy
publishes straight to `/ap/cmd_vel` exactly as it does today, which is what
every existing single-drone check flies. Starting it changes who writes that
topic, so a swarm run starts it and a single-drone run does not.
"""

import rclpy
from geometry_msgs.msg import TwistStamped
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from std_msgs.msg import Float32


def clipped_speed(nominal_mps: float, limit_mps: float) -> float:
    """The commanded speed, never faster than the limit, sign preserved.

    Clipping the magnitude rather than the value: a limit is about how fast
    the machine may move, not which way, and `min()` on a negative command
    would turn a slow reverse into a fast one.
    """
    limit = max(0.0, limit_mps)
    if nominal_mps > limit:
        return limit
    if nominal_mps < -limit:
        return -limit
    return nominal_mps


def effective_limit(
    limit_mps,
    age_s,
    timeout_s: float,
    fallback_mps: float,
) -> float:
    """Which limit applies, given how long ago the coordinator last spoke.

    Silence is not permission. A limit that has gone stale is replaced by the
    fallback - slow, not stopped - because a stopped agent cannot even back
    out of a deadlock, and because the agent's own failsafe (G3,
    `GUID_TIMEOUT`) is the thing that stops it when commands stop arriving.
    The fallback exists for the gap between "the coordinator is quiet" and
    "the autopilot has noticed", which is up to `GUID_TIMEOUT` long.
    """
    if limit_mps is None or age_s is None or age_s > timeout_s:
        return fallback_mps
    return max(0.0, limit_mps)


class Arbiter(Node):
    def __init__(self):
        super().__init__("arbiter")
        self.declare_parameter("nominal_topic", "/v1/cmd_vel_nominal")
        self.declare_parameter("constraint_topic", "/v1/swarm/constraint")
        self.declare_parameter("command_topic", "/ap/v1/cmd_vel")
        # How long a speed limit stays valid. Shorter than GUID_TIMEOUT on
        # purpose: the agent should be creeping under the fallback before the
        # autopilot's own failsafe decides the whole link is gone.
        self.declare_parameter("constraint_timeout_s", 1.0)
        # What applies when the coordinator has said nothing recently. Slow
        # enough that a surprise is survivable, fast enough to get out of the
        # way; 0.25 m/s is the lowest step M1 measured a braking distance for,
        # and it stops in 0.14 m.
        self.declare_parameter("fallback_speed_mps", 0.25)

        self._limit = None
        self._limit_time = None

        self._pub = self.create_publisher(
            TwistStamped, self.get_parameter("command_topic").value, 10)
        self.create_subscription(
            TwistStamped, self.get_parameter("nominal_topic").value,
            self._on_nominal, qos_profile_sensor_data)
        self.create_subscription(
            Float32, self.get_parameter("constraint_topic").value,
            self._on_constraint, 10)

        self.get_logger().info(
            f"Arbiter up: {self.get_parameter('nominal_topic').value} clipped "
            f"to {self.get_parameter('constraint_topic').value}, out on "
            f"{self.get_parameter('command_topic').value}")

    def _on_constraint(self, msg: Float32):
        self._limit = float(msg.data)
        self._limit_time = self.get_clock().now()

    def _on_nominal(self, msg: TwistStamped):
        # Pass-through timing: one command out per command in, so the rate the
        # autopilot sees is the rate the autonomy chose and the arbiter cannot
        # silence the vehicle by failing to tick.
        age = None
        if self._limit_time is not None:
            age = (self.get_clock().now() - self._limit_time).nanoseconds * 1e-9
        limit = effective_limit(
            self._limit, age,
            float(self.get_parameter("constraint_timeout_s").value),
            float(self.get_parameter("fallback_speed_mps").value))

        out = TwistStamped()
        out.header = msg.header
        out.twist.linear.x = clipped_speed(msg.twist.linear.x, limit)
        out.twist.linear.y = clipped_speed(msg.twist.linear.y, limit)
        out.twist.linear.z = clipped_speed(msg.twist.linear.z, limit)
        # Yaw is not a speed limit's business: turning in place cannot close
        # the distance to another agent, and clipping it would stop a vehicle
        # from turning away from one.
        out.twist.angular = msg.twist.angular
        self._pub.publish(out)


def main():
    rclpy.init()
    node = Arbiter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
