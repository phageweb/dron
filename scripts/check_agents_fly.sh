#!/usr/bin/env bash
# Several drones in one world, and a command that reaches only the one it names.
#
# P1 to P4 of spec/roj/05_infrastruktura_simulace.md, and the flying half of
# M2. scripts/check_multi_instance_dds.sh already showed two autopilots can
# share a ROS graph; this adds the simulator, which is where the model name is
# used as an identity - in the world's include, in the plugin's rotor topics,
# and in the JSON port each autopilot talks to.
#
# The test that matters is not that both fly. It is that **only one flies when
# only one is told to**: a crossed fdm_port_in would show up as the other
# vehicle climbing, and no amount of both-took-off would have caught it.
#
# Passing since 2026-09-20. It failed for two days for a reason that had
# nothing to do with two agents: the Pavo20 model carried the CineLog's
# throttle multiplier and could not lift itself, and every "working" variant
# in the hunt was the CineLog being substituted through SDF_PATH. Both are
# fixed; see workflow/troubleshooting.md.
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

# How many agents to fly. Two is what M2 asks for; three is M3, and the
# generator's START_POSES is the limit because a start pose is a decision
# about separation rather than a loop index.
agents="${1:-${OPENIPC_AGENTS:-2}}"
# One is allowed and is the control case: the real time factor with a single
# agent is what the two- and three-agent figures have to be read against.
if ! [ "$agents" -ge 1 ] 2>/dev/null; then
  echo "usage: $0 [agent count >= 1]" >&2
  exit 2
fi

airframe="${OPENIPC_AIRFRAME:-cinewhoop}"
params_name="ardupilot_params.parm"
[ "$airframe" != "cinewhoop" ] && params_name="ardupilot_params_$airframe.parm"
sitl_params="ros_ws/src/openipc_cinewhoop_gazebo/config/$params_name"
dds_params="ros_ws/src/openipc_cinewhoop_gazebo/config/dds_smoke.parm"

for required_path in "$sitl_bin" "$bridge_bin" "$agent_setup" "$agent_bin" \
  "$plugin_dir/libArduPilotPlugin.so" "$sitl_params" "$dds_params" \
  "scripts/generate_agent_models.py"; do
  if [ ! -e "$required_path" ]; then
    echo "Two-agent prerequisite unavailable: $required_path" >&2
    exit 2
  fi
done

if [ ! -f install/setup.bash ]; then
  echo "Workspace is not built; run colcon build first." >&2
  exit 1
fi

unset ROS_DOMAIN_ID || true
export GZ_PARTITION="${GZ_PARTITION:-openipc_cinewhoop}"
export GZ_IP="${GZ_IP:-127.0.0.1}"
export GZ_SIM_SYSTEM_PLUGIN_PATH="$project_root/$plugin_dir${GZ_SIM_SYSTEM_PLUGIN_PATH:+:$GZ_SIM_SYSTEM_PLUGIN_PATH}"

echo "Generating one model per agent from the $airframe airframe:"
generated="$(python3 scripts/generate_agent_models.py --airframe "$airframe" --agents "$agents")"
echo "$generated"
models_path="$(echo "$generated" | sed -n 's/^models //p')"
world_path="$(echo "$generated" | sed -n 's/^world //p')"
mapfile -t bridge_configs < <(echo "$generated" | sed -n 's/^bridge //p')
if [ -z "$models_path" ] || [ -z "$world_path" ]; then
  echo "The generator did not print a models and world path." >&2
  exit 1
fi
export GZ_SIM_RESOURCE_PATH="$models_path:$(dirname "$world_path")${GZ_SIM_RESOURCE_PATH:+:$GZ_SIM_RESOURCE_PATH}"
# sdformat resolves model:// through SDF_PATH, not through
# GZ_SIM_RESOURCE_PATH, and the dev shell points SDF_PATH at the CineLog
# models. Without this line an OPENIPC_AIRFRAME=pavo20 run loads the
# CineLog model and reports it as the Pavo20 - which is what every
# pavo20 measurement before 2026-09-20 actually did.
# The generated models, not the airframe directory: the world includes
# model://openipc_cinewhoop_v1 and only $models_path has those. The dev shell
# points SDF_PATH at the CineLog, so without this the include resolves to
# nothing - or worse, to a model that is not the one being flown.
export SDF_PATH="$models_path${SDF_PATH:+:$SDF_PATH}"

