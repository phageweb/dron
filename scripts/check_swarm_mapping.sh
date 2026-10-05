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
# OPENIPC_SLOT=k flies this swarm beside others (scripts/swarm_batch.py):
# its own ROS domain, Gazebo partition, autopilot instances 3k..3k+2 (and so
# their ports), DDS agent port, generated models and run directory, and a
# cleanup that kills its own process group instead of everything by name.
# Unset, everything is as it always was.
slot="${OPENIPC_SLOT:-}"
instance_base=0
dds_port=20199
agent_out="build/agent_sim"
if [ -n "$slot" ]; then
  export ROS_DOMAIN_ID=$((20 + slot))
  export GZ_PARTITION="openipc_cinewhoop_s$slot"
  instance_base=$((slot * agents))
  dds_port=$((20199 + slot * 10))
  agent_out="build/agent_sim_s$slot"
fi
export GZ_IP="${GZ_IP:-127.0.0.1}"
export GZ_SIM_SYSTEM_PLUGIN_PATH="$project_root/$plugin_dir${GZ_SIM_SYSTEM_PLUGIN_PATH:+:$GZ_SIM_SYSTEM_PLUGIN_PATH}"

# OPENIPC_WORLD picks a variant of the room, e.g. cluttered_room_no_pocket.sdf,
# or is the absolute path of a generated one (scripts/random_world.py).
# The run directory records which, so the replay scores against the same walls.
world="${OPENIPC_WORLD:-cluttered_room.sdf}"
# OPENIPC_CAMERA=0 leaves the front camera out: nothing here reads it, and
# two swarms rendering six of them ran at a tenth of real time.
camera_flag=""
if [ "${OPENIPC_CAMERA:-1}" = "0" ]; then
  camera_flag="--no-camera"
fi
echo "Generating one model per agent from the $airframe airframe:"
generated="$(python3 scripts/generate_agent_models.py --airframe "$airframe" \
  --agents "$agents" --world "$world" --instance-base "$instance_base" \
  --out "$agent_out" ${camera_flag})"
echo "$generated"
models_path="$(echo "$generated" | sed -n 's/^models //p')"
world_path="$(echo "$generated" | sed -n 's/^world //p')"
mapfile -t bridge_configs < <(echo "$generated" | sed -n 's/^bridge //p')
start_offsets="$(echo "$generated" | sed -n 's/^offsets //p')"
if [ -z "$models_path" ] || [ -z "$world_path" ] || [ -z "$start_offsets" ]; then
  echo "The generator did not print a models path, a world path and offsets." >&2
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
run_dir="$project_root/logs/swarm_mapping/$airframe-$(date +%Y%m%d-%H%M%S)${slot:+-s$slot}"
mkdir -p "$run_dir"
if [ "${world#/}" != "$world" ]; then
  # A generated world goes with the run, so the run can be scored and
  # replayed after the batch that made it is gone.
  cp "$world" "$run_dir/world.sdf"
  echo "$run_dir/world.sdf" >"$run_dir/world.txt"
else
  echo "ros_ws/src/openipc_cinewhoop_gazebo/worlds/$world" >"$run_dir/world.txt"
fi
# A label for the code variant this run flew, for comparing runs afterwards.
if [ -n "${OPENIPC_VERSION:-}" ]; then
  echo "$OPENIPC_VERSION" >"$run_dir/version.txt"
fi
if [ -n "${OPENIPC_FLIGHT_S:-}" ]; then
  echo "$OPENIPC_FLIGHT_S" >"$run_dir/flight_s.txt"
fi
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
  if [ -n "$slot" ]; then
    # Beside other swarms, killing by name would kill theirs too. What this
    # run started is in its process group - swarm_batch.py starts each run
    # as a group leader - so that is what goes, wrappers' children included.
    trap - TERM
    kill -9 -- "-$(ps -o pgid= $$ | tr -d ' ')" 2>/dev/null || true
    return
  fi
  # `ros2 run` is a wrapper whose child does not die with it, which is how a
  # failed run left fifteen nodes behind once. Each of these keeps publishing
  # into the next run's graph if it survives.
  for node in range_adapter occupancy_mapper simple_indoor_autonomy arbiter; do
    pkill -9 -f "openipc_cinewhoop_demo/$node" 2>/dev/null || true
  done
  pkill -9 -f "openipc_swarm/coordinator" 2>/dev/null || true
  # The generated bridge configs live under build/, not in the run
  # directory, so a pattern built from $run_dir matched nothing and left one
  # parameter_bridge per agent running after every run - found two hours'
  # worth of them still publishing.
  pkill -9 -f "ros_gz_bridge/parameter_bridge" 2>/dev/null || true
  pkill -9 -f "$project_root/$sitl_bin" 2>/dev/null || true
  pkill -9 -f "gz topic -e -t /world/.*/dynamic_pose/info" 2>/dev/null || true
}
trap cleanup EXIT

