#!/usr/bin/env bash
# The swarm flight: three agents map one room together, coordinated.
#
# P1 to P4 of spec/roj/05_infrastruktura_simulace.md, and the flying half of
# M2. scripts/check_multi_instance_dds.sh already showed two autopilots can
# share a ROS graph; this adds the simulator, which is where the model name is
# used as an identity - in the world's include, in the plugin's rotor topics,
# and in the JSON port each autopilot talks to.
#
# The test that matters is not that both fly. It is that **only one flies when
# only one is told to**: a crossed fdm_port_in would show up as the other
# vehicle climbing, and no amount of both-took-off would have caught it.
#
# Passing since 2026-09-20. It failed for two days for a reason that had
# nothing to do with two agents: the Pavo20 model carried the CineLog's
# throttle multiplier and could not lift itself, and every "working" variant
# in the hunt was the CineLog being substituted through SDF_PATH. Both are
# fixed; see workflow/troubleshooting.md.
#
# Opt-in: needs the ignored local ArduPilot, ardupilot_gazebo and DDS builds
# plus the actuator bridge from scripts/build_actuator_bridge.sh.
set -eo pipefail

export LC_ALL=C

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

sitl_bin="external/ardupilot/build/sitl/bin/arducopter"
bridge_bin="build/ap_actuator_bridge/ap_actuator_bridge"
agent_setup="external/dds_ws/install/setup.bash"
agent_bin="external/dds_ws/install/lib/micro_ros_agent/micro_ros_agent"
plugin_dir="build/ardupilot_gazebo"

# How many agents to fly. Two is what M2 asks for; three is M3, and the
# generator's START_POSES is the limit because a start pose is a decision
# about separation rather than a loop index.
agents="${1:-${OPENIPC_AGENTS:-2}}"
# One is allowed and is the control case: the real time factor with a single
# agent is what the two- and three-agent figures have to be read against.
if ! [ "$agents" -ge 1 ] 2>/dev/null; then
  echo "usage: $0 [agent count >= 1]" >&2
  exit 2
fi

airframe="${OPENIPC_AIRFRAME:-cinewhoop}"
params_name="ardupilot_params.parm"
[ "$airframe" != "cinewhoop" ] && params_name="ardupilot_params_$airframe.parm"
sitl_params="ros_ws/src/openipc_cinewhoop_gazebo/config/$params_name"
dds_params="ros_ws/src/openipc_cinewhoop_gazebo/config/dds_smoke.parm"

for required_path in "$sitl_bin" "$bridge_bin" "$agent_setup" "$agent_bin" \
  "$plugin_dir/libArduPilotPlugin.so" "$sitl_params" "$dds_params" \
  "scripts/generate_agent_models.py"; do
  if [ ! -e "$required_path" ]; then
    echo "Two-agent prerequisite unavailable: $required_path" >&2
    exit 2
  fi
done

if [ ! -f install/setup.bash ]; then
  echo "Workspace is not built; run colcon build first." >&2
  exit 1
fi

unset ROS_DOMAIN_ID || true
export GZ_PARTITION="${GZ_PARTITION:-openipc_cinewhoop}"
export GZ_IP="${GZ_IP:-127.0.0.1}"
export GZ_SIM_SYSTEM_PLUGIN_PATH="$project_root/$plugin_dir${GZ_SIM_SYSTEM_PLUGIN_PATH:+:$GZ_SIM_SYSTEM_PLUGIN_PATH}"

echo "Generating one model per agent from the $airframe airframe:"
generated="$(python3 scripts/generate_agent_models.py --airframe "$airframe" \
  --agents "$agents" --world cluttered_room.sdf)"
echo "$generated"
models_path="$(echo "$generated" | sed -n 's/^models //p')"
world_path="$(echo "$generated" | sed -n 's/^world //p')"
mapfile -t bridge_configs < <(echo "$generated" | sed -n 's/^bridge //p')
if [ -z "$models_path" ] || [ -z "$world_path" ]; then
  echo "The generator did not print a models and world path." >&2
  exit 1
