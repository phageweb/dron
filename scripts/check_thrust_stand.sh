#!/usr/bin/env bash
# Measure the rotor and thrust path with the airframe on a virtual thrust stand.
#
# Fixed-attitude flight is the only reliable way to test thrust here. A free
# quadrotor that cannot hold attitude tips over within a second or two, and
# every reading taken after that - joint velocities especially - describes a
# tumbling wreck rather than the model. Pinning base_link to a vertical slider
# removes attitude from the experiment, so a measured climb means the servo
# path, the rotor joints and the lift surfaces all work.
#
# Opt-in: needs the ignored local ArduPilot and ardupilot_gazebo builds.
set -eo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

sitl_bin="external/ardupilot/build/sitl/bin/arducopter"
plugin_dir="build/ardupilot_gazebo"
model_path="ros_ws/src/openipc_cinewhoop_gazebo/models/openipc_cinewhoop/model.sdf"
sitl_params="ros_ws/src/openipc_cinewhoop_gazebo/config/ardupilot_params.parm"
min_climb="${MIN_CLIMB_M:-2.0}"

for required_path in "$sitl_bin" "$plugin_dir/libArduPilotPlugin.so" "$model_path" "$sitl_params"; do
  if [ ! -e "$required_path" ]; then
    echo "Thrust stand prerequisite unavailable: $required_path" >&2
    exit 2
  fi
done

test_tmpdir="$(mktemp -d)"
gazebo_pid=""
sitl_pid=""

cleanup() {
  # ArduCopter ignores SIGINT while waiting on its JSON peer, so never block on
  # `wait` here: a stray SITL keeps UDP/9002 and breaks the next run silently.
  for pid in "$sitl_pid" "$gazebo_pid"; do
    if [ -n "$pid" ]; then
      kill -INT "$pid" 2>/dev/null || true
    fi
  done
  for _ in $(seq 1 20); do
    remaining=false
    for pid in "$sitl_pid" "$gazebo_pid"; do
      if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        remaining=true
      fi
    done
    if [ "$remaining" = false ]; then
      break
    fi
    sleep 0.5
  done
  for pid in "$sitl_pid" "$gazebo_pid"; do
    if [ -n "$pid" ]; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  done
  pkill -9 -f "$project_root/$sitl_bin" 2>/dev/null || true
  rm -rf "$test_tmpdir"
}
trap cleanup EXIT

python3 - "$model_path" "$test_tmpdir/stand.sdf" <<'PY'
import pathlib
import sys

model = pathlib.Path(sys.argv[1]).read_text()
stand = ('    <joint name="thrust_stand" type="prismatic">'
         '<parent>world</parent><child>base_link</child>'
         '<axis><xyz>0 0 1</xyz><limit><lower>-0.1</lower><upper>60</upper></limit>'
         '<dynamics><damping>0</damping></dynamics></axis></joint>\n')
model = model.replace("</model>", stand + "  </model>")
# The model's own pose puts base_link at z=0, which is inside the floor slab;
# the world file normally lifts it on include. Start clear of the ground so the
# slider has room and the vehicle is not resting on its lower stop.
model = model.replace("<pose>0 0 0 0 0 0</pose>", "<pose>0 0 0.5 0 0 0</pose>", 1)
inner = model[model.index("<model name="):model.rindex("</model>") + len("</model>")]

pathlib.Path(sys.argv[2]).write_text(f"""<?xml version="1.0"?>
<sdf version="1.10">
  <world name="indoor_test">
    <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-user-commands-system" name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>
    <plugin filename="gz-sim-imu-system" name="gz::sim::systems::Imu"/>
    <gravity>0 0 -9.80665</gravity>
    <atmosphere type="adiabatic"/>
    <model name="floor">
      <static>true</static>
      <link name="link">
        <collision name="collision"><geometry><box><size>20 20 0.05</size></box></geometry></collision>
      </link>
    </model>
    {inner}
  </world>
</sdf>
""")
PY

export GZ_PARTITION="${GZ_PARTITION:-openipc_cinewhoop}"
export GZ_IP="${GZ_IP:-127.0.0.1}"
export GZ_SIM_SYSTEM_PLUGIN_PATH="$project_root/$plugin_dir${GZ_SIM_SYSTEM_PLUGIN_PATH:+:$GZ_SIM_SYSTEM_PLUGIN_PATH}"

gz sim -s -r -v 3 "$test_tmpdir/stand.sdf" >"$test_tmpdir/gazebo.log" 2>&1 &
gazebo_pid=$!
sleep 6

(
  cd external/ardupilot/ArduCopter
  exec "$project_root/$sitl_bin" --wipe --model JSON --speedup 1 --slave 0 -I0 \
    --sim-address=127.0.0.1 --sim-port-out=9002 \
    --serial0=udpclient:127.0.0.1:14550 \
    --defaults "$project_root/$sitl_params"
) >"$test_tmpdir/sitl.log" 2>&1 &
sitl_pid=$!
sleep 20

python3 - "$min_climb" <<'PY'
import sys
import time

from pymavlink import mavutil

min_climb = float(sys.argv[1])
master = mavutil.mavlink_connection("udpin:0.0.0.0:14550")
master.wait_heartbeat()

for msg_id, hz in [(mavutil.mavlink.MAVLINK_MSG_ID_LOCAL_POSITION_NED, 10)]:
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
        msg_id, int(1e6 / hz), 0, 0, 0, 0, 0)
    time.sleep(0.2)

master.set_mode_apm("GUIDED")
time.sleep(1)

# The EKF only reports the vehicle armable once it has established home.
armed = False
for _ in range(60):
    master.arducopter_arm()
    time.sleep(0.5)
    heartbeat = master.recv_match(type="HEARTBEAT", blocking=True, timeout=2)
    if heartbeat and (heartbeat.base_mode
                      & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED):
        armed = True
        break
if not armed:
    sys.exit("Vehicle never armed.")

master.mav.command_long_send(
    master.target_system, master.target_component,
    mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, 5.0)

start = None
best = None
deadline = time.time() + 25
while time.time() < deadline:
    msg = master.recv_match(type="LOCAL_POSITION_NED", blocking=True, timeout=2)
    if msg is None:
        continue
    alt = -msg.z
    if start is None:
        start = alt
    best = alt if best is None else max(best, alt)

if start is None or best is None:
    sys.exit("No altitude telemetry received.")

climb = best - start
print(f"  start {start:+.2f} m   peak {best:+.2f} m   climb {climb:+.2f} m")
if climb < min_climb:
    sys.exit(f"Thrust path produced only {climb:.2f} m of climb, "
             f"expected at least {min_climb:.2f} m.")
print("Thrust stand check passed: the servo, rotor and lift path all work.")
PY
