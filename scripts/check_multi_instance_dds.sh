#!/usr/bin/env bash
# Two autopilots, one ROS graph, and neither one wearing the other's name.
#
# First step of M2 in spec/roj/07_plan_a_milniky.md, and deliberately the step
# with no Gazebo and no flight in it: before three models can share a world,
# two autopilots have to be able to share a ROS graph without colliding. SITL's
# own `quad` model is enough for that, so nothing here needs the simulator, the
# actuator bridge or a single propeller turning.
#
# What it establishes:
#   - DDS_USE_NS puts each instance under /ap/v<MAV_SYSID>/ (verified against
#     AP_DDS_Client.cpp:1498 rather than against documentation)
#   - one Micro XRCE-DDS Agent serves both clients, which spec/roj/05 lists as
#     unverified
#   - restarting one instance does not change the other's identity, which is
#     an acceptance item of M2
#
# Opt-in: needs the ignored local ArduPilot and DDS Agent builds.
set -eo pipefail

export LC_ALL=C

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

sitl_bin="$project_root/external/ardupilot/build/sitl/bin/arducopter"
agent_setup="$project_root/external/dds_ws/install/setup.bash"
agent_bin="$project_root/external/dds_ws/install/lib/micro_ros_agent/micro_ros_agent"

for required_path in "$sitl_bin" "$agent_setup" "$agent_bin"; do
  if [ ! -e "$required_path" ]; then
    echo "Multi-instance DDS prerequisite unavailable: $required_path" >&2
    exit 2
  fi
done

# micro_ros_agent ignores ROS_DOMAIN_ID, so setting one hides every /ap topic.
unset ROS_DOMAIN_ID || true

set +u
source "$agent_setup"
set -u

agent_port=20199
test_tmpdir="$(mktemp -d)"
agent_pid=""
declare -A sitl_pid=()

cleanup() {
  for pid in "${sitl_pid[@]}" "$agent_pid"; do
    [ -n "$pid" ] && kill -INT "$pid" 2>/dev/null || true
  done
  sleep 1
  for pid in "${sitl_pid[@]}" "$agent_pid"; do
    [ -n "$pid" ] && kill -9 "$pid" 2>/dev/null || true
  done
  pkill -9 -f "$sitl_bin" 2>/dev/null || true
  if [ -n "${KEEP_LOGS:-}" ]; then
    cp -r "$test_tmpdir" "$KEEP_LOGS" 2>/dev/null || true
    echo "logs kept in $KEEP_LOGS" >&2
  fi
  rm -rf "$test_tmpdir"
}
trap cleanup EXIT

# The ros2 CLI daemon caches the graph and keeps serving names for a while
# after a node is gone, which is how a back-to-back coverage run once tripped
# on its own corpse - see workflow/troubleshooting.md. Every question below is
# about which names exist, so start from a daemon that has no memory.
ros2 daemon stop >/dev/null 2>&1 || true
sleep 2

start_instance() {
  # $1 instance number (0-based, as SITL counts), $2 MAV_SYSID
  local index="$1" sysid="$2"
  local dir="$test_tmpdir/v$sysid"
  mkdir -p "$dir"
  # One parameter file per instance, and the only difference between them is
  # the identity. DDS_UDP_PORT is the same on purpose: whether one Agent can
  # serve both clients is the question spec/roj/05 asks and this answers.
  cat >"$dir/instance.parm" <<EOF
MAV_SYSID $sysid
DDS_USE_NS 1
DDS_UDP_PORT $agent_port
EOF
  # Each instance gets its own directory because --wipe writes eeprom.bin into
  # the working directory, and two autopilots sharing one storage file are not
  # two autopilots.
  (
    cd "$dir"
    exec "$sitl_bin" --wipe --model quad --speedup 1 --slave 0 \
      -I"$index" \
      --serial0="udpclient:127.0.0.1:$((14550 + index * 10))" \
      --defaults "$dir/instance.parm"
  ) >"$dir/sitl.log" 2>&1 &
  sitl_pid[$sysid]=$!
}

