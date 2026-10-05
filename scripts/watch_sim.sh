#!/usr/bin/env bash
# Open a Gazebo window onto a simulation some other script is running.
#
# Every flight check runs Gazebo headless (`gz sim -s`). This attaches the GUI
# client to that server, with the paths it needs to draw the generated agent
# models, so a swarm flight can be watched while check_swarm_mapping.sh flies
# it.
#
# Attach once the agents are in the air - check_swarm_mapping.sh prints
# "waiting for the agents to take themselves off" and then the rangefinder
# line. Twice on 2026-10-03 a window opened while the autopilots were still
# connecting coincided with v1 never becoming armable; with the window opened
# after takeoff it flew normally. Two flights do not prove the window did it,
# so this waits by default rather than finding out a third time.
#
#   scripts/watch_sim.sh            # waits for takeoff, then opens the window
#   scripts/watch_sim.sh --now      # opens it straight away
#
# The window closes on its own when the flight's server goes away.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if ! command -v gz >/dev/null 2>&1; then
  exec nix develop --command "$0" "$@"
fi

airframe="${OPENIPC_AIRFRAME:-pavo20}"
export GZ_PARTITION="${GZ_PARTITION:-openipc_cinewhoop}"
export GZ_IP="${GZ_IP:-127.0.0.1}"
models="$project_root/build/agent_sim/$airframe/models"
export GZ_SIM_RESOURCE_PATH="$models:$project_root/build/agent_sim/$airframe/worlds${GZ_SIM_RESOURCE_PATH:+:$GZ_SIM_RESOURCE_PATH}"
export SDF_PATH="$models${SDF_PATH:+:$SDF_PATH}"
# The GUI's renderer is happier on XWayland than on Wayland directly.
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-xcb}"

if [ "${1:-}" != "--now" ]; then
  echo "Waiting for a flight to take off (Ctrl-C to stop waiting)..."
  # Only the flight going on now: an older run directory already says
  # "taking off" and would open the window too early. A takeoff counts if it
  # was logged after the running server started.
  airborne() {
    local server started log
    server="$(pgrep -f '[g]z sim -s' | head -1)"
    [ -n "$server" ] || return 1
    started="$(stat -c %Y "/proc/$server")"
    for log in logs/swarm_mapping/*/autonomy_v*.log; do
      [ -f "$log" ] || continue
      if [ "$(stat -c %Y "$log")" -ge "$started" ] \
          && grep -qs "taking off" "$log"; then
        return 0
      fi
    done
    return 1
  }
  until airborne; do
    sleep 2
  done
  # Takeoff is requested, not finished; give the climb a moment.
  sleep 10
fi

if ! pgrep -f "[g]z sim -s" >/dev/null; then
  echo "No headless Gazebo server is running. Start a flight first, e.g.:" >&2
  echo "  OPENIPC_AIRFRAME=pavo20 nix develop --command scripts/check_swarm_mapping.sh 3" >&2
  exit 1
fi

exec gz sim -g -v 2
