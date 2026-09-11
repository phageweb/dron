#!/usr/bin/env bash
# Verify that the map the vehicle builds is the room it flew round.
#
# check_room_circuit.sh proves the vehicle turns at a wall and carries on, which
# is a flight and not a result: it kept nothing. This flies the same circuit with
# occupancy_mapper running and asks the map what the room was, then compares that
# against the walls read out of the world file.
#
# The comparison is doing more work than it looks. A map is right only if the
# whole chain is: the scan's angular convention, the yaw the returns are turned
# by, the frame the pose is in, the ray casting, and the EKF's own position -
# which nothing here has ever checked, because every previous check either asked
# about attitude or measured a distance the vehicle did not have to know where it
# was to get right. A drifting position puts the far wall in the wrong place, and
# that shows up as a room of the wrong size.
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
world_path="ros_ws/src/openipc_cinewhoop_gazebo/worlds/room_test.sdf"
sitl_params="ros_ws/src/openipc_cinewhoop_gazebo/config/ardupilot_params.parm"
dds_params="ros_ws/src/openipc_cinewhoop_gazebo/config/dds_smoke.parm"

for required_path in "$sitl_bin" "$bridge_bin" "$agent_setup" "$agent_bin" \
  "$plugin_dir/libArduPilotPlugin.so" "$world_path" "$sitl_params" "$dds_params" \
  "$gz_bridge_config"; do
  if [ ! -e "$required_path" ]; then
    echo "Room mapping prerequisite unavailable: $required_path" >&2
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

# The room's inner faces come out of the world file rather than being written
# here: a number kept in two places is the defect this project keeps finding.
python3 - "$test_tmpdir" "$project_root/$world_path" <<'ANALYSIS'
import math
import sys
import time
import xml.etree.ElementTree as ET

import rclpy
from nav_msgs.msg import OccupancyGrid
from rclpy.qos import QoSDurabilityPolicy, QoSProfile

from openipc_cinewhoop_demo.grid_helpers import (
    UNKNOWN,
    cell_centre,
    cell_of,
    coverage_fraction,
    map_extent,
    nearest_wall_distance,
)

FLIGHT_S = 110.0
# Half a cell of quantisation, plus where in the beam's 0.1 m the return landed,
# plus whatever the EKF's position has drifted. Tighter than the 0.4 m the
# circuit check keeps off a wall, so a map that merely looks room-shaped does
# not pass: 0.30 m is about three cells.
WALL_TOLERANCE_M = 0.30
# Occupied cells further than this from any wall are things the map invented.
# The room is empty, so the honest answer is none; the allowance is for the
# corners, where a beam grazing along a wall lands a cell or two off it.
STRAY_DISTANCE_M = 0.60
STRAY_FRACTION = 0.05

tmpdir, world_path = sys.argv[1], sys.argv[2]
root = ET.parse(world_path).getroot()

# Each wall is a box, so its inner face is its centre less half its thickness.
faces = {}
for model in root.iter("model"):
    name = model.get("name") or ""
    if not name.startswith("wall_"):
        continue
    pose = [float(v) for v in model.find("pose").text.split()]
    size = [float(v) for v in
            model.find(".//collision/geometry/box/size").text.split()]
    axis = 0 if "_x_" in name else 1
    faces[name] = pose[axis] - math.copysign(size[axis] / 2.0, pose[axis])
if len(faces) != 4:
    sys.exit(f"Expected four walls in {world_path}, found {sorted(faces)}.")
half_x = min(abs(v) for k, v in faces.items() if "_x_" in k)
half_y = min(abs(v) for k, v in faces.items() if "_y_" in k)
print(f"  room: inner faces at x = +-{half_x:.2f} m, y = +-{half_y:.2f} m")

rclpy.init()
node = rclpy.create_node("room_mapping_check")
latest = {}
node.create_subscription(
    OccupancyGrid, "/openipc_cinewhoop/map", lambda msg: latest.update(map=msg),
    # The mapper latches its map, so a subscriber that starts late still gets
    # one. Matching that here is not optional: a volatile subscriber against a
    # transient local publisher is a QoS mismatch and receives nothing at all.
    QoSProfile(depth=1, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL))

