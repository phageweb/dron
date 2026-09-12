#!/usr/bin/env bash
# Ask what a one-plane lidar makes of a table, and get the answer in numbers.
#
# Everything the vehicle knows about a room is a horizontal slice of it. The
# LD06 sweeps 360 degrees and exactly one ray high, so the map, the obstacle
# monitor and the autonomy node see whatever crosses the plane the lidar is
# flying at, and nothing else. A table is the everyday shape of what that
# misses: its top is at 0.75 m and the demo cruises at 1.00 m.
#
# The obvious check - fly over it and assert it is absent, fly through its legs
# and assert it is there - was written first and is wrong, which the measurement
# said and the reasoning had not. Flown at 1.00 m the map held seven cells of a
# table the level plane passes 0.28 m above. The plane is the airframe's, not
# the world's: it tips with every degree of pitch, and at the 0.90 m the vehicle
# came to the table, 18 degrees of nose-down reaches it - which is what braking
# looks like. Height alone decides nothing.
#
# What is true at both heights, and is what this asserts:
#
#   - the table is never a surface in the map. Its footprint is 126 cells and a
#     tenth of them or so come back occupied, whichever height it is flown at
#   - what does come back is its outline. Every occupied cell sits within a
#     couple of cells of the footprint's edge, because a slice of a table is the
#     line where the plane crosses its legs and its rim, never the top
#
# The count moved once, and for a good reason worth keeping written down. With
# the floor rejection using a flat 0.25 m bar, 0.50 m through the legs gave four
# cells and two legs; with the bar made an error bar that grows with range, the
# same flight gives fourteen and all four legs. Most of the table was being
# thrown away as ground, because a beam that meets a leg 0.2 m up meets it below
# a flat bar - which is the same defect that discarded walls, seen from the other
# side.
#
# So the map cannot say there is a table, only that something stands about
# there. Nothing downstream can fly under it, avoid its top, or know it is one
# object, and a check that passes at both heights is the honest way to say so.
#
#   scripts/check_table_height.sh          # 1.00 m, the demo's usual cruise
#   scripts/check_table_height.sh 0.50     # 0.50 m, the plane through the legs
#
# Opt-in: needs the ignored local ArduPilot, ardupilot_gazebo and DDS builds
# plus the actuator bridge from scripts/build_actuator_bridge.sh.
set -eo pipefail

# Distances are parsed as decimal-point strings; a comma locale breaks printf.
export LC_ALL=C

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

# How high to fly. The lidar sits above the airframe, so what decides what is
# seen is this plus that offset, and the analysis works the plane out rather
# than being told it.
altitude="${1:-1.0}"

sitl_bin="external/ardupilot/build/sitl/bin/arducopter"
bridge_bin="build/ap_actuator_bridge/ap_actuator_bridge"
gz_bridge_config="ros_ws/src/openipc_cinewhoop_gazebo/config/gz_bridge.yaml"
agent_setup="external/dds_ws/install/setup.bash"
agent_bin="external/dds_ws/install/lib/micro_ros_agent/micro_ros_agent"
plugin_dir="build/ardupilot_gazebo"
world_path="ros_ws/src/openipc_cinewhoop_gazebo/worlds/table_room.sdf"
sitl_params="ros_ws/src/openipc_cinewhoop_gazebo/config/ardupilot_params.parm"
dds_params="ros_ws/src/openipc_cinewhoop_gazebo/config/dds_smoke.parm"

for required_path in "$sitl_bin" "$bridge_bin" "$agent_setup" "$agent_bin" \
  "$plugin_dir/libArduPilotPlugin.so" "$world_path" "$sitl_params" "$dds_params" \
  "$gz_bridge_config"; do
  if [ ! -e "$required_path" ]; then
    echo "Table height prerequisite unavailable: $required_path" >&2
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
  --ros-args -p takeoff_altitude_m:="$altitude" -p enable_turning:=true \
  >"$test_tmpdir/demo.log" 2>&1 &
demo_pid=$!

# Every height below comes out of the world file and out of the model: what the
# table is, and where the lidar rides. A number kept in two places is the defect
# this project keeps finding, and this check is nothing but a comparison of
# heights.
python3 - "$test_tmpdir" "$project_root/$world_path" "$altitude" <<'ANALYSIS'
import math
import sys
import time
import xml.etree.ElementTree as ET

