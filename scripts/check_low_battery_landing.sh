#!/usr/bin/env bash
# Verify the demo puts itself down when the battery runs out.
#
# Nothing watched the battery at all until now, and ArduPilot's own failsafe sat
# at its default, which is to do nothing. A vehicle that ran its pack flat would
# have gone on hovering until it fell out of the air, indoors, over whatever was
# underneath it.
#
# There are two layers and this flies the upper one. The demo node reads
# /ap/battery, decides at 3.5 V per cell that a controlled descent is still a
# choice, stops commanding velocity and asks ArduPilot for LAND. Underneath it,
# BATT_FS_LOW_ACT in the parameter file lands the vehicle whether or not any of
# this is running, which is the layer that matters if the DDS agent dies.
#
# The pack is not drained here, it is redefined: the node flies with
# land_below_volts_per_cell raised above what a healthy 4S LiHV reads, so a full
# battery is a flat one as far as the decision goes. What that leaves untested
# is the number, and the number is what the unit tests are for; what it tests is
# everything else - that the topic arrives, that the reading is believed, that
# the mode switch is accepted, and that the vehicle actually reaches the floor
# and disarms there.
#
# The check insists the reason logged is the voltage one. There are two ways to
# decide the battery is done, the other being that it stopped reporting, and a
# run where /ap/battery never arrived would land for that reason and look
# exactly like a pass.
#
# Opt-in: needs the ignored local ArduPilot, ardupilot_gazebo and DDS builds
# plus the actuator bridge from scripts/build_actuator_bridge.sh.
set -eo pipefail

# Distances are parsed as decimal-point strings; a comma locale breaks printf.
export LC_ALL=C

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

# How high to fly before the battery is declared flat.
altitude="${1:-1.0}"

# Above what a 4S LiHV reads at any state of charge. It is not passed to the
# node at startup - that would land it during the climb, which is correct
# behaviour and a useless test - but set on the running node once it is
# cruising, which is the pack going flat in mid-air as far as anything here can
# tell.
land_at_volts_per_cell="${2:-4.5}"

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
    echo "Low-battery landing prerequisite unavailable: $required_path" >&2
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
range_adapter_pid=""

