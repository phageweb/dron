#!/usr/bin/env bash
# Verify the local ArduPilot JSON interface against the custom Gazebo model.
# This is intentionally opt-in: the upstream sources and their native build
# outputs live in ignored external/ and are not part of the normal ROS CI job.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ardupilot_dir="$project_root/external/ardupilot"
plugin_dir="$project_root/build/ardupilot_gazebo"
world_path="$project_root/ros_ws/src/openipc_cinewhoop_gazebo/worlds/indoor_test.sdf"
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
models_path="$project_root/ros_ws/src/openipc_cinewhoop_gazebo/$models_dir"
sitl_bin="$ardupilot_dir/build/sitl/bin/arducopter"
sitl_params="$project_root/ros_ws/src/openipc_cinewhoop_gazebo/config/$params_name"
for required_path in "$sitl_bin" "$plugin_dir/libArduPilotPlugin.so" "$world_path" "$sitl_params"; do
  if [ ! -e "$required_path" ]; then
    echo "SITL smoke prerequisites unavailable: $required_path" >&2
    echo "Build the ignored external/ ArduPilot and ardupilot_gazebo checkouts first." >&2
    exit 2
  fi
done

test_tmpdir="$(mktemp -d)"
gazebo_pid=""

cleanup() {
  if [ -n "$gazebo_pid" ]; then
    kill -INT "$gazebo_pid" 2>/dev/null || true
    wait "$gazebo_pid" 2>/dev/null || true
  fi
  rm -rf "$test_tmpdir"
}
trap cleanup EXIT

export GZ_SIM_SYSTEM_PLUGIN_PATH="$plugin_dir${GZ_SIM_SYSTEM_PLUGIN_PATH:+:$GZ_SIM_SYSTEM_PLUGIN_PATH}"
export GZ_SIM_RESOURCE_PATH="$models_path:$project_root/ros_ws/src/openipc_cinewhoop_gazebo/worlds${GZ_SIM_RESOURCE_PATH:+:$GZ_SIM_RESOURCE_PATH}"
# sdformat resolves model:// through SDF_PATH, not through
# GZ_SIM_RESOURCE_PATH, and the dev shell points SDF_PATH at the CineLog
# models. Without this line an OPENIPC_AIRFRAME=pavo20 run loads the
# CineLog model and reports it as the Pavo20 - which is what every
# pavo20 measurement before 2026-09-20 actually did.
export SDF_PATH="$project_root/ros_ws/src/openipc_cinewhoop_gazebo/$models_dir${SDF_PATH:+:$SDF_PATH}"

gz sim -s -r -v 4 "$world_path" >"$test_tmpdir/gazebo.log" 2>&1 &
gazebo_pid=$!

# Model parsing and the render context normally settle in under six seconds.
sleep 6

(
  cd "$ardupilot_dir/ArduCopter"
  timeout -s INT 15 "$sitl_bin" \
    --wipe --model JSON --speedup 1 --slave 0 -I0 \
    --sim-address=127.0.0.1 --sim-port-out=9002 \
    --serial0=udpclient:127.0.0.1:14550 \
    --defaults "$sitl_params"
) >"$test_tmpdir/sitl.log" 2>&1 || true

grep -F "JSON received:" "$test_tmpdir/sitl.log"
grep -F "ArduPilot controller has reset" "$test_tmpdir/gazebo.log"
echo "Custom cinewhoop ArduPilot SITL/Gazebo smoke check passed."