gz sim -s -r -v 3 "$world_path" >"$run_dir/gazebo.log" 2>&1 &
gazebo_pid=$!
sleep 8
# How fast the simulation runs against the wall clock, every 10 s. The nodes
# time out on the wall clock and the autopilots run on the simulation's, so a
# run well under 1.0 is a different flight, not a slower one (two swarms with
# cameras side by side ran at 0.1).
(
  while true; do
    timeout 8 gz topic -e -t /stats -n 1 2>/dev/null       | sed -n 's/^real_time_factor: //p'
    sleep 10
  done
) >"$run_dir/rtf.log" 2>&1 &
demo_pids+=($!)

# One actuator bridge per model. ArduPilot publishes a Double per rotor on
# topics scoped by the model's name and the motor models read one Actuators
# array, so a single bridge would drive whichever model it was told about and
# leave the other one's rotors stopped.
for index in $(seq 1 "$agents"); do
  "$project_root/$bridge_bin" --model "openipc_cinewhoop_v$index" \
    >"$run_dir/bridge_v$index.log" 2>&1 &
  bridge_pids+=($!)
done

"$project_root/$agent_bin" udp4 -p "$dds_port" >"$run_dir/agent.log" 2>&1 &
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
  instance=$((instance_base + index - 1))
  dir="$run_dir/v$index"
  mkdir -p "$dir"
  # --wipe writes eeprom.bin into the working directory, so each autopilot
  # needs its own; see check_multi_instance_dds.sh.
  cat >"$dir/identity.parm" <<EOF
MAV_SYSID $index
DDS_USE_NS 1
DDS_UDP_PORT $dds_port
DDS_DOMAIN_ID ${ROS_DOMAIN_ID:-0}
EOF
  # What the autopilot says, above all why it will not arm: ROS only hears
  # "not armable", and an agent that never takes off fails the run with no
  # reason anywhere. SERIAL0 is sent to this port and nothing else reads it.
  python3 - "$((14550 + instance * 10))" >"$dir/statustext.log" 2>&1 <<'PY' &
import sys, time
from pymavlink import mavutil
link = mavutil.mavlink_connection(f"udpin:127.0.0.1:{sys.argv[1]}",
                                  source_system=255)
start = time.monotonic()
beat = 0.0
while True:
    # ArduPilot sends STATUSTEXT only on channels it has heard from. A udpin
    # link drops what it writes until the autopilot's first packet arrives.
    if time.monotonic() - beat > 1.0:
        link.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS,
                                mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
        beat = time.monotonic()
    msg = link.recv_match(type="STATUSTEXT", blocking=True, timeout=1)
    if msg is not None:
        print(f"{time.monotonic() - start:7.1f} {msg.text}", flush=True)
PY
  sitl_pids+=($!)
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
# One `ros2 topic list` per round, not one per topic: each call starts a
# Python CLI for about a second, and asked per topic the waits below spent
# a minute of every run on it.
for _ in $(seq 1 90); do
  missing=""
  listed="$(ros2 topic list 2>/dev/null)"
  for topic in $wanted_topics; do
    grep -Fxq "$topic" <<<"$listed" || missing="$missing $topic"
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
real_time_factor="$(timeout 10 gz topic -e -t /stats -n 1 2>/dev/null \
  | grep -A2 real_time_factor | grep -oE "[0-9]+\.[0-9]+" | tail -1)"
echo "  real time factor with $agents agents: ${real_time_factor:-unknown}"

# Each agent's sensors have to arrive in ROS under its own namespace, or the
# mapper the coordinator merges from has nothing to map.
missing_sensors=""
for _ in $(seq 1 20); do
  missing_sensors=""
  listed="$(ros2 topic list 2>/dev/null)"
  for index in $(seq 1 "$agents"); do
    for suffix in scan/front range/down_raw; do
      grep -Fxq "/v$index/$suffix" <<<"$listed" \
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
# All at once rather than one after another: each is its own CLI start-up.
echo_pids=()
echo_topics=()
for index in $(seq 1 "$agents"); do
  for suffix in scan/front range/down_raw; do
    timeout 20 ros2 topic echo --once "/v$index/$suffix" >/dev/null 2>&1 &
    echo_pids+=($!)
    echo_topics+=("/v$index/$suffix")
  done