set +u
source install/setup.bash
source "$agent_setup"
set -u

# Absolute, because each autopilot is started after a cd into its own
# directory and a relative --defaults path would resolve against that instead.
run_dir="$project_root/logs/two_agents/$airframe-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$run_dir"
gazebo_pid=""
agent_pid=""
bridge_pids=()
gz_bridge_pids=()
sitl_pids=()

cleanup() {
  for pid in "${sitl_pids[@]}" "$agent_pid" "${gz_bridge_pids[@]}" \
             "${bridge_pids[@]}" "$gazebo_pid"; do
    [ -n "$pid" ] && kill -INT "$pid" 2>/dev/null || true
  done
  sleep 1
  for pid in "${sitl_pids[@]}" "$agent_pid" "${gz_bridge_pids[@]}" \
             "${bridge_pids[@]}" "$gazebo_pid"; do
    [ -n "$pid" ] && kill -9 "$pid" 2>/dev/null || true
  done
  pkill -9 -f "parameter_bridge --ros-args -p config_file:=$run_dir" 2>/dev/null || true
  pkill -9 -f "$project_root/$sitl_bin" 2>/dev/null || true
  pkill -9 -f "gz topic -e -t /world/.*/dynamic_pose/info" 2>/dev/null || true
}
trap cleanup EXIT

gz sim -s -r -v 3 "$world_path" >"$run_dir/gazebo.log" 2>&1 &
gazebo_pid=$!
sleep 8

# One actuator bridge per model. ArduPilot publishes a Double per rotor on
# topics scoped by the model's name and the motor models read one Actuators
# array, so a single bridge would drive whichever model it was told about and
# leave the other one's rotors stopped.
for index in $(seq 1 "$agents"); do
  "$project_root/$bridge_bin" --model "openipc_cinewhoop_v$index" \
    >"$run_dir/bridge_v$index.log" 2>&1 &
  bridge_pids+=($!)
done

"$project_root/$agent_bin" udp4 -p 20199 >"$run_dir/agent.log" 2>&1 &
agent_pid=$!

# One ros_gz_bridge per agent, each rendered from the single-drone template
# with its own model and its own ROS namespace. Without these the agents have
# no scans and no rangefinder in ROS, so nothing above the autopilot can map.
for index in $(seq 1 "$agents"); do
  ros2 run ros_gz_bridge parameter_bridge --ros-args \
    -p "config_file:=${bridge_configs[$((index - 1))]}" \
    >"$run_dir/gz_bridge_v$index.log" 2>&1 &
  gz_bridge_pids+=($!)
done
sleep 3

for index in $(seq 1 "$agents"); do
  instance=$((index - 1))
  dir="$run_dir/v$index"
  mkdir -p "$dir"
  # --wipe writes eeprom.bin into the working directory, so each autopilot
  # needs its own; see check_multi_instance_dds.sh.
  cat >"$dir/identity.parm" <<EOF
MAV_SYSID $index
DDS_USE_NS 1
EOF
  (
    cd "$dir"
    exec "$project_root/$sitl_bin" --wipe --model JSON --speedup 1 --slave 0 \
      -I"$instance" \
      --sim-address=127.0.0.1 --sim-port-out=$((9002 + instance * 10)) \
      --serial0="udpclient:127.0.0.1:$((14550 + instance * 10))" \
      --defaults "$project_root/$sitl_params,$project_root/$dds_params,$dir/identity.parm"
  ) >"$dir/sitl.log" 2>&1 &
  sitl_pids+=($!)
done

wanted_topics=""
for index in $(seq 1 "$agents"); do
  wanted_topics="$wanted_topics /ap/v$index/time"
