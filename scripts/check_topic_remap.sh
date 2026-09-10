#!/usr/bin/env bash
# Verify the sim-to-hardware abstraction the build spec requires: every topic and
# service the demo nodes touch must be a parameter, so moving off SITL changes
# the launch rather than the algorithm.
#
# See spec/realna_stavba_dronu/02_rozhrani_sim_real.md. Topic remapping is
# checked always; service remapping needs ardupilot_msgs from the opt-in DDS
# workspace, so it is checked only when that workspace is sourced.
set -eo pipefail
export LC_ALL=C

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if [ ! -f install/setup.bash ]; then
  echo "Workspace is not built; run colcon build first." >&2
  exit 1
fi

set +u
source install/setup.bash
set -u

# An isolated domain so a running simulation cannot satisfy this check.
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-91}"

test_tmpdir="$(mktemp -d)"
node_pid=""

cleanup() {
  if [ -n "$node_pid" ]; then
    kill -INT "$node_pid" 2>/dev/null || true
    sleep 1
    kill -9 "$node_pid" 2>/dev/null || true
  fi
  pkill -9 -f "$project_root/install/openipc_cinewhoop_demo/lib/openipc_cinewhoop_demo/simple_indoor_autonomy" 2>/dev/null || true
  pkill -9 -f "$project_root/install/openipc_cinewhoop_demo/lib/openipc_cinewhoop_demo/obstacle_monitor" 2>/dev/null || true
  pkill -9 -f "$project_root/install/openipc_cinewhoop_demo/lib/openipc_cinewhoop_demo/trajectory_publisher" 2>/dev/null || true
  rm -rf "$test_tmpdir"
}
trap cleanup EXIT

stop_node() {
  # `wait` reaps the job so bash does not print "Killed" for a process we meant
  # to kill; the check's own output stays readable.
  if [ -n "$node_pid" ]; then
    kill -INT "$node_pid" 2>/dev/null || true
    sleep 1
    kill -9 "$node_pid" 2>/dev/null || true
    wait "$node_pid" 2>/dev/null || true
    node_pid=""
  fi
  # `ros2 run` is a wrapper whose child outlives it, and a survivor from an
  # earlier phase keeps subscribing: that is how a stale trajectory_publisher
  # produced a QoS warning against the next phase's publisher.
  for exe in simple_indoor_autonomy obstacle_monitor trajectory_publisher; do
    pkill -9 -f "$project_root/install/openipc_cinewhoop_demo/lib/openipc_cinewhoop_demo/$exe" \
      2>/dev/null || true
  done
}

wait_for_node() {
  local name="$1"
  for _ in $(seq 1 40); do
    if ros2 node list 2>/dev/null | grep -Fxq "$name"; then
      return 0
    fi
    sleep 0.25
  done
  echo "Node $name never appeared." >&2
  return 1
}

require_in_node_info() {
  local node="$1" needle="$2" what="$3"
  if ! grep -Fq "$needle" "$test_tmpdir/info.log"; then
    echo "$node does not $what $needle; the parameter is not honoured." >&2
    echo "--- ros2 node info ---" >&2
    cat "$test_tmpdir/info.log" >&2
    return 1
  fi
  echo "  $node $what $needle"
}

echo "==> simple_indoor_autonomy honours remapped topics"
# auto_takeoff:=false keeps this independent of the opt-in ardupilot_msgs.
ros2 run openipc_cinewhoop_demo simple_indoor_autonomy --ros-args \
  -p auto_takeoff:=false \
  -p scan_topic:=/hw/front_scan \
  -p cmd_vel_topic:=/hw/cmd_vel \
  -p pose_topic:=/hw/pose \
  >"$test_tmpdir/autonomy.log" 2>&1 &
node_pid=$!
wait_for_node /simple_indoor_autonomy
ros2 node info /simple_indoor_autonomy >"$test_tmpdir/info.log" 2>&1
require_in_node_info simple_indoor_autonomy /hw/front_scan "subscribes to"
require_in_node_info simple_indoor_autonomy /hw/pose "subscribes to"
require_in_node_info simple_indoor_autonomy /hw/cmd_vel "publishes"
# The defaults must be gone, or the node would quietly listen to both.
if grep -Fq /openipc_cinewhoop/scan/front "$test_tmpdir/info.log"; then
  echo "simple_indoor_autonomy still uses the default scan topic." >&2
  exit 1
fi
stop_node

echo "==> obstacle_monitor honours a remapped scan topic"
ros2 run openipc_cinewhoop_demo obstacle_monitor --ros-args \
  -p scan_topic:=/hw/front_scan >"$test_tmpdir/monitor.log" 2>&1 &
