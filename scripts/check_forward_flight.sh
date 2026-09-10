#!/usr/bin/env bash
# Verify the indoor autonomy demo: take off, creep forward, stop for the wall.
#
# This is phase 11 of the iteration plan end to end. The vehicle must arm and
# climb on its own through ArduPilot's ROS 2 services, move towards the world's
# front obstacle at roughly the configured speed, and hold station before it
# reaches the stop distance rather than flying into the wall.
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
world_path="ros_ws/src/openipc_cinewhoop_gazebo/worlds/indoor_test.sdf"
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

test_tmpdir="$(mktemp -d)"
gazebo_pid=""
bridge_pid=""
gz_bridge_pid=""
agent_pid=""
sitl_pid=""
demo_pid=""

cleanup() {
  for pid in "$demo_pid" "$sitl_pid" "$agent_pid" "$gz_bridge_pid" "$bridge_pid" "$gazebo_pid"; do
    if [ -n "$pid" ]; then
      kill -INT "$pid" 2>/dev/null || true
    fi
  done
  sleep 1
  for pid in "$demo_pid" "$sitl_pid" "$agent_pid" "$gz_bridge_pid" "$bridge_pid" "$gazebo_pid"; do
    if [ -n "$pid" ]; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  done
  pkill -9 -f "$project_root/$sitl_bin" 2>/dev/null || true
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
ros2 run ros_gz_bridge parameter_bridge --ros-args \
  -p "config_file:=$project_root/$gz_bridge_config" \
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

ros2 run openipc_cinewhoop_demo simple_indoor_autonomy \
  --ros-args -p takeoff_altitude_m:=1.0 >"$test_tmpdir/demo.log" 2>&1 &
demo_pid=$!

# The world places the front obstacle face at x = 1.74 and the vehicle starts
# at the origin, so a healthy run travels forward and then holds short of it.
python3 - "$test_tmpdir" <<'PY'
import re
import subprocess
import sys
import time

tmpdir = sys.argv[1]
topic = "/world/indoor_test/dynamic_pose/info"


def motor_speed():
    """Peak commanded rotor speed, which shows whether ArduPilot is driving."""
    try:
        out = subprocess.run(
            ["gz", "topic", "-e", "-t", "/openipc_cinewhoop/command/motor_speed",
             "-n", "1"], capture_output=True, text=True, timeout=8).stdout
    except subprocess.TimeoutExpired:
        return None
    vals = [float(v) for v in re.findall(r"velocity:\s*([-\d.e+]+)", out)]
    return max(vals) if vals else None


def pose():
    try:
        out = subprocess.run(["gz", "topic", "-e", "-t", topic, "-n", "1"],
                             capture_output=True, text=True, timeout=12).stdout
    except subprocess.TimeoutExpired:
        return None
    for block in re.split(r"\npose \{", out):
        if '"openipc_cinewhoop"' in block:
            got = re.search(r"position \{(.*?)\}", block, re.S)
            if got:
                xyz = {k: float(v)
                       for k, v in re.findall(r"([xyz]):\s*([-\d.e+]+)", got.group(1))}
                return xyz.get("x", 0.0), xyz.get("z", 0.0)
    return None


start = time.time()
samples = []
speeds = []
while time.time() - start < 75:
    p = pose()
    if p is not None:
        samples.append(p)
    if len(samples) % 5 == 0:
        v = motor_speed()
        if v is not None:
            speeds.append(v)
    time.sleep(1)

if speeds:
    print(f"  commanded rotor speed: max {max(speeds):.0f} rad/s, "
          f"last {speeds[-1]:.0f}")
else:
    print("  commanded rotor speed: no samples")

if len(samples) < 10:
    sys.exit(f"Only {len(samples)} pose samples; the simulation did not run.")

peak_alt = max(z for _, z in samples)
peak_x = max(x for x, _ in samples)
final_x = samples[-1][0]
print(f"  peak altitude {peak_alt:.2f} m   furthest x {peak_x:.2f} m   final x {final_x:.2f} m")

with open(f"{tmpdir}/demo.log") as handle:
    log = handle.read()
print("  demo states: " + ", ".join(
    sorted(set(re.findall(r"\] \[simple_indoor_autonomy\]: (\w[\w ]+)", log)))))

if peak_alt < 0.6:
    sys.exit(f"Never climbed: peak altitude {peak_alt:.2f} m.")
if peak_x < 0.25:
    sys.exit(f"Never moved forward: furthest x {peak_x:.2f} m.")
# The obstacle face is at x = 1.74 and the lidar sits 0.073 m ahead of the
# origin, so stopping 0.8 m short means the body should hold well below 1.0 m.
if peak_x > 1.10:
    sys.exit(f"Flew too close to the wall: reached x {peak_x:.2f} m.")
print("Forward flight check passed: took off, advanced and held short of the wall.")
PY
