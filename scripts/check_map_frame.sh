#!/usr/bin/env bash
# Verify that map -> base_link is where the vehicle really is.
#
# pose_tf_broadcaster gives the TF tree its first root in the world; before it,
# robot_state_publisher knew where the lidar was relative to the airframe and
# nothing knew where the airframe was. Everything downstream of that transform -
# RViz drawing the occupancy map, anything asking what a scan means in the room -
# is exactly as right as it is.
#
# Two of the three things it asserts have never been checked here. The EKF's
# *position* against ground truth: check_attitude_estimate.sh parks the vehicle
# on a ramp and compares attitude, and a parked vehicle at the origin says
# nothing about position. And yaw: a ramp is tilted in roll and pitch and cannot
# be tilted in yaw, so the one axis the floor rejection never needed is the one
# nothing had ever compared against truth. A circuit yaws through 630 degrees,
# which is where a sign error in it stops being subtle.
#
# Opt-in: needs the ignored local ArduPilot, ardupilot_gazebo and DDS builds
# plus the actuator bridge from scripts/build_actuator_bridge.sh.
#
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
# Which airframe to fly. The variants are separate model directories holding a
# model of the same name, so worlds and the bridge config need no change; see
# ros_ws/src/openipc_cinewhoop_gazebo/launch/gazebo.launch.py.
airframe="${OPENIPC_AIRFRAME:-cinewhoop}"
if [ "$airframe" = "cinewhoop" ]; then
  models_dir="models"
  params_name="ardupilot_params.parm"
else
  models_dir="models_$airframe"
  params_name="ardupilot_params_$airframe.parm"
fi
sitl_params="ros_ws/src/openipc_cinewhoop_gazebo/config/$params_name"
dds_params="ros_ws/src/openipc_cinewhoop_gazebo/config/dds_smoke.parm"

for required_path in "$sitl_bin" "$bridge_bin" "$agent_setup" "$agent_bin" \
  "$plugin_dir/libArduPilotPlugin.so" "$world_path" "$sitl_params" "$dds_params" \
  "$gz_bridge_config"; do
  if [ ! -e "$required_path" ]; then
    echo "Map frame prerequisite unavailable: $required_path" >&2
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
export GZ_SIM_RESOURCE_PATH="$project_root/ros_ws/src/openipc_cinewhoop_gazebo/$models_dir:$project_root/ros_ws/src/openipc_cinewhoop_gazebo/worlds${GZ_SIM_RESOURCE_PATH:+:$GZ_SIM_RESOURCE_PATH}"
# sdformat resolves model:// through SDF_PATH, not through
# GZ_SIM_RESOURCE_PATH, and the dev shell points SDF_PATH at the CineLog
# models. Without this line an OPENIPC_AIRFRAME=pavo20 run loads the
# CineLog model and reports it as the Pavo20 - which is what every
# pavo20 measurement before 2026-09-20 actually did.
export SDF_PATH="$project_root/ros_ws/src/openipc_cinewhoop_gazebo/$models_dir${SDF_PATH:+:$SDF_PATH}"

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
broadcaster_pid=""
range_adapter_pid=""