start = time.time()
while time.time() - start < FLIGHT_S:
    rclpy.spin_once(node, timeout_sec=0.5)

grid = latest.get("map")
node.destroy_node()
rclpy.shutdown()

if grid is None:
    sys.exit("No map was published at all. The mapper never ran, or it never "
             "had a fresh pose to place a scan with.")

with open(f"{tmpdir}/mapper.log") as handle:
    mapper_log = handle.read()
with open(f"{tmpdir}/demo.log") as handle:
    demo_log = handle.read()

if "Turning" not in demo_log:
    sys.exit("The demo never turned, so this is a map of one wall seen from a "
             "standstill and not of a room. That is check_room_circuit.sh's "
             "property failing, not this one's.")

resolution = grid.info.resolution
cols, rows = grid.info.width, grid.info.height
origin_x = grid.info.origin.position.x
origin_y = grid.info.origin.position.y
print(f"  map: {cols} by {rows} cells of {resolution:.2f} m, origin "
      f"({origin_x:+.2f}, {origin_y:+.2f})")

occupied = [(index % cols, index // cols)
            for index, value in enumerate(grid.data) if value >= 65]
known = sum(1 for value in grid.data if value != UNKNOWN)
print(f"  {known} cells known, {len(occupied)} of them occupied")
if len(occupied) < 100:
    sys.exit(f"Only {len(occupied)} occupied cells. A room 8 by 6 m has 28 m of "
             "wall in it, which at 0.10 m cells is about 280 cells of it.")

extent = map_extent(occupied, resolution, origin_x, origin_y)
min_x, max_x, min_y, max_y = extent
print(f"  the map says the room runs x {min_x:+.2f} to {max_x:+.2f} m, "
      f"y {min_y:+.2f} to {max_y:+.2f} m")
for got, want, label in ((min_x, -half_x, "x-"), (max_x, half_x, "x+"),
                         (min_y, -half_y, "y-"), (max_y, half_y, "y+")):
    if abs(got - want) > WALL_TOLERANCE_M:
        sys.exit(f"The map puts the {label} wall at {got:+.2f} m and the world "
                 f"file puts it at {want:+.2f} m, {abs(got - want):.2f} m out. "
                 "Either the returns are being placed wrongly or the position "
                 "the map is built on has drifted.")

# Every wall, not just the extent. A vehicle that flew one leg and mapped the
# two ends of the room would pass an extent check on its own.
seen = {"x-": 0, "x+": 0, "y-": 0, "y+": 0}
strays = []
for col, row in occupied:
    x, y = cell_centre(col, row, resolution, origin_x, origin_y)
    distance = nearest_wall_distance(x, y, half_x, half_y)
    if distance > STRAY_DISTANCE_M:
        strays.append((x, y, distance))
        continue
    if abs(abs(x) - half_x) <= WALL_TOLERANCE_M:
        seen["x+" if x > 0 else "x-"] += 1
    if abs(abs(y) - half_y) <= WALL_TOLERANCE_M:
        seen["y+" if y > 0 else "y-"] += 1
print("  cells on each wall: " + ", ".join(
    f"{label} {count}" for label, count in sorted(seen.items())))

# Not how many cells landed on each wall but how much of each wall is there.
# A vehicle that hovered in one spot puts plenty of cells on every wall and
# leaves the far half of each of them empty, and a count cannot tell the two
# apart. This walks each wall end to end and asks whether the map has anything
# within two cells of that point.
occupied_set = set(occupied)


def wall_coverage(fixed, low, high, along_x):
    """What fraction of one wall's length the map has something on."""
    steps = max(1, int(round((high - low) / resolution)))
    found = 0
    gaps = []
    for step in range(steps):
        value = low + (step + 0.5) * resolution
        x, y = (value, fixed) if along_x else (fixed, value)
        col, row = cell_of(x, y, resolution, origin_x, origin_y)
        # Across the wall, not along it. A wall lands a cell or two off where
        # the world file puts it, and the direction it is off in is the one
        # perpendicular to it - so a horizontal wall is searched for in row and
        # a vertical one in column. Searching along instead passes on any wall
        # that is continuous, whether or not the point being asked about is in
        # the map, which is the opposite of what this is for.
        near = any((col + (0 if along_x else dc), row + (dc if along_x else 0))
                   in occupied_set for dc in (-2, -1, 0, 1, 2))
        if near:
            found += 1
        else:
            gaps.append(round(value, 2))
    return found / steps, gaps


walls = {
    "x-": (-half_x, -half_y, half_y, False),
    "x+": (half_x, -half_y, half_y, False),
    "y-": (-half_y, -half_x, half_x, True),
    "y+": (half_y, -half_x, half_x, True),
}
print("  length of each wall mapped: " + ", ".join(
    f"{label} {100 * wall_coverage(*spec)[0]:.0f} per cent"
    for label, spec in sorted(walls.items())))
for label, spec in sorted(walls.items()):
    covered, gaps = wall_coverage(*spec)
    if covered < 0.90:
        sys.exit(f"Only {100 * covered:.0f} per cent of the {label} wall is in "
                 f"the map; nothing within two cells of {gaps[:8]}. The vehicle "
                 "either never got a look at that stretch or its returns went "
                 "somewhere else.")

# The extent above is two extreme cells and says nothing about the other four
# hundred. This is the bulk: how far a typical wall cell landed from the wall.
# Quantisation alone puts it at half a cell, so a median near 0.05 m means the
# geometry is right and the extremes are a few smeared cells rather than a bias.
offsets = sorted(nearest_wall_distance(
    *cell_centre(col, row, resolution, origin_x, origin_y), half_x, half_y)
    for col, row in occupied)
median = offsets[len(offsets) // 2]
ninetieth = offsets[int(0.9 * (len(offsets) - 1))]
print(f"  wall cells sit {median:.3f} m off the wall at the median, "
      f"{ninetieth:.3f} m at the 90th percentile, {offsets[-1]:.3f} m at worst")
if median > 0.5 * resolution + 0.05:
    sys.exit(f"Wall cells are {median:.3f} m off the wall at the median, which "
             "is past what a half-cell of quantisation explains: the map is "
             "biased rather than merely smeared at the edges.")
fraction = len(strays) / len(occupied)
print(f"  {len(strays)} occupied cells more than {STRAY_DISTANCE_M:.2f} m from "
      f"any wall ({100 * fraction:.1f} per cent)")
if fraction > STRAY_FRACTION:
    worst = sorted(strays, key=lambda s: -s[2])[:5]
    print("    furthest: " + ", ".join(
        f"({x:+.2f}, {y:+.2f}) {d:.2f} m off" for x, y, d in worst))
    sys.exit(f"{100 * fraction:.1f} per cent of the map is obstacles in an "
             "empty room. The floor being mapped, the scan being turned by the "
             "wrong yaw and a drifting position all look like this.")

coverage = coverage_fraction(grid.data, cols, resolution, origin_x, origin_y,
                             half_x, half_y)
print(f"  the map calls {100 * coverage:.0f} per cent of the room's floor free")
if coverage < 0.90:
    sys.exit(f"Only {100 * coverage:.0f} per cent of the room was mapped as "
             "free. The lidar sweeps the whole circle and the room is convex, "
             "so a vehicle that flew it at all should have seen nearly all of "
             "it - this is a mapper that is dropping most of its scans.")

skipped = [line for line in mapper_log.splitlines() if "Not mapping scans" in line]
if skipped:
    print("  the mapper skipped scans: " + "; ".join(
        line.split("] ")[-1] for line in skipped[:3]))

# Keep the map itself, not only the numbers read off it. Every question this
# check raised needed another six-minute flight to answer; one of these files
# answers most of them, and KEEP_LOGS carries it out of the temporary directory.
with open(f"{tmpdir}/map.pgm", "wb") as handle:
    handle.write(f"P5\n{cols} {rows}\n255\n".encode())
    # Row 0 of an OccupancyGrid is the bottom one and row 0 of a PGM is the top,
    # so the rows go out backwards or the room comes out mirrored.
    for row in range(rows - 1, -1, -1):
        handle.write(bytes(
            128 if value == UNKNOWN else 255 - int(2.55 * value)
            for value in grid.data[row * cols:(row + 1) * cols]))
print(f"  map written to {tmpdir}/map.pgm")

print("Room mapping check passed: the map is the room the vehicle flew round.")
ANALYSIS
