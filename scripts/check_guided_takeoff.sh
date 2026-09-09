#!/usr/bin/env bash
# Verify a real guided takeoff of the custom cinewhoop: arm, climb, hold.
#
# This is the check that the whole rotor rebuild exists to satisfy. It flies the
# airframe free, so it fails if attitude control is broken - unlike the thrust
# stand, which deliberately removes attitude from the experiment.
#
# Opt-in: needs the ignored local ArduPilot and ardupilot_gazebo builds plus the
# actuator bridge from scripts/build_actuator_bridge.sh.
set -eo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

sitl_bin="external/ardupilot/build/sitl/bin/arducopter"
bridge_bin="build/ap_actuator_bridge/ap_actuator_bridge"
plugin_dir="build/ardupilot_gazebo"
world_path="ros_ws/src/openipc_cinewhoop_gazebo/worlds/indoor_test.sdf"
sitl_params="ros_ws/src/openipc_cinewhoop_gazebo/config/ardupilot_params.parm"
target_alt="${TARGET_ALT_M:-2.0}"

for required_path in "$sitl_bin" "$bridge_bin" "$plugin_dir/libArduPilotPlugin.so" \
  "$world_path" "$sitl_params"; do
  if [ ! -e "$required_path" ]; then
    echo "Guided takeoff prerequisite unavailable: $required_path" >&2
    exit 2
  fi
done

export GZ_PARTITION="${GZ_PARTITION:-openipc_cinewhoop}"
export GZ_IP="${GZ_IP:-127.0.0.1}"
export GZ_SIM_SYSTEM_PLUGIN_PATH="$project_root/$plugin_dir${GZ_SIM_SYSTEM_PLUGIN_PATH:+:$GZ_SIM_SYSTEM_PLUGIN_PATH}"
export GZ_SIM_RESOURCE_PATH="$project_root/ros_ws/src/openipc_cinewhoop_gazebo/models:$project_root/ros_ws/src/openipc_cinewhoop_gazebo/worlds${GZ_SIM_RESOURCE_PATH:+:$GZ_SIM_RESOURCE_PATH}"

test_tmpdir="$(mktemp -d)"
gazebo_pid=""
bridge_pid=""
sitl_pid=""

cleanup() {
  # ArduCopter ignores SIGINT while waiting on its JSON peer, so never block on
  # `wait`: a stray SITL holds UDP/9002 and breaks the next run silently.
  for pid in "$sitl_pid" "$bridge_pid" "$gazebo_pid"; do
    if [ -n "$pid" ]; then
      kill -INT "$pid" 2>/dev/null || true
    fi
  done
  sleep 1
  for pid in "$sitl_pid" "$bridge_pid" "$gazebo_pid"; do
    if [ -n "$pid" ]; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  done
  pkill -9 -f "$project_root/$sitl_bin" 2>/dev/null || true
  rm -rf "$test_tmpdir"
}
trap cleanup EXIT

gz sim -s -r -v 3 "$world_path" >"$test_tmpdir/gazebo.log" 2>&1 &
gazebo_pid=$!
sleep 6

# ArduPilot publishes one Double per rotor; the motor models read one Actuators
# array. Without this bridge the rotors never turn.
"$project_root/$bridge_bin" >"$test_tmpdir/bridge.log" 2>&1 &
bridge_pid=$!
sleep 1

(
  cd external/ardupilot/ArduCopter
  exec "$project_root/$sitl_bin" --wipe --model JSON --speedup 1 --slave 0 -I0 \
    --sim-address=127.0.0.1 --sim-port-out=9002 \
    --serial0=udpclient:127.0.0.1:14550 \
    --defaults "$project_root/$sitl_params"
) >"$test_tmpdir/sitl.log" 2>&1 &
sitl_pid=$!
sleep 20

python3 - "$target_alt" <<'PY'
import math
import sys
import time

from pymavlink import mavutil

target = float(sys.argv[1])
master = mavutil.mavlink_connection("udpin:0.0.0.0:14550")
master.wait_heartbeat()

for msg_id in (mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE,
               mavutil.mavlink.MAVLINK_MSG_ID_LOCAL_POSITION_NED):
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
        msg_id, 100000, 0, 0, 0, 0, 0)
    time.sleep(0.2)

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
    mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, target)

peak = 0.0
worst_tilt = 0.0
settled = []
start = time.time()
while time.time() - start < 16:
    msg = master.recv_match(type=["LOCAL_POSITION_NED", "ATTITUDE"],
                            blocking=True, timeout=2)
    if msg is None:
        continue
    if msg.get_type() == "ATTITUDE":
        tilt = math.degrees(max(abs(msg.roll), abs(msg.pitch)))
        worst_tilt = max(worst_tilt, tilt)
    else:
        alt = -msg.z
        peak = max(peak, alt)
        # The last stretch is the one that shows whether it holds altitude.
        if time.time() - start > 8:
            settled.append(alt)

if not settled:
    sys.exit("No altitude telemetry in the settled window.")

mean_alt = sum(settled) / len(settled)
print(f"  peak {peak:.2f} m   settled mean {mean_alt:.2f} m "
      f"(target {target:.2f})   worst tilt {worst_tilt:.1f} deg")

if peak < target * 0.75:
    sys.exit(f"Climbed only {peak:.2f} m against a {target:.2f} m target.")
if abs(mean_alt - target) > 0.5:
    sys.exit(f"Settled at {mean_alt:.2f} m, more than 0.5 m off target.")
if worst_tilt > 25.0:
    sys.exit(f"Attitude reached {worst_tilt:.1f} deg; the airframe is not stable.")
print("Guided takeoff check passed: armed, climbed and held altitude.")
PY