done
for i in "${!echo_pids[@]}"; do
  if ! wait "${echo_pids[$i]}"; then
    echo "${echo_topics[$i]} exists but published nothing in 20 s." >&2
    exit 1
  fi
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

corridor_margin="${OPENIPC_CORRIDOR_MARGIN:-0.25}"
corridor_geometry="$(python3 - "$corridor_margin" "${airframe_args[@]}" <<'PY'
import sys
tip = 0.08335
for arg in sys.argv[2:]:
    if arg.startswith("rotor_tip_half_width_m:="):
        tip = float(arg.split(":=", 1)[1])
print(tip + float(sys.argv[1]), tip)
PY
)"

read -r corridor_half_width body_half_width <<< "$corridor_geometry"

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
    -p "constraint_topic:=/$ns/swarm/constraint" \
    -p "battery_topic:=/ap/$ns/battery" \
    -p "status_topic:=/ap/$ns/status" \
    -p "prearm_service:=/ap/$ns/prearm_check" \
    -p "mode_service:=/ap/$ns/mode_switch" \
    -p "arm_service:=/ap/$ns/arm_motors" \
    -p "takeoff_service:=/ap/$ns/experimental/takeoff" \
    -p enable_turning:=true -p enable_exploring:=true \
    -p auto_takeoff:=true \
    -p "approach_mode:=${OPENIPC_APPROACH:-route}" \
    -p "corridor_margin_m:=$corridor_margin" \
    -p "require_target:=true" \
    -p "steer_max_off_deg:=${OPENIPC_STEER_MAX_OFF:-20.0}" \
    -p "turn_yaw_rate_rps:=${OPENIPC_TURN_RATE:-0.4}" \
    -p "align_tolerance_deg:=8.0" \
    -p "route_align_deg:=10.0" \
    >"$run_dir/autonomy_$ns.log" 2>&1 &
  demo_pids+=($!)

  ros2 run openipc_cinewhoop_demo arbiter --ros-args \
    -p "nominal_topic:=/$ns/cmd_vel_nominal" \
    -p "constraint_topic:=/$ns/swarm/constraint" \
    -p "command_topic:=/ap/$ns/cmd_vel" \
    -p "filter_mode:=${OPENIPC_SAFETY_FILTER:-vector}" \
    -p "barrier_topic:=/$ns/swarm/barrier" \
    -p "scan_topic:=/$ns/scan/front" \
    >"$run_dir/arbiter_$ns.log" 2>&1 &
  demo_pids+=($!)
done

ros2 run openipc_swarm coordinator --ros-args \
  -p "agents:=[$(seq -s, -f 'v%g' 1 "$agents" | sed 's/[^,]*/\"&\"/g')]" \
  -p "start_offsets:=[$(echo "$start_offsets" | sed 's/ /, /g')]" \
  -p "trace_path:=$run_dir/trace.jsonl" \
  -p "allocator:=${OPENIPC_ALLOCATOR:-utility}" \
  -p "turn_yaw_rate_rps:=${OPENIPC_TURN_RATE:-0.4}" \
  -p "safety_filter:=${OPENIPC_SAFETY_FILTER:-vector}" \
  -p "reserve_passages:=${OPENIPC_RESERVE_PASSAGES:-false}" \
  -p "lookahead_m:=${OPENIPC_LOOKAHEAD:-1.4}" \
  -p "carrot_mode:=${OPENIPC_CARROT:-visible}" \
  -p "corridor_half_width_m:=$corridor_half_width" \
  -p "body_half_width_m:=$body_half_width" \
  >"$run_dir/coordinator.log" 2>&1 &
demo_pids+=($!)
sleep 8

echo "Waiting for the loop to close: maps out of the agents, targets back in"
closed=false
for _ in $(seq 1 60); do
  have_maps=true
  listed="$(ros2 topic list 2>/dev/null)"
  for index in $(seq 1 "$agents"); do
    grep -Fxq "/v$index/map" <<<"$listed" || have_maps=false
  done
  if [ "$have_maps" = true ] && grep -Fxq /swarm/map <<<"$listed"; then
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
traffic_pids=()
for topic in /swarm/map /v1/swarm/constraint; do
  timeout 25 ros2 topic echo --once "$topic" >/dev/null 2>&1 &
  traffic_pids+=($!)