cleanup() {
  for pid in "$range_adapter_pid" "$broadcaster_pid" "$demo_pid" "$sitl_pid" "$agent_pid" "$gz_bridge_pid" \
    "$bridge_pid" "$gazebo_pid"; do
    if [ -n "$pid" ]; then
      kill -INT "$pid" 2>/dev/null || true
    fi
  done
  sleep 1
  for pid in "$range_adapter_pid" "$broadcaster_pid" "$demo_pid" "$sitl_pid" "$agent_pid" "$gz_bridge_pid" \
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
  pkill -9 -f "$project_root/install/openipc_cinewhoop_demo/lib/openipc_cinewhoop_demo/pose_tf_broadcaster" 2>/dev/null || true
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
# the hardware driver would publish. Without it the demo node has no height and
# flies the whole circuit with the floor rejection off.
# The demo nodes default to the flown airframe's geometry; a variant has to be
# handed its own. check_model_consistency.py prints exactly this list, so the
# two cannot drift apart without that check failing first.
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

ros2 run openipc_cinewhoop_demo range_adapter \
  >"$test_tmpdir/range_adapter.log" 2>&1 &
range_adapter_pid=$!

ros2 run openipc_cinewhoop_demo pose_tf_broadcaster \
  >"$test_tmpdir/broadcaster.log" 2>&1 &
broadcaster_pid=$!

ros2 run openipc_cinewhoop_demo simple_indoor_autonomy \
  --ros-args "${airframe_args[@]}" -p takeoff_altitude_m:=1.0 -p enable_turning:=true \
  >"$test_tmpdir/demo.log" 2>&1 &
demo_pid=$!

# Where the vehicle starts comes out of the world file: ArduPilot's home, and so
# the origin of the map frame, is wherever it was when the EKF set home, and
# that is the spawn pose. Reading it rather than writing 0 0 0.035 here is the
# same rule the walls follow - a number kept in two places goes stale silently.
python3 - "$test_tmpdir" "$project_root/$world_path" <<'ANALYSIS'
import math
import re
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET

import rclpy
from rclpy.duration import Duration
from rclpy.executors import SingleThreadedExecutor
from tf2_ros import Buffer, TransformListener

FLIGHT_S = 95.0
# Generous on purpose. What this is built to catch is a frame that is wrong -
# axes swapped, a sign flipped, the pose read as body-relative - and over a
# circuit that reaches 3 m from the origin those are metres, not centimetres.
# The median is held to a tighter number because that is the one that describes
# the estimate rather than the worst moment of it.
MAX_ERROR_M = 0.50
MEDIAN_ERROR_M = 0.20
MAX_YAW_ERROR_DEG = 10.0

tmpdir, world_path = sys.argv[1], sys.argv[2]
root = ET.parse(world_path).getroot()
world = root.find("world")
world_name = world.get("name")

spawn = None
for include in world.iter("include"):
    uri = include.find("uri")
    if uri is not None and uri.text.strip().endswith("openipc_cinewhoop"):
        pose = include.find("pose")
        spawn = [float(v) for v in pose.text.split()] if pose is not None else [0.0] * 6
if spawn is None:
    sys.exit(f"No openipc_cinewhoop include in {world_path} to take home from.")
print(f"  home, from the world file: ({spawn[0]:+.2f}, {spawn[1]:+.2f}, "
      f"{spawn[2]:+.3f}) m")

topic = f"/world/{world_name}/dynamic_pose/info"


def truth():
    """Position and yaw from Gazebo, or None if it did not answer in time."""
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


rclpy.init()
node = rclpy.create_node("map_frame_check")
buffer = Buffer()
listener = TransformListener(buffer, node)
# Spun on its own thread, and that is not a detail. Calling spin_once between
# samples processes one message a time, /tf arrives at 30 Hz, and the loop below
# spends most of each iteration waiting on `gz topic` - so the buffer falls
# further behind every second and the lookup returns where the vehicle was, not
# where it is. Written that way first, this check reported the transform 1.17 m
# and 86 degrees out and blamed the broadcaster.
executor = SingleThreadedExecutor()
executor.add_node(node)
spinner = threading.Thread(target=executor.spin, daemon=True)
spinner.start()


def broadcast():
    """The latest map -> base_link, or None while TF has nothing to give."""
    try:
        tf = buffer.lookup_transform("map", "base_link", rclpy.time.Time(),
                                     timeout=Duration(seconds=0.2))
    except Exception:
        return None
    t, q = tf.transform.translation, tf.transform.rotation
    yaw = math.atan2(2 * (q.w * q.z + q.x * q.y),
                     1 - 2 * (q.y ** 2 + q.z ** 2))
    return t.x, t.y, t.z, yaw


samples = []
start = time.time()
while time.time() - start < FLIGHT_S:
    # Both sides read as close together as the two interfaces allow, and the TF
    # side twice - before and after - so a sample taken while the vehicle was
    # moving fast can be told from one taken at rest. At 0.5 m/s the gap between
    # them is centimetres; during a turn it is what the yaw column shows.
    before = broadcast()
    reference = truth()
    after = broadcast()
    if before is not None and after is not None and reference is not None:
        samples.append((time.time() - start, before, after, reference))
    time.sleep(0.2)


# Latest-transform lookups are not the whole story, and this is the half that
# matters to anything drawing the map. RViz asks for a transform *at the stamp
# of the thing it is drawing*, and that only works when the asker's clock and
# the transform's stamp are on the same epoch. They are not automatically: the
# simulation runs two clocks. Gazebo's /clock, and every sensor message the
# bridge carries, count seconds from when the simulator started; AP_DDS stamps
# /ap/pose/filtered - and so this transform - with UTC. A consumer on sim time
# sees a transform 56 years in the future and refuses it.
timed = 0
timed_error = None
for _ in range(20):
    when = node.get_clock().now() - Duration(seconds=0.5)
    try:
        buffer.lookup_transform("map", "base_link", when,
                                timeout=Duration(seconds=0.5))
        timed += 1
    except Exception as problem:  # noqa: BLE001 - the message is the evidence
        timed_error = problem
    time.sleep(0.05)
print(f"  timed lookups at a stamp half a second old: {timed} of 20")
if timed < 15:
    sys.exit("The transform can be looked up at 'latest' but not at a time, so "
             "nothing can place anything stamped in it - which is RViz's whole "
             f"way of working. Last refusal: {timed_error}")

executor.shutdown()
node.destroy_node()
rclpy.shutdown()

if len(samples) < 20:
    sys.exit(f"Only {len(samples)} usable samples in {FLIGHT_S:.0f} s. Either "
             "the transform was never broadcast or Gazebo stopped answering; "
             "a TF tree with no map frame in it looks exactly like this.")

with open(f"{tmpdir}/demo.log") as handle:
    demo_log = handle.read()
if "Turning" not in demo_log:
    sys.exit("The demo never turned, so the vehicle barely yawed and the yaw "
             "half of this check saw nothing. That is check_room_circuit.sh's "
             "property failing, not this one's.")

# The map frame's origin is home, which is where the vehicle spawned; Gazebo
# measures from the world origin. Subtracting the spawn pose is what makes the
# two comparable, and getting it wrong shows up as a constant offset rather
# than as drift - which is why the median is reported and not just the maximum.
errors = []
yaw_errors = []
for elapsed, before, after, reference in samples:
    expected = (reference[0] - spawn[0], reference[1] - spawn[1],
                reference[2] - spawn[2])
    # Whichever of the two TF reads is closer: the truth was sampled between
    # them, and holding the transform to the better of its own two neighbours
    # measures the frame rather than the sampling gap.
    best = min((before, after), key=lambda tf: math.dist(tf[:3], expected))
    errors.append((math.dist(best[:3], expected), elapsed, best, expected))
    yaw_errors.append(abs(
        (best[3] - reference[3] + math.pi) % (2 * math.pi) - math.pi))

distances = sorted(error for error, _, _, _ in errors)
median = distances[len(distances) // 2]
worst, when, got, wanted = max(errors)
print(f"  {len(samples)} samples over {FLIGHT_S:.0f} s")
print(f"  map -> base_link against Gazebo: {median:.3f} m at the median, "
      f"{distances[int(0.9 * (len(distances) - 1))]:.3f} m at the 90th "
      f"percentile, {worst:.3f} m at worst")
print(f"  worst at {when:.0f} s: TF ({got[0]:+.2f}, {got[1]:+.2f}, {got[2]:+.2f}) "
      f"against ({wanted[0]:+.2f}, {wanted[1]:+.2f}, {wanted[2]:+.2f})")
median_yaw = sorted(yaw_errors)[len(yaw_errors) // 2]
print(f"  yaw against Gazebo: {math.degrees(median_yaw):.2f} degrees at the "
      f"median, {math.degrees(max(yaw_errors)):.2f} at worst")

# A circuit that never left the origin would pass every tolerance above while
# proving nothing, so assert the vehicle actually went somewhere first.
reach = max(math.hypot(reference[0] - spawn[0], reference[1] - spawn[1])
            for _, _, _, reference in samples)
print(f"  the vehicle reached {reach:.2f} m from home")
if reach < 1.5:
    sys.exit(f"The vehicle never got further than {reach:.2f} m from home, so "
             "an error in the frame would have nothing to show up in.")

if median > MEDIAN_ERROR_M:
    sys.exit(f"map -> base_link is {median:.2f} m from the truth at the median, "
             f"past {MEDIAN_ERROR_M:.2f} m. A constant offset here is the home "
             "position being taken from the wrong place; one that grows with "
             "distance is the estimate drifting.")
if worst > MAX_ERROR_M:
    sys.exit(f"map -> base_link was {worst:.2f} m from the truth at {when:.0f} s, "
             f"past {MAX_ERROR_M:.2f} m.")
if math.degrees(max(yaw_errors)) > MAX_YAW_ERROR_DEG:
    sys.exit(f"The broadcast yaw is {math.degrees(max(yaw_errors)):.1f} degrees "
             f"from the truth at worst, past {MAX_YAW_ERROR_DEG:.0f}. A sign "
             "flip would look like this, and a ramp cannot be tilted in yaw so "
             "nothing else here would have caught it.")

print("Map frame check passed: map -> base_link is where the vehicle really is.")
ANALYSIS
