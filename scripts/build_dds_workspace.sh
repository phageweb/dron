#!/usr/bin/env bash
# Build the optional local ROS 2 workspace used by ArduPilot AP_DDS.
# Upstream sources and build products intentionally remain under ignored
# external/ so standard ROS/Gazebo CI stays lightweight and self-contained.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
external_dir="$project_root/external"
ardupilot_dir="$external_dir/ardupilot"
agent_dir="$external_dir/micro_ros_agent"
messages_dir="$external_dir/micro_ros_msgs"
dds_workspace="$external_dir/dds_ws"

if [ ! -d "$ardupilot_dir/.git" ]; then
  echo "Missing $ardupilot_dir; clone the official ArduPilot source first." >&2
  exit 2
fi

if [ ! -d "$agent_dir/.git" ]; then
  git clone --depth 1 --branch jazzy \
    https://github.com/micro-ROS/micro-ROS-Agent.git "$agent_dir"
fi

if [ ! -d "$messages_dir/.git" ]; then
  git clone --depth 1 --branch jazzy \
    https://github.com/micro-ROS/micro_ros_msgs.git "$messages_dir"
fi

# Do not inherit this repository's colcon defaults: this is a separate
# workspace, with only the three AP_DDS packages below.
export COLCON_DEFAULTS_FILE=/dev/null
cd "$external_dir"
colcon --log-base "$dds_workspace/log" build \
  --paths \
    "$messages_dir" \
    "$ardupilot_dir/Tools/ros2/ardupilot_msgs" \
    "$agent_dir/micro_ros_agent" \
  --build-base "$dds_workspace/build" \
  --install-base "$dds_workspace/install" \
  --merge-install
