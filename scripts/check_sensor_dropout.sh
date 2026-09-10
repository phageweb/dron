#!/usr/bin/env bash
# Verify that a dead front lidar puts the demo nodes into a safe state.
#
# This is the last item of the transition checklist in
# spec/realna_stavba_dronu/02_rozhrani_sim_real.md. It needs no Gazebo and no
# SITL: the scan is published from the command line and then stopped, which is
# exactly what a disconnected sensor looks like to a node.
set -eo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if [ ! -f install/setup.bash ]; then
  echo "Workspace is not built; run colcon build first." >&2
  exit 1
fi

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-$((100 + ($$ % 100)))}"
set +u
source install/setup.bash
set -u

test_tmpdir="$(mktemp -d)"
scan_pid=""
monitor_pid=""
autonomy_pid=""

cleanup() {
  for pid in "$scan_pid" "$monitor_pid" "$autonomy_pid"; do
    if [ -n "$pid" ]; then
      kill -TERM -- "-$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
  # A `ros2 run` child outlives its wrapper, and a leftover node publishing
  # /ap/cmd_vel silently ruins the next flight check.
  pkill -9 -f "$project_root/install/openipc_cinewhoop_demo/lib" 2>/dev/null || true
  rm -rf "$test_tmpdir"
}
trap cleanup EXIT

publish_scan() {
  # BEST_EFFORT because that is the QoS real sensor drivers use, and -w 1 so the
  # publisher starts only once it has actually discovered the node under test.
  # One CI run in five saw no scan at all for fifteen seconds, which is DDS
  # discovery losing the pairing rather than anything the nodes did.
  setsid ros2 topic pub -r 10 -w 1 --qos-reliability best_effort \
    /openipc_cinewhoop/scan/front sensor_msgs/msg/LaserScan \
    "{header: {frame_id: front_lidar_link}, angle_min: -0.5, angle_max: 0.5,
      angle_increment: 0.25, range_min: 0.1, range_max: 8.0,
      ranges: [5.0, 5.0, 5.0, 5.0, 5.0]}" \
    >"$test_tmpdir/scan.log" 2>&1 &
  scan_pid=$!
}

stop_scan() {
  kill -TERM -- "-$scan_pid" 2>/dev/null || true
  wait "$scan_pid" 2>/dev/null || true
  scan_pid=""
}

forward_speed() {
  # One sample of the commanded forward velocity, or "none" if nothing is sent.
  # `ros2 topic echo` prints its own warning on stdout when the topic has no
  # publisher yet, so only a number counts as an answer; without the filter the
  # warning text itself passed for a speed.
  local value
  value="$(timeout 4 ros2 topic echo --once --field twist.linear.x \
    /ap/cmd_vel 2>/dev/null | grep -m1 -E '^-?[0-9]+\.?[0-9]*$' || true)"
  echo "${value:-none}"
}

echo "==> obstacle_monitor reports a silent lidar"
setsid ros2 run openipc_cinewhoop_demo obstacle_monitor \
  --ros-args -p log_period_s:=0.1 -p scan_timeout_s:=0.5 \
  >"$test_tmpdir/monitor.log" 2>&1 &
monitor_pid=$!

# Two attempts, because a lost pairing is recovered by republishing and the
# check is about the nodes rather than about DDS.
seen=false
for attempt in 1 2; do
  publish_scan
  for _ in $(seq 1 40); do
    if grep -q "Nearest obstacle" "$test_tmpdir/monitor.log"; then
      seen=true
      break
    fi
    sleep 0.25
  done
  [ "$seen" = true ] && break
  echo "  no scan reached the monitor on attempt $attempt; republishing" >&2
  stop_scan
done
if [ "$seen" != true ]; then
  echo "obstacle_monitor never saw the injected scan." >&2
  cat "$test_tmpdir/monitor.log" >&2
  echo "--- scan publisher ---" >&2
  cat "$test_tmpdir/scan.log" >&2
  ros2 topic info /openipc_cinewhoop/scan/front >&2 || true
  exit 1
fi

stop_scan
for _ in $(seq 1 40); do
  grep -q "No front lidar scan any more" "$test_tmpdir/monitor.log" && break
  sleep 0.25
done
if ! grep -q "No front lidar scan any more" "$test_tmpdir/monitor.log"; then
  echo "obstacle_monitor stayed quiet after the lidar stopped." >&2
  tail -n 20 "$test_tmpdir/monitor.log" >&2
  exit 1
fi
echo "  warned: $(grep -m1 'No front lidar scan any more' "$test_tmpdir/monitor.log")"

echo "==> simple_indoor_autonomy stops commanding when the lidar dies"
# auto_takeoff false keeps this out of ardupilot_msgs, so it runs in baseline CI.
setsid ros2 run openipc_cinewhoop_demo simple_indoor_autonomy \
  --ros-args -p auto_takeoff:=false -p scan_timeout_s:=0.5 \
  >"$test_tmpdir/autonomy.log" 2>&1 &
autonomy_pid=$!

publish_scan
moving="none"
for _ in $(seq 1 40); do
  moving="$(forward_speed)"
  [ "$moving" != "none" ] && [ "$moving" != "0.0" ] && break
  sleep 0.25
done
if [ "$moving" = "none" ] || [ "$moving" = "0.0" ]; then
  echo "The node never commanded forward flight with 5 m of clear air (got '$moving')." >&2
  cat "$test_tmpdir/autonomy.log" >&2
  exit 1
fi
echo "  with a live lidar: twist.linear.x = $moving"

stop_scan
sleep 1
stopped="$(forward_speed)"
if [ "$stopped" != "0.0" ]; then
  echo "The node kept commanding $stopped after the lidar stopped." >&2
  cat "$test_tmpdir/autonomy.log" >&2
  exit 1
fi
echo "  with a dead lidar: twist.linear.x = $stopped"

echo "Sensor dropout check passed."
