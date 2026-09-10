#!/usr/bin/env bash
# Verify a real AP_DDS takeoff against the unmodified upstream Iris reference.
# This is opt-in: it needs local ignored ArduPilot, Agent and Gazebo builds.
set -eo pipefail

# Altitudes are decimal-point strings; a comma locale makes printf reject them.
export LC_ALL=C

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ardupilot_dir="$project_root/external/ardupilot"
agent_setup="$project_root/external/dds_ws/install/setup.bash"
agent_bin="$project_root/external/dds_ws/install/lib/micro_ros_agent/micro_ros_agent"
sitl_bin="$ardupilot_dir/build/sitl/bin/arducopter"
plugin_dir="$project_root/build/ardupilot_gazebo"
world_path="$project_root/external/ardupilot_gazebo/worlds/iris_runway.sdf"
copter_params="$ardupilot_dir/Tools/autotest/default_params/copter.parm"
iris_params="$project_root/external/ardupilot_gazebo/config/gazebo-iris-gimbal.parm"
dds_params="$project_root/ros_ws/src/openipc_cinewhoop_gazebo/config/dds_smoke.parm"

for required_path in "$agent_setup" "$agent_bin" "$sitl_bin" \
  "$plugin_dir/libArduPilotPlugin.so" "$world_path" "$copter_params" \
  "$iris_params" "$dds_params"; do
  if [ ! -e "$required_path" ]; then
    echo "Iris DDS control prerequisite unavailable: $required_path" >&2
    exit 2
  fi
done

set +u
source "$agent_setup"
set -u
# Isolation comes from the dedicated Agent port below, not from a ROS domain:
# micro_ros_agent has no domain option and does not follow ROS_DOMAIN_ID, so
# setting one only hides the Agent's topics from ros2 and the check then fails
# with "AP_DDS services did not appear".

test_tmpdir="$(mktemp -d)"
gazebo_pid=""
agent_pid=""
sitl_pid=""

cleanup() {
  for pid in "$sitl_pid" "$agent_pid" "$gazebo_pid"; do
    if [ -n "$pid" ]; then
      kill -INT "$pid" 2>/dev/null || true
    fi
  done
  for _ in $(seq 1 20); do
    remaining=false
    for pid in "$sitl_pid" "$agent_pid" "$gazebo_pid"; do
      if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        remaining=true
      fi
    done
    if [ "$remaining" = false ]; then
      break
    fi
    sleep 0.5
  done
  for pid in "$sitl_pid" "$agent_pid" "$gazebo_pid"; do
    if [ -n "$pid" ]; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  done
  pkill -9 -f "$sitl_bin" 2>/dev/null || true
  rm -rf "$test_tmpdir"
}
trap cleanup EXIT

export GZ_SIM_SYSTEM_PLUGIN_PATH="$plugin_dir${GZ_SIM_SYSTEM_PLUGIN_PATH:+:$GZ_SIM_SYSTEM_PLUGIN_PATH}"
export GZ_SIM_RESOURCE_PATH="$project_root/external/ardupilot_gazebo/models:$project_root/external/ardupilot_gazebo/worlds${GZ_SIM_RESOURCE_PATH:+:$GZ_SIM_RESOURCE_PATH}"

gz sim -s -r -v 3 "$world_path" >"$test_tmpdir/gazebo.log" 2>&1 &
gazebo_pid=$!
sleep 5

agent_port=20199
"$agent_bin" udp4 -p "$agent_port" >"$test_tmpdir/agent.log" 2>&1 &
agent_pid=$!
sleep 1

"$sitl_bin" --wipe --model JSON --speedup 1 --slave 0 \
  --sim-address=127.0.0.1 --sim-port-out=9002 \
  --serial0=udpclient:127.0.0.1:14550 \
  --defaults "$copter_params,$iris_params,$dds_params" \
  >"$test_tmpdir/sitl.log" 2>&1 &
sitl_pid=$!

for _ in $(seq 1 50); do
  if ros2 service list | grep -Fxq /ap/experimental/takeoff; then
    break
  fi
  sleep 1
done

if ! ros2 service list | grep -Fxq /ap/experimental/takeoff; then
  tail -100 "$test_tmpdir/gazebo.log" >&2 || true
  tail -100 "$test_tmpdir/agent.log" >&2 || true
  tail -100 "$test_tmpdir/sitl.log" >&2 || true
  echo "Iris AP_DDS services did not appear." >&2
  exit 1
fi

prearm_ready=false
for _ in $(seq 1 70); do
  prearm_response="$(ros2 service call /ap/prearm_check std_srvs/srv/Trigger '{}')"
  if grep -Fq "success=True" <<<"$prearm_response"; then
    prearm_ready=true
    break
  fi
  sleep 1
done
if [ "$prearm_ready" != true ]; then
  echo "$prearm_response" >&2
  exit 1
fi

mode_response="$(ros2 service call /ap/mode_switch ardupilot_msgs/srv/ModeSwitch '{mode: 4}')"
grep -Fq "status=True, curr_mode=4" <<<"$mode_response"

armed=false
for _ in $(seq 1 70); do
  arm_response="$(ros2 service call /ap/arm_motors ardupilot_msgs/srv/ArmMotors '{arm: true}')"
  if grep -Fq "result=True" <<<"$arm_response"; then
    armed=true
    break
  fi
  sleep 1
done
if [ "$armed" != true ]; then
  echo "$arm_response" >&2
  exit 1
fi

before_pose="$(timeout 12 ros2 topic echo /ap/geopose/filtered --once)"
before_altitude="$(awk '/altitude:/{print $2; exit}' <<<"$before_pose")"
if [ -z "$before_altitude" ]; then
  echo "$before_pose" >&2
  echo "No initial Iris geopose altitude." >&2
  exit 1
fi

takeoff_response="$(ros2 service call /ap/experimental/takeoff ardupilot_msgs/srv/Takeoff '{alt: 2.0}')"
grep -Fq "status=True" <<<"$takeoff_response"
sleep 15

after_pose="$(timeout 12 ros2 topic echo /ap/geopose/filtered --once)"
after_altitude="$(awk '/altitude:/{print $2; exit}' <<<"$after_pose")"
if ! awk -v before="$before_altitude" -v after="$after_altitude" \
  'BEGIN { exit !(after >= before + 1.0) }'; then
  printf 'Iris did not climb: before=%s after=%s\n' "$before_altitude" "$after_altitude" >&2
  exit 1
fi

printf 'Iris DDS control check passed: altitude %.2f -> %.2f m.\n' \
  "$before_altitude" "$after_altitude"