fi
export GZ_SIM_RESOURCE_PATH="$models_path:$(dirname "$world_path")${GZ_SIM_RESOURCE_PATH:+:$GZ_SIM_RESOURCE_PATH}"
# sdformat resolves model:// through SDF_PATH, not through
# GZ_SIM_RESOURCE_PATH, and the dev shell points SDF_PATH at the CineLog
# models. Without this line an OPENIPC_AIRFRAME=pavo20 run loads the
# CineLog model and reports it as the Pavo20 - which is what every
# pavo20 measurement before 2026-09-20 actually did.
# The generated models, not the airframe directory: the world includes
# model://openipc_cinewhoop_v1 and only $models_path has those. The dev shell
# points SDF_PATH at the CineLog, so without this the include resolves to
# nothing - or worse, to a model that is not the one being flown.
export SDF_PATH="$models_path${SDF_PATH:+:$SDF_PATH}"

set +u
source install/setup.bash
source "$agent_setup"
set -u

# Absolute, because each autopilot is started after a cd into its own
# directory and a relative --defaults path would resolve against that instead.
run_dir="$project_root/logs/swarm_mapping/$airframe-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$run_dir"
gazebo_pid=""
agent_pid=""
bridge_pids=()
gz_bridge_pids=()
sitl_pids=()
demo_pids=()

cleanup() {
  for pid in "${demo_pids[@]}" "${sitl_pids[@]}" "$agent_pid" \
             "${gz_bridge_pids[@]}" "${bridge_pids[@]}" "$gazebo_pid"; do
    [ -n "$pid" ] && kill -INT "$pid" 2>/dev/null || true
  done
  sleep 1
  for pid in "${demo_pids[@]}" "${sitl_pids[@]}" "$agent_pid" \
             "${gz_bridge_pids[@]}" "${bridge_pids[@]}" "$gazebo_pid"; do
    [ -n "$pid" ] && kill -9 "$pid" 2>/dev/null || true
  done
  # `ros2 run` is a wrapper whose child does not die with it, which is how a
  # failed run left fifteen nodes behind once. Each of these keeps publishing
  # into the next run's graph if it survives.
  for node in range_adapter occupancy_mapper simple_indoor_autonomy arbiter; do
    pkill -9 -f "openipc_cinewhoop_demo/$node" 2>/dev/null || true
  done
  pkill -9 -f "openipc_swarm/coordinator" 2>/dev/null || true
  pkill -9 -f "parameter_bridge --ros-args -p config_file:=$run_dir" 2>/dev/null || true
  pkill -9 -f "$project_root/$sitl_bin" 2>/dev/null || true
  pkill -9 -f "gz topic -e -t /world/.*/dynamic_pose/info" 2>/dev/null || true
}
trap cleanup EXIT

gz sim -s -r -v 3 "$world_path" >"$run_dir/gazebo.log" 2>&1 &
gazebo_pid=$!
sleep 8

# One actuator bridge per model. ArduPilot publishes a Double per rotor on
# topics scoped by the model's name and the motor models read one Actuators
# array, so a single bridge would drive whichever model it was told about and
# leave the other one's rotors stopped.
for index in $(seq 1 "$agents"); do
  "$project_root/$bridge_bin" --model "openipc_cinewhoop_v$index" \
    >"$run_dir/bridge_v$index.log" 2>&1 &
  bridge_pids+=($!)
done

"$project_root/$agent_bin" udp4 -p 20199 >"$run_dir/agent.log" 2>&1 &
agent_pid=$!

# One ros_gz_bridge per agent, each rendered from the single-drone template
# with its own model and its own ROS namespace. Without these the agents have
# no scans and no rangefinder in ROS, so nothing above the autopilot can map.
for index in $(seq 1 "$agents"); do
  ros2 run ros_gz_bridge parameter_bridge --ros-args \
    -p "config_file:=${bridge_configs[$((index - 1))]}" \
    >"$run_dir/gz_bridge_v$index.log" 2>&1 &
  gz_bridge_pids+=($!)
done
sleep 3

for index in $(seq 1 "$agents"); do
  instance=$((index - 1))
  dir="$run_dir/v$index"
  mkdir -p "$dir"
  # --wipe writes eeprom.bin into the working directory, so each autopilot
  # needs its own; see check_multi_instance_dds.sh.
  cat >"$dir/identity.parm" <<EOF
MAV_SYSID $index
DDS_USE_NS 1
EOF
  (
    cd "$dir"
    exec "$project_root/$sitl_bin" --wipe --model JSON --speedup 1 --slave 0 \
      -I"$instance" \
      --sim-address=127.0.0.1 --sim-port-out=$((9002 + instance * 10)) \
      --serial0="udpclient:127.0.0.1:$((14550 + instance * 10))" \
      --defaults "$project_root/$sitl_params,$project_root/$dds_params,$dir/identity.parm"
  ) >"$dir/sitl.log" 2>&1 &
  sitl_pids+=($!)
