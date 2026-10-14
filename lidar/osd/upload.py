#!/usr/bin/env python3
"""Put a Lua script on the flight controller's SD card over USB and restart scripting.

MAVLink FTP, so the SD card stays in. Refuses when the vehicle is armed.
The file is read back and compared before scripting is restarted; the
flight controller's own messages are printed for a few seconds after.

    python3 lidar/osd/upload.py                       # lidar/osd/scan_osd.lua
    python3 lidar/osd/upload.py my.lua --port /dev/ttyACM0
    nix run .#fc-upload

Needs pymavlink and pyserial.
"""

import argparse
import filecmp
import glob
import sys
import tempfile
import time
from pathlib import Path

from pymavlink import mavutil
from pymavlink.mavftp import MAVFTP

HERE = Path(__file__).resolve().parent
MAV_CMD_SCRIPTING = 42701
SCRIPTING_CMD_STOP_AND_RESTART = 3


def find_port():
    ports = sorted(glob.glob("/dev/serial/by-id/usb-ArduPilot_*-if00"))
    return ports[0] if ports else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script", type=Path, nargs="?", default=HERE / "scan_osd.lua")
    ap.add_argument("--port", help="flight controller's USB port, found by name when not given")
    ap.add_argument("--dir", default="APM/scripts", help="directory on the SD card")
    ap.add_argument("--watch", type=float, default=10, help="seconds of the FC's messages to print after")
    args = ap.parse_args()

    port = args.port or find_port()
    if not port:
        sys.exit("no ArduPilot board on USB")
    m = mavutil.mavlink_connection(port, baud=115200)
    hb = m.wait_heartbeat(timeout=10)
    if hb is None:
        sys.exit(f"{port}: no heartbeat")
    if hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED:
        sys.exit("the vehicle is armed; disarm it first")

    ftp = MAVFTP(m, m.target_system, m.target_component)
    remote = f"{args.dir}/{args.script.name}"
    with tempfile.TemporaryDirectory() as tmp:
        old = Path(tmp) / "old"
        ftp.cmd_get([remote, str(old)])
        ftp.process_ftp_reply("ReadFile", timeout=20)
        if old.exists() and filecmp.cmp(args.script, old, shallow=False):
            print(f"{remote} is already this file")
        else:
            ftp.cmd_put([str(args.script), remote])
            r = ftp.process_ftp_reply("CreateFile", timeout=30)
            if r is None or r.error_code:
                sys.exit(f"upload of {remote} failed")
            back = Path(tmp) / "back"
            ftp.cmd_get([remote, str(back)])
            ftp.process_ftp_reply("ReadFile", timeout=30)
            if not back.exists() or not filecmp.cmp(args.script, back, shallow=False):
                sys.exit(f"{remote} reads back different from {args.script}")
            print(f"{args.script} -> {remote}, read back the same")

    m.mav.command_long_send(m.target_system, m.target_component, MAV_CMD_SCRIPTING, 0,
                            SCRIPTING_CMD_STOP_AND_RESTART, 0, 0, 0, 0, 0, 0)
    end = time.time() + args.watch
    while time.time() < end:
        msg = m.recv_match(type=["COMMAND_ACK", "STATUSTEXT"], blocking=True, timeout=1)
        if msg is None:
            continue
        if msg.get_type() == "COMMAND_ACK" and msg.command == MAV_CMD_SCRIPTING:
            print("scripting restart " + ("accepted" if msg.result == 0 else f"refused ({msg.result})"))
        elif msg.get_type() == "STATUSTEXT":
            print(f"FC: {msg.text}")


if __name__ == "__main__":
    main()
