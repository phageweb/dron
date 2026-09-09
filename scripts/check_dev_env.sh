#!/usr/bin/env bash
set -euo pipefail

checks=(
  "ros2 --help"
  "colcon --help"
  "rviz2 --help"
  "gz sim --versions"
  "python3 -c 'import rclpy; print(\"rclpy ok\")'"
)

for check in "${checks[@]}"; do
  echo "==> $check"
  bash -lc "$check" >/tmp/openipc_cinewhoop_check.out
  tail -n 3 /tmp/openipc_cinewhoop_check.out || true
done

echo "Development environment smoke check passed."
