#!/usr/bin/env bash
# Confirm that the locally built Micro XRCE-DDS Agent starts its UDP transport.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
setup_file="$project_root/external/dds_ws/install/setup.bash"
agent_bin="$project_root/external/dds_ws/install/lib/micro_ros_agent/micro_ros_agent"

if [ ! -f "$setup_file" ] || [ ! -x "$agent_bin" ]; then
  echo "DDS Agent workspace unavailable: $setup_file or $agent_bin" >&2
  echo "Run scripts/build_dds_workspace.sh from nix develop first." >&2
  exit 2
fi

# Generated colcon setup scripts reference optional variables directly.
set +u
source "$setup_file"
set -u
test_tmpdir="$(mktemp -d)"
agent_pid=""

cleanup() {
  if [ -n "$agent_pid" ]; then
    kill -TERM "$agent_pid" 2>/dev/null || true
    wait "$agent_pid" 2>/dev/null || true
  fi
  rm -rf "$test_tmpdir"
}
trap cleanup EXIT

# UDP/2019 is the AP_DDS SITL default transport. Use a dedicated port for this
# standalone smoke check so a locally running SITL session does not conflict.
# The Agent itself is an XRCE bridge rather than a ROS graph node; AP_DDS
# topics appear only after SITL connects to it.
agent_port=20199
"$agent_bin" udp4 -p "$agent_port" >"$test_tmpdir/agent.log" 2>&1 &
agent_pid=$!

sleep 1
if kill -0 "$agent_pid" 2>/dev/null && grep -Fq "running..." "$test_tmpdir/agent.log" && \
  grep -Fq "port: $agent_port" "$test_tmpdir/agent.log"; then
  echo "Micro XRCE-DDS Agent UDP smoke check passed."
  exit 0
fi

cat "$test_tmpdir/agent.log" >&2
echo "Micro XRCE-DDS Agent did not start UDP/$agent_port." >&2
exit 1
