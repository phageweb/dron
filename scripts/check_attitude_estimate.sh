#!/usr/bin/env bash
# Verify that ArduPilot's attitude estimate is the attitude the vehicle has.
#
# The demo's floor rejection projects lidar returns using roll and pitch from
# /ap/pose/filtered, and nothing checked that those are the vehicle's real
# attitude in the convention the projection assumes. A flipped sign there would
# discard the ceiling and keep the floor while every other test still passed.
#
# Parking on a slope turns that into two steady numbers instead of two streams
# to align during a transient. ramp_test.sdf tilts the vehicle 20 degrees in
# pitch and 10 in roll, in both axes so a swap cannot hide, and the check
# compares the world file, Gazebo's ground truth and AP_DDS against each other.
#
# Nothing is armed and nothing flies. Opt-in: needs the ignored local ArduPilot,
# ardupilot_gazebo and DDS builds.
set -eo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

sitl_bin="external/ardupilot/build/sitl/bin/arducopter"
bridge_bin="build/ap_actuator_bridge/ap_actuator_bridge"
agent_setup="external/dds_ws/install/setup.bash"
agent_bin="external/dds_ws/install/lib/micro_ros_agent/micro_ros_agent"
plugin_dir="build/ardupilot_gazebo"
world_path="ros_ws/src/openipc_cinewhoop_gazebo/worlds/ramp_test.sdf"
# Which airframe to fly. The variants are separate model directories holding a
# model of the same name, so worlds and the bridge config need no change; see
# ros_ws/src/openipc_cinewhoop_gazebo/launch/gazebo.launch.py.
airframe="${OPENIPC_AIRFRAME:-cinewhoop}"
if [ "$airframe" = "cinewhoop" ]; then
  models_dir="models"
  params_name="ardupilot_params.parm"
else
  models_dir="models_$airframe"
  params_name="ardupilot_params_$airframe.parm"
fi
sitl_params="ros_ws/src/openipc_cinewhoop_gazebo/config/$params_name"
dds_params="ros_ws/src/openipc_cinewhoop_gazebo/config/dds_smoke.parm"

for required_path in "$sitl_bin" "$bridge_bin" "$agent_setup" "$agent_bin" \
  "$plugin_dir/libArduPilotPlugin.so" "$world_path" "$sitl_params" "$dds_params"; do
  if [ ! -e "$required_path" ]; then
    echo "Attitude estimate prerequisite unavailable: $required_path" >&2
    exit 2
  fi
done

if [ ! -f install/setup.bash ]; then
  echo "Workspace is not built; run colcon build first." >&2
  exit 1
fi

# micro_ros_agent has no domain option and ignores ROS_DOMAIN_ID, so leave the
# domain alone: setting one hides every /ap/ topic from ros2.
unset ROS_DOMAIN_ID || true
export GZ_PARTITION="${GZ_PARTITION:-openipc_cinewhoop}"
export GZ_IP="${GZ_IP:-127.0.0.1}"
export GZ_SIM_SYSTEM_PLUGIN_PATH="$project_root/$plugin_dir${GZ_SIM_SYSTEM_PLUGIN_PATH:+:$GZ_SIM_SYSTEM_PLUGIN_PATH}"
export GZ_SIM_RESOURCE_PATH="$project_root/ros_ws/src/openipc_cinewhoop_gazebo/$models_dir:$project_root/ros_ws/src/openipc_cinewhoop_gazebo/worlds${GZ_SIM_RESOURCE_PATH:+:$GZ_SIM_RESOURCE_PATH}"

set +u
source install/setup.bash
source "$agent_setup"
set -u

test_tmpdir="$(mktemp -d)"
gazebo_pid=""
bridge_pid=""
agent_pid=""
sitl_pid=""

cleanup() {
  for pid in "$sitl_pid" "$agent_pid" "$bridge_pid" "$gazebo_pid"; do
    [ -n "$pid" ] && kill -INT "$pid" 2>/dev/null || true
  done
  sleep 1
  for pid in "$sitl_pid" "$agent_pid" "$bridge_pid" "$gazebo_pid"; do
    [ -n "$pid" ] && kill -9 "$pid" 2>/dev/null || true
  done
  pkill -9 -f "$project_root/$sitl_bin" 2>/dev/null || true
  rm -rf "$test_tmpdir"
}
trap cleanup EXIT

gz sim -s -r -v 2 "$world_path" >"$test_tmpdir/gazebo.log" 2>&1 &
gazebo_pid=$!
sleep 6

# The plugin drives the rotors through this even with nothing armed; without it
# ArduPilot's servo output goes nowhere and the run is less like a real one.
"$project_root/$bridge_bin" >"$test_tmpdir/bridge.log" 2>&1 &
bridge_pid=$!

"$project_root/$agent_bin" udp4 -p 20199 >"$test_tmpdir/agent.log" 2>&1 &
agent_pid=$!
sleep 2

(
  cd external/ardupilot/ArduCopter
  exec "$project_root/$sitl_bin" --wipe --model JSON --speedup 1 --slave 0 -I0 \
    --sim-address=127.0.0.1 --sim-port-out=9002 \
    --serial0=udpclient:127.0.0.1:14550 \
    --defaults "$project_root/$sitl_params,$project_root/$dds_params"
) >"$test_tmpdir/sitl.log" 2>&1 &
sitl_pid=$!

echo "==> waiting for AP_DDS"
for _ in $(seq 1 60); do
  ros2 topic list 2>/dev/null | grep -Fxq /ap/pose/filtered && break
  sleep 1
done
if ! ros2 topic list 2>/dev/null | grep -Fxq /ap/pose/filtered; then
  echo "/ap/pose/filtered never appeared." >&2
  # This is what a model pinned to one world looks like from here: Gazebo runs,
  # SITL runs, and the two never complete a frame.
  if grep -q "No JSON sensor message received" "$test_tmpdir/sitl.log"; then
    echo "SITL got no JSON state from Gazebo. If the model's sensors declare" >&2
    echo "their own topics, they name a world and the plugin cannot find the" >&2
    echo "IMU; scripts/check_model_consistency.py guards against that." >&2
  fi
  tail -20 "$test_tmpdir/agent.log" >&2 || true
  exit 1
fi

# Let the vehicle settle onto the ramp and the estimate converge before reading.
sleep 10

echo "==> comparing the ramp, Gazebo and AP_DDS"
python3 scripts/check_attitude_estimate.py "$world_path"

echo "Attitude estimate check passed: the demo's floor rejection is fed the real attitude."
