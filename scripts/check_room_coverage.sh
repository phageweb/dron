#!/usr/bin/env bash
# Measure how much of a room with things in it the demo actually gets a look at.
#
# check_room_mapping.sh already proves the map is the room, but it flies
# room_test.sdf, which is empty and convex - and that makes the coverage question
# meaningless there. The LD06 sweeps the whole circle and reaches 12 m, so a
# vehicle that is airborne at all has seen 97 per cent of that room whatever path
# it flew. Coverage only separates a good path from a bad one where something
# stands in the way.
#
# cluttered_room.sdf puts two things in the way, and they differ on purpose. The
# enclosure is a dogleg behind one door, with a pocket no ray through that door
# can reach, so it has to be flown into; the pillar casts a shadow that sweeps
# across the room and fills itself in as the vehicle moves. A policy that handles
# the second and not the first is the distinction worth measuring, so the
# enclosure's inside is counted separately from the room.
#
# Two earlier shapes of that world failed to occlude anything, and both failed
# the same way. An alcove 4.5 m wide and 1.45 m deep measured 94 per cent against
# the room's 96. A plain 2.8 m enclosure behind a 1.6 m door measured 97 against
# 94 - better than the room it stands in - on a flight that never went nearer
# than 0.60 m to it. A doorway is an aperture, not a pinhole: every point outside
# admits a different wedge, and over a circuit their union is very nearly
# everything. Occlusion needs a turn behind the opening, not depth behind it.
#
# What this asserts is that the measurement works - the walls and every obstacle
# reach the map, and the room is substantially covered - and that the world is
# still asking the question, which is what the two earlier shapes stopped doing
# without saying so. There is no ceiling on the enclosure figure while the
# vehicle goes inside: that number is the one a better rule for where to fly is
# supposed to raise, and a check that failed when it went up would be punishing
# the improvement it exists to track. The ceiling applies only to a flight that
# stayed out, where a high number cannot be a good path and can only be a
# geometry that has stopped hiding anything.
#
# Opt-in: needs the ignored local ArduPilot, ardupilot_gazebo and DDS builds
# plus the actuator bridge from scripts/build_actuator_bridge.sh.
set -eo pipefail

# Distances are parsed as decimal-point strings; a comma locale breaks printf.
export LC_ALL=C

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

sitl_bin="external/ardupilot/build/sitl/bin/arducopter"
bridge_bin="build/ap_actuator_bridge/ap_actuator_bridge"
gz_bridge_config="ros_ws/src/openipc_cinewhoop_gazebo/config/gz_bridge.yaml"
agent_setup="external/dds_ws/install/setup.bash"
agent_bin="external/dds_ws/install/lib/micro_ros_agent/micro_ros_agent"
plugin_dir="build/ardupilot_gazebo"
world_path="ros_ws/src/openipc_cinewhoop_gazebo/worlds/cluttered_room.sdf"
sitl_params="ros_ws/src/openipc_cinewhoop_gazebo/config/ardupilot_params.parm"
dds_params="ros_ws/src/openipc_cinewhoop_gazebo/config/dds_smoke.parm"

for required_path in "$sitl_bin" "$bridge_bin" "$agent_setup" "$agent_bin" \
  "$plugin_dir/libArduPilotPlugin.so" "$world_path" "$sitl_params" "$dds_params" \
  "$gz_bridge_config"; do
  if [ ! -e "$required_path" ]; then
    echo "Room coverage prerequisite unavailable: $required_path" >&2
    exit 2
  fi
done

if [ ! -f install/setup.bash ]; then
  echo "Workspace is not built; run colcon build first." >&2
  exit 1
fi

