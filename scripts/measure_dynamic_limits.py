#!/usr/bin/env python3
"""Measure the four numbers a swarm needs about one machine, from one flight.

`spec/roj/03_vrstva_roje.md` writes the separation between two machines as

    d_safe = 2*r_rotor + 2*e_pozice + v_max*t_latence + s_brzdna + rezerva

and three of those five terms are things nobody in this repository has measured:
the braking distance, the command-to-motion latency, and how far the estimate
drifts from where the vehicle really is. This flies one sortie in an empty room
and produces all three, plus the velocity tracking error that says whether a
commanded speed is the speed that happens.

Everything is measured against Gazebo ground truth rather than against the
estimate under test. The estimate is measured too, but only as the thing being
compared - `/ap/pose/filtered` is what drifts, and a drift cannot be seen from
inside the frame that is drifting.

Two clocks would ruin this. AP_DDS stamps its poses with ArduPilot's UTC while
Gazebo counts from the start of the simulation (see
`workflow/troubleshooting.md`), and the wall clock in this process is a third.
So every interval below is read from **one** stream: the simulator's own stamps
in the ground-truth messages. A command's moment is the simulator stamp of the
last truth sample that had arrived when the command went out, which means the
pipeline delay sits in both ends of every interval and cancels out of the
difference.

Writes a JSON summary and a printed table. Assertions live in the caller;
this program measures and reports, and fails only when it cannot measure.
"""

import argparse
import json
import math
import subprocess
import sys
import threading
import time

import rclpy
from geometry_msgs.msg import PoseStamped, TwistStamped
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

# Below this the vehicle counts as stopped. Ground truth is noiseless, so this
# is not a noise floor - it is "close enough to rest that the remaining creep is
# the position controller, not the manoeuvre".
AT_REST_MPS = 0.05
# A speed has to stay above the threshold this long before it counts as motion,
# so a single differentiated sample cannot start the clock.
MOTION_CONFIRM_S = 0.05
# Half-width of the window the speed is differentiated over.
DIFF_HALF_S = 0.05


