#!/usr/bin/env bash
set -euo pipefail

echo "==> Development environment smoke check"
scripts/check_dev_env.sh

if [ -d ros_ws/src ] && find ros_ws/src -mindepth 2 -name package.xml -print -quit | grep -q .; then
  echo "==> ROS workspace build"
  colcon build

  echo "==> ROS workspace tests"
  colcon test
  colcon test-result --verbose

  if [ -d ros_ws/src/openipc_cinewhoop_demo/test ]; then
    echo "==> Python unit tests"
    python3 -m pytest ros_ws/src/openipc_cinewhoop_demo/test
  fi

  echo "==> URDF/SDF model consistency check"
  python3 scripts/check_model_consistency.py

  echo "==> ROS graph smoke check"
  scripts/check_ros_graph.sh

  echo "==> Topic and service remapping check"
  scripts/check_topic_remap.sh

  echo "==> Sensor dropout safe-state check"
  scripts/check_sensor_dropout.sh

  echo "==> Sensor interface check"
  scripts/check_sensor_interface.sh

  echo "==> TF tree smoke check"
  scripts/check_tf_tree.sh

  echo "==> Gazebo headless smoke check"
  scripts/check_gazebo_headless.sh

  echo "==> Front-lidar E2E check"
  scripts/check_front_lidar.sh
else
  echo "==> ROS workspace build skipped: no ROS packages found under ros_ws/src yet."
fi

echo "CI checks passed."
