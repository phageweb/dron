"""Slow indoor forward flight that stops for obstacles.

The node takes the vehicle off the ground itself through ArduPilot's ROS 2
services, then creeps forward while watching the front lidar. It is meant to be
readable and slow rather than clever: every step is a named state and the
vehicle refuses to move whenever it cannot see.
"""

import math

import rclpy
from geometry_msgs.msg import PoseStamped, TwistStamped
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan, Range
from std_srvs.srv import Trigger

from openipc_cinewhoop_demo.scan_helpers import (
    compensation_height,
    turn_direction,
    way_is_clear,
    hold_reason,
    nearest_in_sector,
    reading_is_fresh,
    roll_pitch_from_quaternion,
    safe_forward_speed,
    takeoff_needs_retry,
)

# ArduPilot's own message package lives in the opt-in DDS workspace, so it is
# imported lazily: the velocity-only mode and the unit tests must work without it.
try:
    from ardupilot_msgs.msg import Status
    from ardupilot_msgs.srv import ArmMotors, ModeSwitch, Takeoff
    ARDUPILOT_SRVS = True
except ImportError:  # pragma: no cover - depends on an external workspace
    ARDUPILOT_SRVS = False

GUIDED_MODE = 4

WAIT_SCAN = "waiting for the front lidar"
WAIT_SERVICES = "waiting for ArduPilot services"
PREARM = "waiting for the vehicle to become armable"
MODE = "switching to GUIDED"
ARM = "arming"
WAIT_ARMED = "waiting for the motors to arm"
TAKEOFF = "taking off"
CLIMB = "climbing to altitude"
CRUISE = "cruising"
TURN = "turning away from an obstacle"