cleanup() {
  for pid in "$range_adapter_pid" "$demo_pid" "$sitl_pid" "$agent_pid" "$gz_bridge_pid" \
    "$bridge_pid" "$gazebo_pid"; do
    if [ -n "$pid" ]; then
      kill -INT "$pid" 2>/dev/null || true
    fi
  done
  sleep 1
  for pid in "$range_adapter_pid" "$demo_pid" "$sitl_pid" "$agent_pid" "$gz_bridge_pid" \
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

# No use_sim_time, matching the autonomy node this runs beside. Both compute
# ages from their own clock at the moment a message arrives, so either clock is
# self-consistent - but two nodes in one run on different clocks would not be,
# and a node told to use sim time when /clock is not reaching it reads the same
# instant for ever, which makes every staleness guard pass.
ros2 run openipc_cinewhoop_demo simple_indoor_autonomy \
  --ros-args "${airframe_args[@]}" -p takeoff_altitude_m:="$altitude" -p enable_turning:=true \
  >"$test_tmpdir/demo.log" 2>&1 &
demo_pid=$!

# Fly first, and only then take the battery away. A vehicle told at startup that
# its pack is flat lands during the climb, which is the right thing to do and
# proves nothing about a flight.
echo "  waiting for it to get up and cruise"
airborne=false
for _ in $(seq 1 90); do
  if grep -q "cruising" "$test_tmpdir/demo.log" 2>/dev/null; then
    airborne=true
    break
  fi
  sleep 1
done
if [ "$airborne" != true ]; then
  echo "The demo never reached cruise, so there was no flight to end." >&2
  tail -n 25 "$test_tmpdir/demo.log" >&2 || true
  exit 1
fi

echo "  it is up; telling it the pack is flat"
if ! ros2 param set /simple_indoor_autonomy land_below_volts_per_cell \
    "$land_at_volts_per_cell" >"$test_tmpdir/param.log" 2>&1; then
  echo "Could not set the threshold on the running node:" >&2
  cat "$test_tmpdir/param.log" >&2
  exit 1
fi

python3 - "$test_tmpdir" "$altitude" <<'ANALYSIS'
import re
import sys
import time

import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import BatteryState

try:
    from ardupilot_msgs.msg import Status
except ImportError:
    sys.exit("ardupilot_msgs is not on the path; source "
             "external/dds_ws/install/setup.bash before running this.")

FLIGHT_S = 45.0
# What counts as being on the floor. The vehicle sits 0.035 m up on its ducts
# and the estimate is worth a few centimetres, so this is generous; the disarm
# below is the part that cannot be argued with.
ON_THE_FLOOR_M = 0.25

tmpdir, altitude = sys.argv[1], float(sys.argv[2])

rclpy.init()
node = rclpy.create_node("low_battery_landing_check")
heights = []
node.create_subscription(
    PoseStamped, "/ap/pose/filtered",
    lambda msg: heights.append(msg.pose.position.z), qos_profile_sensor_data)
volts = []
node.create_subscription(
    BatteryState, "/ap/battery", lambda msg: volts.append(msg.voltage),
    qos_profile_sensor_data)
armed = []
node.create_subscription(
    Status, "/ap/status", lambda msg: armed.append(msg.armed),
    qos_profile_sensor_data)

start = time.time()
while time.time() - start < FLIGHT_S:
    rclpy.spin_once(node, timeout_sec=0.5)
node.destroy_node()
rclpy.shutdown()

with open(f"{tmpdir}/demo.log") as handle:
    log = handle.read()

if not volts:
    sys.exit("No battery message arrived on /ap/battery at all, so the node "
             "cannot have decided anything from one. AP_DDS publishes it "
             "BEST_EFFORT; a RELIABLE subscription silently never matches.")
print(f"  the pack reported {min(volts):.2f} to {max(volts):.2f} V over "
      f"{len(volts)} messages")

if not heights:
    sys.exit("No pose arrived, so there is no altitude to read the landing "
             "against.")
peak = max(heights)
print(f"  peak altitude {peak:.2f} m, final {heights[-1]:.2f} m")

# It has to have flown before it can have landed. Without this the check would
# pass just as happily on a node that refuses to take off.
# Watching starts after the threshold is set, so this is the vehicle still at
# cruise when the pack went flat rather than the climb itself - which the shell
# above has already waited for.
if peak < 0.8 * altitude:
    sys.exit(f"The vehicle never reached {0.8 * altitude:.2f} m, so it did not "
             "fly and nothing below is about landing.")

landing = re.search(r"Landing: (.+)\.", log)
if landing is None:
    sys.exit("The demo never decided the battery was done. It flew with a "
             "threshold above anything a 4S LiHV reads, so either /ap/battery "
             "is not reaching the node or the decision is not being asked.")
print(f"  the demo said: {landing.group(1)}")
if "V across" not in landing.group(1):
    sys.exit(f"The demo landed for the wrong reason: {landing.group(1)}. That "
             "is the silence path, not the voltage path, and a run where the "
             "battery never reported would look exactly like a pass.")

if "ArduPilot has it" not in log:
    sys.exit("The demo asked for LAND and ArduPilot did not accept it. The "
             "vehicle is then in GUIDED with nothing commanding it, which is a "
             "hover until the failsafe underneath takes over.")

# Nothing may be commanded after the decision. A velocity command in a
# position-controlled mode is what replaced the takeoff once already, and the
# same trick would fight the descent.
after = log[log.index("Landing:"):]
if re.search(r"cruising|turning away", after):
    sys.exit("The demo went back to flying after deciding to land:\n"
             + "\n".join(after.splitlines()[:6]))

if heights[-1] > ON_THE_FLOOR_M:
    sys.exit(f"It ended at {heights[-1]:.2f} m, off the floor. The mode switch "
             "was accepted, so the descent is what did not happen.")

# The one assertion that cannot be argued with. Altitude is an estimate and a
# vehicle sitting on the floor with its motors turning is not a landed vehicle.
if not armed:
    sys.exit("No /ap/status arrived, so whether the motors ever stopped is "
             "unknown and the landing is unproven.")
if not any(armed):
    sys.exit("The vehicle never showed as armed, so it cannot have landed.")
if armed[-1]:
    sys.exit("It reached the floor and the motors are still turning. LAND "
             "disarms on the ground, so either it is not on the ground or the "
             "mode did not take.")
print(f"  it came down to {heights[-1]:.2f} m and disarmed there")

print("Low-battery landing check passed: it flew, saw a flat pack, said so, "
      "and put itself on the floor.")
ANALYSIS
