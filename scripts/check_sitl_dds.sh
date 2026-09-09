#!/usr/bin/env bash
# Verify the AP_DDS ROS 2 graph against locally built ArduPilot SITL.
# This is intentionally opt-in: ArduPilot, the Micro XRCE-DDS generator, and
# the Agent workspace live below ignored external/ paths.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
sitl_bin="$project_root/external/ardupilot/build/sitl/bin/arducopter"
setup_file="$project_root/external/dds_ws/install/setup.bash"
agent_bin="$project_root/external/dds_ws/install/lib/micro_ros_agent/micro_ros_agent"
dds_params="$project_root/ros_ws/src/openipc_cinewhoop_gazebo/config/dds_smoke.parm"

for required_path in "$sitl_bin" "$setup_file" "$agent_bin" "$dds_params"; do
  if [ ! -e "$required_path" ]; then
    echo "DDS SITL smoke prerequisite unavailable: $required_path" >&2
    echo "Build the local Agent workspace and DDS-enabled SITL first." >&2
    exit 2
  fi
done

# Generated colcon setup scripts reference optional variables directly.
set +u
source "$setup_file"
set -u

test_tmpdir="$(mktemp -d)"
agent_pid=""
sitl_pid=""

cleanup() {
  for pid in "$sitl_pid" "$agent_pid"; do
    if [ -n "$pid" ]; then
      kill -TERM "$pid" 2>/dev/null || true
    fi
  done
  for pid in "$sitl_pid" "$agent_pid"; do
    if [ -n "$pid" ]; then
      wait "$pid" 2>/dev/null || true
    fi
  done
  rm -rf "$test_tmpdir"
}
trap cleanup EXIT

# Use a dedicated endpoint rather than UDP/2019, which may already be in use
# by an interactive Agent session on the workstation.
agent_port=20199
"$agent_bin" udp4 -p "$agent_port" >"$test_tmpdir/agent.log" 2>&1 &
agent_pid=$!
sleep 1

if ! kill -0 "$agent_pid" 2>/dev/null || ! grep -Fq "running..." "$test_tmpdir/agent.log"; then
  cat "$test_tmpdir/agent.log" >&2
  echo "Micro XRCE-DDS Agent did not start on UDP/$agent_port." >&2
  exit 1
fi

"$sitl_bin" --wipe --model quad --speedup 1 --slave 0 \
  --serial0=udpclient:127.0.0.1:14550 \
  --defaults "$dds_params" >"$test_tmpdir/sitl.log" 2>&1 &
sitl_pid=$!

for _ in $(seq 1 30); do
  if ros2 topic list | grep -Fxq /ap/time && \
     ros2 service list | grep -Fxq /ap/arm_motors; then
    echo "AP_DDS ROS 2 graph smoke check passed."
    ros2 topic list | grep '^/ap/'
    ros2 service list | grep '^/ap/'
    exit 0
  fi
  sleep 1
done

echo "--- Micro XRCE-DDS Agent ---" >&2
tail -80 "$test_tmpdir/agent.log" >&2
echo "--- ArduCopter SITL ---" >&2
tail -120 "$test_tmpdir/sitl.log" >&2
echo "AP_DDS topics and services did not appear within 30 seconds." >&2
exit 1