class SimpleIndoorAutonomy(Node):
    def __init__(self):
        super().__init__("simple_indoor_autonomy")
        self.declare_parameter("scan_topic", "/openipc_cinewhoop/scan/front")
        self.declare_parameter("cmd_vel_topic", "/ap/cmd_vel")
        self.declare_parameter("forward_speed_mps", 0.5)
        self.declare_parameter("stop_distance_m", 0.8)
        # Measured from Gazebo ground truth: a stop from 0.5 m/s coasts about
        # 0.6 m under ArduPilot's default horizontal motion shaping. Without
        # this the vehicle held 0.8 m from the wall and then drifted to 0.2 m.
        self.declare_parameter("braking_distance_m", 0.6)
        self.declare_parameter("takeoff_altitude_m", 1.0)
        self.declare_parameter("scan_timeout_s", 0.5)
        # The LD06 sweeps all 360 degrees, so "the obstacle ahead" has to say
        # how far ahead it means. Without this the vehicle stops for the wall
        # behind it, on hardware exactly as in simulation.
        self.declare_parameter("forward_sector_deg", 60.0)
        # The lidar leans with the airframe, so its forward beams find the floor
        # as soon as the nose drops. Returns that work out to be the ground are
        # dropped, which needs the height the downward rangefinder measures.
        self.declare_parameter("range_topic", "/openipc_cinewhoop/range/down")
        self.declare_parameter("ground_margin_m", 0.25)
        # The scan has a freshness guard and these two did not, although neither
        # arrives with the scan: the pose comes from the flight controller over
        # DDS and the height from a different sensor. A lean that stopped
        # arriving keeps being applied to every scan after it.
        self.declare_parameter("compensation_timeout_s", 0.5)
        # The rangefinder is not the sensor being projected. It sits behind and
        # below the lidar, so its reading is not the lidar's height: level, that
        # is 66 mm thrown away. These are the URDF's own numbers and
        # check_model_consistency.py fails if the model moves away from them.
        self.declare_parameter("lidar_ahead_of_rangefinder_m", 0.026)
        self.declare_parameter("lidar_above_rangefinder_m", 0.066)
        self.declare_parameter("pose_topic", "/ap/pose/filtered")
        self.declare_parameter("status_topic", "/ap/status")
        # Service names are parameters for the same reason the topic names are:
        # spec/realna_stavba_dronu/02_rozhrani_sim_real.md requires that moving
        # from SITL to hardware changes the launch, not the algorithm.
        self.declare_parameter("prearm_service", "/ap/prearm_check")
        self.declare_parameter("mode_service", "/ap/mode_switch")
        self.declare_parameter("arm_service", "/ap/arm_motors")
        self.declare_parameter("takeoff_service", "/ap/experimental/takeoff")
        # An accepted takeoff that does not lift the vehicle is re-requested
        # after this long; ArduPilot auto-disarms after ten seconds on the
        # ground, so the window has to be well inside that.
        self.declare_parameter("takeoff_retry_s", 3.0)
        self.declare_parameter("climb_margin_m", 0.15)
        # With auto_takeoff false the node only publishes velocity and expects
        # something else to have put the vehicle in the air.
        self.declare_parameter("auto_takeoff", True)
        # Turning is off by default. Stopping for the wall is the behaviour the
        # flight check verifies and the one worth trusting; flying on past it is
        # a second thing to ask for, not a change to the first.
        self.declare_parameter("enable_turning", False)
        self.declare_parameter("turn_yaw_rate_rps", 0.4)
        # Resuming demands more clearance than stopping did, so a vehicle that
        # has just turned away from a wall does not find itself back inside the
        # threshold and turn again. Without the gap the two decisions chatter.
        self.declare_parameter("turn_clear_margin_m", 0.3)
        self.declare_parameter("side_sector_deg", 60.0)

        self._nearest = None
        self._left = None
        self._right = None
        self._turn_sign = 0.0
        self._last_scan_time = None
        self._roll = 0.0
        self._pitch = 0.0
        self._slant_range = None
        self._pose_time = None
        self._range_time = None
        self._blind_reason = None
        self._pending = None
        self._hold_reason = None
        self._altitude = None
        self._armed = False
        self._takeoff_time = None
        self._altitude_at_takeoff = None

        scan_topic = self.get_parameter("scan_topic").value
        self.create_subscription(
            LaserScan, scan_topic, self._on_scan, qos_profile_sensor_data)
        self._cmd_pub = self.create_publisher(
            TwistStamped, self.get_parameter("cmd_vel_topic").value, 10)
        self.create_subscription(
            PoseStamped, self.get_parameter("pose_topic").value,
            self._on_pose, qos_profile_sensor_data)
        self.create_subscription(
            Range, self.get_parameter("range_topic").value,
            self._on_range, qos_profile_sensor_data)

        self._auto = bool(self.get_parameter("auto_takeoff").value)
        if self._auto and not ARDUPILOT_SRVS:
            raise RuntimeError(
                "auto_takeoff needs ardupilot_msgs. Source the DDS workspace "
                "(external/dds_ws/install/setup.bash) or set auto_takeoff:=false."
            )

        if self._auto:
            self.create_subscription(
                Status, self.get_parameter("status_topic").value,
                self._on_status, qos_profile_sensor_data)
            self._prearm = self.create_client(
                Trigger, self.get_parameter("prearm_service").value)
            self._mode = self.create_client(
                ModeSwitch, self.get_parameter("mode_service").value)
            self._arm = self.create_client(
                ArmMotors, self.get_parameter("arm_service").value)
            self._takeoff = self.create_client(
                Takeoff, self.get_parameter("takeoff_service").value)

        self._state = WAIT_SCAN
        self.create_timer(0.1, self._tick)
        self.get_logger().info(
            f"Listening on {scan_topic}; "
            f"{'will arm and take off' if self._auto else 'velocity only'}.")

    def _on_scan(self, msg: LaserScan):
        sector = math.radians(
            float(self.get_parameter("forward_sector_deg").value))
        side = math.radians(float(self.get_parameter("side_sector_deg").value))
        height = self._rejection_height()
        margin = float(self.get_parameter("ground_margin_m").value)

        def nearest(centre_rad):
            return nearest_in_sector(
                msg.ranges, msg.angle_min, msg.angle_increment,
                msg.range_min, msg.range_max,
                sector if centre_rad == 0.0 else side,
                self._roll, self._pitch, height, margin, centre_rad)

        self._nearest = nearest(0.0)
        # What is off each wing, for deciding which way to turn. The same
        # rejection applies there: leaning, the floor is off the wing too.
        self._left = nearest(math.pi / 2.0)
        self._right = nearest(-math.pi / 2.0)
        self._last_scan_time = self.get_clock().now()

    def _on_status(self, msg):
        self._armed = msg.armed

    def _on_pose(self, msg: PoseStamped):
        self._altitude = msg.pose.position.z
        q = msg.pose.orientation
        self._roll, self._pitch = roll_pitch_from_quaternion(q.x, q.y, q.z, q.w)
        self._pose_time = self.get_clock().now()

    def _on_range(self, msg: Range):
        # Outside the sensor's window the reading means "no detection", and an
        # unknown height must not start discarding real obstacles. What is kept
        # is the slant range the sensor measured, not a height: turning one into
        # the other needs the lean, which compensation_height applies.
        self._slant_range = (msg.range
                             if msg.min_range <= msg.range <= msg.max_range
                             else None)
        self._range_time = self.get_clock().now()

    def _age_s(self, stamp):
        if stamp is None:
            return None
        return (self.get_clock().now() - stamp).nanoseconds / 1e9

    def _rejection_height(self):
        """The height to drop floor returns with, saying so when there is none.

        Switching the rejection off makes the vehicle stop for the floor again,
        which is the safe half of the trade: the unsafe half is a stale lean
        that drops a wall the vehicle is flying at.
        """
        height, reason, detail = compensation_height(
            self._age_s(self._pose_time), self._age_s(self._range_time),
            float(self.get_parameter("compensation_timeout_s").value),
            self._slant_range, self._roll, self._pitch,
            float(self.get_parameter("lidar_ahead_of_rangefinder_m").value),
            float(self.get_parameter("lidar_above_rangefinder_m").value))
        if reason != self._blind_reason:
            if reason:
                self.get_logger().warning(
                    f"Not rejecting floor returns: {reason}{detail}")
            else:
                self.get_logger().info("Rejecting floor returns again")
            self._blind_reason = reason
        return height

    def _since_takeoff_s(self):
        if self._takeoff_time is None:
            return 0.0
        return (self.get_clock().now() - self._takeoff_time).nanoseconds / 1e9

    def _scan_age_s(self):
        if self._last_scan_time is None:
            return None
        return (self.get_clock().now() - self._last_scan_time).nanoseconds / 1e9

    def _enter(self, state):
        self._state = state
        self.get_logger().info(state)

    def _call(self, client, request, on_done):
        """Issue one service call and route its result, one call at a time."""
        if self._pending is not None:
            if not self._pending.done():
                return
            self._pending = None
        if not client.service_is_ready():
            return
        future = client.call_async(request)
        future.add_done_callback(lambda f: on_done(f.result()))
        self._pending = future

    def _tick(self):
        # A stale scan is treated exactly like no scan: the vehicle stops.
        fresh = reading_is_fresh(
            self._scan_age_s(), float(self.get_parameter("scan_timeout_s").value))

        if self._state == WAIT_SCAN:
            if fresh:
                self._enter(WAIT_SERVICES if self._auto else CRUISE)
        elif self._state == WAIT_SERVICES:
            ready = all(c.service_is_ready()
                        for c in (self._prearm, self._mode, self._arm, self._takeoff))
            if ready:
                self._enter(PREARM)
        elif self._state == PREARM:
            self._call(self._prearm, Trigger.Request(), self._on_prearm)
        elif self._state == MODE:
            request = ModeSwitch.Request()
            request.mode = GUIDED_MODE
            self._call(self._mode, request, self._on_mode)
        elif self._state == ARM:
            request = ArmMotors.Request()
            request.arm = True
            self._call(self._arm, request, self._on_arm)
        elif self._state == WAIT_ARMED:
            # The arm service acknowledges the request, not the motors. Asking
            # for takeoff before the vehicle is really armed is accepted and
            # then quietly ignored, and it disarms again a few seconds later.
            if self._armed:
                self._enter(TAKEOFF)
        elif self._state == TAKEOFF:
            request = Takeoff.Request()
            request.alt = float(self.get_parameter("takeoff_altitude_m").value)
            self._call(self._takeoff, request, self._on_takeoff)
        elif self._state == CLIMB:
            # A velocity command in GUIDED replaces the takeoff, so the climb
            # has to finish before any forward motion is published.
            target = float(self.get_parameter("takeoff_altitude_m").value)
            if self._altitude is not None and self._altitude >= target * 0.8:
                self._enter(CRUISE)
            elif not self._armed:
                # ArduPilot auto-disarms after ten seconds on the ground, so a
                # takeoff that never started leaves the vehicle disarmed.
                self.get_logger().warn("Disarmed before the climb; re-arming.")
                self._enter(ARM)
            elif takeoff_needs_retry(
                    self._altitude, self._altitude_at_takeoff,
                    self._since_takeoff_s(),
                    float(self.get_parameter("takeoff_retry_s").value),
                    float(self.get_parameter("climb_margin_m").value)):
                self.get_logger().warn(
                    "Takeoff was accepted but nothing moved; requesting again.")
                self._enter(TAKEOFF)
        elif self._state == CRUISE:
            self._cruise(fresh)
        elif self._state == TURN:
            self._turn(fresh)

    def _on_prearm(self, result):
        if result is not None and result.success:
            self._enter(MODE)

    def _on_mode(self, result):
        if result is not None and result.status:
            self._enter(ARM)

    def _on_arm(self, result):
        # The EKF can report the vehicle armable just before it sets home, so
        # a refusal here is normal and simply retried on the next tick.
        if result is not None and result.result:
            self._enter(WAIT_ARMED)

    def _on_takeoff(self, result):
        if result is not None and result.status:
            # Record where the vehicle was, so the climb can be confirmed
            # against ground truth rather than against the service reply.
            self._altitude_at_takeoff = self._altitude
            self._takeoff_time = self.get_clock().now()
            self._enter(CLIMB)

    def _publish(self, forward_mps, yaw_rps=0.0):
        cmd = TwistStamped()
        cmd.header.stamp = self.get_clock().now().to_msg()
        # AP_DDS reads this frame_id: base_link means body frame, and it is what
        # turns twist.angular.z into a yaw rate rather than nothing at all.
        cmd.header.frame_id = "base_link"
        cmd.twist.linear.x = forward_mps
        cmd.twist.angular.z = yaw_rps
        self._cmd_pub.publish(cmd)

    def _turn(self, fresh):
        """Yaw in place until the way ahead is clear, then cruise again.

        Nothing moves forward here. The demo decides on a forward sector, so
        while the vehicle is rotating it is deciding about air it is not flying
        into; committing to a translation on that would be flying blind through
        the turn.
        """
        if not fresh:
            # A stale scan during a turn is the same danger as during a cruise,
            # and the vehicle stops rather than keeps rotating: the clearance it
            # would resume on could be seconds old.
            if self._hold_reason != "no recent scan":
                self.get_logger().info("Holding: no recent scan")
                self._hold_reason = "no recent scan"
            self._publish(0.0)
            return

        if way_is_clear(
                self._nearest,
                float(self.get_parameter("stop_distance_m").value),
                float(self.get_parameter("braking_distance_m").value),
                float(self.get_parameter("turn_clear_margin_m").value)):
            ahead = ("nothing in range" if self._nearest is None
                     else f"{self._nearest:.2f} m of room")
            self.get_logger().info(f"Turn finished: {ahead} ahead")
            self._hold_reason = None
            self._enter(CRUISE)
            return

        self._publish(
            0.0,
            self._turn_sign
            * float(self.get_parameter("turn_yaw_rate_rps").value))

    def _cruise(self, fresh):
        speed = 0.0
        if fresh:
            speed = safe_forward_speed(
                self._nearest,
                float(self.get_parameter("stop_distance_m").value),
                float(self.get_parameter("forward_speed_mps").value),
                float(self.get_parameter("braking_distance_m").value))

        if speed == 0.0:
            # A fresh scan can still be all inf or nan, so nearest may be None.
            reason, detail = hold_reason(fresh, self._nearest)
            # Latch the reason rather than the fact of holding. A vehicle that
            # stops because the scan went stale and then stays stopped because a
            # wall appeared used to log only the first of those, so the log said
            # the lidar was dead long after it had recovered. The reason is what
            # is latched, so the distance does not re-log every 0.1 s.
            if reason != self._hold_reason:
                self.get_logger().info(f"Holding: {reason}{detail}")
                self._hold_reason = reason
            # Only an obstacle is a reason to turn. A stale scan or an empty one
            # means the vehicle cannot see, and rotating on that would be
            # choosing a direction out of a picture it does not have.
            if reason == "obstacle" and bool(
                    self.get_parameter("enable_turning").value):
                # The side is chosen once and latched. A rule that can change
                # its mind halfway through leaves the vehicle rocking in place.
                self._turn_sign = turn_direction(self._left, self._right)
                towards = "left" if self._turn_sign > 0 else "right"
                self.get_logger().info(
                    f"Turning {towards}: "
                    f"{self._describe(self._left)} off the left wing, "
                    f"{self._describe(self._right)} off the right")
                self._enter(TURN)
                return
        else:
            self._hold_reason = None

        self._publish(speed)

    @staticmethod
    def _describe(value):
        return "nothing in range" if value is None else f"{value:.3f} m"


def main(args=None):
    rclpy.init(args=args)
    node = SimpleIndoorAutonomy()
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
