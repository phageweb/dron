#!/usr/bin/env bash
# Verify phase 12: one launch brings up the whole demo.
#
# Checks what can be checked without a screen: that a single
# `ros2 launch openipc_cinewhoop_gazebo sitl_gazebo.launch.py` produces the
# Gazebo sensor topics, the ArduPilot /ap/ topics and a TF tree at the same
# time. The visual criteria - the model and lidar appearing correctly in RViz -
# still need someone at a display.
#
# Opt-in: needs the ignored local ArduPilot, ardupilot_gazebo, Agent and
# actuator bridge builds.
set -eo pipefail
export LC_ALL=C

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

sitl_bin="external/ardupilot/build/sitl/bin/arducopter"
bridge_bin="build/ap_actuator_bridge/ap_actuator_bridge"
agent_bin="external/dds_ws/install/lib/micro_ros_agent/micro_ros_agent"
agent_setup="external/dds_ws/install/setup.bash"
plugin_dir="build/ardupilot_gazebo"

for required_path in "$sitl_bin" "$bridge_bin" "$agent_bin" "$agent_setup" \
  "$plugin_dir/libArduPilotPlugin.so"; do
  if [ ! -e "$required_path" ]; then
    echo "Unified launch prerequisite unavailable: $required_path" >&2
    exit 2
  fi
done

if [ ! -f install/setup.bash ]; then
  echo "Workspace is not built; run colcon build first." >&2
  exit 1
fi

# micro_ros_agent has no domain option and ignores ROS_DOMAIN_ID, so a domain
# override here would only hide every /ap/ topic from ros2.
unset ROS_DOMAIN_ID || true

set +u
source install/setup.bash
set -u

test_tmpdir="$(mktemp -d)"
launch_pid=""

cleanup() {
  if [ -n "$launch_pid" ]; then
    # The launch owns a whole process group; signal the group, not just ros2.
    kill -INT -- "-$launch_pid" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "$launch_pid" 2>/dev/null || break
      sleep 0.5
    done
    kill -9 -- "-$launch_pid" 2>/dev/null || true
  fi
  # ArduCopter ignores SIGINT while waiting on its JSON peer and would keep
  # UDP/9002, and `ros2 run`-style children outlive their wrapper.
  pkill -9 -f "$project_root/$sitl_bin" 2>/dev/null || true
  pkill -9 -f "$project_root/$agent_bin" 2>/dev/null || true
  pkill -9 -f "parameter_bridge --ros-args -p config_file:=$project_root" 2>/dev/null || true
  if [ -n "${KEEP_LOGS:-}" ]; then
    cp -r "$test_tmpdir" "$KEEP_LOGS" 2>/dev/null || true
    echo "logs kept in $KEEP_LOGS" >&2
  fi
  # Gazebo can outlive the launch that started it: killing the process group
  # misses it often enough that a survivor was found holding the partition and
  # failing the next check. Scoped to this project's own world files, so an
  # unrelated simulation on the same machine is not touched.
  pkill -9 -f "gz sim.*$project_root/install/openipc_cinewhoop_gazebo" 2>/dev/null || true
  rm -rf "$test_tmpdir"
}
trap cleanup EXIT

# rviz:=false keeps this headless; everything else is the documented default.
setsid ros2 launch openipc_cinewhoop_gazebo sitl_gazebo.launch.py \
  rviz:=false gui:=false >"$test_tmpdir/launch.log" 2>&1 &
launch_pid=$!

gazebo_topic="/openipc_cinewhoop/scan/front"
ardupilot_topic="/ap/geopose/filtered"

ready=false
for _ in $(seq 1 90); do
  topics="$(ros2 topic list 2>/dev/null || true)"
  if grep -Fxq "$gazebo_topic" <<<"$topics" \
    && grep -Fxq "$ardupilot_topic" <<<"$topics"; then
    ready=true
    break
  fi
  sleep 1
done

if [ "$ready" != true ]; then
  echo "The launch did not produce both Gazebo and ArduPilot topics." >&2
  echo "--- topics seen ---" >&2
  printf '%s\n' "$topics" >&2
  tail -60 "$test_tmpdir/launch.log" >&2 || true
  exit 1
fi

echo "  Gazebo and ArduPilot topics are both present."

# A topic name only proves a publisher exists, so require real messages.
for topic in "$gazebo_topic" "$ardupilot_topic" /tf_static; do
  if ! timeout 20 ros2 topic echo "$topic" --once >"$test_tmpdir/msg.log" 2>&1; then
    echo "No message arrived on $topic." >&2
    tail -20 "$test_tmpdir/msg.log" >&2 || true
    exit 1
  fi
  echo "  $topic delivers messages."
done

# robot_state_publisher must be the one serving TF, not a leftover process.
if ! ros2 node list 2>/dev/null | grep -Fxq /robot_state_publisher; then
  echo "robot_state_publisher is not running; TF comes from somewhere else." >&2
  exit 1
fi

# A TF tree rooted in nothing is the state this launch was in until
# pose_tf_broadcaster existed: robot_state_publisher served base_link and every
# sensor hanging off it, and nothing said where base_link was. Anything stamped
# in a world-fixed frame - the occupancy map above all - had no transform
# reaching it. /tf_static above proves the airframe's own tree; this proves it
# is attached to the world.
if ! timeout 30 ros2 run tf2_ros tf2_echo map base_link --ros-args \
    -p use_sim_time:=true >"$test_tmpdir/tf_echo.log" 2>&1; then
  # tf2_echo never exits on its own, so a timeout is the success path: what
  # matters is whether it printed a transform before being cut off.
  :
fi
if ! grep -q "Translation" "$test_tmpdir/tf_echo.log"; then
  echo "No map -> base_link transform; the TF tree has no root in the world." >&2
  tail -20 "$test_tmpdir/tf_echo.log" >&2 || true
  exit 1
fi
echo "  map -> base_link is broadcast, so the TF tree is rooted in the world."

# The demo nodes must stay runnable on their own, which is the plan's last point.
if ! ros2 topic list 2>/dev/null | grep -Fxq /ap/cmd_vel; then
  echo "/ap/cmd_vel is missing, so the autonomy demo could not be run against it." >&2
  exit 1
fi

echo "Unified launch check passed: one launch serves Gazebo, ArduPilot and a rooted TF tree."