done
for i in 0 1; do
  topic=$([ "$i" = 0 ] && echo /swarm/map || echo /v1/swarm/constraint)
  if ! wait "${traffic_pids[$i]}"; then
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
# R3's 130 s; OPENIPC_FLIGHT_S for a room it was not set for (a 12 x 9 m
# generated world is 2.25 times the floor). Recorded in flight_s.txt.
FLIGHT_S = float(os.environ.get("OPENIPC_FLIGHT_S", "130"))

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
# The coordinator already publishes why it did what it did. Recording both
# logs turns the flight into a diagnosis rather than a single number: the
# safety log says how much of the time the swarm was braking itself, and the
# assignment log says whether the three were ever sent to different places.
import json as _json
from std_msgs.msg import String
safety_log = []
assignment_log = []
node.create_subscription(
    String, "/swarm/safety",
    lambda m: safety_log.append(_json.loads(m.data)), 50)
node.create_subscription(
    String, "/swarm/assignment",
    lambda m: assignment_log.append(_json.loads(m.data)), 50)
for index in indices:
    node.create_subscription(
        OccupancyGrid, f"/v{index}/map",
        (lambda i: lambda m: agent_maps.update({i: m}))(index),
        QoSProfile(depth=1, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL))
heights = {}
for index in indices:
    node.create_subscription(
        PoseStamped, f"/ap/v{index}/pose/filtered",
        (lambda i: lambda m: (paths[i].append(
            (m.pose.position.x, m.pose.position.y)),
            heights.update({i: m.pose.position.z})))(index),
        qos_profile_sensor_data)

# Each agent takes itself off through its own autonomy, which is the path the
# single-drone checks fly and the only one that gets the order right: that
# node publishes nothing at all while climbing, because a velocity command
# replaces the takeoff submode. Commanding the takeoff from here instead - as
# the first version of this check did - leaves the autonomy cruising on the
# ground, and then the rangefinder sits 0.021 m up reading inf and the mapper
# maps nothing. Wait for them rather than telling them.
# What the coordinator actually sees. The MAVLink check said the three EKFs
# share an origin, but that was MAVLink; AP_DDS publishes its own pose in ENU
# and whether it carries the same offsets is a separate question - one the
# coordinator's whole separation argument rests on.
deadline = time.time() + 6
while time.time() < deadline:
    rclpy.spin_once(node, timeout_sec=0.1)
for index in indices:
    if paths[index]:
        x, y = paths[index][-1]
        print(f"  /ap/v{index}/pose/filtered reads ({x:+.2f}, {y:+.2f})")
    else:
        print(f"  /ap/v{index}/pose/filtered has published nothing")

# The 130 s run from the moment the last agent is up, as R3 means them. This
# used to wait a fixed 90 s for take-off, and the agents are up in about 10:
# every swarm figure before 2026-10-03 afternoon was taken after some 220 s
# of exploring, against a single-drone baseline given 130 s including its
# own take-off.
print("  waiting for the agents to take themselves off", flush=True)
deadline = time.time() + 90
while time.time() < deadline:
    rclpy.spin_once(node, timeout_sec=0.2)
    if len(heights) == agents and all(z > 0.3 for z in heights.values()):
        break
airborne = len(heights) == agents and all(z > 0.3 for z in heights.values())
print(f"  all {len(heights)} airborne: {airborne}")
# A run with an agent left on the ground is not a swarm run: measuring the
# two that flew gave figures that looked like the swarm's. One agent in four
# never armed in SITL on 2026-10-03.
if not airborne:
    sys.exit("Not every agent took off: "
             + ", ".join(f"v{i} {heights.get(i, float('nan')):.2f} m"
                         for i in indices))
start = time.time()

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
# How far each actually went. A swarm the safety filter holds still looks
# exactly like a working one in every other line of this summary.
travelled = {f"v{i}": round(sum(math.dist(a, b) for a, b in zip(p, p[1:])), 1)
             for i, p in paths.items()}
