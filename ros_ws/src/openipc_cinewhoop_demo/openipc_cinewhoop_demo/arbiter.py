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

Two modes. `scalar` is R19 as first decided: one speed limit, each
component clipped to it. `vector` (R19a, the default since 2026-10-05) also
takes the coordinator's barrier half-planes and moves the command to the
nearest velocity inside them (`velocity_barrier`): it may add a slow
sideways component, which is what
lets two agents face to face pass by the right instead of both standing
still. It reads the agent's own 360° scan for that, so that what it adds
never heads into a wall the autonomy did not look at. Stale half-planes are
ignored and the scalar limit applies alone, with its own fallback; a stale
scan leaves the sideways part at `lateral_max_mps` with no wall check, as it
was before the walls were added.

It is opt-in, and deliberately so. With no arbiter running the autonomy
publishes straight to `/ap/cmd_vel` exactly as it does today, which is what
every existing single-drone check flies. Starting it changes who writes that
topic, so a swarm run starts it and a single-drone run does not.
"""

import rclpy
from geometry_msgs.msg import TwistStamped
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Float32, Float32MultiArray

from openipc_cinewhoop_demo.velocity_barrier import (
    filter_velocity,
    wall_half_planes,
)


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


def to_ap_body_y(y_left_mps: float) -> float:
    """A ROS body-frame y (left) as AP_DDS actually reads it.

    `AP_DDS_ExternalControl::handle_velocity_control` says it takes base_link
    as x forward, y left, z up, flips z, and hands the vector to
    `body_to_earth`, which is forward-right-down: y is never flipped, so a
    positive y flies right. The autonomy never sent a y and never met it;
    the first flight with the barrier did, and every sideways step went the
    mirror way - the right-hand rule became a left-hand one and a back-off
    from a neighbour beside the agent closed on it, to 0.20 m.
    """
    return -y_left_mps


def barrier_command(x: float, y: float, flat, age_s, timeout_s: float,
                    lateral_max_mps: float, back_off_max_mps: float = 0.25,
                    walls=()):
    """The horizontal command filtered by the barrier, if it is fresh.

    `flat` is the message as sent: a_x, a_y, b for each neighbour, in the
    body frame. `walls` are `wall_half_planes` of the latest scan, also in
    the body frame. Returns (x, y, action); action "none" when there was
    nothing fresh to filter with, and the command then passes unchanged.
    """
    if flat is None or age_s is None or age_s > timeout_s:
        return x, y, "none"
    if len(flat) % 3:
        return x, y, "none"
    planes = [tuple(flat[i:i + 3]) for i in range(0, len(flat), 3)]
    (fx, fy), action = filter_velocity((x, y), planes, lateral_max_mps,
                                       walls=walls)
    if action == "back_off":
        # Straight away from the neighbours, possibly into a wall when there
        # was no other way: no faster than it takes to open the gap gently.
        speed = (fx * fx + fy * fy) ** 0.5
        if speed > back_off_max_mps:
            fx, fy = fx * back_off_max_mps / speed, fy * back_off_max_mps / speed
    return fx, fy, action


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
        # "scalar" (R19) or "vector" (R19a): see the module docstring.
        self.declare_parameter("filter_mode", "vector")
        self.declare_parameter("barrier_topic", "/v1/swarm/barrier")
        # The most the barrier may add that the autonomy did not ask for:
        # sideways, or backwards. 0.15 while nothing checked those
        # directions for walls; the scan's wall planes do now.
        self.declare_parameter("lateral_max_mps", 0.25)
        # Wall planes from the agent's own lidar (`wall_half_planes`).
        self.declare_parameter("scan_topic", "/v1/scan/front")
        self.declare_parameter("wall_clearance_m", 0.30)
        self.declare_parameter("scan_timeout_s", 0.5)
        self._mode = str(self.get_parameter("filter_mode").value)
        if self._mode not in ("scalar", "vector"):
            raise ValueError(f"filter_mode {self._mode!r}: scalar or vector")
        self._barrier = None
        self._barrier_time = None
        self._walls = []
        self._walls_time = None

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
        if self._mode == "vector":
            self.create_subscription(
                Float32MultiArray, self.get_parameter("barrier_topic").value,
                self._on_barrier, 10)
            self.create_subscription(
                LaserScan, self.get_parameter("scan_topic").value,
                self._on_scan, qos_profile_sensor_data)

        self.get_logger().info(
            f"Arbiter up: {self.get_parameter('nominal_topic').value} clipped "
            f"to {self.get_parameter('constraint_topic').value}, out on "
            f"{self.get_parameter('command_topic').value}")

    def _on_constraint(self, msg: Float32):
        self._limit = float(msg.data)
        self._limit_time = self.get_clock().now()

    def _on_barrier(self, msg: Float32MultiArray):
        self._barrier = list(msg.data)
        self._barrier_time = self.get_clock().now()

    def _on_scan(self, msg: LaserScan):
        self._walls = wall_half_planes(
            msg.ranges, msg.angle_min, msg.angle_increment,
            msg.range_min, msg.range_max,
            float(self.get_parameter("wall_clearance_m").value))
        self._walls_time = self.get_clock().now()

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

        x, y = msg.twist.linear.x, msg.twist.linear.y
        if self._mode == "vector":
            barrier_age = None
            if self._barrier_time is not None:
                barrier_age = (self.get_clock().now()
                               - self._barrier_time).nanoseconds * 1e-9
            # Without a fresh scan nothing checks sideways for walls, so the
            # sideways allowance falls back to what it was before it did.
            walls, lateral = (), 0.15
            scan_age = None
            if self._walls_time is not None:
                scan_age = (self.get_clock().now()
                            - self._walls_time).nanoseconds * 1e-9
            if scan_age is not None and scan_age <= float(
                    self.get_parameter("scan_timeout_s").value):
                walls = self._walls
                lateral = float(self.get_parameter("lateral_max_mps").value)
            x, y, _ = barrier_command(
                x, y, self._barrier, barrier_age,
                float(self.get_parameter("constraint_timeout_s").value),
                lateral, walls=walls)

        out = TwistStamped()
        out.header = msg.header
        out.twist.linear.x = clipped_speed(x, limit)
        # The arbiter is the boundary to the autopilot, so the ROS axis is
        # turned into the one AP_DDS reads here, whatever the mode.
        out.twist.linear.y = to_ap_body_y(clipped_speed(y, limit))
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
