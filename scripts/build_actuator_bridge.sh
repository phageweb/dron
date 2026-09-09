#!/usr/bin/env bash
# Build the ArduPilot-to-MulticopterMotorModel actuator bridge.
set -eo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

build_dir="build/ap_actuator_bridge"
cmake -S tools/ap_actuator_bridge -B "$build_dir" -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build "$build_dir" -j"$(nproc)"

echo "Built $build_dir/ap_actuator_bridge"
