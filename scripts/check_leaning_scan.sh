#!/usr/bin/env bash
# Verify that a leaning vehicle does not report the floor as an obstacle.
#
# The attitude compensation in scan_helpers had unit tests and no flight behind
# it: check_forward_flight.sh cruises at 1 m with a gentle attitude, so the floor
# never enters the lidar's range there and the rejection is never exercised on a
# scan Gazebo produced. leaning_test.sdf holds the model static at 30 degrees
# nose-down, 0.60 m up, which is where the forward beams do meet the floor.
#
# Two things are asserted, and the second is worthless without the first:
#   * the scan really does report the floor inside the demo's stop threshold
#   * both demo nodes, given the attitude and the measured height, ignore it
# The same nodes are run a second time with the rangefinder topic pointed at
# nothing, which is how an unknown height is supposed to look. They must then
# report the floor, because an unknown altitude may not discard anything - that
# pair is what shows the compensation is doing the work rather than the scan
# being empty.
#
# Headless, no SITL, no ArduPilot: this belongs in baseline CI.
#
# The world is an argument, because the same property has to hold at more than
# one attitude: leaning_test.sdf pitches the vehicle, banked_test.sdf rolls it
# as well. A minimum roll can be demanded so the banked run fails rather than
# quietly becoming a second pitched one.
set -eo pipefail

world="${1:-leaning_test}"
min_roll_deg="${2:-0}"

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
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-78}"
# The launch pins the partition to this, and `gz topic` below has to look in the
# same one to find the world.
export GZ_PARTITION="${GZ_PARTITION:-openipc_cinewhoop}"
export GZ_IP="${GZ_IP:-127.0.0.1}"

test_tmpdir="$(mktemp -d)"
launch_pid=""
pose_pid=""
node_pids=()

cleanup() {
  for pid in "${node_pids[@]:-}" "$pose_pid" "$launch_pid"; do
    if [ -n "$pid" ]; then
      kill -TERM -- "-$pid" 2>/dev/null || true
    fi
  done
  # `ros2 run` and `ros2 launch` children outlive a TERM to the group leader on
  # some shutdown orders, and a leftover demo node publishing /ap/cmd_vel
  # silently ruins the next flight check.
  pkill -f "$project_root/install/openipc_cinewhoop_demo" 2>/dev/null || true
  for pid in "${node_pids[@]:-}" "$pose_pid" "$launch_pid"; do
    [ -n "$pid" ] && wait "$pid" 2>/dev/null || true
  done
  # Gazebo can outlive the launch that started it: killing the process group
  # misses it often enough that a survivor was found holding the partition and
  # failing the next check. Scoped to this project's own world files, so an
  # unrelated simulation on the same machine is not touched.
  pkill -9 -f "gz sim.*$project_root/install/openipc_cinewhoop_gazebo" 2>/dev/null || true
  rm -rf "$test_tmpdir"
}
trap cleanup EXIT

echo "==> Gazebo over $world"
setsid ros2 launch openipc_cinewhoop_gazebo gazebo.launch.py \
  gui:=false use_bridge:=true world:="$world.sdf" \
  >"$test_tmpdir/gazebo.log" 2>&1 &
launch_pid=$!

for topic in /openipc_cinewhoop/scan/front /openipc_cinewhoop/range/down; do
  for _ in $(seq 1 160); do
    ros2 topic list 2>/dev/null | grep -Fxq "$topic" && break
    sleep 0.25
  done
  if ! ros2 topic list 2>/dev/null | grep -Fxq "$topic"; then
    echo "$topic never appeared." >&2
    tail -n 60 "$test_tmpdir/gazebo.log" >&2 || true
    exit 1
  fi
done

# The attitude the demo nodes use comes from the flight controller's estimate on
# /ap/pose/filtered, and AP_DDS is not running here. Take it from Gazebo's own
# report of where the model is rather than repeating the world file's numbers in
# this script, so the two cannot drift apart. The same query returns where the
# front lidar really is above the floor - the sensor whose beams are projected,
# not the one that measures. Getting from one to the other is the whole of what
# compensation_height does to a Range message, so that is what to check.
quat="$(timeout 40 python3 scripts/gazebo_link_truth.py \
  "ros_ws/src/openipc_cinewhoop_gazebo/worlds/$world.sdf" "$world" \
  openipc_cinewhoop front_lidar_link 2>"$test_tmpdir/truth.log")"
if [ -z "$quat" ]; then
  echo "Could not read the vehicle's attitude out of Gazebo." >&2
  cat "$test_tmpdir/truth.log" >&2 || true
  exit 1
fi
read -r qx qy qz qw true_height <<<"$quat"
echo "  vehicle attitude from Gazebo: x=$qx y=$qy z=$qz w=$qw"
echo "  front_lidar_link is $true_height m above the floor surface"

setsid ros2 topic pub -r 10 --qos-reliability best_effort /ap/pose/filtered \
  geometry_msgs/msg/PoseStamped \
  "{header: {frame_id: map}, pose: {position: {z: 0.6},
    orientation: {x: $qx, y: $qy, z: $qz, w: $qw}}}" \
  >"$test_tmpdir/pose.log" 2>&1 &
pose_pid=$!

echo "==> the scan is the floor, and the geometry rejects it"
python3 scripts/check_leaning_scan.py "$true_height" "$min_roll_deg"