node_pid=$!
wait_for_node /obstacle_monitor
ros2 node info /obstacle_monitor >"$test_tmpdir/info.log" 2>&1
require_in_node_info obstacle_monitor /hw/front_scan "subscribes to"
stop_node

echo "==> trajectory_publisher honours remapped topics"
ros2 run openipc_cinewhoop_demo trajectory_publisher --ros-args \
  -p pose_topic:=/hw/pose -p path_topic:=/hw/path \
  >"$test_tmpdir/trajectory.log" 2>&1 &
node_pid=$!
wait_for_node /trajectory_publisher
ros2 node info /trajectory_publisher >"$test_tmpdir/info.log" 2>&1
require_in_node_info trajectory_publisher /hw/pose "subscribes to"
require_in_node_info trajectory_publisher /hw/path "publishes"
stop_node

if python3 -c "import ardupilot_msgs" >/dev/null 2>&1; then
  echo "==> simple_indoor_autonomy honours remapped ArduPilot services"
  # `ros2 node info` does not list service clients, so introspection cannot
  # answer this. Stand up the services under the remapped names instead and
  # require the node to actually call them, which also exercises the whole
  # state machine without a simulator.
  ros2 run openipc_cinewhoop_demo simple_indoor_autonomy --ros-args \
    -p scan_topic:=/hw/front_scan -p cmd_vel_topic:=/hw/cmd_vel \
    -p pose_topic:=/hw/pose -p status_topic:=/hw/status \
    -p prearm_service:=/hw/prearm -p mode_service:=/hw/mode \
    -p arm_service:=/hw/arm -p takeoff_service:=/hw/takeoff \
    >"$test_tmpdir/services.log" 2>&1 &
  node_pid=$!
  wait_for_node /simple_indoor_autonomy

  # 5 m of clear air is well beyond the 0.8 m clearance plus 0.6 m braking, so a
  # healthy node walks the whole sequence and then commands forward motion.
  if ! python3 "$project_root/scripts/fake_ardupilot_services.py" \
      --prearm-service /hw/prearm --mode-service /hw/mode \
      --arm-service /hw/arm --takeoff-service /hw/takeoff \
      --scan-topic /hw/front_scan --pose-topic /hw/pose \
      --status-topic /hw/status --cmd-vel-topic /hw/cmd_vel \
      --range-m 5.0 --expect-forward --timeout-s 40; then
    echo "--- node log ---" >&2
    cat "$test_tmpdir/services.log" >&2
    exit 1
  fi
  stop_node

  echo "==> the node holds when the fake lidar reports an obstacle"
  ros2 run openipc_cinewhoop_demo simple_indoor_autonomy --ros-args \
    -p scan_topic:=/hw/front_scan -p cmd_vel_topic:=/hw/cmd_vel \
    -p pose_topic:=/hw/pose -p status_topic:=/hw/status \
    -p prearm_service:=/hw/prearm -p mode_service:=/hw/mode \
    -p arm_service:=/hw/arm -p takeoff_service:=/hw/takeoff \
    >"$test_tmpdir/hold.log" 2>&1 &
  node_pid=$!
  wait_for_node /simple_indoor_autonomy
  # 1.0 m is inside the 1.4 m threshold, so it must never command forward motion.
  if ! python3 "$project_root/scripts/fake_ardupilot_services.py" \
      --prearm-service /hw/prearm --mode-service /hw/mode \
      --arm-service /hw/arm --takeoff-service /hw/takeoff \
      --scan-topic /hw/front_scan --pose-topic /hw/pose \
      --status-topic /hw/status --cmd-vel-topic /hw/cmd_vel \
      --range-m 1.0 --timeout-s 40 >"$test_tmpdir/hold_result.log"; then
    cat "$test_tmpdir/hold_result.log" >&2
    echo "--- node log ---" >&2
    cat "$test_tmpdir/hold.log" >&2
    exit 1
  fi
  cat "$test_tmpdir/hold_result.log"
  if ! grep -Eq "peak forward: 0\.00 m/s" "$test_tmpdir/hold_result.log"; then
    echo "The node commanded forward motion with an obstacle at 1.0 m." >&2
    exit 1
  fi
  echo "  held at 1.0 m, inside the 0.80 m clearance plus 0.60 m braking"
else
  echo "==> skipping service remapping: ardupilot_msgs is not on the path"
  echo "    (source external/dds_ws/install/setup.bash to include it)"
fi

echo "Topic and service remapping check passed."