done
for _ in $(seq 1 90); do
  missing=""
  for topic in $wanted_topics; do
    ros2 topic list 2>/dev/null | grep -Fxq "$topic" || missing="$missing $topic"
  done
  [ -z "$missing" ] && break
  sleep 1
done
if [ -n "$missing" ]; then
  echo "These autopilots never reached the ROS graph:$missing" >&2
  tail -20 "$run_dir/agent.log" >&2 || true
  exit 1
fi
echo "All $agents autopilots are on the graph:$wanted_topics"

# What the simulator is costing. Three machines with a 360-point lidar each is
# the load M3 asks about, and a Gazebo that has quietly stopped keeping up does
# not announce it - it just makes every measurement above mean something else.
real_time_factor="$(timeout 10 gz topic -e -t /stats -n 5 2>/dev/null \
  | grep -A2 real_time_factor | grep -oE "[0-9]+\.[0-9]+" | tail -1)"
echo "  real time factor with $agents agents: ${real_time_factor:-unknown}"

# Each agent's sensors have to arrive in ROS under its own namespace, or the
# mapper the coordinator merges from has nothing to map.
missing_sensors=""
for index in $(seq 1 "$agents"); do
  for suffix in scan/front range/down_raw; do
    ros2 topic list 2>/dev/null | grep -Fxq "/v$index/$suffix" \
      || missing_sensors="$missing_sensors /v$index/$suffix"
  done
done
if [ -n "$missing_sensors" ]; then
  echo "These bridged sensor topics never appeared:$missing_sensors" >&2
  tail -10 "$run_dir/gz_bridge_v1.log" >&2 || true
  exit 1
fi
echo "  each agent's scan and rangefinder are bridged under its own namespace"