import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import OccupancyGrid
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, qos_profile_sensor_data

from openipc_cinewhoop_demo.grid_helpers import UNKNOWN, cell_centre

FLIGHT_S = 100.0
# The lidar's height above base_link, out of the same model the demo nodes read
# it from; check_model_consistency.py holds that copy to the SDF.
LIDAR_ABOVE_BASE_M = 0.050
# How near an occupied cell has to be to a leg to be that leg rather than a bit
# of wall behind it.
NEAR_M = 0.25

tmpdir, world_path, altitude = sys.argv[1], sys.argv[2], float(sys.argv[3])
root = ET.parse(world_path).getroot()


def box(model):
    """A model's (x_min, x_max, y_min, y_max, z_min, z_max), from its pose and box."""
    pose = [float(v) for v in model.find("pose").text.split()]
    size = [float(v) for v in
            model.find(".//collision/geometry/box/size").text.split()]
    return tuple(value
                 for axis in range(3)
                 for value in (pose[axis] - size[axis] / 2.0,
                               pose[axis] + size[axis] / 2.0))


parts = {}
for model in root.iter("model"):
    name = model.get("name") or ""
    if not name.startswith("table_"):
        continue
    parts[name] = box(model)
if not parts:
    sys.exit(f"No table_* models in {world_path}; this check has nothing to ask "
             "about.")

plane_m = altitude + LIDAR_ABOVE_BASE_M
print(f"  flying at {altitude:.2f} m, so the scan plane is at "
      f"{plane_m:.2f} m")
for name, part in sorted(parts.items()):
    print(f"  {name}: {part[4]:.2f} to {part[5]:.2f} m tall")

crossed = sorted(name for name, part in parts.items()
                 if part[4] <= plane_m <= part[5])
if crossed:
    print("  level, the plane crosses " + ", ".join(crossed))
else:
    print("  level, the plane crosses nothing of the table")

rclpy.init()
node = rclpy.create_node("table_height_check")
latest = {}
node.create_subscription(
    OccupancyGrid, "/openipc_cinewhoop/map", lambda msg: latest.update(map=msg),
    QoSProfile(depth=1, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL))

# Where the vehicle went, which is the other half of every number below. "The
# table is not in the map" says nothing about the table if the vehicle never got
# near it, and this check asserted exactly that before the path was recorded -
# the same mistake check_room_coverage.sh had to be corrected for twice.
# BEST_EFFORT to match AP_DDS's publisher; a RELIABLE subscription silently
# never matches it.
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
    sys.exit("No pose arrived, so there is no path to read the map against. "
             "AP_DDS publishes /ap/pose/filtered BEST_EFFORT.")

if grid is None:
    sys.exit("No map was published at all. The mapper never ran, or it never "
             "had a fresh pose to place a scan with.")

with open(f"{tmpdir}/demo.log") as handle:
    demo_log = handle.read()
if "Turning" not in demo_log:
    sys.exit("The demo never turned, so it stopped at the first thing it saw "
             "and this is a map of one wall rather than a flight round a room.")

resolution = grid.info.resolution
cols = grid.info.width
# Written before any assertion, because a run that fails is the one whose map
# somebody will want to look at.
with open(f"{tmpdir}/map.pgm", "wb") as handle:
    handle.write(f"P5\n{cols} {grid.info.height}\n255\n".encode())
    for row in range(grid.info.height - 1, -1, -1):
        handle.write(bytes(
            128 if value == UNKNOWN else 255 - int(2.55 * value)
            for value in grid.data[row * cols:(row + 1) * cols]))
