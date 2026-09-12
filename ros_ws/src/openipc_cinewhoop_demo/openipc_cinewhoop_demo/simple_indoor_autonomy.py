"""Slow indoor forward flight that stops for obstacles.

The node takes the vehicle off the ground itself through ArduPilot's ROS 2
services, then creeps forward while watching the front lidar. It is meant to be
readable and slow rather than clever: every step is a named state and the
vehicle refuses to move whenever it cannot see.
"""

import math

import rclpy
from geometry_msgs.msg import PointStamped, PoseStamped, TwistStamped
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan, Range
from std_srvs.srv import Trigger

from openipc_cinewhoop_demo.scan_helpers import (
    compensation_height,
    nearest_in_corridor,
    nearest_valid_range,
    relative_bearing,
    turn_direction,
    turn_is_finished,
    turn_is_going_round,
    turn_sign_towards,
    way_is_clear,
    hold_reason,
    nearest_in_sector,
    reading_is_fresh,
    roll_pitch_from_quaternion,
    safe_forward_speed,
    takeoff_needs_retry,
    yaw_from_quaternion,
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
        # how far ahead it means. This is still how the vehicle asks what is off
        # each wing; what is in front of it is the corridor below.
        self.declare_parameter("forward_sector_deg", 60.0)
        # What is in the way is asked about as the swath the vehicle flies down
        # rather than as a cone, because a cone cannot tell a wall from a
        # doorjamb: at the 1.7 m this demo wants clear a 60 degree cone spans
        # 1.7 m across, so no opening narrower than that can ever read clear,
        # and the vehicle is 0.167 m wide. The coverage flight showed what that
        # costs - eight approaches to a 1.6 m door, eight turns away at 1.35 to
        # 1.40 m - and no better steering could have got through it.
        #
        # The rotor tips reach this far from the centre in every direction:
        # 0.04525 m of arm plus a 0.0381 m propeller radius, the numbers that
        # are in the model. check_model_consistency.py fails if the airframe
        # moves away from them, the same guard the sensor offsets have.
        self.declare_parameter("rotor_tip_half_width_m", 0.08335)
        # How much room to leave either side of the tips. The forward flight
        # check measures 0.16 to 0.23 m of clearance where the vehicle stops
        # itself against a wall, so this is the same order of room asked for
        # sideways, rounded up: it covers the cross-track error of a GUIDED
        # velocity command and the yaw the vehicle holds while cruising. It
        # makes the corridor 0.67 m wide, so the 1.6 m door has to be found to
        # within 0.47 m of its centre rather than exactly.
        self.declare_parameter("corridor_margin_m", 0.25)
        # The lidar leans with the airframe, so its forward beams find the floor
        # as soon as the nose drops. Returns that work out to be the ground are
        # dropped, which needs the height the downward rangefinder measures.
        self.declare_parameter("range_topic", "/openipc_cinewhoop/range/down")
        # An error bar rather than a clearance, which is what it always was.
        # `ground_margin_m` covers what is wrong here - the rangefinder's
        # reading, the floor not being flat - and the attitude term covers the
        # lean, which is the part that grows with distance: an attitude wrong by
        # two degrees puts a return 3 m out wrong by 0.10 m. A flat bar big
        # enough for the far field throws away near walls struck low, which is
        # exactly what a leaning vehicle's forward beams do.
        self.declare_parameter("ground_margin_m", 0.10)
        self.declare_parameter("ground_attitude_margin_deg", 2.0)
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
        # Turning towards somewhere chosen instead of towards the roomier side.
        # Off by default and separate from enable_turning, because the two are
        # different promises: turning at all is what check_room_circuit.sh
        # verifies, and where to turn is what check_room_coverage.sh measures.
        # With this off the demo is the reactive circuit it has always been,
        # frontier_explorer running or not.
        self.declare_parameter("enable_exploring", False)
        self.declare_parameter("target_topic", "/openipc_cinewhoop/explore/target")
        # The target comes from another node reading a map built from a third
        # node's scans, so it is the furthest thing here from first hand and it
        # gets the same freshness guard as everything else that is not. A stale
        # target means the explorer has stopped or has nothing left to say, and
        # the answer is the reactive rule rather than a heading from memory.
        self.declare_parameter("target_timeout_s", 3.0)
        # How close to the nose the target has to be before the turn may end.
        # Wide enough that the vehicle is not chasing the last degree while a
        # wall sits in front of it, narrow enough to be a direction: at 4 m,
        # 10 degrees is 0.7 m.
        self.declare_parameter("align_tolerance_deg", 10.0)

        self._nearest = None
        self._scan_has_returns = False
        self._left = None
        self._right = None
        self._turn_sign = 0.0
        # Whether the turn in progress has set its target aside and is just
        # looking for a way through. Per turn, cleared by _enter(TURN).
        self._going_round = False
        self._last_scan_time = None
        self._roll = 0.0
        self._pitch = 0.0
        self._yaw = 0.0
        self._position = None
        self._target = None
        self._target_time = None
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
        self.create_subscription(
            PointStamped, self.get_parameter("target_topic").value,
            self._on_target, 10)

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
        lean_margin = math.radians(
            float(self.get_parameter("ground_attitude_margin_deg").value))

        def nearest(centre_rad):
            return nearest_in_sector(
                msg.ranges, msg.angle_min, msg.angle_increment,
                msg.range_min, msg.range_max,
                sector if centre_rad == 0.0 else side,
                self._roll, self._pitch, height, margin, centre_rad,
                lean_margin)

        # What is in the way, which is a different question from what is in
        # front: the corridor reports how far the vehicle gets flying straight,
        # and ignores what it would pass cleanly to one side. obstacle_monitor
        # still reports the cone, and that is not the two nodes disagreeing -
        # it is telling whoever is watching what is nearby, which is what a
        # proximity warning is for, while this decides whether to move.
        # Whether the lidar saw anything at all, anywhere in its sweep, which
        # is a different question from whether anything is in the way and has to
        # be asked separately now that the way ahead is a corridor. A corridor
        # with nothing in it is the ordinary case of a clear run; a scan with
        # nothing in it is a vehicle that cannot see.
        self._scan_has_returns = nearest_valid_range(
            msg.ranges, msg.range_min, msg.range_max) is not None
        tip = float(self.get_parameter("rotor_tip_half_width_m").value)
        self._nearest = nearest_in_corridor(
            msg.ranges, msg.angle_min, msg.angle_increment,
            msg.range_min, msg.range_max,
            tip + float(self.get_parameter("corridor_margin_m").value), tip,
            self._roll, self._pitch, height, margin, lean_margin)
        # What is off each wing, for deciding which way to turn, and a cone is
        # right for that one: the question there is which side has more room,
        # not what the vehicle would hit going sideways, which it never does.
        # The same floor rejection applies: leaning, the floor is off the wing
        # too.
        self._left = nearest(math.pi / 2.0)
        self._right = nearest(-math.pi / 2.0)
        self._last_scan_time = self.get_clock().now()

    def _on_status(self, msg):
        self._armed = msg.armed

    def _on_pose(self, msg: PoseStamped):
        self._altitude = msg.pose.position.z
        # Where the vehicle is, as well as how it is leaning. The pose's own
        # header.frame_id says base_link and is wrong - AP_DDS fills the body
        # from get_relative_position_NED_home swapped into ENU, so the content
        # is where base_link is relative to home, which cannot be expressed in
        # base_link. It is the same frame the map is built in, which is the only
        # reason a target out of the map can be compared against it at all.
        self._position = (msg.pose.position.x, msg.pose.position.y)
        q = msg.pose.orientation
        self._roll, self._pitch = roll_pitch_from_quaternion(q.x, q.y, q.z, q.w)
        self._yaw = yaw_from_quaternion(q.x, q.y, q.z, q.w)
        self._pose_time = self.get_clock().now()

    def _on_target(self, msg: PointStamped):
        self._target = (msg.point.x, msg.point.y)
        self._target_time = self.get_clock().now()

    def _bearing_to_target(self):
        """Where the chosen opening lies relative to the nose, or None.

        None every time anything is missing or stale, and None is what makes
        the steering fall back to the reactive rule rather than to a guess.
        """
        if not bool(self.get_parameter("enable_exploring").value):
            return None
        if self._target is None or self._position is None:
            return None
        if self._target_time is None:
            return None
        age = (self.get_clock().now() - self._target_time).nanoseconds * 1e-9
        if not reading_is_fresh(
                age, float(self.get_parameter("target_timeout_s").value)):
            return None
        return relative_bearing(
            self._position[0], self._position[1], self._yaw,
            self._target[0], self._target[1])

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
        if state == TURN:
            # Each turn asks the target question again from scratch, against
            # the map as it now stands rather than as it stood last time.
            self._going_round = False
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

        clear = way_is_clear(
            self._nearest,
            float(self.get_parameter("stop_distance_m").value),
            float(self.get_parameter("braking_distance_m").value),
            float(self.get_parameter("turn_clear_margin_m").value))
        bearing = self._bearing_to_target()
        tolerance = math.radians(
            float(self.get_parameter("align_tolerance_deg").value))

        was_going_round = self._going_round
        self._going_round = turn_is_going_round(
            bearing, clear, tolerance, self._going_round)
        if self._going_round and not was_going_round:
            self.get_logger().info(
                "The opening is on the nose and the way is still blocked, so "
                "it is behind a wall; carrying on round to look for another")

        if turn_is_finished(bearing, clear, tolerance, self._going_round):
            ahead = ("nothing in range" if self._nearest is None
                     else f"{self._nearest:.2f} m of room")
            towards = ("" if bearing is None or self._going_round
                       else f", pointed at the opening within "
                            f"{math.degrees(abs(bearing)):.0f} deg")
            self.get_logger().info(f"Turn finished: {ahead} ahead{towards}")
            self._hold_reason = None
            self._enter(CRUISE)
            return

        # The sign is recomputed every tick rather than held from the decision
        # that started the turn, so while the target is off to one side this
        # steers towards it by the short way round and self-corrects on an
        # overshoot. What is held is the decision to stop steering at it: once
        # the turn has committed to going round, the latched sign carries it the
        # rest of the way. Recomputing that part every tick instead is what left
        # the vehicle rocking at the edge of the tolerance for 92 seconds of a
        # 130 second flight.
        self._publish(
            0.0,
            turn_sign_towards(
                bearing, tolerance, self._turn_sign, self._going_round)
            * float(self.get_parameter("turn_yaw_rate_rps").value))

    def _cruise(self, fresh):
        speed = 0.0
        if fresh:
            speed = safe_forward_speed(
                self._nearest,
                self._scan_has_returns,
                float(self.get_parameter("stop_distance_m").value),
                float(self.get_parameter("forward_speed_mps").value),
                float(self.get_parameter("braking_distance_m").value))

        if speed == 0.0:
            # A fresh scan can still be all inf or nan, which is a blind
            # vehicle rather than a clear way ahead.
            reason, detail = hold_reason(
                fresh, self._scan_has_returns, self._nearest)
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
                # The reactive choice is still made, and it is still what the
                # vehicle turns on when there is nothing better. What it is not
                # any more is the whole decision: with an opening to fly at, the
                # side with more room is only the direction to go round in when
                # that opening turns out to be behind something.
                self._turn_sign = turn_direction(self._left, self._right)
                towards = "left" if self._turn_sign > 0 else "right"
                bearing = self._bearing_to_target()
                if bearing is None:
                    self.get_logger().info(
                        f"Turning {towards}: "
                        f"{self._describe(self._left)} off the left wing, "
                        f"{self._describe(self._right)} off the right")
                else:
                    self.get_logger().info(
                        f"Turning towards the opening at "
                        f"({self._target[0]:+.2f}, {self._target[1]:+.2f}), "
                        f"{math.degrees(bearing):+.0f} deg off the nose; "
                        f"{towards} if it turns out to be blocked")
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