wait_for_topic() {
  # $1 topic, $2 seconds
  local topic="$1" limit="$2"
  for _ in $(seq 1 "$limit"); do
    if ros2 topic list 2>/dev/null | grep -Fxq "$topic"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

"$agent_bin" udp4 -p "$agent_port" >"$test_tmpdir/agent.log" 2>&1 &
agent_pid=$!
sleep 1
if ! kill -0 "$agent_pid" 2>/dev/null; then
  cat "$test_tmpdir/agent.log" >&2
  echo "The Agent did not start on UDP/$agent_port." >&2
  exit 1
fi

echo "Starting two SITL instances against one Agent on UDP/$agent_port"
start_instance 0 1
start_instance 1 2

for sysid in 1 2; do
  if ! wait_for_topic "/ap/v$sysid/time" 60; then
    echo "/ap/v$sysid/time never appeared." >&2
    echo "--- agent ---" >&2; tail -30 "$test_tmpdir/agent.log" >&2
    echo "--- sitl v$sysid ---" >&2; tail -40 "$test_tmpdir/v$sysid/sitl.log" >&2
    exit 1
  fi
  echo "  /ap/v$sysid/ is up"
done

# The namespace has to be the only place these topics live. An un-namespaced
# /ap/time alongside them would mean one of the two is still answering to the
# shared name, and the first swarm bug would be a command reaching the wrong
# vehicle.
if ros2 topic list 2>/dev/null | grep -Eq '^/ap/(time|pose/filtered|cmd_vel)$'; then
  echo "A bare /ap topic exists beside the namespaced ones:" >&2
  ros2 topic list | grep -E '^/ap/(time|pose/filtered|cmd_vel)$' >&2
  echo "One instance is not namespaced, so two vehicles share a name." >&2
  exit 1
fi

# Existing is not publishing. Both have to actually carry traffic, or the graph
# is two names and one autopilot.
for sysid in 1 2; do
  if ! timeout 20 ros2 topic echo --once "/ap/v$sysid/time" >/dev/null 2>&1; then
    echo "/ap/v$sysid/time exists but published nothing in 20 s." >&2
    exit 1
  fi
  echo "  /ap/v$sysid/time is publishing"
done

count_v1="$(ros2 topic list | grep -c '^/ap/v1/' || true)"
count_v2="$(ros2 topic list | grep -c '^/ap/v2/' || true)"
echo "  $count_v1 topics under /ap/v1/, $count_v2 under /ap/v2/"
if [ "$count_v1" -lt 3 ] || [ "$count_v1" != "$count_v2" ]; then
  echo "The two instances do not offer the same set of topics." >&2
  exit 1
fi

# An acceptance item of M2 in its own right: one agent going away must not take
# the other's identity with it, and the one that returns must come back as
# itself rather than as a second copy of its neighbour.
echo "Restarting instance v2 while v1 keeps flying"
# Reaped here rather than left to the shell, which would otherwise announce
# the kill as a "Killed" line in the middle of the check's own output.
kill -9 "${sitl_pid[2]}" 2>/dev/null || true
wait "${sitl_pid[2]}" 2>/dev/null || true
sleep 5
if ! timeout 20 ros2 topic echo --once /ap/v1/time >/dev/null 2>&1; then
  echo "v1 stopped publishing when v2 was killed; the identities are coupled." >&2
  exit 1
fi
echo "  v1 still publishing with v2 gone"

start_instance 1 2
if ! wait_for_topic "/ap/v2/time" 60; then
  echo "/ap/v2/time did not come back after a restart." >&2
  tail -40 "$test_tmpdir/v2/sitl.log" >&2
  exit 1
fi
if ! timeout 20 ros2 topic echo --once /ap/v2/time >/dev/null 2>&1; then
  echo "/ap/v2/time came back as a name but publishes nothing." >&2
  exit 1
fi
if ros2 topic list 2>/dev/null | grep -Eq '^/ap/v[^12]/'; then
  echo "A third identity appeared after the restart:" >&2
  ros2 topic list | grep -E '^/ap/v[^12]/' >&2
  exit 1
fi
echo "  v2 came back as v2"

echo "Multi-instance DDS check passed: two autopilots, one Agent, two namespaces."