print(f"  map written to {tmpdir}/map.pgm")
origin_x = grid.info.origin.position.x  # noqa: E501 - kept beside its pair
origin_y = grid.info.origin.position.y
occupied = [cell_centre(index % cols, index // cols, resolution, origin_x, origin_y)
            for index, value in enumerate(grid.data) if value >= 65]
print(f"  {sum(1 for v in grid.data if v != UNKNOWN)} cells known, "
      f"{len(occupied)} of them occupied")

# The whole table's footprint, so a return anywhere under it counts. At 1.00 m
# the assertion is that this is empty, and being generous about what counts as
# the table is what makes that assertion worth something.
footprint = (min(part[0] for part in parts.values()),
             max(part[1] for part in parts.values()),
             min(part[2] for part in parts.values()),
             max(part[3] for part in parts.values()))
on_table = [point for point in occupied
            if footprint[0] - NEAR_M <= point[0] <= footprint[1] + NEAR_M
            and footprint[2] - NEAR_M <= point[1] <= footprint[3] + NEAR_M]
print(f"  {len(on_table)} occupied cells inside the table's footprint "
      f"(x {footprint[0]:+.2f} to {footprint[1]:+.2f}, "
      f"y {footprint[2]:+.2f} to {footprint[3]:+.2f})")

# How near the vehicle actually got, which is what says whether the count above
# is about the table or about where the flight happened to go.
nearest_m = min(
    math.hypot(max(footprint[0] - x, 0.0, x - footprint[1]),
               max(footprint[2] - y, 0.0, y - footprint[3]))
    for x, y in path)
print(f"  the path is {len(path)} poses; the closest came {nearest_m:.2f} m to "
      "the table")
# One sample per degree, so the beams are range * 0.0175 apart and a leg
# 0.08 m across is a certainty inside 4.6 m and a coin toss beyond it. If the
# flight never came that close, nothing below is about the table's height.
LEG_M = min(min(part[1] - part[0], part[3] - part[2])
            for name, part in parts.items() if "leg" in name)
sure_within_m = LEG_M / math.radians(1.0)
if nearest_m > sure_within_m:
    sys.exit(
        f"The closest the vehicle came was {nearest_m:.2f} m, and a "
        f"{LEG_M:.2f} m leg is only sure of catching a beam inside "
        f"{sure_within_m:.2f} m. Whatever the map says about the table is "
        "about the flight rather than about the scan plane.")

# A map with no walls in it would pass the "table is absent" case for the wrong
# reason, so the room is asserted first, exactly as the blind pair is asserted
# first in check_leaning_scan.sh.
if len(occupied) < 100:
    sys.exit(f"Only {len(occupied)} occupied cells in the whole map, which is "
             "not a room. Nothing below is about the table.")

# The footprint in cells, which is what "not a surface" is measured against.
footprint_cells = round(((footprint[1] - footprint[0])
                         * (footprint[3] - footprint[2])) / resolution ** 2)
# Fourteen cells of the 126 is the most this map has held of the table, and it
# holds them as an outline. Thirty per cent is far above that and far below
# anything that could be called a surface, so this fails on a map that has
# started representing the table rather than on a flight that went a little
# differently.
MOST_OF_IT = 0.30
print(f"  that is {100.0 * len(on_table) / footprint_cells:.0f} per cent of the "
      f"{footprint_cells} cells the table stands on")
if len(on_table) > MOST_OF_IT * footprint_cells:
    sys.exit(
        f"{len(on_table)} of the {footprint_cells} cells under the table are "
        f"occupied, over the {100 * MOST_OF_IT:.0f} per cent this map has ever "
        "held of it. Either the map has stopped being a horizontal slice, or "
        "something is putting returns where the lidar cannot have got them - "
        "and either way what the rest of this stack believes about obstacles "
        "has changed.")

# And what there is of it is its outline. A slice of a table is the line where
# the plane crosses the rim and the legs; a cell in the middle of the top would
# mean the map is recording a surface no single plane can have seen.
EDGE_M = 0.30
middle = [point for point in on_table
          if min(abs(point[0] - footprint[0]), abs(point[0] - footprint[1]),
                 abs(point[1] - footprint[2]), abs(point[1] - footprint[3]))
          > EDGE_M]
if middle:
    sys.exit(
        f"{len(middle)} occupied cells sit more than {EDGE_M:.2f} m inside the "
        f"table's outline, the first at ({middle[0][0]:+.2f}, "
        f"{middle[0][1]:+.2f}). One plane cannot see the middle of a table top, "
        "so these came from somewhere the reasoning above does not cover.")
print(f"  all {len(on_table)} of them are on its outline, which is what a slice "
      "of a table is: the legs and the rim, never the top")

print("Table height check passed: the table reaches the map as a few cells of "
      "its outline, and never as a table.")
ANALYSIS
