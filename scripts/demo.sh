#!/usr/bin/env bash
# The whole demo from one command: scene, simulator, and the flight to the wall.
#
# Starts Gazebo with its window, ArduPilot SITL, both bridges, RViz and the DDS
# Agent, waits until ArduPilot's ROS 2 services actually answer, then flies the
# autonomy demo in the foreground. It stays up after the vehicle stops, holding
# position, until Ctrl-C - so the scene can be looked at rather than raced past.
#
# Everything it starts, it kills on the way out. A leftover autonomy node keeps
# publishing /ap/cmd_vel and silently stops the *next* run from ever taking off.
set -uo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

gui="true"
altitude="1.0"
world="indoor_test.sdf"
turning="false"
mapping="false"
passthrough=()
while [ $# -gt 0 ]; do
  case "$1" in
    --no-gui) gui="false"; passthrough+=("--no-gui") ;;
    # A circuit needs a closed room to fly round; indoor_test.sdf is a floor
    # with two panels on it, so a turning vehicle simply leaves.
    --circuit)
      turning="true"
      world="room_test.sdf"
      passthrough+=("--circuit") ;;
    # Builds the map live rather than only inside the check. Not yet watchable
    # in RViz: the grid is stamped in a "map" frame and nothing broadcasts
    # map -> base_link, so RViz has nowhere to put it. `ros2 topic echo` and
    # the mapper's own log are what there is until that transform exists.
    --map) mapping="true"; passthrough+=("--map") ;;
    --altitude)
      altitude="${2:?--altitude needs a value}"
      passthrough+=("--altitude" "$2")
      shift ;;
    -h|--help)
      echo "usage: scripts/demo.sh [--no-gui] [--circuit] [--map] [--altitude METRES]"
      echo "  --circuit  fly a closed room and turn at the walls instead of"
      echo "             stopping at one obstacle in indoor_test.sdf"
      echo "  --map      build an occupancy grid on /openipc_cinewhoop/map"
      exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

if ! command -v ros2 >/dev/null 2>&1; then
  if command -v nix >/dev/null 2>&1; then
    echo "Not in the dev shell; re-entering through nix develop."
    exec nix develop --command "$0" "${passthrough[@]}"
  fi
  echo "Neither ros2 nor nix is on PATH." >&2
  exit 1
fi

sitl_bin="external/ardupilot/build/sitl/bin/arducopter"
for required in install/setup.bash "$sitl_bin" \
    build/ap_actuator_bridge/ap_actuator_bridge \
    build/ardupilot_gazebo/libArduPilotPlugin.so \
    external/dds_ws/install/setup.bash; do
  if [ ! -e "$required" ]; then
    echo "Demo prerequisite missing: $required" >&2
    echo "See the first-time setup in workflow/running.md." >&2
    exit 2
  fi
done

# Two simulators cannot share the JSON and MAVLink ports. Say so now rather than
# failing later with something that points at the wrong thing.
stray="$(pgrep -f "$sitl_bin" 2>/dev/null || true)"
if [ -n "$stray" ]; then
  echo "ArduPilot SITL is already running (pid $(echo "$stray" | tr '\n' ' '))." >&2
  echo "Stop it first:  pkill -f $sitl_bin" >&2
  exit 1
fi

set +u
source install/setup.bash
source external/dds_ws/install/setup.bash
set -u

launch_pid=""
demo_pid=""
mapper_pid=""

cleanup() {
  # The trap catches INT, TERM and EXIT, and Ctrl-C fires two of them; without
  # this the whole shutdown ran twice.
  trap - EXIT INT TERM
  echo
  echo "==> Shutting the demo down."
  for pid in "$mapper_pid" "$demo_pid" "$launch_pid"; do
    [ -n "$pid" ] && kill -TERM -- "-$pid" 2>/dev/null || true
  done
  sleep 2
  # `ros2 run` and `ros2 launch` both outlive a TERM to the wrapper on some
  # orders, so finish the job by install path and binary.
  pkill -9 -f "$project_root/install/openipc_cinewhoop_demo/lib" 2>/dev/null || true
  pkill -9 -f "$project_root/$sitl_bin" 2>/dev/null || true
  pkill -9 -f "$project_root/build/ap_actuator_bridge" 2>/dev/null || true
  for pid in "$mapper_pid" "$demo_pid" "$launch_pid"; do
    [ -n "$pid" ] && kill -9 -- "-$pid" 2>/dev/null || true
  done
  echo "==> Done."
}
trap cleanup EXIT INT TERM

echo "==> Starting the scene: Gazebo${gui:+ (gui=$gui)}, SITL, bridges, RViz, DDS Agent."
setsid ros2 launch openipc_cinewhoop_gazebo sitl_gazebo.launch.py "gui:=$gui" \
  "world:=$world" \
  >"$project_root/logs/demo-launch.log" 2>&1 &
launch_pid=$!

echo "==> Waiting for ArduPilot's ROS 2 services."
ready=false
for _ in $(seq 1 120); do
  if ros2 service list 2>/dev/null | grep -q "^/ap/experimental/takeoff$"; then
    ready=true
    break
  fi
  sleep 1
done
if [ "$ready" != true ]; then
  echo "ArduPilot services never appeared. Last of the launch log:" >&2
  tail -n 25 "$project_root/logs/demo-launch.log" >&2
  exit 1
fi

if [ "$mapping" = true ]; then
  echo "==> Mapping into /openipc_cinewhoop/map."
  setsid ros2 run openipc_cinewhoop_demo occupancy_mapper &
  mapper_pid=$!
fi

echo "==> Flying: arm, take off to ${altitude} m, creep forward, stop for the wall."
echo "==> It holds position when it stops. Ctrl-C when you have seen enough."
echo
setsid ros2 run openipc_cinewhoop_demo simple_indoor_autonomy \
  --ros-args -p takeoff_altitude_m:="$altitude" \
  -p enable_turning:="$turning" &
demo_pid=$!
wait "$demo_pid"
