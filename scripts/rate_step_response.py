#!/usr/bin/env python3
"""Fly a repeatable roll step and measure how well the rate loop tracks it.

The attitude rate gains this airframe flies on were not tuned. They were derived
once, by dividing ArduPilot's defaults by the ratio between this airframe's
control authority and a ten-inch quad's. That got it flying on the first attempt,
which is evidence the number is in the right decade and no evidence at all that
it is the right number.

This drives the vehicle to altitude, holds it there, and commands a square wave
in roll through SET_ATTITUDE_TARGET, which puts GUIDED into its angle submode.
Altitude is held by sending the neutral thrust that ArduPilot reads as zero climb
rate, so the only thing under test is the attitude and rate loop.

Prints one line of metrics and writes the whole trace as CSV, so a sweep can put
several gains beside each other instead of asking whether each one "felt" stable.
"""

import argparse
import csv
import json
import math
import sys
import time

from pymavlink import mavutil

# One cycle is level, right, level, left. Two cycles give eight edges to average
# over, which is enough to separate a real difference from one noisy step.
STEP_DEG = 10.0
STEP_HOLD_S = 2.0
CYCLES = 2
SETTLE_BAND_DEG = 1.0


def wait_armed(master, timeout_s, notices):
    """Keep asking to arm until it takes, collecting ArduPilot's own reasons.

    A refusal is normal for the first few seconds while the EKF settles, so the
    interesting thing is not that it failed but what it said. Without the
    STATUSTEXT capture this reports "never armed" and nothing else, which is
    what it did the first time a run was watched with the Gazebo window open.
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        master.arducopter_arm()
        until = time.time() + 1.0
        while time.time() < until:
            msg = master.recv_match(type=["HEARTBEAT", "STATUSTEXT"],
                                    blocking=True, timeout=0.3)
            if msg is None:
                continue
            if msg.get_type() == "STATUSTEXT":
                text = msg.text.strip()
                if text and (not notices or notices[-1] != text):
                    notices.append(text)
            elif msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED:
                return True
    return False


def climb_to(master, target_alt, timeout_s):
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, target_alt)
    start = time.time()
    altitude = 0.0
    while time.time() - start < timeout_s:
        msg = master.recv_match(type="LOCAL_POSITION_NED", blocking=True, timeout=2)
        if msg is None:
            continue
        altitude = -msg.z
        if altitude >= target_alt * 0.9:
            # Let the climb stop before asking the attitude loop for anything.
            time.sleep(4.0)
            return True, altitude
    return False, altitude


def send_attitude(master, roll_rad):
    """Roll-only attitude target with the thrust ArduPilot reads as hold."""
    half = roll_rad / 2.0
    quaternion = [math.cos(half), math.sin(half), 0.0, 0.0]
    master.mav.set_attitude_target_send(
        int((time.time() % 1000) * 1000),
        master.target_system, master.target_component,
        0b00000111,  # ignore body rates, use the quaternion and the thrust
        quaternion, 0.0, 0.0, 0.0, 0.5)


def schedule():
    """The commanded roll in degrees as a function of time from the first step."""
    steps = []
    for _ in range(CYCLES):
        steps.extend([0.0, STEP_DEG, 0.0, -STEP_DEG])
    return steps


def run(master, csv_path):
    steps = schedule()
    samples = []
    edges = []
    start = time.time()

    for index, target_deg in enumerate(steps):
        edge_time = time.time()
        edges.append((edge_time - start, target_deg))
        target_rad = math.radians(target_deg)
        while time.time() - edge_time < STEP_HOLD_S:
            send_attitude(master, target_rad)
            deadline = time.time() + 0.05
            while time.time() < deadline:
                msg = master.recv_match(type="ATTITUDE", blocking=True, timeout=0.05)
                if msg is None:
                    break
                samples.append((time.time() - start, target_deg,
                                math.degrees(msg.roll), math.degrees(msg.rollspeed)))

    with open(csv_path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["t_s", "target_deg", "roll_deg", "rollspeed_dps"])
        writer.writerows(samples)
    return samples, edges


def metrics(samples, edges):
    """Overshoot, rise, settle and steady error, averaged over the moving edges."""
    overshoots, rises, settles, errors, crossings = [], [], [], [], 0

    for index, (edge_t, target) in enumerate(edges):
        if index == 0:
            continue
        previous = edges[index - 1][1]
        travel = target - previous
        if abs(travel) < 1e-6:
            continue
        end_t = edge_t + STEP_HOLD_S
        window = [s for s in samples if edge_t <= s[0] < end_t]
        if len(window) < 10:
            continue

        # Overshoot past the commanded angle, as a fraction of the step taken.
        extreme = max((s[2] for s in window), key=lambda v: v * (1 if travel > 0 else -1))
        overshoots.append(max(0.0, (extreme - target) * (1 if travel > 0 else -1))
                          / abs(travel) * 100.0)

        rise = next((s[0] - edge_t for s in window
                     if (s[2] - previous) * (1 if travel > 0 else -1)
                     >= abs(travel) * 0.9), None)
        if rise is not None:
            rises.append(rise)

        settle = None
        for position, sample in enumerate(window):
            if all(abs(later[2] - target) <= SETTLE_BAND_DEG
                   for later in window[position:]):
                settle = sample[0] - edge_t
                break
        if settle is not None:
            settles.append(settle)

        tail = [s for s in window if s[0] - edge_t > STEP_HOLD_S / 2]
        if tail:
            errors.append(math.sqrt(sum((s[2] - target) ** 2 for s in tail) / len(tail)))

        # Ringing shows up as the error changing sign repeatedly after arrival.
        signs = [1 if s[2] - target > 0 else -1 for s in window]
        crossings += sum(1 for a, b in zip(signs, signs[1:]) if a != b)

    def mean(values):
        return sum(values) / len(values) if values else float("nan")

    return {
        "overshoot_pct": mean(overshoots),
        "rise_s": mean(rises),
        "settle_s": mean(settles),
        "rms_error_deg": mean(errors),
        "sign_changes": crossings,
        "steps_measured": len(overshoots),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--altitude", type=float, default=3.0)
    parser.add_argument("--label", default="")
    # Watching costs real time factor, so every wait that is really "until the
    # simulator catches up" is scaled rather than guessed at again.
    parser.add_argument("--patience", type=float, default=1.0,
                        help="multiplier on every timeout; raise it when the "
                             "Gazebo window is open and the sim runs slow")
    args = parser.parse_args()

    master = mavutil.mavlink_connection("udpin:0.0.0.0:14550")
    master.wait_heartbeat()
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
        mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE, 10000, 0, 0, 0, 0, 0)
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
        mavutil.mavlink.MAVLINK_MSG_ID_LOCAL_POSITION_NED, 50000, 0, 0, 0, 0, 0)
    time.sleep(0.5)

    master.set_mode_apm("GUIDED")
    time.sleep(1)

    notices = []
    if not wait_armed(master, 30.0 * args.patience, notices):
        reasons = "\n  ".join(notices[-6:]) or "ArduPilot said nothing at all."
        sys.exit(f"Vehicle never armed in {30.0 * args.patience:.0f} s. "
                 f"ArduPilot's last messages:\n  {reasons}")

    climbed, altitude = climb_to(master, args.altitude, 25.0 * args.patience)
    if not climbed:
        sys.exit(f"Only reached {altitude:.2f} m of a {args.altitude:.2f} m target.")

    samples, edges = run(master, args.csv)
    if len(samples) < 100:
        sys.exit(f"Only {len(samples)} attitude samples; telemetry did not keep up.")

    result = metrics(samples, edges)
    result["label"] = args.label
    result["samples"] = len(samples)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