class GroundTruth(threading.Thread):
    """Gazebo's own pose stream for one model, parsed as it arrives.

    `gz topic -e --json-output` prints one JSON object per message with no
    separator, so the buffer is decoded with `raw_decode` and whatever is left
    over stays for the next read.
    """

    def __init__(self, world, model):
        super().__init__(daemon=True)
        self._world = world
        self._model = model
        self._lock = threading.Lock()
        self._samples = []  # (sim_seconds, x, y, z)
        self._proc = None
        self.error = None

    def run(self):
        topic = f"/world/{self._world}/dynamic_pose/info"
        self._proc = subprocess.Popen(
            ["gz", "topic", "-e", "-t", topic, "--json-output"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        decoder = json.JSONDecoder()
        buffer = ""
        while True:
            chunk = self._proc.stdout.read(4096)
            if not chunk:
                return
            buffer += chunk
            while True:
                buffer = buffer.lstrip()
                if not buffer:
                    break
                try:
                    message, end = decoder.raw_decode(buffer)
                except ValueError:
                    break  # a partial object; wait for more
                buffer = buffer[end:]
                self._take(message)

    def _take(self, message):
        header = message.get("header") or {}
        stamp = header.get("stamp") or {}
        # Protobuf JSON omits a field at its default, so a message in the first
        # second of the simulation has no "sec" at all.
        sec = float(stamp.get("sec", 0) or 0)
        nsec = float(stamp.get("nsec", stamp.get("nanosec", 0)) or 0)
        when = sec + nsec * 1e-9
        for pose in message.get("pose") or []:
            if pose.get("name") != self._model:
                continue
            position = pose.get("position") or {}
            with self._lock:
                self._samples.append((
                    when,
                    float(position.get("x", 0.0) or 0.0),
                    float(position.get("y", 0.0) or 0.0),
                    float(position.get("z", 0.0) or 0.0),
                ))

    def samples(self):
        with self._lock:
            return list(self._samples)

    def now(self):
        """Simulator time of the newest sample, or None before the first."""
        with self._lock:
            return self._samples[-1][0] if self._samples else None

    def position(self):
        with self._lock:
            return self._samples[-1][1:] if self._samples else None

    def stop(self):
        if self._proc is not None:
            self._proc.terminate()


def speed_at(samples, when):
    """Horizontal speed at a simulator time, by central difference."""
    before = [s for s in samples if s[0] <= when - DIFF_HALF_S]
    after = [s for s in samples if s[0] >= when + DIFF_HALF_S]
    if not before or not after:
        return None
    a, b = before[-1], after[0]
    span = b[0] - a[0]
    if span <= 0:
        return None
    return math.hypot(b[1] - a[1], b[2] - a[2]) / span


def speed_series(samples, start, end):
    """(simulator time, horizontal speed) over a window."""
    out = []
    for sample in samples:
        if start <= sample[0] <= end:
            speed = speed_at(samples, sample[0])
            if speed is not None:
                out.append((sample[0], speed))
    return out


def first_motion(samples, after):
    """When the vehicle first moved, confirmed over MOTION_CONFIRM_S."""
    series = speed_series(samples, after, after + 5.0)
    for index, (when, speed) in enumerate(series):
        if speed < AT_REST_MPS:
            continue
        window = [s for t, s in series[index:] if t <= when + MOTION_CONFIRM_S]
        if window and min(window) >= AT_REST_MPS:
            return when
    return None


def first_rest(samples, after):
    """When the vehicle next came to rest, confirmed over MOTION_CONFIRM_S."""
    series = speed_series(samples, after, after + 12.0)
    for index, (when, speed) in enumerate(series):
        if speed > AT_REST_MPS:
            continue
        window = [s for t, s in series[index:] if t <= when + MOTION_CONFIRM_S]
        if window and max(window) <= AT_REST_MPS:
            return when
    return None


def travelled(samples, start, end):
    """Straight-line horizontal distance between two simulator times."""
    before = [s for s in samples if s[0] <= start]
    after = [s for s in samples if s[0] <= end]
    if not before or not after:
        return None
    a, b = before[-1], after[-1]
    return math.hypot(b[1] - a[1], b[2] - a[2])


class Pilot(Node):
    """Publishes body-frame velocity and remembers what the estimate says.

    The command goes out on the same topic and in the same frame the demo node
    uses, because the number being measured is the latency of the path the
    swarm will actually command through, not of MAVLink.

    Nothing is published until `start()`. A GUIDED velocity command replaces
    the takeoff submode, so a node that begins publishing zero the moment it
    exists cancels the climb and pins the vehicle to the floor - with every
    service still reporting success. The first run of this script did exactly
    that and measured a flight of zeros.
    """

    def __init__(self, truth):
        super().__init__("dynamic_limits_pilot")
        self._truth = truth
        self._publishing = False
        self._pub = self.create_publisher(TwistStamped, "/ap/cmd_vel", 10)
        self.estimate = []  # (simulator time at arrival, x, y, z)
        self.create_subscription(
            PoseStamped, "/ap/pose/filtered", self._on_pose,
            qos_profile_sensor_data)
        self._command = (0.0, 0.0)
        self.create_timer(0.05, self._tick)

    def _on_pose(self, msg):
        # Stamped with the simulator's clock rather than the message's own,
        # deliberately: the pose carries ArduPilot's UTC, which cannot be
        # compared with anything else here. What is wanted is where the
        # estimate was when the simulator was at t, and the arrival time is the
        # only common reference this process has.
        when = self._truth.now()
        if when is not None:
            self.estimate.append(
                (when, msg.pose.position.x, msg.pose.position.y,
                 msg.pose.position.z))

    def start(self):
        """Begin publishing. Only safe once the vehicle has finished climbing."""
        self._publishing = True

    def _tick(self):
        if not self._publishing:
            return
        forward, yaw = self._command
        cmd = TwistStamped()
        cmd.header.stamp = self.get_clock().now().to_msg()
        # base_link means body frame; AP_DDS reads this field.
        cmd.header.frame_id = "base_link"
        cmd.twist.linear.x = forward
        cmd.twist.angular.z = yaw
        self._pub.publish(cmd)

    def command(self, forward_mps):
        """Set the standing command and return the simulator time it went out."""
        self._command = (forward_mps, 0.0)
        return self._truth.now()


def spin(node, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.02)


def arm_and_take_off(altitude, timeout=90.0):
    """Arm and climb, by the same MAVLink path check_guided_takeoff.sh uses."""
    from pymavlink import mavutil

    master = mavutil.mavlink_connection("udpin:0.0.0.0:14550")
    if master.wait_heartbeat(timeout=timeout) is None:
        sys.exit("No ArduPilot heartbeat; SITL is not talking MAVLink.")
    master.set_mode_apm("GUIDED")
    time.sleep(1)

    armed = False
    for _ in range(60):
        master.arducopter_arm()
        deadline = time.time() + 0.5
        while time.time() < deadline:
            msg = master.recv_match(type="HEARTBEAT", blocking=True, timeout=0.3)
            if msg and (msg.base_mode
                        & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED):
                armed = True
                break
        if armed:
            break
    if not armed:
        sys.exit("Vehicle never armed.")

    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, altitude)
    return master


def toward_origin(truth):
    """Which way to fly so the next run heads back towards the middle."""
    position = truth.position()
    if position is None:
        return 1.0
    return -1.0 if position[0] > 0 else 1.0


def run_step(pilot, truth, speed, hold_s, label, results):
    """One velocity step: accelerate, hold, stop. Measures both ends of it."""
    direction = toward_origin(truth)
    t_command = pilot.command(direction * speed)
    spin(pilot, hold_s)
    t_stop = pilot.command(0.0)
    spin(pilot, 6.0)

    samples = truth.samples()
    started = first_motion(samples, t_command)
    rested = first_rest(samples, t_stop + 0.2)
    steady = [s for t, s in speed_series(samples, t_stop - 1.0, t_stop)]

    entry = {
        "commanded_mps": speed,
        "hold_s": hold_s,
        "latency_s": None if started is None else started - t_command,
        "steady_mps": None if not steady else sum(steady) / len(steady),
        "braking_m": None if rested is None else travelled(samples, t_stop, rested),
        "braking_s": None if rested is None else rested - t_stop,
    }
    results[label] = entry
    tracking = ("-" if entry["steady_mps"] is None
                else f"{entry['steady_mps']:.3f}")
    print(f"  {label}: commanded {speed:.2f} m/s, held {tracking} m/s, "
          f"latency {_fmt(entry['latency_s'], 's')}, "
          f"coast {_fmt(entry['braking_m'], 'm')} in {_fmt(entry['braking_s'], 's')}",
          flush=True)
    return entry


def _fmt(value, unit):
    return "-" if value is None else f"{value:.3f} {unit}"


def drift(pilot, truth, since=None):
    """How far the estimate has walked away from the truth, over a window.

    Both series are referred to a common instant, because the estimate lives in
    the EKF's origin and the truth in the world's, and the question is the
    growth of the difference rather than the offset between two frames.

    The instant has to be the same one in both, and getting that wrong is not a
    small error: referring the estimate to its own first sample - taken after
    the climb - and the truth to its own - taken on the ground before it -
    charges the whole takeoff to the drift. It read 0.96 m vertically that way,
    which was the takeoff altitude and not an error at all.
    """
    estimate = [e for e in pilot.estimate if since is None or e[0] >= since]
    samples = truth.samples()
    if len(estimate) < 20 or len(samples) < 20:
        return None
    e0 = estimate[0]
    earlier = [s for s in samples if s[0] <= e0[0]]
    t0 = earlier[-1] if earlier else samples[0]
    out = []
    for when, x, y, z in estimate:
        near = [s for s in samples if s[0] <= when]
        if not near:
            continue
        s = near[-1]
        out.append((
            when - e0[0],
            math.hypot((x - e0[1]) - (s[1] - t0[1]),
                       (y - e0[2]) - (s[2] - t0[2])),
            abs((z - e0[3]) - (s[3] - t0[3])),
        ))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", default="room_test")
    parser.add_argument("--model", default="openipc_cinewhoop")
    parser.add_argument("--altitude", type=float, default=1.0)
    parser.add_argument("--hover-s", type=float, default=60.0,
                        help="Seconds of stationary hover for the drift figure.")
    parser.add_argument("--out", required=True, help="Directory for the JSON.")
    args = parser.parse_args()

    truth = GroundTruth(args.world, args.model)
    truth.start()
    for _ in range(100):
        if truth.now() is not None:
            break
        time.sleep(0.1)
    if truth.now() is None:
        sys.exit(f"No pose for {args.model} on /world/{args.world}/dynamic_pose/info.")

    arm_and_take_off(args.altitude)

    # Watch the climb in ground truth rather than assuming it. Nothing may
    # publish /ap/cmd_vel while this runs - see Pilot's docstring.
    ground_z = truth.position()[2]
    climbed = False
    deadline = time.monotonic() + 40.0
    while time.monotonic() < deadline:
        position = truth.position()
        if position is not None and position[2] - ground_z >= 0.8 * args.altitude:
            climbed = True
            break
        time.sleep(0.2)
    if not climbed:
        height = truth.position()[2] - ground_z
        sys.exit(f"Never climbed: {height:.2f} m above where it started, "
                 f"against a {args.altitude:.2f} m target. Nothing was "
                 "measured, because there was no flight to measure.")

    rclpy.init()
    pilot = Pilot(truth)
    pilot.start()
    # Let the takeoff excursion finish: a guided takeoff drifts about 0.35 m
    # forward on its own, and measuring a step through the tail of that would
    # put the excursion into the braking distance.
    spin(pilot, 10.0)

    results = {"airframe": None, "world": args.world}
    rates = truth.samples()
    if len(rates) > 10:
        span = rates[-1][0] - rates[0][0]
        results["truth_rate_hz"] = (len(rates) - 1) / span if span > 0 else None

    print("Steps, each measured from the simulator's own stamps:", flush=True)
    # Three at the same speed first: the spread between them is the jitter, and
    # a single latency figure without it is not usable in a safety margin.
    for trial in (1, 2, 3):
        entry = run_step(pilot, truth, 0.5, 1.5, f"latency trial {trial}", results)
        if trial == 1 and (entry["steady_mps"] or 0.0) < AT_REST_MPS:
            sys.exit("The first step commanded 0.5 m/s and the vehicle did not "
                     "move at all. Something is holding it, and the rest of "
                     "the sequence would only measure that again.")
    for speed, hold in ((0.25, 4.0), (0.5, 4.0), (1.0, 3.0)):
        run_step(pilot, truth, speed, hold, f"step {speed:.2f} m/s", results)

    # A ramp asks a different question than a step: whether the vehicle keeps up
    # with a demand that is always changing, which is what a formation is.
    print("Ramp 0 to 0.5 m/s over 4 s:", flush=True)
    direction = toward_origin(truth)
    t_ramp = truth.now()
    errors = []
    for index in range(80):
        want = 0.5 * min(1.0, index / 60.0)
        pilot.command(direction * want)
        spin(pilot, 0.05)
        got = speed_at(truth.samples(), truth.now() - 0.2)
        if got is not None and index > 10:
            errors.append(abs(got - want))
    pilot.command(0.0)
    spin(pilot, 6.0)
    ramp_rms = (math.sqrt(sum(e * e for e in errors) / len(errors))
                if errors else None)
    results["ramp"] = {"rms_error_mps": ramp_rms, "samples": len(errors),
                       "start_sim_s": t_ramp}
    print(f"  RMS tracking error {_fmt(ramp_rms, 'm/s')} over {len(errors)} samples",
          flush=True)

    print(f"Hover {args.hover_s:.0f} s for the drift figure:", flush=True)
    pilot.command(0.0)
    hover_start = truth.now()
    spin(pilot, args.hover_s)

    # Two windows, because they answer different questions. Over the whole
    # sortie the estimate is being pushed around by the manoeuvres; standing
    # still is where drift is drift and nothing else.
    for label, since in (("drift", None), ("drift_hover", hover_start)):
        series = drift(pilot, truth, since)
        if not series:
            results[label] = None
            print(f"  {label}: too few samples on one of the two streams",
                  flush=True)
            continue
        final = series[-1]
        minutes = final[0] / 60.0 if final[0] > 0 else None
        results[label] = {
            "seconds": final[0],
            "horizontal_m": final[1],
            "vertical_m": final[2],
            "horizontal_m_per_min": None if not minutes else final[1] / minutes,
            "samples": len(series),
        }
        print(f"  {label}: {final[1]:.3f} m horizontally, "
              f"{final[2]:.3f} m vertically, over {final[0]:.0f} s", flush=True)

    pilot.command(0.0)
    spin(pilot, 1.0)
    rclpy.shutdown()
    truth.stop()

    path = f"{args.out}/dynamic_limits.json"
    with open(path, "w") as handle:
        json.dump(results, handle, indent=2, sort_keys=True)
    print(f"Wrote {path}")

    measured = [v for k, v in results.items()
                if k.startswith(("step", "latency")) and isinstance(v, dict)]
    if not measured or any(m["braking_m"] is None for m in measured):
        sys.exit("At least one step produced no braking distance; "
                 "the flight did not do what was asked of it.")


if __name__ == "__main__":
    main()
