#!/usr/bin/env bash
# Verify the demo's publisher/subscriber path without requiring Gazebo.
set -eo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if [ ! -f install/setup.bash ]; then
  echo "Workspace is not built; run colcon build first." >&2
  exit 1
fi

# Keep this local smoke test independent of any ROS graph on the host.
# A per-process domain avoids stale DDS discovery from a previous local run.
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-$((100 + ($$ % 100)))}"
source install/setup.bash

test_tmpdir="$(mktemp -d)"
node_pid=""
echo_pid=""

cleanup() {
  if [ -n "$echo_pid" ]; then
    kill "$echo_pid" 2>/dev/null || true
    wait "$echo_pid" 2>/dev/null || true
  fi
  if [ -n "$node_pid" ]; then
    kill "$node_pid" 2>/dev/null || true
    wait "$node_pid" 2>/dev/null || true
  fi
  # `ros2 run` is a wrapper and its child outlives it, so killing the wrapper
  # alone leaked one publisher per run. Harmless here, but it is the same leak
  # that made the autonomy demo's /ap/cmd_vel poison a later flight test.
  pkill -9 -f "openipc_cinewhoop_demo/lib/openipc_cinewhoop_demo/trajectory_publisher" \
    2>/dev/null || true
  rm -rf "$test_tmpdir"
}
trap cleanup EXIT

ros2 run openipc_cinewhoop_demo trajectory_publisher \
  >"$test_tmpdir/trajectory_publisher.log" 2>&1 &
node_pid=$!

for _ in $(seq 1 20); do
  if ros2 node list | grep -Fxq /trajectory_publisher; then
    break
  fi
  sleep 0.25
done
ros2 node list | grep -Fx /trajectory_publisher

ros2 topic echo --once /openipc_cinewhoop/path nav_msgs/msg/Path \
  >"$test_tmpdir/path.log" 2>&1 &
echo_pid=$!

# The echo process must finish DDS discovery before the one-shot input arrives.
for _ in $(seq 1 40); do
  path_info="$(ros2 topic info /openipc_cinewhoop/path 2>/dev/null || true)"
  if grep -Eq '^Subscription count: [1-9][0-9]*$' <<<"$path_info"; then
    break
  fi
  sleep 0.25
done
grep -Eq '^Subscription count: [1-9][0-9]*$' <<<"$path_info"

# Publish BEST_EFFORT because that is what AP_DDS does. With the default
# RELIABLE the test matched a subscriber that real ArduPilot never would, and a
# RELIABLE pose subscription in the node passed here while receiving nothing in
# the field.
ros2 topic pub --once --wait-matching-subscriptions 1 \
  --qos-reliability best_effort \
  /ap/pose/filtered geometry_msgs/msg/PoseStamped \
  "{header: {frame_id: map}, pose: {position: {x: 1.0, y: 2.0, z: 3.0}}}"

for _ in $(seq 1 20); do
  if ! kill -0 "$echo_pid" 2>/dev/null; then
    wait "$echo_pid"
    echo_pid=""
    grep -Fq "x: 1.0" "$test_tmpdir/path.log"
    grep -Fq "y: 2.0" "$test_tmpdir/path.log"
    grep -Fq "z: 3.0" "$test_tmpdir/path.log"
    cat "$test_tmpdir/path.log"
    echo "ROS graph smoke check passed."
    exit 0
  fi
  sleep 0.25
done

echo "Timed out waiting for /openipc_cinewhoop/path." >&2
cat "$test_tmpdir/trajectory_publisher.log" >&2 || true
exit 1