print(f"  metres flown per agent: {travelled}")
# The closest any two came while both were airborne, from the coordinator's
# trace. Whatever a safety filter is, this is what it is for.
closest = None
trace_file = os.path.join(run_dir, "trace.jsonl")
if os.path.isfile(trace_file):
    for line in open(trace_file):
        pos = _json.loads(line)["pos"]
        up = [p for p in pos.values() if p[2] > 0.3]
        for i in range(len(up)):
            for j in range(i):
                gap = math.dist(up[i][:2], up[j][:2])
                closest = gap if closest is None else min(closest, gap)
if closest is not None:
    print(f"  closest two agents came while airborne: {closest:.2f} m")
print(f"  the merged map calls {100 * whole:.0f} per cent of the room free")
print(f"  of the enclosure inside, {100 * inside:.0f} per cent")

with open(os.path.join(run_dir, "coverage.txt"), "w") as handle:
    handle.write(f"room {whole:.4f}\nenclosure {inside:.4f}\n")

# Why it came out that way, from the coordinator's own account of itself.
ticks = len(assignment_log)
stops = sum(1 for entry in safety_log
            for i in entry.get("interventions", []) if i["action"] == "stop")
slows = sum(1 for entry in safety_log
            for i in entry.get("interventions", []) if i["action"] == "slow")
backoffs = sum(1 for entry in safety_log if entry.get("backoff"))
print(f"  coordinator ticks logged: {ticks}; safety messages: "
      f"{len(safety_log)} ({stops} stops, {slows} slowdowns, "
      f"{backoffs} ticks with somebody backing off)")
if ticks:
    idle = sum(1 for entry in assignment_log if not entry["assigned"])
    unassigned = sum(len(entry["unassigned"]) for entry in assignment_log)
    distinct = {tuple(sorted((n, tuple(t["cell"]))
                             for n, t in entry["assigned"].items()))
                for entry in assignment_log}
    conflicts = [entry["conflict_fraction"] for entry in assignment_log]
    print(f"  ticks with nobody assigned: {idle} of {ticks}; "
          f"agent-ticks unassigned: {unassigned}")
    print(f"  distinct assignments over the flight: {len(distinct)}")
    spread_ticks = sum(1 for entry in assignment_log if entry.get("spread"))
    plan = sorted(entry["plan_ms"] for entry in assignment_log
                  if "plan_ms" in entry)
    if plan:
        print(f"  allocator {assignment_log[-1].get('allocator')}: planning "
              f"median {plan[len(plan) // 2]:.0f} ms, "
              f"p95 {plan[int(0.95 * (len(plan) - 1))]:.0f} ms")
    print(f"  ticks with somebody sent away from the others: {spread_ticks}")
    openings = sorted(entry.get("frontier_clusters", 0)
                      for entry in assignment_log)
    print(f"  openings in the merged map: median {openings[len(openings) // 2]}, "
          f"most {openings[-1]}")
    last = assignment_log[-1].get("agent_cells", {})
    print("  where the agents stood on the last tick (col, row, cell value): "
          + ", ".join(f"{n} {tuple(c)}" for n, c in sorted(last.items())))
    print(f"  conflicting cells, worst tick: {max(conflicts):.4f}")
    limited = [min(entry["limits_mps"].values()) for entry in assignment_log
               if entry["limits_mps"]]
    if limited:
        braked = sum(1 for v in limited if v < 0.5)
        print(f"  ticks where somebody was held under 0.5 m/s: "
              f"{braked} of {len(limited)}")
with open(os.path.join(run_dir, "coordinator_log.json"), "w") as handle:
    _json.dump({"safety": safety_log, "assignment": assignment_log}, handle)
# The last merged map and where everybody stood on it, so an assignment can
# be replayed offline against exactly what the coordinator saw.
with open(os.path.join(run_dir, "merged_map.json"), "w") as handle:
    _json.dump({"width": grid.info.width, "height": grid.info.height,
                "resolution": grid.info.resolution,
                "origin": [grid.info.origin.position.x,
                           grid.info.origin.position.y],
                "data": list(grid.data),
                "agent_cells": assignment_log[-1].get("agent_cells", {})
                if assignment_log else {}}, handle)

if min(flown.values()) == 0:
    sys.exit("An agent published no pose at all; it never flew.")
if whole < 0.40:
    sys.exit(f"Only {100 * whole:.0f} per cent of the room was mapped.")
print("Swarm mapping flight finished.")
MEASURE

echo "Swarm mapping check passed: $agents agents mapping, one coordinator, loop closed."
