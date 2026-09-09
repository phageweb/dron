#!/usr/bin/env bash
# Verify that the four rotors actually turn in their configured directions.
#
# The ArduPilot plugin's velocity loop is explicit, so a rotor whose inertia is
# small next to the applied torque can diverge and settle spinning backwards.
# gz-sim LiftDrag then produces exactly zero force for that rotor, because it
# skips any surface whose blade moves opposite its <forward> vector. The result
# is a vehicle that accepts a takeoff command and never leaves the ground, with
# nothing logged as an error anywhere in the stack.
#
# Opt-in: needs the ignored local ArduPilot and ardupilot_gazebo builds.
set -eo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

sitl_bin="external/ardupilot/build/sitl/bin/arducopter"
plugin_dir="build/ardupilot_gazebo"
world_path="ros_ws/src/openipc_cinewhoop_gazebo/worlds/indoor_test.sdf"
sitl_params="ros_ws/src/openipc_cinewhoop_gazebo/config/ardupilot_params.parm"

for required_path in "$sitl_bin" "$plugin_dir/libArduPilotPlugin.so" "$world_path" "$sitl_params"; do
  if [ ! -e "$required_path" ]; then
    echo "Rotor spin prerequisite unavailable: $required_path" >&2
    exit 2
  fi
done

# gazebo.launch.py pins the simulator to this partition; Gazebo Transport only
# discovers peers inside the same one, so the CLI has to join it explicitly.
export GZ_PARTITION="${GZ_PARTITION:-openipc_cinewhoop}"
export GZ_IP="${GZ_IP:-127.0.0.1}"
export GZ_SIM_SYSTEM_PLUGIN_PATH="$project_root/$plugin_dir${GZ_SIM_SYSTEM_PLUGIN_PATH:+:$GZ_SIM_SYSTEM_PLUGIN_PATH}"
export GZ_SIM_RESOURCE_PATH="$project_root/ros_ws/src/openipc_cinewhoop_gazebo/models:$project_root/ros_ws/src/openipc_cinewhoop_gazebo/worlds${GZ_SIM_RESOURCE_PATH:+:$GZ_SIM_RESOURCE_PATH}"

export project_root sitl_bin sitl_params

test_tmpdir="$(mktemp -d)"
gazebo_pid=""
sitl_pid=""

cleanup() {
  # ArduCopter does not exit on SIGINT while it is waiting on its JSON peer,
  # so an unconditional `wait` here blocks forever and leaves a stray SITL
  # holding UDP/9002 and MAVLink, which silently breaks the next run.
  for pid in "$sitl_pid" "$gazebo_pid"; do
    if [ -n "$pid" ]; then
      kill -INT "$pid" 2>/dev/null || true
    fi
  done
  for _ in $(seq 1 20); do
    remaining=false
    for pid in "$sitl_pid" "$gazebo_pid"; do
      if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        remaining=true
      fi
    done
    if [ "$remaining" = false ]; then
      break
    fi
    sleep 0.5
  done
  for pid in "$sitl_pid" "$gazebo_pid"; do
    if [ -n "$pid" ]; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  done
  # Belt and braces: the SITL launcher is a subshell, so $! may not be the
  # binary itself. Match this checkout's own build path and nothing else.
  pkill -9 -f "$project_root/$sitl_bin" 2>/dev/null || true
  rm -rf "$test_tmpdir"
}
trap cleanup EXIT

setsid gz sim -s -r -v 3 "$world_path" >"$test_tmpdir/gazebo.log" 2>&1 &
gazebo_pid=$!
sleep 6

(
  cd external/ardupilot/ArduCopter
  exec "$project_root/$sitl_bin" --wipe --model JSON --speedup 1 --slave 0 -I0 \
    --sim-address=127.0.0.1 --sim-port-out=9002 \
    --serial0=udpclient:127.0.0.1:14550 \
    --defaults "$project_root/$sitl_params"
) >"$test_tmpdir/sitl.log" 2>&1 &
sitl_pid=$!

# ArduPilot must reach the point of driving servo output before the joint
# velocities mean anything.
sleep 25

# An unarmed vehicle idles its rotors at a few tens of rad/s, which says
# nothing about direction. Arm and command a climb so ArduPilot drives real
# throttle. The command may time out while EKF settles; the rotor reading
# below is the actual assertion, so do not fail the test on it here.
timeout 90 python3 scripts/takeoff.py --altitude 2.0 --confirm --timeout 60 \
  >"$test_tmpdir/takeoff.log" 2>&1 || true
sleep 4

joint_topic="/world/indoor_test/model/openipc_cinewhoop/joint_state"
if ! timeout 15 gz topic -e -t "$joint_topic" -n 1 >"$test_tmpdir/joint_state.txt" 2>&1; then
  echo "No joint_state on $joint_topic (is GZ_PARTITION correct?)." >&2
  exit 1
fi

python3 - "$test_tmpdir/joint_state.txt" <<'PY'
import re
import sys

text = open(sys.argv[1]).read()
# Quad X: rotor 0 and 1 turn one way, rotor 2 and 3 the other.
expected = {"rotor_0_joint": 1, "rotor_1_joint": 1,
            "rotor_2_joint": -1, "rotor_3_joint": -1}
measured = {}
for block in re.split(r"\njoint \{", text):
    name = re.search(r'name:\s*"(rotor_\d+_joint)"', block)
    vel = re.search(r"velocity:\s*([-\d.e+]+)", block)
    if name and vel:
        measured[name.group(1)] = float(vel.group(1))

missing = sorted(set(expected) - set(measured))
if missing:
    sys.exit(f"joint_state did not report {', '.join(missing)}")

if all(abs(v) <= 200 for v in measured.values()):
    sys.exit("All rotors are still idling; ArduPilot never drove throttle, so "
             "rotor direction was not exercised.")

failures = []
for joint, sign in expected.items():
    speed = measured[joint]
    print(f"  {joint}: {speed:9.2f} rad/s (expected sign {sign:+d})")
    # An idle rotor is not evidence of a direction fault; a reversed one is.
    if abs(speed) > 200 and (speed > 0) != (sign > 0):
        failures.append(f"{joint} turns {speed:.1f} rad/s against its configured direction")

if failures:
    sys.exit("Rotor direction fault:\n  " + "\n  ".join(failures))
print("Rotor spin directions match the Quad X configuration.")
PY
