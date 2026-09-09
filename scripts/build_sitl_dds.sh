#!/usr/bin/env bash
# Configure and build the optional local ArduCopter SITL binary with AP_DDS.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ardupilot_dir="$project_root/external/ardupilot"
generator_dir="$project_root/external/microxrcedds_gen"

for required_path in "$ardupilot_dir/waf" "$generator_dir/gradlew"; do
  if [ ! -e "$required_path" ]; then
    echo "DDS SITL prerequisite unavailable: $required_path" >&2
    echo "Clone the local ArduPilot and Micro-XRCE-DDS-Gen sources under external/." >&2
    exit 2
  fi
done

git -C "$generator_dir" submodule update --init --recursive
(
  cd "$generator_dir"
  ./gradlew assemble
)

# Put the compatibility wrapper first and the upstream generator second.
export PATH="$project_root/scripts:$generator_dir/scripts:$PATH"
cd "$ardupilot_dir"
./waf configure --board sitl --enable-DDS
./waf copter
