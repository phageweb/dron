#!/usr/bin/env bash
# Fly one sortie and measure what the swarm layer needs to know about one drone.
#
# This is M1 of spec/roj/07_plan_a_milniky.md. `d_safe` between two machines is
# a sum of five terms and three of them - braking distance, command-to-motion
# latency, and the drift of the estimate - have never been measured here. The
# flight is a sequence of velocity steps and a hover in an empty room;
# scripts/measure_dynamic_limits.py does the measuring and this script is only
# the stack it needs underneath.
#
# Deliberately no ros_gz_bridge and no demo nodes. Nothing here reads a scan,
# and a second node publishing /ap/cmd_vel would be commanding the same vehicle
# from a different opinion.
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
# An empty room, because this measures the machine and not a policy. Interior
# is 8 x 6 m, so a 1 m/s step from the middle has room to accelerate, hold and
# coast without a wall deciding when it stops.
world_path="ros_ws/src/openipc_cinewhoop_gazebo/worlds/room_test.sdf"

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
  "scripts/measure_dynamic_limits.py"; do
  if [ ! -e "$required_path" ]; then
    echo "Dynamic limits prerequisite unavailable: $required_path" >&2
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

# A leftover node from an earlier run would command this run's vehicle. The
# ros2 CLI daemon caches the graph and keeps serving names for a while after
# the node is gone, so stop it first and then ask - see the entry in
# workflow/troubleshooting.md, which is what a back-to-back run tripped on.
ros2 daemon stop >/dev/null 2>&1 || true
sleep 3
for _ in $(seq 1 10); do
  if ! ros2 node list 2>/dev/null \
      | grep -Eq '^/(simple_indoor_autonomy|dynamic_limits_pilot)$'; then
    break
  fi
  sleep 1
done
if ros2 node list 2>/dev/null \
    | grep -Eq '^/(simple_indoor_autonomy|dynamic_limits_pilot)$'; then
  echo "Another node is already publishing /ap/cmd_vel; stop it first." >&2
  exit 1
fi

run_dir="logs/dynamic_limits/$airframe-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$run_dir"
gazebo_pid=""
bridge_pid=""
agent_pid=""
sitl_pid=""

cleanup() {
  for pid in "$sitl_pid" "$agent_pid" "$bridge_pid" "$gazebo_pid"; do
    if [ -n "$pid" ]; then
      kill -INT "$pid" 2>/dev/null || true
    fi
  done
  sleep 1
  for pid in "$sitl_pid" "$agent_pid" "$bridge_pid" "$gazebo_pid"; do
    if [ -n "$pid" ]; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  done
  pkill -9 -f "$project_root/$sitl_bin" 2>/dev/null || true
  # gz topic -e is a child of the measuring program and outlives a kill of it.
  pkill -9 -f "gz topic -e -t /world/.*/dynamic_pose/info" 2>/dev/null || true
}
trap cleanup EXIT

gz sim -s -r -v 3 "$world_path" >"$run_dir/gazebo.log" 2>&1 &
gazebo_pid=$!
sleep 6

"$project_root/$bridge_bin" >"$run_dir/bridge.log" 2>&1 &
bridge_pid=$!

"$project_root/$agent_bin" udp4 -p 20199 >"$run_dir/agent.log" 2>&1 &
agent_pid=$!
sleep 2

(
  cd external/ardupilot/ArduCopter
  exec "$project_root/$sitl_bin" --wipe --model JSON --speedup 1 --slave 0 -I0 \
    --sim-address=127.0.0.1 --sim-port-out=9002 \
    --serial0=udpclient:127.0.0.1:14550 \
    --defaults "$project_root/$sitl_params,$project_root/$dds_params"
) >"$run_dir/sitl.log" 2>&1 &
sitl_pid=$!

for _ in $(seq 1 60); do
  if ros2 topic list 2>/dev/null | grep -Fxq /ap/cmd_vel; then
    break
  fi
  sleep 1
done
if ! ros2 topic list 2>/dev/null | grep -Fxq /ap/cmd_vel; then
  echo "AP_DDS topics did not appear; the agent never saw the autopilot." >&2
  tail -40 "$run_dir/agent.log" >&2 || true
  exit 1
fi

echo "Airframe $airframe, world $(basename "$world_path"), logs in $run_dir"
python3 scripts/measure_dynamic_limits.py \
  --world "$(sed -n 's/.*<world[[:space:]]\+name="\([^"]*\)".*/\1/p' "$world_path" | head -1)" \
  --out "$run_dir" \
  --hover-s "${HOVER_S:-60}" \
  | tee "$run_dir/measurement.log"

python3 - "$run_dir/dynamic_limits.json" "$airframe" <<'PY'
import json
import sys

results = json.load(open(sys.argv[1]))
airframe = sys.argv[2]

# The rotor tip reach of each airframe, from the models these flights use.
# It is the only term of d_safe that is geometry rather than behaviour.
ROTOR_TIP_M = {"cinewhoop": 0.08335, "pavo20": 0.06107}
tip = ROTOR_TIP_M.get(airframe)

steps = {k: v for k, v in results.items()
         if k.startswith("step") and isinstance(v, dict)}
trials = [v["latency_s"] for k, v in results.items()
          if k.startswith("latency trial") and isinstance(v, dict)
          and v["latency_s"] is not None]

if not steps:
    sys.exit("No velocity steps in the results; nothing to check.")

print()
print("  what this means for d_safe:")
if trials:
    print(f"    latency {min(trials):.3f} to {max(trials):.3f} s "
          f"over {len(trials)} trials at the same speed")
worst = max((v for v in steps.values() if v["braking_m"] is not None),
            key=lambda v: v["braking_m"], default=None)
if worst is None:
    sys.exit("No braking distance was measured on any step.")
print(f"    worst coast {worst['braking_m']:.2f} m "
      f"from {worst['commanded_mps']:.2f} m/s commanded")

# The hover window is the one that belongs in d_safe: it is the estimate
# walking away on its own, not the estimate being pushed around by manoeuvres.
drift = results.get("drift_hover") or results.get("drift")
if drift:
    print(f"    drift {drift['horizontal_m']:.2f} m horizontally in "
          f"{drift['seconds']:.0f} s of hover")

if tip is not None and trials and drift:
    # d_safe = 2*r_rotor + 2*e_position + v_max*t_latency + s_braking + margin.
    # The margin is deliberately not chosen here: it is a decision to be written
    # down before a test, not a number a measuring script may invent.
    v_max = max(v["commanded_mps"] for v in steps.values())
    core = (2 * tip + 2 * drift["horizontal_m"]
            + v_max * max(trials) + worst["braking_m"])
    print(f"    so d_safe = {core:.2f} m + margin, at {v_max:.2f} m/s: "
          f"2*{tip:.5f} geometry + 2*{drift['horizontal_m']:.2f} estimate "
          f"+ {v_max:.2f}*{max(trials):.3f} latency "
          f"+ {worst['braking_m']:.2f} braking")

# Failures are about the measurement, not about the vehicle: this script exists
# to produce numbers, and a number outside anyone's expectation is a result.
for name, step in sorted(steps.items()):
    if step["steady_mps"] is None:
        sys.exit(f"{name} never reached a steady speed.")
print("Dynamic limits measured.")
PY
