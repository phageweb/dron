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
pose_pid=""
range_pid=""
monitor_pid=""
autonomy_pid=""

cleanup() {
  for pid in "$scan_pid" "$pose_pid" "$range_pid" "$monitor_pid" "$autonomy_pid"; do
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

echo "==> simple_indoor_autonomy ignores what is behind it"
# The LD06 sweeps the whole circle, so a wall behind the vehicle appears in the
# same scan as the clear air ahead. Taking the minimum over the whole array
# would stop the demo dead; only the forward sector may count.
setsid ros2 topic pub -r 10 -w 1 --qos-reliability best_effort \
  /openipc_cinewhoop/scan/front sensor_msgs/msg/LaserScan \
  "{header: {frame_id: front_lidar_link}, angle_min: -3.14159, angle_max: 1.5708,
    angle_increment: 1.5708, range_min: 0.02, range_max: 12.0,
    ranges: [0.3, 5.0, 5.0, 5.0]}" \
  >"$test_tmpdir/scan.log" 2>&1 &
scan_pid=$!

behind="none"
for _ in $(seq 1 40); do
  behind="$(forward_speed)"
  [ "$behind" != "none" ] && [ "$behind" != "0.0" ] && break
  sleep 0.25
done
stop_scan
if [ "$behind" = "none" ] || [ "$behind" = "0.0" ]; then
  echo "A wall 0.3 m behind stopped the demo (got '$behind'); the forward" >&2
  echo "sector is not being applied." >&2
  cat "$test_tmpdir/autonomy.log" >&2
  exit 1
fi
echo "  wall 0.3 m behind, clear ahead: twist.linear.x = $behind"

echo "==> simple_indoor_autonomy stops trusting an attitude that stopped arriving"
# The floor rejection needs two inputs that do not arrive with the scan: the
# lean, over DDS from the flight controller, and the height, from a different
# sensor. Either can stop while the lidar stays healthy, and a lean applied to a
# scan taken at some other attitude does not merely over-reject. Returns are
# dropped on `range * cos(bearing)`, so a nose-down attitude drops a wall
# straight ahead before it drops a farther return at the edge of the sector.
#
# The numbers are that failure, arranged so both halves are visible. The
# rangefinder reports 1.039 m of slant, which at 30 degrees of lean is 0.90 m of
# height. Returns are then floor beyond 1.30 m of horizontal reach: the 1.35 m
# wall dead ahead is floor, the 1.45 m return at 29 degrees reaches only 1.27 m
# and is not. So a vehicle that really is leaning may fly -
# and the same scan, once the lean can no longer be trusted, must stop it,
# because 1.35 m is inside the 1.40 m the demo stops at.
publish_leaning_scan() {
  setsid ros2 topic pub -r 10 -w 1 --qos-reliability best_effort \
    /openipc_cinewhoop/scan/front sensor_msgs/msg/LaserScan \
    "{header: {frame_id: front_lidar_link}, angle_min: -0.50615, angle_max: 0.50615,
      angle_increment: 0.25307, range_min: 0.02, range_max: 12.0,
      ranges: [4.0, 4.0, 1.35, 4.0, 1.45]}" \
    >"$test_tmpdir/scan.log" 2>&1 &
  scan_pid=$!
}

setsid ros2 topic pub -r 10 -w 1 --qos-reliability best_effort \
  /openipc_cinewhoop/range/down sensor_msgs/msg/Range \
  "{header: {frame_id: rangefinder_link}, radiation_type: 1, field_of_view: 0.1,
    min_range: 0.05, max_range: 8.0, range: 1.039}" \
  >"$test_tmpdir/range.log" 2>&1 &
range_pid=$!

# 30 degrees nose-down: REP 103 puts y to the left, so a positive rotation about
# it drops the nose. w = cos(15 deg), y = sin(15 deg).
setsid ros2 topic pub -r 10 -w 1 --qos-reliability best_effort \
  /ap/pose/filtered geometry_msgs/msg/PoseStamped \
  "{header: {frame_id: map}, pose: {position: {z: 0.9},
    orientation: {x: 0.0, y: 0.258819, z: 0.0, w: 0.965926}}}" \
  >"$test_tmpdir/pose.log" 2>&1 &
pose_pid=$!

publish_leaning_scan
leaning="none"
for _ in $(seq 1 40); do
  leaning="$(forward_speed)"
  [ "$leaning" != "none" ] && [ "$leaning" != "0.0" ] && break
  sleep 0.25
done
if [ "$leaning" = "none" ] || [ "$leaning" = "0.0" ]; then
  echo "The demo held with a live attitude saying the 1.35 m return is floor" >&2
  echo "(got '$leaning'); the rest of this case would then pass over nothing." >&2
  tail -n 20 "$test_tmpdir/autonomy.log" >&2
  exit 1
fi
echo "  leaning 30 deg, 1.039 m of slant = 0.90 m up, floor at 1.35 m: twist.linear.x = $leaning"

# Only the attitude stops. The scan and the height keep arriving, so nothing
# the node watches for staleness today has changed.
kill -TERM -- "-$pose_pid" 2>/dev/null || true
wait "$pose_pid" 2>/dev/null || true
pose_pid=""
sleep 1.5
blind="$(forward_speed)"
stop_scan
if [ "$blind" != "0.0" ]; then
  echo "The demo kept commanding $blind after the attitude stopped arriving." >&2
  echo "It is still rejecting the 1.35 m wall as floor using a lean it can no" >&2
  echo "longer see, and 1.35 m is inside the distance it stops at." >&2
  tail -n 20 "$test_tmpdir/autonomy.log" >&2
  exit 1
fi
if ! grep -q "Not rejecting floor returns: the attitude is stale" \
    "$test_tmpdir/autonomy.log"; then
  echo "The demo stopped, but never said the attitude had gone stale, so it" >&2
  echo "may have stopped for some other reason." >&2
  tail -n 20 "$test_tmpdir/autonomy.log" >&2
  exit 1
fi
echo "  attitude stale: twist.linear.x = $blind"
echo "  $(grep -m1 'the attitude is stale' "$test_tmpdir/autonomy.log" \
  | sed 's/.*\] //')"

echo "Sensor dropout check passed."