# micro_ros_agent has no domain option and ignores ROS_DOMAIN_ID, so leave the
# domain alone: setting one hides every /ap/ topic from ros2.
unset ROS_DOMAIN_ID || true
export GZ_PARTITION="${GZ_PARTITION:-openipc_cinewhoop}"
export GZ_IP="${GZ_IP:-127.0.0.1}"
export GZ_SIM_SYSTEM_PLUGIN_PATH="$project_root/$plugin_dir${GZ_SIM_SYSTEM_PLUGIN_PATH:+:$GZ_SIM_SYSTEM_PLUGIN_PATH}"
export GZ_SIM_RESOURCE_PATH="$project_root/ros_ws/src/openipc_cinewhoop_gazebo/models:$project_root/ros_ws/src/openipc_cinewhoop_gazebo/worlds${GZ_SIM_RESOURCE_PATH:+:$GZ_SIM_RESOURCE_PATH}"

set +u
source install/setup.bash
source "$agent_setup"
set -u

# Fail loudly rather than blaming the vehicle: a leftover demo node from an
# earlier run keeps commanding GUIDED velocity, which replaces the takeoff and
# holds the new vehicle on the ground while every service still reports success.
# DDS keeps a dead node in the graph for a few seconds, so back-to-back runs
# would trip on the previous run's corpse. A real survivor stays.
stale_node=true
for _ in $(seq 1 10); do
  if ! ros2 node list 2>/dev/null | grep -Fxq /simple_indoor_autonomy; then
    stale_node=false
    break
  fi
  sleep 1
done
if [ "$stale_node" = true ]; then
  echo "A simple_indoor_autonomy node is already running; it would command" >&2
  echo "/ap/cmd_vel into this run's vehicle and prevent takeoff. Stop it first." >&2
  exit 1
fi

test_tmpdir="$(mktemp -d)"
gazebo_pid=""
bridge_pid=""
gz_bridge_pid=""
agent_pid=""
sitl_pid=""
demo_pid=""
mapper_pid=""
range_adapter_pid=""

cleanup() {
  for pid in "$range_adapter_pid" "$mapper_pid" "$demo_pid" "$sitl_pid" "$agent_pid" "$gz_bridge_pid" \
    "$bridge_pid" "$gazebo_pid"; do
    if [ -n "$pid" ]; then
      kill -INT "$pid" 2>/dev/null || true
    fi
  done
  sleep 1
  for pid in "$range_adapter_pid" "$mapper_pid" "$demo_pid" "$sitl_pid" "$agent_pid" "$gz_bridge_pid" \
    "$bridge_pid" "$gazebo_pid"; do
    if [ -n "$pid" ]; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  done
  pkill -9 -f "$project_root/$sitl_bin" 2>/dev/null || true
  # `ros2 run` is a wrapper whose child does not die with it, and an orphaned
  # demo node keeps publishing /ap/cmd_vel. A GUIDED velocity command replaces
  # the takeoff submode, so one survivor silently pins the next run's vehicle to
  # the floor at zero throttle while every service still reports success.
  pkill -9 -f "$project_root/install/openipc_cinewhoop_demo/lib/openipc_cinewhoop_demo/simple_indoor_autonomy" 2>/dev/null || true
  pkill -9 -f "$project_root/install/openipc_cinewhoop_demo/lib/openipc_cinewhoop_demo/occupancy_mapper" 2>/dev/null || true
  pkill -9 -f "$project_root/install/openipc_cinewhoop_demo/lib/openipc_cinewhoop_demo/range_adapter" 2>/dev/null || true
  pkill -9 -f "parameter_bridge --ros-args -p config_file:=$test_tmpdir" 2>/dev/null || true
  if [ -n "${KEEP_LOGS:-}" ]; then
    cp -r "$test_tmpdir" "$KEEP_LOGS" 2>/dev/null || true
    echo "logs kept in $KEEP_LOGS" >&2
  fi
  rm -rf "$test_tmpdir"
}
trap cleanup EXIT

gz sim -s -r -v 3 "$world_path" >"$test_tmpdir/gazebo.log" 2>&1 &
gazebo_pid=$!
sleep 6

"$project_root/$bridge_bin" >"$test_tmpdir/bridge.log" 2>&1 &
bridge_pid=$!