python3 - "$(sed -n 's/.*<world[[:space:]]\+name="\([^"]*\)".*/\1/p' "$world_path" | head -1)" "$agents" <<'PY'
import math
import sys
import time

sys.path.insert(0, "scripts")
# The same ground-truth reader M1 uses. Two instances rather than one reader
# for both models: it keeps the class that M1's numbers came out of untouched,
# and a second `gz topic -e` costs nothing next to a simulator.
from measure_dynamic_limits import GroundTruth
from pymavlink import mavutil

world = sys.argv[1]
agents = int(sys.argv[2])
indices = list(range(1, agents + 1))
truth = {}
for index in indices:
    reader = GroundTruth(world, f"openipc_cinewhoop_v{index}")
    reader.start()
    truth[index] = reader

for _ in range(150):
    if all(reader.position() is not None for reader in truth.values()):
        break
    time.sleep(0.1)
missing = [i for i, r in truth.items() if r.position() is None]
if missing:
    sys.exit(f"No ground truth for agent(s) {missing}; the world did not "
             "spawn one model per agent.")

ground = {i: truth[i].position() for i in truth}
print("  on the ground at "
      + ", ".join(f"v{i}: x {p[0]:+.2f} y {p[1]:+.2f}" for i, p in ground.items()))

# The generator's own start poses, so a silent change there fails here rather
# than quietly moving the vehicles.
for index, want_y in list(zip(indices, (-2.0, 0.0, 2.0)))[:agents]:
    if abs(ground[index][1] - want_y) > 0.2:
        sys.exit(f"v{index} spawned at y {ground[index][1]:+.2f}, expected "
                 f"{want_y:+.2f}. The world and the generator disagree.")


def connect(index):
    link = mavutil.mavlink_connection(
        f"udpin:0.0.0.0:{14550 + (index - 1) * 10}")
    if link.wait_heartbeat(timeout=90) is None:
        sys.exit(f"No heartbeat from agent v{index}.")
    return link


def take_off(link, index, altitude=1.0):
    link.set_mode_apm("GUIDED")
    time.sleep(1)
    armed = False
    for _ in range(60):
        link.arducopter_arm()
        deadline = time.time() + 0.5
        while time.time() < deadline and not armed:
            msg = link.recv_match(type="HEARTBEAT", blocking=True, timeout=0.3)
            if msg and (msg.base_mode
                        & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED):
                armed = True
        if armed:
            break
    if not armed:
        sys.exit(f"Agent v{index} never armed: "
                 + "; ".join(complaints(link)) or "no reason given")

    link.mav.command_long_send(
        link.target_system, link.target_component,
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, altitude)
    # Ask whether it was accepted rather than assuming. A refused takeoff and a
    # takeoff that does nothing look identical from outside, and the autopilot
    # is willing to say which it is.
    deadline = time.time() + 5
    while time.time() < deadline:
        ack = link.recv_match(type="COMMAND_ACK", blocking=True, timeout=1)
        if ack is None or ack.command != mavutil.mavlink.MAV_CMD_NAV_TAKEOFF:
            continue
        if ack.result not in (mavutil.mavlink.MAV_RESULT_ACCEPTED,
                              mavutil.mavlink.MAV_RESULT_IN_PROGRESS):
            sys.exit(f"v{index} refused the takeoff, MAVLink result "
                     f"{ack.result}: " + "; ".join(complaints(link)))
        print(f"  v{index} armed, takeoff to {altitude:.1f} m accepted")
        return
    print(f"  v{index} armed, takeoff sent but never acknowledged: "
          + "; ".join(complaints(link)))


def complaints(link, seconds=2.0):
    """Whatever the autopilot has been saying about itself lately."""
    said = []
    deadline = time.time() + seconds
    while time.time() < deadline:
        msg = link.recv_match(type="STATUSTEXT", blocking=True, timeout=0.5)
        if msg is not None:
            said.append(msg.text)
    return said or ["said nothing"]


def height(index):
    return truth[index].position()[2] - ground[index][2]


def actuator_path(model):
    """Say which link of the actuator chain is silent, not just that it is.

    A vehicle that will not climb looks the same whether the autopilot is not
    commanding its rotors, the bridge is not relaying them, or the motors are
    not listening. These are three different bugs and the topics can tell them
    apart.
    """
    import subprocess

    def alive(topic, kind):
        try:
            out = subprocess.run(["gz", "topic", "-e", "-t", topic, "-n", "1"],
                                 capture_output=True, text=True, timeout=5)
            return bool(out.stdout.strip())
        except subprocess.TimeoutExpired:
            return False

    def sample(topic):
        try:
            out = subprocess.run(["gz", "topic", "-e", "-t", topic, "-n", "1"],
                                 capture_output=True, text=True, timeout=5)
            return " ".join(out.stdout.split())[:120] or "silent"
        except subprocess.TimeoutExpired:
            return "silent"

    rotor = alive(f"/model/{model}/joint/rotor_0_joint/cmd", "rotor")
    actuators = alive(f"/{model}/command/motor_speed", "actuators")
    return (f"Autopilot commanding rotors: {rotor} "
            f"[{sample(f'/model/{model}/joint/rotor_0_joint/cmd')}]. "
            f"Bridge publishing actuators: {actuators} "
            f"[{sample(f'/{model}/command/motor_speed')}].")


links = {index: connect(index) for index in indices}

# R16 in spec/roj/08: do the three EKFs share an origin? The agents stand at
# different places, so their own reported positions answer it without anyone
# having to move. If each EKF is anchored at its own spawn, all three read
# about zero; if they share the world's origin, they read their spawn offsets
# and the merged map has one frame rather than three.
for index in indices:
    links[index].mav.command_long_send(
        links[index].target_system, links[index].target_component,
        mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
        mavutil.mavlink.MAVLINK_MSG_ID_LOCAL_POSITION_NED, 200000, 0, 0, 0, 0, 0)
time.sleep(2)
origins = {}
for index in indices:
    msg = links[index].recv_match(type="LOCAL_POSITION_NED", blocking=True,
                                  timeout=5)
    if msg is None:
        print(f"  v{index}: no LOCAL_POSITION_NED, origin not checked")
        continue
    origins[index] = (msg.x, msg.y)
    truth_here = truth[index].position()
    print(f"  v{index} thinks it is at ({msg.x:+.2f}, {msg.y:+.2f}) while "
          f"ground truth puts it at ({truth_here[0]:+.2f}, {truth_here[1]:+.2f})")
if len(origins) == len(indices):
    spread = max(abs(v) for pair in origins.values() for v in pair)
    print("  EKF origins: "
          + ("each agent's own spawn point - a merged map needs the offsets "
             "adding back" if spread < 0.5 else
             "shared, the reported positions carry the spawn offsets"))
for link in links.values():
    # Ask for position at 5 Hz; without this the autopilot sends it rarely and
    # the comparison below has nothing to compare.
    link.mav.command_long_send(
        link.target_system, link.target_component,
        mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
        mavutil.mavlink.MAVLINK_MSG_ID_LOCAL_POSITION_NED, 200000, 0, 0, 0, 0, 0)

# One at a time, and this is the whole point of the check. If fdm_port_in is
# crossed, or a bridge is driving the wrong model, the vehicle that climbs is
# not the one that was told to - and both flying at the end would have hidden
# it completely.
take_off(links[1], 1)
# Sampled while it should be climbing, not after. A vehicle that fails to climb
# disarms itself a few seconds later, and once disarmed its rotor commands are
# zero for an entirely ordinary reason - so a probe taken at the end of the
# wait says nothing about why the start of it was quiet.
time.sleep(3)
print("  three seconds in: " + actuator_path("openipc_cinewhoop_v1"))
# Truth beside estimate while it climbs. A machine that cannot lift and a
# machine that believes it is already up look the same from the ground.
deadline = time.time() + 25
while time.time() < deadline and height(1) < 0.8:
    msg = links[1].recv_match(type="LOCAL_POSITION_NED", blocking=False)
    if msg is not None:
        print(f"    t+{time.time() - (deadline - 25):4.1f}s truth "
              f"{height(1):+.2f} m, autopilot believes {-msg.z:+.2f} m, "
              f"climb {-msg.vz:+.2f} m/s", flush=True)
    time.sleep(0.5)
print("  after v1's takeoff: "
      + "  ".join(f"v{i} {height(i):.2f} m" for i in indices))
if height(1) < 0.8:
    sys.exit(f"v1 was told to climb and reached {height(1):.2f} m. "
             + actuator_path("openipc_cinewhoop_v1"))
for other in indices[1:]:
    if height(other) > 0.2:
        sys.exit(f"v{other} climbed to {height(other):.2f} m without being "
                 "told to. A command reached the wrong vehicle.")

# The rest climb one at a time, which is R2: a failure to arm has to stop the
# ones behind it rather than being noticed after they are all airborne.
for index in indices[1:]:
    take_off(links[index], index)
    deadline = time.time() + 25
    while time.time() < deadline and height(index) < 0.8:
        time.sleep(0.2)
    heights = "  ".join(f"v{i} {height(i):.2f} m" for i in indices)
    print(f"  after v{index}'s takeoff: {heights}")
    if height(index) < 0.8:
        sys.exit(f"v{index} was told to climb and reached {height(index):.2f} m.")

# Both are up. Watch them hold for a while and record the closest they came:
# not a separation test - nothing is commanding them together yet - but the
# number M5 will be read against, measured the same way.
closest = None
start = time.time()
while time.time() - start < 15:
    for first in indices:
        for second in indices[indices.index(first) + 1:]:
            gap = math.dist(truth[first].position(), truth[second].position())
            closest = gap if closest is None else min(closest, gap)
    time.sleep(0.2)
print(f"  all {agents} holding; closest approach "
      + (f"{closest:.2f} m over 15 s" if closest is not None
         else "not measured, one agent"))
if closest is not None and closest < 1.0:
    sys.exit(f"They came within {closest:.2f} m while only holding station.")

for reader in truth.values():
    reader.stop()
print(f"Agent check passed: {agents} models, {agents} autopilots, "
      "no crossed wires.")
PY
