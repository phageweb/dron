#!/usr/bin/env python3
"""Arm the local ArduCopter SITL instance and command a Guided takeoff."""

import argparse
import sys
import time


def wait_for_ack(master, mavlink, command, timeout):
    """Wait for a successful MAVLink acknowledgement of one command."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        message = master.recv_match(type="COMMAND_ACK", blocking=True, timeout=1)
        if message is None or message.command != command:
            continue
        accepted = {
            mavlink.MAV_RESULT_ACCEPTED,
            mavlink.MAV_RESULT_IN_PROGRESS,
        }
        if message.result in accepted:
            return
        raise RuntimeError(
            f"ArduPilot rejected command {command}; MAVLink result {message.result}"
        )
    raise TimeoutError(f"Timed out waiting for acknowledgement of command {command}")


def main():
    parser = argparse.ArgumentParser(
        description="Arm the local ArduCopter SITL and take off in Guided mode."
    )
    parser.add_argument(
        "--connection",
        default="udpin:0.0.0.0:14550",
        help="MAVLink endpoint (default: %(default)s)",
    )
    parser.add_argument(
        "--altitude",
        type=float,
        default=0.5,
        help="Target takeoff altitude in metres (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Seconds to wait for the vehicle and command acknowledgements (default: %(default)s)",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required acknowledgement before arming and sending the takeoff command.",
    )
    args = parser.parse_args()

    if args.altitude <= 0:
        parser.error("--altitude must be positive")
    if not args.confirm:
        parser.error("refusing to arm without --confirm")

    try:
        from pymavlink import mavutil
    except ImportError as error:
        raise SystemExit(
            "pymavlink is unavailable. Enter the project shell with `nix develop` first."
        ) from error

    master = mavutil.mavlink_connection(args.connection)
    print(f"Waiting for ArduPilot heartbeat on {args.connection} …")
    heartbeat = master.wait_heartbeat(timeout=args.timeout)
    if heartbeat is None:
        raise TimeoutError("No ArduPilot heartbeat received")
    print(f"Connected to system {master.target_system}, component {master.target_component}.")

    master.set_mode_apm("GUIDED")
    wait_for_ack(
        master, mavutil.mavlink, mavutil.mavlink.MAV_CMD_DO_SET_MODE, args.timeout
    )
    print("Guided mode enabled.")

    master.arducopter_arm()
    master.motors_armed_wait()
    print("Vehicle armed.")

    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        0,
        0,  # minimum pitch
        0,
        0,
        0,
        0,
        0,
        args.altitude,
    )
    wait_for_ack(
        master, mavutil.mavlink, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, args.timeout
    )
    print(f"Takeoff command accepted: target altitude {args.altitude:.2f} m.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, TimeoutError) as error:
        print(f"Takeoff failed: {error}", file=sys.stderr)
        raise SystemExit(1)