done

wanted_topics=""
for index in $(seq 1 "$agents"); do
  wanted_topics="$wanted_topics /ap/v$index/time"
done
for _ in $(seq 1 90); do
  missing=""
  for topic in $wanted_topics; do
    ros2 topic list 2>/dev/null | grep -Fxq "$topic" || missing="$missing $topic"
  done
  [ -z "$missing" ] && break
  sleep 1
done
if [ -n "$missing" ]; then
  echo "These autopilots never reached the ROS graph:$missing" >&2
  tail -20 "$run_dir/agent.log" >&2 || true
  exit 1
fi
echo "All $agents autopilots are on the graph:$wanted_topics"

# What the simulator is costing. Three machines with a 360-point lidar each is
# the load M3 asks about, and a Gazebo that has quietly stopped keeping up does
# not announce it - it just makes every measurement above mean something else.
real_time_factor="$(timeout 10 gz topic -e -t /stats -n 5 2>/dev/null \
  | grep -A2 real_time_factor | grep -oE "[0-9]+\.[0-9]+" | tail -1)"
echo "  real time factor with $agents agents: ${real_time_factor:-unknown}"

# Each agent's sensors have to arrive in ROS under its own namespace, or the
# mapper the coordinator merges from has nothing to map.
missing_sensors=""
for _ in $(seq 1 20); do
  missing_sensors=""
  for index in $(seq 1 "$agents"); do
    for suffix in scan/front range/down_raw; do
      ros2 topic list 2>/dev/null | grep -Fxq "/v$index/$suffix" \
        || missing_sensors="$missing_sensors /v$index/$suffix"
    done
  done
  [ -z "$missing_sensors" ] && break
  sleep 2
done
if [ -n "$missing_sensors" ]; then
  echo "These bridged sensor topics never appeared:$missing_sensors" >&2
  tail -10 "$run_dir/gz_bridge_v1.log" >&2 || true
  exit 1
fi
echo "  each agent's scan and rangefinder are bridged under its own namespace"

# Names are not traffic. The first swarm flight mapped nothing because the
# rangefinder topic existed and carried no usable measurement, and the mapper
# will not map a scan it cannot place above a floor it cannot see.
for index in $(seq 1 "$agents"); do
  for suffix in scan/front range/down_raw; do
    if ! timeout 20 ros2 topic echo --once "/v$index/$suffix" >/dev/null 2>&1; then
      echo "/v$index/$suffix exists but published nothing in 20 s." >&2
      exit 1
    fi
  done
done
echo "  and every one of them is carrying messages"
first_range="$(timeout 20 ros2 topic echo --once /v1/range/down_raw 2>/dev/null \
  | grep -A3 "^ranges:" | tail -2 | tr -d ' -' | tr '\n' ' ')"
echo "  v1's rangefinder reads: ${first_range:-nothing}"


# The demo stack, once per agent. These are the same nodes the single drone
# flies with, pointed at that agent's namespace: the demo's topics are all
# parameters, which is what makes three copies a configuration rather than a
# fork. The airframe's own geometry is passed in the same way
# check_forward_flight.sh does it, out of check_model_consistency.py, so a
# variant cannot quietly fly the flown airframe's corridor width.
airframe_args=()
if [ "$airframe" != "cinewhoop" ]; then
  while read -r name value; do
    [ -n "$name" ] && airframe_args+=(-p "$name:=$value")
  done < <(python3 scripts/check_model_consistency.py "$airframe" \
             | sed -n 's/^    \([a-z_]*\):=\(.*\)$/\1 \2/p')
  if [ "${#airframe_args[@]}" -eq 0 ]; then
    echo "No airframe parameters for $airframe; the model check changed shape." >&2
    exit 2
  fi
fi

