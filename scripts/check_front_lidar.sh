#!/usr/bin/env bash
# Verify that Gazebo produces a front-lidar scan and that the ROS demo consumes it.
set -eo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if [ ! -f install/setup.bash ]; then
  echo "Workspace is not built; run colcon build first." >&2
  exit 1
fi

# Generated colcon hooks access optional variables, so do not enable nounset
# until the overlay has been sourced.
set +u
source install/setup.bash
set -u
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-77}"

test_tmpdir="$(mktemp -d)"
launch_pid=""
monitor_pid=""

cleanup() {
  for pid in "$monitor_pid" "$launch_pid"; do
    if [ -n "$pid" ]; then
      kill -TERM -- "-$pid" 2>/dev/null || true
    fi
  done
  wait "$monitor_pid" 2>/dev/null || true
  wait "$launch_pid" 2>/dev/null || true
  rm -rf "$test_tmpdir"
}
trap cleanup EXIT

setsid ros2 launch openipc_cinewhoop_gazebo gazebo.launch.py gui:=false use_bridge:=true \
  >"$test_tmpdir/gazebo.log" 2>&1 &
launch_pid=$!

for _ in $(seq 1 160); do
  if ros2 topic list 2>/dev/null | grep -Fxq /openipc_cinewhoop/scan/front; then
    break
  fi
  sleep 0.25
done

if ! ros2 topic list 2>/dev/null | grep -Fxq /openipc_cinewhoop/scan/front; then
  echo "Front-lidar bridge topic did not appear." >&2
  cat "$test_tmpdir/gazebo.log" >&2 || true
  exit 1
fi

setsid ros2 run openipc_cinewhoop_demo obstacle_monitor --ros-args -p log_period_s:=0.1 \
  >"$test_tmpdir/monitor.log" 2>&1 &
monitor_pid=$!

for _ in $(seq 1 90); do
  if rg -q "Nearest obstacle|Obstacle close" "$test_tmpdir/monitor.log"; then
    cat "$test_tmpdir/monitor.log"
    echo "Front-lidar demo integration check passed."
    exit 0
  fi
  sleep 0.5
done

echo "No valid bridged front-lidar measurement within 45 seconds." >&2
cat "$test_tmpdir/monitor.log" >&2 || true
rg -i "error|warn|sensor|ogre|lidar" "$test_tmpdir/gazebo.log" | tail -n 100 >&2 || true
exit 1
