#!/usr/bin/env bash
# The VRX in ROS 2 with one command: builds openipc_vrx if needed, starts the
# bridge, the people detector and the picture with boxes in the browser on
# http://localhost:8090. Ctrl+C ends all.
#
#   vrx/ros.sh                    people and all other 80 COCO classes
#   vrx/ros.sh person             only people
#   vrx/ros.sh person,backpack    chosen classes, comma separated
#   vrx/ros.sh off                no detection, just the picture
set -euo pipefail
cd "$(dirname "$0")/.."
what=${1:-all}
case "$what" in
  off) args="detect:=false" ;;
  all) args="detect:=true" ;;
  *)   args="detect:=true classes:=$what" ;;
esac
shift || true
exec nix develop --command bash -c "
  set -e
  colcon build --packages-select openipc_vrx > /tmp/openipc_vrx_build.log 2>&1 \\
    || { cat /tmp/openipc_vrx_build.log; exit 1; }
  source install/setup.bash
  exec ros2 launch openipc_vrx vrx_bridge.launch.py view:=true $args $*
"