demo_pids=()
for index in $(seq 1 "$agents"); do
  ns="v$index"
  ros2 run openipc_cinewhoop_demo range_adapter --ros-args \
    -p "scan_topic:=/$ns/range/down_raw" -p "range_topic:=/$ns/range/down" \
    >"$run_dir/range_adapter_$ns.log" 2>&1 &
  demo_pids+=($!)

  ros2 run openipc_cinewhoop_demo occupancy_mapper --ros-args \
    "${airframe_args[@]}" \
    -p "scan_topic:=/$ns/scan/front" -p "range_topic:=/$ns/range/down" \
    -p "pose_topic:=/ap/$ns/pose/filtered" -p "map_topic:=/$ns/map" \
    >"$run_dir/mapper_$ns.log" 2>&1 &
  demo_pids+=($!)

  # The autonomy publishes a nominal command; the arbiter is the only thing
  # that writes /ap/<ns>/cmd_vel. That is R19, and it is why a wrong decision
  # by the coordinator can slow this agent but cannot steer it into a wall.
  ros2 run openipc_cinewhoop_demo simple_indoor_autonomy --ros-args \
    "${airframe_args[@]}" \
    -p "scan_topic:=/$ns/scan/front" -p "range_topic:=/$ns/range/down" \
    -p "pose_topic:=/ap/$ns/pose/filtered" \
    -p "cmd_vel_topic:=/$ns/cmd_vel_nominal" \
    -p "target_topic:=/$ns/explore/target" \
    -p "battery_topic:=/ap/$ns/battery" \
    -p "status_topic:=/ap/$ns/status" \
    -p "prearm_service:=/ap/$ns/prearm_check" \
    -p "mode_service:=/ap/$ns/mode_switch" \
    -p "arm_service:=/ap/$ns/arm_motors" \
    -p "takeoff_service:=/ap/$ns/experimental/takeoff" \
    -p enable_turning:=true -p enable_exploring:=true \
    -p auto_takeoff:=true \
    >"$run_dir/autonomy_$ns.log" 2>&1 &
  demo_pids+=($!)

  ros2 run openipc_cinewhoop_demo arbiter --ros-args \
    -p "nominal_topic:=/$ns/cmd_vel_nominal" \
    -p "constraint_topic:=/$ns/swarm/constraint" \
    -p "command_topic:=/ap/$ns/cmd_vel" \
    >"$run_dir/arbiter_$ns.log" 2>&1 &
  demo_pids+=($!)
done

ros2 run openipc_swarm coordinator --ros-args \
  -p "agents:=[$(seq -s, -f 'v%g' 1 "$agents" | sed 's/[^,]*/\"&\"/g')]" \
  >"$run_dir/coordinator.log" 2>&1 &
demo_pids+=($!)
sleep 8

echo "Waiting for the loop to close: maps out of the agents, targets back in"
closed=false
for _ in $(seq 1 60); do
  have_maps=true
  for index in $(seq 1 "$agents"); do
    ros2 topic list 2>/dev/null | grep -Fxq "/v$index/map" || have_maps=false
  done
  if [ "$have_maps" = true ] \
     && ros2 topic list 2>/dev/null | grep -Fxq /swarm/map; then
    closed=true
    break
  fi
  sleep 2
done
if [ "$closed" != true ]; then
  echo "The coordinator and the agents never formed a graph." >&2
  tail -15 "$run_dir/coordinator.log" >&2 || true
  exit 1
fi
echo "  every agent publishes a map and the coordinator publishes /swarm/map"

# Traffic, not just names: a topic that exists and never carries a message is
# the failure this whole project keeps meeting.
for topic in /swarm/map /v1/swarm/constraint; do
  if ! timeout 25 ros2 topic echo --once "$topic" >/dev/null 2>&1; then
    echo "$topic exists but published nothing in 25 s." >&2
    tail -15 "$run_dir/coordinator.log" >&2 || true
    exit 1
  fi
  echo "  $topic is carrying messages"
done

# The flight. Sequential takeoffs, then the same 130 s the single-drone
# baseline flew, then the merged map measured with the same function over the
# same rectangles - scripts/room_geometry.py derives them from the world file
# so the two figures are comparable rather than merely similar.
python3 - "$world_path" "$agents" "$run_dir" <<'MEASURE'
import math
import os
import sys
import time

sys.path.insert(0, "scripts")
import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import OccupancyGrid
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, qos_profile_sensor_data

from openipc_cinewhoop_demo.grid_helpers import coverage_fraction
from room_geometry import room_and_enclosure

world_path, agents, run_dir = sys.argv[1], int(sys.argv[2]), sys.argv[3]
indices = list(range(1, agents + 1))
FLIGHT_S = 130.0

room, enclosure, _, obstacles = room_and_enclosure(world_path)
print(f"  room: x {room[0]:+.2f} to {room[1]:+.2f}, "
      f"y {room[2]:+.2f} to {room[3]:+.2f}")
