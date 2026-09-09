#!/usr/bin/env bash
# Verify AP_DDS pre-arm, GUIDED, arm, and takeoff service requests in SITL.
# This is intentionally opt-in: ArduPilot and the Agent workspace live under
# ignored external/ paths and are not part of baseline ROS CI.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
setup_file="$project_root/external/dds_ws/install/setup.bash"
agent_bin="$project_root/external/dds_ws/install/lib/micro_ros_agent/micro_ros_agent"
sitl_bin="$project_root/external/ardupilot/build/sitl/bin/arducopter"
copter_params="$project_root/external/ardupilot/Tools/autotest/default_params/copter.parm"
dds_params="$project_root/ros_ws/src/openipc_cinewhoop_gazebo/config/dds_smoke.parm"

for required_path in "$setup_file" "$agent_bin" "$sitl_bin" "$copter_params" "$dds_params"; do
  if [ ! -e "$required_path" ]; then
    echo "DDS control smoke prerequisite unavailable: $required_path" >&2
    exit 2
  fi
done

# Generated colcon setup scripts reference optional variables directly.
set +u
source "$setup_file"
set -u

test_tmpdir="$(mktemp -d)"
agent_pid=""
sitl_pid=""

cleanup() {
  for pid in "$sitl_pid" "$agent_pid"; do
    if [ -n "$pid" ]; then
      kill -TERM "$pid" 2>/dev/null || true
    fi
  done
  for pid in "$sitl_pid" "$agent_pid"; do
    if [ -n "$pid" ]; then
      wait "$pid" 2>/dev/null || true
    fi
  done
  rm -rf "$test_tmpdir"
}
trap cleanup EXIT

agent_port=20199
"$agent_bin" udp4 -p "$agent_port" >"$test_tmpdir/agent.log" 2>&1 &
agent_pid=$!
sleep 1

if ! kill -0 "$agent_pid" 2>/dev/null || ! grep -Fq "running..." "$test_tmpdir/agent.log"; then
  cat "$test_tmpdir/agent.log" >&2
  echo "Micro XRCE-DDS Agent did not start on UDP/$agent_port." >&2
  exit 1
fi

"$sitl_bin" --wipe --model quad --speedup 1 --slave 0 \
  --serial0=udpclient:127.0.0.1:14550 \
  --defaults "$copter_params,$dds_params" >"$test_tmpdir/sitl.log" 2>&1 &
sitl_pid=$!

for _ in $(seq 1 30); do
  if ros2 service list | grep -Fxq /ap/experimental/takeoff; then
    break
  fi
  sleep 1
done

if ! ros2 service list | grep -Fxq /ap/experimental/takeoff; then
  echo "--- Micro XRCE-DDS Agent ---" >&2
  tail -80 "$test_tmpdir/agent.log" >&2
  echo "--- ArduCopter SITL ---" >&2
  tail -120 "$test_tmpdir/sitl.log" >&2
  echo "AP_DDS control services did not appear." >&2
  exit 1
fi

# EKF needs time to establish home after its topics first appear on DDS.
prearm_ready="false"
for _ in $(seq 1 60); do
  prearm_response="$(ros2 service call /ap/prearm_check std_srvs/srv/Trigger '{}')"
  if grep -Fq "success=True" <<<"$prearm_response"; then
    prearm_ready="true"
    break
  fi
  sleep 1
done

if [ "$prearm_ready" != "true" ]; then
  echo "$prearm_response" >&2
  echo "AP_DDS pre-arm service did not report an armable vehicle." >&2
  exit 1
fi

mode_response="$(ros2 service call /ap/mode_switch ardupilot_msgs/srv/ModeSwitch '{mode: 4}')"
if ! grep -Fq "status=True, curr_mode=4" <<<"$mode_response"; then
  echo "$mode_response" >&2
  echo "AP_DDS mode service did not enter GUIDED." >&2
  exit 1
fi

# The EKF can publish its first pre-arm success just before it establishes
# home. Retry the arm request until that initialization is complete.
armed="false"
for _ in $(seq 1 60); do
  arm_response="$(ros2 service call /ap/arm_motors ardupilot_msgs/srv/ArmMotors '{arm: true}')"
  if grep -Fq "result=True" <<<"$arm_response"; then
    armed="true"
    break
  fi
  sleep 1
done

if [ "$armed" != "true" ]; then
  echo "$arm_response" >&2
  echo "AP_DDS arm service did not succeed after EKF initialization." >&2
  exit 1
fi

takeoff_response="$(ros2 service call /ap/experimental/takeoff ardupilot_msgs/srv/Takeoff '{alt: 2.0}')"
if ! grep -Fq "status=True" <<<"$takeoff_response"; then
  echo "$takeoff_response" >&2
  echo "AP_DDS takeoff service did not accept the request." >&2
  exit 1
fi

echo "AP_DDS control service smoke check passed."
