#!/usr/bin/env bash
# Verify the URDF/Xacro TF tree without requiring an RViz GUI.
set -eo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if [ ! -f install/setup.bash ]; then
  echo "Workspace is not built; run colcon build first." >&2
  exit 1
fi

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-75}"
source install/setup.bash

test_tmpdir="$(mktemp -d)"
launch_pid=""

cleanup() {
  if [ -n "$launch_pid" ]; then
    kill -INT -- "-$launch_pid" 2>/dev/null || true
    for _ in $(seq 1 40); do
      if ! kill -0 "$launch_pid" 2>/dev/null; then
        break
      fi
      sleep 0.25
    done
    if kill -0 "$launch_pid" 2>/dev/null; then
      kill -TERM -- "-$launch_pid" 2>/dev/null || true
    fi
    wait "$launch_pid" 2>/dev/null || true
  fi
  rm -rf "$test_tmpdir"
}
trap cleanup EXIT

setsid ros2 launch openipc_cinewhoop_description display.launch.py \
  rviz:=false use_sim_time:=false >"$test_tmpdir/launch.log" 2>&1 &
launch_pid=$!

for _ in $(seq 1 40); do
  if ros2 node list | grep -Fxq /robot_state_publisher; then
    break
  fi
  sleep 0.25
done
ros2 node list | grep -Fx /robot_state_publisher

(
  cd "$test_tmpdir"
  ros2 run tf2_tools view_frames >view_frames.log 2>&1
)

for frame in imu_link front_lidar_link rangefinder_link camera_link camera_optical_frame; do
  if ! grep -Fq "$frame:" "$test_tmpdir/view_frames.log"; then
    cat "$test_tmpdir/view_frames.log" >&2
    exit 1
  fi
done
if ! grep -Fq "parent: 'base_link'" "$test_tmpdir/view_frames.log"; then
  cat "$test_tmpdir/view_frames.log" >&2
  exit 1
fi

echo "TF tree smoke check passed."
