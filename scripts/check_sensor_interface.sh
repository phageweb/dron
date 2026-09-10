#!/usr/bin/env bash
# Verify that the bridged sensors present the interface the real drone will:
# the message types spec/04_ros_rozhrani.md fixes, frames that exist in the TF
# tree, and axes the right way up.
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
gazebo_pid=""
tf_pid=""

cleanup() {
  for pid in "$tf_pid" "$gazebo_pid"; do
    if [ -n "$pid" ]; then
      kill -TERM -- "-$pid" 2>/dev/null || true
    fi
  done
  # range_adapter is a ros2 run style child of the launch and outlives a plain
  # TERM to the group leader on some shutdown orders.
  pkill -f "$project_root/install/openipc_cinewhoop_demo" 2>/dev/null || true
  wait "$tf_pid" 2>/dev/null || true
  wait "$gazebo_pid" 2>/dev/null || true
  rm -rf "$test_tmpdir"
}
trap cleanup EXIT

setsid ros2 launch openipc_cinewhoop_gazebo gazebo.launch.py gui:=false use_bridge:=true \
  >"$test_tmpdir/gazebo.log" 2>&1 &
gazebo_pid=$!

# robot_state_publisher is the authority on the TF tree the URDF describes, and
# it is what RViz would be transforming against.
setsid ros2 launch openipc_cinewhoop_description display.launch.py \
  rviz:=false use_sim_time:=true >"$test_tmpdir/tf.log" 2>&1 &
tf_pid=$!

for _ in $(seq 1 160); do
  if ros2 topic list 2>/dev/null | grep -Fxq /openipc_cinewhoop/range/down; then
    break
  fi
  sleep 0.25
done

echo "==> Message types"
types_ok=true
check_type() {
  local topic="$1" want="$2" got
  got="$(ros2 topic type "$topic" 2>/dev/null || true)"
  if [ "$got" = "$want" ]; then
    echo "  $topic: $want"
  else
    echo "  $topic: expected $want, got '${got:-nothing}'" >&2
    types_ok=false
  fi
}
# spec/04_ros_rozhrani.md fixes these, and the rangefinder is the one that used
# to differ: Gazebo can only produce a LaserScan, hardware produces a Range.
check_type /openipc_cinewhoop/range/down sensor_msgs/msg/Range
check_type /openipc_cinewhoop/scan/front sensor_msgs/msg/LaserScan
check_type /openipc_cinewhoop/imu sensor_msgs/msg/Imu
check_type /openipc_cinewhoop/camera/image_raw sensor_msgs/msg/Image

echo "==> Frames, cone and axes"
if ! python3 "$project_root/scripts/check_sensor_interface.py"; then
  echo "--- gazebo log ---" >&2
  tail -n 40 "$test_tmpdir/gazebo.log" >&2 || true
  echo "--- robot_state_publisher log ---" >&2
  tail -n 20 "$test_tmpdir/tf.log" >&2 || true
  exit 1
fi

if [ "$types_ok" != true ]; then
  echo "Sensor message types do not match the ROS interface spec." >&2
  exit 1
fi

echo "Sensor interface check passed."
