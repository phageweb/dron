#!/usr/bin/env bash
# Verify that the demo flies a circuit rather than stopping dead at a wall.
#
# check_forward_flight.sh proves the vehicle stops for what is ahead of it, and
# that is the property worth having. This proves the other half of a demo worth
# watching: with enable_turning it yaws towards whichever side has more room and
# carries on, so a closed room is something it flies around instead of into.
#
# room_test.sdf is that closed room, 8 m by 6 m. indoor_test.sdf is not a room
# at all - a floor and two panels - so a turning vehicle simply leaves it.
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
    echo "Forward flight prerequisite unavailable: $required_path" >&2
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
# Ask ROS rather than matching process command lines, which also match this
# script's own shell.
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
range_adapter_pid=""

cleanup() {
  for pid in "$range_adapter_pid" "$demo_pid" "$sitl_pid" "$agent_pid" "$gz_bridge_pid" "$bridge_pid" "$gazebo_pid"; do
    if [ -n "$pid" ]; then
      kill -INT "$pid" 2>/dev/null || true
    fi
  done
  sleep 1
  for pid in "$range_adapter_pid" "$demo_pid" "$sitl_pid" "$agent_pid" "$gz_bridge_pid" "$bridge_pid" "$gazebo_pid"; do
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
# the hardware driver would publish. Without it the demo node has no height, so
# the floor rejection never switches on and the whole flight runs without the
# compensation the leaning worlds prove it needs - silently, because a rejection
# that was never on cannot be seen switching off.
ros2 run openipc_cinewhoop_demo range_adapter \
  >"$test_tmpdir/range_adapter.log" 2>&1 &
range_adapter_pid=$!

ros2 run openipc_cinewhoop_demo simple_indoor_autonomy \
  --ros-args -p takeoff_altitude_m:=1.0 -p enable_turning:=true \
  >"$test_tmpdir/demo.log" 2>&1 &
demo_pid=$!

# The room's inner faces come out of the world file rather than being written
# here: a number kept in two places is the defect this project keeps finding.
python3 - "$test_tmpdir" "$project_root/$world_path" <<'ANALYSIS'
import math
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

tmpdir, world_path = sys.argv[1], sys.argv[2]
root = ET.parse(world_path).getroot()
world_name = root.find("world").get("name")
topic = f"/world/{world_name}/dynamic_pose/info"

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


def pose():
    """Position and yaw from Gazebo's ground truth, or None if it did not answer."""
    try:
        out = subprocess.run(["gz", "topic", "-e", "-t", topic, "-n", "1"],
                             capture_output=True, text=True, timeout=12).stdout
    except subprocess.TimeoutExpired:
        return None
    for block in re.split(r"\npose \{", out):
        if '"openipc_cinewhoop"' not in block:
            continue
        position = re.search(r"position \{(.*?)\}", block, re.S)
        orientation = re.search(r"orientation \{(.*?)\}", block, re.S)
        if position is None or orientation is None:
            return None
        p = {k: float(v) for k, v in
             re.findall(r"([xyz]):\s*([-\d.e+]+)", position.group(1))}
        # Protobuf omits fields at their default, so w alone is printed for a
        # vehicle that has not yawed at all.
        q = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 0.0}
        q.update({k: float(v) for k, v in
                  re.findall(r"([xyzw]):\s*([-\d.e+]+)", orientation.group(1))})
        yaw = math.atan2(2 * (q["w"] * q["z"] + q["x"] * q["y"]),
                         1 - 2 * (q["y"] ** 2 + q["z"] ** 2))
        return p.get("x", 0.0), p.get("y", 0.0), p.get("z", 0.0), yaw
    return None


start = time.time()
track = []
while time.time() - start < 110:
    sample = pose()
    if sample is not None:
        track.append((time.time() - start, *sample))
    time.sleep(0.5)

if len(track) < 20:
    sys.exit(f"Only {len(track)} pose samples; the simulation did not run.")

print("  track (t, x, y, yaw): " + "  ".join(
    f"{t:.0f}s {x:+.2f} {y:+.2f} {math.degrees(yaw):+.0f}deg"
    for t, x, y, _, yaw in track[::12]))

with open(f"{tmpdir}/demo.log") as handle:
    log = handle.read()

peak_alt = max(z for _, _, _, z, _ in track)
if peak_alt < 0.6:
    sys.exit(f"Never climbed: peak altitude {peak_alt:.2f} m.")

# Yaw is unwrapped before anything is asked of it: a vehicle that turns past
# +-180 degrees would otherwise look like one that had turned back.
total, previous, unwrapped = 0.0, track[0][4], []
for _, _, _, _, yaw in track:
    total += (yaw - previous + math.pi) % (2 * math.pi) - math.pi
    unwrapped.append(total)
    previous = yaw
turned_deg = math.degrees(max(abs(v) for v in unwrapped))
print(f"  turned {turned_deg:.0f} degrees in all")

turning = re.search(r"Turning (left|right): (.+)", log)
if turning is None:
    sys.exit("The demo never turned. It stopped for the wall and stayed there, "
             "which is check_forward_flight.sh's property and not this one.")
print(f"  demo said: Turning {turning.group(1)}: {turning.group(2)}")
finished = re.search(r"Turn finished: .+", log)
if finished is None:
    sys.exit("The demo started turning and never finished: it is still looking "
             "for a way out, or rotating on a scan it cannot use.")
print(f"  demo said: {finished.group(0)}")

if turned_deg < 45.0:
    sys.exit(f"The demo logged a turn but the vehicle only yawed "
             f"{turned_deg:.0f} degrees, so the yaw rate is not reaching it.")

# The first leg runs out along x and the second has to go somewhere else.
# Comparing the furthest point against the last one separates a vehicle that
# flew on from one that turned on the spot and sat there: the second has a turn
# in its log and no circuit in the world.
furthest = max(track, key=lambda sample: sample[1])
final = track[-1]
leg = math.hypot(final[1] - furthest[1], final[2] - furthest[2])
heading = math.degrees(math.atan2(final[2] - furthest[2], final[1] - furthest[1]))
print(f"  first leg reached x = {furthest[1]:.2f} m, then travelled "
      f"{leg:.2f} m on a heading of {heading:+.0f} degrees")
if leg < 0.5:
    sys.exit(f"The vehicle turned and then went nowhere: {leg:.2f} m after the "
             "turn. A turn that is not followed by flight is not a circuit.")
if abs(heading) < 45.0:
    sys.exit(f"After turning, the vehicle carried on at {heading:+.0f} degrees, "
             "which is still down the first leg.")

# No wall may be reached. That is the property the turn exists to preserve, so
# it is asserted over the whole run rather than only at the end.
clearance = min(min(half_x - abs(x), half_y - abs(y))
                for _, x, y, _, _ in track)
print(f"  closest approach to any wall: {clearance:.2f} m")
if clearance < 0.4:
    sys.exit(f"The vehicle came within {clearance:.2f} m of a wall, inside the "
             "clearance the demo is supposed to keep.")

print("Room circuit check passed: the demo turned away from the wall and flew on.")
ANALYSIS