# Without this the demo node never sees a LaserScan and stays on the ground.
# The config is a template: the sensors let Gazebo scope their topics under the
# world's own name, so the world goes in here rather than into the model.
world_name="$(sed -n 's/.*<world[[:space:]]\+name="\([^"]*\)".*/\1/p' \
  "$project_root/$world_path" | head -1)"
if [ -z "$world_name" ]; then
  echo "No <world name=...> in $world_path." >&2
  exit 1
fi
sed "s/@world@/$world_name/g" "$project_root/$gz_bridge_config" \
  >"$test_tmpdir/gz_bridge.yaml"
ros2 run ros_gz_bridge parameter_bridge --ros-args \
  -p "config_file:=$test_tmpdir/gz_bridge.yaml" \
  >"$test_tmpdir/gz_bridge.log" 2>&1 &
gz_bridge_pid=$!

"$project_root/$agent_bin" udp4 -p 20199 >"$test_tmpdir/agent.log" 2>&1 &
agent_pid=$!
sleep 2

(
  cd external/ardupilot/ArduCopter
  exec "$project_root/$sitl_bin" --wipe --model JSON --speedup 1 --slave 0 -I0 \
    --sim-address=127.0.0.1 --sim-port-out=9002 \
    --serial0=udpclient:127.0.0.1:14550 \
    --defaults "$project_root/$sitl_params,$project_root/$dds_params"
) >"$test_tmpdir/sitl.log" 2>&1 &
sitl_pid=$!

for _ in $(seq 1 60); do
  if ros2 service list 2>/dev/null | grep -Fxq /ap/experimental/takeoff; then
    break
  fi
  sleep 1
done
if ! ros2 service list 2>/dev/null | grep -Fxq /ap/experimental/takeoff; then
  echo "AP_DDS services did not appear." >&2
  tail -40 "$test_tmpdir/agent.log" >&2 || true
  exit 1
fi

# The rangefinder's logical topic, which the bridge does not publish: Gazebo can
# only produce a LaserScan and range_adapter turns it into the sensor_msgs/Range
# the hardware driver would publish. Without it nothing here has a height, the
# floor rejection never switches on, and the mapper drops every scan.
ros2 run openipc_cinewhoop_demo range_adapter \
  >"$test_tmpdir/range_adapter.log" 2>&1 &
range_adapter_pid=$!

# No use_sim_time, matching the autonomy node this runs beside. Both compute
# ages from their own clock at the moment a message arrives, so either clock is
# self-consistent - but two nodes in one run on different clocks would not be,
# and a node told to use sim time when /clock is not reaching it reads the same
# instant for ever, which makes every staleness guard pass.
ros2 run openipc_cinewhoop_demo occupancy_mapper \
  >"$test_tmpdir/mapper.log" 2>&1 &
mapper_pid=$!

ros2 run openipc_cinewhoop_demo simple_indoor_autonomy \
  --ros-args -p takeoff_altitude_m:=1.0 -p enable_turning:=true \
  >"$test_tmpdir/demo.log" 2>&1 &
demo_pid=$!


# Every rectangle below comes out of the world file: the walls, the partition
# that make the enclosure, and the pillar. A number kept in two places is the
# defect this project keeps finding, and this check is nothing but numbers
# about geometry.
python3 - "$test_tmpdir" "$project_root/$world_path" <<'ANALYSIS'
import math
import sys
import time
import xml.etree.ElementTree as ET

import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import OccupancyGrid
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, qos_profile_sensor_data

from openipc_cinewhoop_demo.grid_helpers import (
    UNKNOWN,
    cell_centre,
    cell_of,
    coverage_fraction,
    in_rectangle,
)

FLIGHT_S = 130.0
# A room with obstacles in it takes longer to get round than an empty one, and
# the point of the flight is to give the vehicle a fair chance at the enclosure
# before its coverage is written down.
WALL_TOLERANCE_M = 0.30
# Below this the run is broken rather than merely incomplete: the vehicle never
# flew, or the mapper dropped its scans. Well under what a single hover from the
# middle of the room already achieves, so it cannot pass by accident either.
MIN_ROOM_COVERAGE = 0.40

tmpdir, world_path = sys.argv[1], sys.argv[2]
root = ET.parse(world_path).getroot()


def footprint(model):
    """A model's (x_min, x_max, y_min, y_max) on the floor, from its box."""
    pose = [float(v) for v in model.find("pose").text.split()]
    size = [float(v) for v in
            model.find(".//collision/geometry/box/size").text.split()]
    return (pose[0] - size[0] / 2.0, pose[0] + size[0] / 2.0,
            pose[1] - size[1] / 2.0, pose[1] + size[1] / 2.0)


boxes = {}
for model in root.iter("model"):
    name = model.get("name") or ""
    if name == "floor" or model.find(".//collision/geometry/box/size") is None:
        continue
    boxes[name] = footprint(model)

walls = {name: box for name, box in boxes.items() if name.startswith("wall_")}
obstacles = {name: box for name, box in boxes.items()
             if not name.startswith("wall_")}
if len(walls) != 4 or not obstacles:
    sys.exit(f"Expected four walls and at least one obstacle in {world_path}; "
             f"found walls {sorted(walls)} and obstacles {sorted(obstacles)}.")

# The room's inner faces: the wall boxes' edges nearest the origin.
half_x = min(min(abs(box[0]), abs(box[1]))
             for name, box in walls.items() if "_x_" in name)
half_y = min(min(abs(box[2]), abs(box[3]))
             for name, box in walls.items() if "_y_" in name)
room = (-half_x, half_x, -half_y, half_y)
print(f"  room: inner faces at x = +-{half_x:.2f} m, y = +-{half_y:.2f} m")

# What the enclosure encloses, derived from its own walls rather than written
# down again: the bounding box of everything named inner_*, pulled in by their
# thickness to get the inside rather than the outside. Moving a wall in the
# world file moves the region this reports on.
inner = {name: box for name, box in boxes.items() if name.startswith("inner_")}
if len(inner) < 3:
    sys.exit(f"Expected the enclosure's walls as inner_* in {world_path}; "
             f"found {sorted(inner)}.")
thickness = min(min(box[1] - box[0], box[3] - box[2]) for box in inner.values())
outside = (min(box[0] for box in inner.values()),
           max(box[1] for box in inner.values()),
           min(box[2] for box in inner.values()),
           max(box[3] for box in inner.values()))
enclosure = (outside[0] + thickness, outside[1] - thickness,
             outside[2] + thickness, outside[3] - thickness)
print(f"  enclosure inside: x {enclosure[0]:+.2f} to {enclosure[1]:+.2f} m, "
      f"y {enclosure[2]:+.2f} to {enclosure[3]:+.2f} m "
      f"({(enclosure[1] - enclosure[0]) * (enclosure[3] - enclosure[2]):.1f} m2 "
      f"of {4 * half_x * half_y:.0f} m2)")
if enclosure[1] <= enclosure[0] or enclosure[3] <= enclosure[2]:
    sys.exit("The inner_* walls do not enclose anything.")

rclpy.init()
node = rclpy.create_node("room_coverage_check")
latest = {}
node.create_subscription(
    OccupancyGrid, "/openipc_cinewhoop/map", lambda msg: latest.update(map=msg),
    QoSProfile(depth=1, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL))

# Where the vehicle went, which is the other half of every number below. A
# coverage figure on its own cannot say whether the map is good because the path
# was good or because the room was easy, and those are the two things this world
# exists to tell apart. BEST_EFFORT to match AP_DDS's publisher; a RELIABLE
# subscription silently never matches it.
path = []
node.create_subscription(
    PoseStamped, "/ap/pose/filtered",
    lambda msg: path.append((msg.pose.position.x, msg.pose.position.y)),
    qos_profile_sensor_data)

start = time.time()
while time.time() - start < FLIGHT_S:
    rclpy.spin_once(node, timeout_sec=0.5)

grid = latest.get("map")
node.destroy_node()
rclpy.shutdown()

if not path:
    sys.exit("No pose arrived, so there is no path to read the coverage "
             "against. AP_DDS is publishing /ap/pose/filtered BEST_EFFORT.")

if grid is None:
    sys.exit("No map was published at all. The mapper never ran, or it never "
             "had a fresh pose to place a scan with.")

with open(f"{tmpdir}/demo.log") as handle:
    demo_log = handle.read()
if "Turning" not in demo_log:
    sys.exit("The demo never turned, so it stopped at the first thing it saw "
             "and this is a map of one wall. That is check_room_circuit.sh's "
             "property failing, not this one's.")

resolution = grid.info.resolution
cols, rows = grid.info.width, grid.info.height
origin_x = grid.info.origin.position.x
origin_y = grid.info.origin.position.y
occupied = {(index % cols, index // cols)
            for index, value in enumerate(grid.data) if value >= 65}
print(f"  {sum(1 for v in grid.data if v != UNKNOWN)} cells known, "
      f"{len(occupied)} of them occupied")

# Every obstacle has to reach the map. Coverage of a room whose furniture the
# mapper never saw is a number about the wrong room - and an obstacle missing
# from the map is also an obstacle casting no shadow, so the enclosure figure
# would look respectable for the worst possible reason.
for name, box in sorted(obstacles.items()):
    near = 0
    for col, row in occupied:
        x, y = cell_centre(col, row, resolution, origin_x, origin_y)
        if (box[0] - WALL_TOLERANCE_M <= x <= box[1] + WALL_TOLERANCE_M
                and box[2] - WALL_TOLERANCE_M <= y <= box[3] + WALL_TOLERANCE_M):
            near += 1
    print(f"  {name}: {near} occupied cells on it")
    if near < 5:
        sys.exit(f"{name} is not in the map, so nothing it should be hiding is "
                 "actually hidden and the coverage below would mean nothing.")

# The outer walls, but not to the standard check_room_mapping.sh holds them to.
# It demands every wall along 100 per cent of its length and gets it, because
# room_test.sdf is empty; here the enclosure stands half a metre off the x- wall
# and hides the stretch behind it from every place the vehicle can fit. A wall
# partly missing is this world working, not the mapper failing - which is why
# the empty room keeps the strict version and this one only asks that each wall
# is substantially there, enough to catch a mapper that has stopped working.
def wall_coverage(fixed, low, high, along_x):
    steps = max(1, int(round((high - low) / resolution)))
    found = 0
    for step in range(steps):
        value = low + (step + 0.5) * resolution
        x, y = (value, fixed) if along_x else (fixed, value)
        col, row = cell_of(x, y, resolution, origin_x, origin_y)
        if any((col + (0 if along_x else dc), row + (dc if along_x else 0))
               in occupied for dc in (-2, -1, 0, 1, 2)):
            found += 1
    return found / steps


sides = {
    "x-": (-half_x, -half_y, half_y, False),
    "x+": (half_x, -half_y, half_y, False),
    "y-": (-half_y, -half_x, half_x, True),
    "y+": (half_y, -half_x, half_x, True),
}
print("  length of each outer wall mapped: " + ", ".join(
    f"{label} {100 * wall_coverage(*spec):.0f} per cent"
    for label, spec in sorted(sides.items())))
MIN_WALL_COVERAGE = 0.60
for label, spec in sorted(sides.items()):
    covered = wall_coverage(*spec)
    if covered < MIN_WALL_COVERAGE:
        sys.exit(f"Only {100 * covered:.0f} per cent of the {label} wall is in "
                 f"the map, under {100 * MIN_WALL_COVERAGE:.0f}. Some of it is "
                 "legitimately behind the enclosure, but not that much - "
                 "check_room_mapping.sh reaches 100 per cent on every wall of "
                 "an empty room, so this is the mapper and not the geometry.")

# The path, before the coverage it explains. Whether the vehicle went through
# the door is the single fact that decides how the enclosure's figure should be
# read: a high number with the vehicle never inside means the door is letting
# the lidar do the work, and the world is not asking the question it was built
# to ask.
inside_path = [point for point in path if in_rectangle(point[0], point[1],
                                                       enclosure)]
print(f"  the path is {len(path)} poses, {len(inside_path)} of them inside the "
      f"enclosure ({100.0 * len(inside_path) / len(path):.0f} per cent)")
if inside_path:
    print(f"  it went in: x {min(p[0] for p in inside_path):+.2f} to "
          f"{max(p[0] for p in inside_path):+.2f} m, "
          f"y {min(p[1] for p in inside_path):+.2f} to "
          f"{max(p[1] for p in inside_path):+.2f} m")
else:
    nearest = min(
        math.hypot(max(enclosure[0] - x, 0.0, x - enclosure[1]),
                   max(enclosure[2] - y, 0.0, y - enclosure[3]))
        for x, y in path)
    print(f"  it never went in; closest approach {nearest:.2f} m")

# The numbers this was flown for. Obstacle footprints come out of both halves of
# every fraction: a cell inside a pillar is not floor the vehicle failed to see,
# and counting it as unseen makes a map look worse the more furniture it found.
excluded = list(obstacles.values())
whole = coverage_fraction(grid.data, cols, resolution, origin_x, origin_y,
                          room, excluded)
inside = coverage_fraction(grid.data, cols, resolution, origin_x, origin_y,
                           enclosure, excluded)
print(f"  the map calls {100 * whole:.0f} per cent of the room's floor free")
print(f"  of the enclosure inside, {100 * inside:.0f} per cent")

if whole < MIN_ROOM_COVERAGE:
    sys.exit(f"Only {100 * whole:.0f} per cent of the room was mapped, under "
             f"the {100 * MIN_ROOM_COVERAGE:.0f} per cent a single hover in the "
             "middle already gets. The vehicle did not fly, or the mapper "
             "dropped its scans.")

# No ceiling on either figure while the vehicle goes in, and none on the gap
# between them. The enclosure number is what a better rule for where to fly is
# meant to raise, and a check that failed when it rose would be punishing the
# improvement it tracks. It is printed loudly instead, with the gap named so it
# cannot be read past.
gap = whole - inside
print(f"  the enclosure is {abs(100 * gap):.0f} points {'behind' if gap > 0 else 'ahead of'} "
      "the room as a whole")

# The one ceiling, and it is on the world rather than on the flight. A vehicle
# that stayed outside cannot have earned the inside of a dogleg: the pocket past
# the baffle is dark from every point of the doorway, so from out in the room
# there is about a sixth of the enclosure no ray can reach. Reading much above
# that without going in means the geometry has stopped hiding anything, which is
# how both earlier shapes of this world failed - quietly, while the check passed.
# Measured on both geometries rather than guessed. With the baffle, a circuit
# that stayed outside reads 80 per cent; with it taken out, the same circuit
# reads 94, and the two earlier shapes read 94 and 97. Run to run the figure
# moves about three points, so the threshold sits between the bands rather than
# just above one of them: eight points clear of the occluding world and six
# below the world that has stopped.
MAX_COVERAGE_FROM_OUTSIDE = 0.88
if not inside_path and inside > MAX_COVERAGE_FROM_OUTSIDE:
    sys.exit(
        f"The map calls {100 * inside:.0f} per cent of the enclosure free on a "
        f"flight that never entered it, over the "
        f"{100 * MAX_COVERAGE_FROM_OUTSIDE:.0f} per cent a doorway should let "
        "through. The vehicle has not got better; the world has stopped "
        "occluding. Check that inner_baffle is still across the enclosure and "
        "still reaches the wall the door is flush with - a gap at either end "
        "lets the whole pocket be seen from outside, and every number above "
        "stays plausible while it does.")

with open(f"{tmpdir}/map.pgm", "wb") as handle:
    handle.write(f"P5\n{cols} {rows}\n255\n".encode())
    for row in range(rows - 1, -1, -1):
        handle.write(bytes(
            128 if value == UNKNOWN else 255 - int(2.55 * value)
            for value in grid.data[row * cols:(row + 1) * cols]))
print(f"  map written to {tmpdir}/map.pgm")

print("Room coverage check passed: the clutter is mapped and the room is "
      "measured, the enclosure separately.")
ANALYSIS