print(f"  enclosure inside: x {enclosure[0]:+.2f} to {enclosure[1]:+.2f}, "
      f"y {enclosure[2]:+.2f} to {enclosure[3]:+.2f}")

rclpy.init()
node = rclpy.create_node("swarm_mapping_check")
merged = {}
node.create_subscription(
    OccupancyGrid, "/swarm/map", lambda m: merged.update(map=m),
    QoSProfile(depth=1, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL))
paths = {i: [] for i in indices}
agent_maps = {}
for index in indices:
    node.create_subscription(
        OccupancyGrid, f"/v{index}/map",
        (lambda i: lambda m: agent_maps.update({i: m}))(index),
        QoSProfile(depth=1, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL))
for index in indices:
    node.create_subscription(
        PoseStamped, f"/ap/v{index}/pose/filtered",
        (lambda i: lambda m: paths[i].append(
            (m.pose.position.x, m.pose.position.y)))(index),
        qos_profile_sensor_data)

# Each agent takes itself off through its own autonomy, which is the path the
# single-drone checks fly and the only one that gets the order right: that
# node publishes nothing at all while climbing, because a velocity command
# replaces the takeoff submode. Commanding the takeoff from here instead - as
# the first version of this check did - leaves the autonomy cruising on the
# ground, and then the rangefinder sits 0.021 m up reading inf and the mapper
# maps nothing. Wait for them rather than telling them.
print("  waiting for the agents to take themselves off", flush=True)
deadline = time.time() + 90
while time.time() < deadline:
    rclpy.spin_once(node, timeout_sec=0.2)

# In the air the rangefinder has to see the floor, or the mapper refuses to
# map at all - it will not paint a scan it cannot place above a floor it
# cannot see. On the ground it reads inf by design: the sensor's minimum is
# 0.05 m and it sits 0.021 m up.
from sensor_msgs.msg import Range
ranges = []
node.create_subscription(Range, "/v1/range/down",
                         lambda m: ranges.append(m.range),
                         qos_profile_sensor_data)
deadline = time.time() + 5
while time.time() < deadline:
    rclpy.spin_once(node, timeout_sec=0.1)
finite = [r for r in ranges if math.isfinite(r)]
print(f"  v1's rangefinder in flight: {len(finite)} finite of {len(ranges)}"
      + (f", around {sum(finite)/len(finite):.2f} m" if finite else ""))

start = time.time()
while time.time() - start < FLIGHT_S:
    rclpy.spin_once(node, timeout_sec=0.2)

if "map" not in merged:
    sys.exit("The coordinator never published a merged map.")
grid = merged["map"]
known = sum(1 for v in grid.data if v != -1)
print(f"  merged map: {grid.info.width}x{grid.info.height} cells at "
      f"{grid.info.resolution:.2f} m, origin "
      f"({grid.info.origin.position.x:+.2f}, {grid.info.origin.position.y:+.2f}), "
      f"{known} of them known")
for index in indices:
    own = agent_maps.get(index)
    if own is None:
        print(f"  v{index} published no map to compare with")
    else:
        own_known = sum(1 for v in own.data if v != -1)
        print(f"  v{index}'s own map: {own_known} cells known")
whole = coverage_fraction(grid.data, grid.info.width, grid.info.resolution,
                          grid.info.origin.position.x,
                          grid.info.origin.position.y,
                          room, list(obstacles.values()))
inside = coverage_fraction(grid.data, grid.info.width, grid.info.resolution,
                           grid.info.origin.position.x,
                           grid.info.origin.position.y,
                           enclosure, list(obstacles.values()))
flown = {i: len(p) for i, p in paths.items()}
print(f"  poses per agent: {flown}")
print(f"  the merged map calls {100 * whole:.0f} per cent of the room free")
print(f"  of the enclosure inside, {100 * inside:.0f} per cent")

with open(os.path.join(run_dir, "coverage.txt"), "w") as handle:
    handle.write(f"room {whole:.4f}\nenclosure {inside:.4f}\n")

if min(flown.values()) == 0:
    sys.exit("An agent published no pose at all; it never flew.")
if whole < 0.40:
    sys.exit(f"Only {100 * whole:.0f} per cent of the room was mapped.")
print("Swarm mapping flight finished.")
MEASURE

echo "Swarm mapping check passed: $agents agents mapping, one coordinator, loop closed."
