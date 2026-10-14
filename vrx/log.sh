#!/usr/bin/env bash
# Turn the log of what the camera saw on or off while vrx/ros.sh runs.
# Off by default. Lines and pictures go to ~/Videos/vrx/nalezy/.
#
#   vrx/log.sh on
#   vrx/log.sh off
set -euo pipefail
cd "$(dirname "$0")/.."
case "${1:-}" in
  on)  value=true ;;
  off) value=false ;;
  *)   echo "usage: vrx/log.sh on|off" >&2; exit 2 ;;
esac
# Without the daemon and with time to find the node: through the daemon a
# freshly started node is often "not found".
exec nix develop --command bash -c "
  source install/setup.bash
  ros2 param set --no-daemon --spin-time 3 /vrx_detector log_sightings $value
" 2>&1 | grep -v -E '^warning: Git tree|^OpenIPC|^ROS_DISTRO|^GZ_VERSION|^Run:'