echo "==> the demo nodes over the same scan"
# Blind variants point at a rangefinder topic nobody publishes, which is exactly
# what the node sees when the altitude is unknown: it may then discard nothing.
run_node() {
  local exe="$1" name="$2"
  shift 2
  setsid ros2 run openipc_cinewhoop_demo "$exe" --ros-args \
    -r "__node:=$name" "$@" >"$test_tmpdir/$name.log" 2>&1 &
  node_pids+=($!)
}

run_node obstacle_monitor obstacle_monitor -p log_period_s:=0.1
run_node obstacle_monitor obstacle_monitor_blind -p log_period_s:=0.1 \
  -p range_topic:=/openipc_cinewhoop/range/absent
run_node simple_indoor_autonomy simple_indoor_autonomy \
  -p auto_takeoff:=false
run_node simple_indoor_autonomy simple_indoor_autonomy_blind \
  -p auto_takeoff:=false -p cmd_vel_topic:=/ap/cmd_vel_blind \
  -p range_topic:=/openipc_cinewhoop/range/absent

expect() {
  local name="$1" pattern="$2" what="$3"
  local log="$test_tmpdir/$name.log"
  for _ in $(seq 1 80); do
    if grep -qE "$pattern" "$log" 2>/dev/null; then
      echo "  $name: $(grep -hoE "$pattern" "$log" | head -1)"
      return 0
    fi
    sleep 0.25
  done
  echo "$name never $what (looked for /$pattern/)." >&2
  tail -n 30 "$log" >&2 || true
  exit 1
}

# Blind first: it is the one that must see something, so if the scan or the
# wiring is broken this fails before the compensated nodes pass vacuously.
expect obstacle_monitor_blind "(Nearest obstacle|Obstacle close): [0-9.]+ m" \
  "reported the floor with the height unknown"
expect simple_indoor_autonomy_blind "Holding: obstacle at [0-9.]+ m" \
  "held for the floor with the height unknown"
expect obstacle_monitor "No valid front lidar range" \
  "dropped the floor"

# The autonomy node is asked for its command rather than for a log line, and
# that is the difference the corridor made. It used to hold with "no valid range
# in the scan" - the floor gone and nothing else in the forward cone - and that
# line was the evidence. Asking about the corridor instead, an empty corridor is
# a clear way ahead rather than a blind vehicle, so a node that has dropped the
# floor now flies. Commanding 0.5 m/s over a scan that is entirely floor is the
# same property stated the stronger way: not "it stopped reporting the floor"
# but "it is willing to fly through it".
moving="none"
for _ in $(seq 1 40); do
  moving="$(timeout 4 ros2 topic echo --once --field twist.linear.x \
    /ap/cmd_vel 2>/dev/null | grep -m1 -E '^-?[0-9]+\.?[0-9]*$' || true)"
  [ -n "$moving" ] && [ "$moving" != "0.0" ] && break
  moving="${moving:-none}"
  sleep 0.25
done
if [ "$moving" = "none" ] || [ "$moving" = "0.0" ]; then
  echo "simple_indoor_autonomy would not fly over a scan that is all floor" >&2
  echo "(commanded '$moving'); it is still treating the floor as an obstacle." >&2
  tail -n 30 "$test_tmpdir/simple_indoor_autonomy.log" >&2 || true
  exit 1
fi
echo "  simple_indoor_autonomy: flies at $moving m/s over it"

# And the blind one must not, over the same scan at the same moment. Without
# this the line above would pass just as happily if the demo had stopped
# stopping for anything at all.
blind_speed="$(timeout 4 ros2 topic echo --once --field twist.linear.x \
  /ap/cmd_vel_blind 2>/dev/null | grep -m1 -E '^-?[0-9]+\.?[0-9]*$' || true)"
if [ "${blind_speed:-none}" != "0.0" ]; then
  echo "simple_indoor_autonomy_blind commanded '${blind_speed:-none}' over a" >&2
  echo "scan it cannot tell from an obstacle; it should be holding." >&2
  exit 1
fi
echo "  simple_indoor_autonomy_blind: holds at $blind_speed m/s over the same scan"

# A compensated node that also reported an obstacle would have satisfied the
# greps above and still be wrong, so the absence is asserted too. Only from the
# first correct line onwards: a node that has not yet received the pose and the
# rangefinder has no attitude and no height, and reporting the floor is then the
# right thing for it to do. The property is that it never goes back.
absent_after() {
  local name="$1" marker="$2"
  local log="$test_tmpdir/$name.log"
  local from
  from="$(grep -nm1 -- "$marker" "$log" | cut -d: -f1)"
  if tail -n "+$from" "$log" \
      | grep -qE "Nearest obstacle|Obstacle close|Holding: obstacle at"; then
    echo "$name went back to reporting the floor after it had the attitude" >&2
    echo "and the height:" >&2
    tail -n "+$from" "$log" \
      | grep -hE "Nearest obstacle|Obstacle close|Holding: obstacle at" \
      | head -5 >&2
    exit 1
  fi
}

absent_after obstacle_monitor "No valid front lidar range"
# Anchored on the node saying the compensation is on, which is the first moment
# it has both inputs. Before that it has no height and reporting the floor is
# the right thing for it to do.
absent_after simple_indoor_autonomy "Rejecting floor returns"

echo "Leaning scan check passed over $world: the floor stops an uncompensated node and not a compensated one."
