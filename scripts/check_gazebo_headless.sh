#!/usr/bin/env bash
# Start the packaged Gazebo world headlessly and check its ROS bridge.
set -eo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if [ ! -f install/setup.bash ]; then
  echo "Workspace is not built; run colcon build first." >&2
  exit 1
fi

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-74}"
source install/setup.bash

test_tmpdir="$(mktemp -d)"
launch_pid=""

cleanup() {
  if [ -n "$launch_pid" ]; then
    # ros2 launch and its children need the signal as a process group.
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

setsid ros2 launch openipc_cinewhoop_gazebo gazebo.launch.py gui:=false use_bridge:=true \
  >"$test_tmpdir/gazebo.log" 2>&1 &
launch_pid=$!

required_topics=(
  /clock
  /openipc_cinewhoop/imu
  /openipc_cinewhoop/scan/front
  /openipc_cinewhoop/range/down
  /openipc_cinewhoop/camera/image_raw
)

for _ in $(seq 1 80); do
  topic_list="$(ros2 topic list 2>/dev/null || true)"
  ready=true
  for topic in "${required_topics[@]}"; do
    if ! grep -Fxq "$topic" <<<"$topic_list"; then
      ready=false
      break
    fi
  done
  if [ "$ready" = true ]; then
    break
  fi
  sleep 0.25
done

for topic in "${required_topics[@]}"; do
  grep -Fx "$topic" <<<"$topic_list"
done

echo "Gazebo headless smoke check passed."
