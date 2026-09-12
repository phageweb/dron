#!/usr/bin/env bash
# One place to launch everything this project can run.
#
# The repository has grown about twenty scripts with different prerequisites,
# and remembering which of them needs the opt-in `external/` builds is not a
# good use of anyone's attention. This lists them, says up front which ones can
# actually run right now, and runs the one that is picked.
#
# Re-enters `nix develop` on its own if it is started outside the shell.
set -uo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if ! command -v ros2 >/dev/null 2>&1; then
  if command -v nix >/dev/null 2>&1; then
    echo "Not in the dev shell; re-entering through nix develop."
    exec nix develop --command "$0" "$@"
  fi
  echo "Neither ros2 nor nix is on PATH. Run this from a checkout with Nix installed." >&2
  exit 1
fi

bold=$'\033[1m'; dim=$'\033[2m'; red=$'\033[31m'; green=$'\033[32m'; reset=$'\033[0m'

# --- what is available -------------------------------------------------------
have_workspace=false;  [ -f install/setup.bash ] && have_workspace=true
have_sitl=false;       [ -x external/ardupilot/build/sitl/bin/arducopter ] && have_sitl=true
have_bridge=false;     [ -x build/ap_actuator_bridge/ap_actuator_bridge ] && have_bridge=true
have_plugin=false;     [ -f build/ardupilot_gazebo/libArduPilotPlugin.so ] && have_plugin=true
have_dds=false;        [ -f external/dds_ws/install/setup.bash ] && have_dds=true

flight_ready=false
if $have_sitl && $have_bridge && $have_plugin; then flight_ready=true; fi

mark() { if [ "$1" = true ]; then printf '%s' "${green}yes${reset}"; else printf '%s' "${red}no${reset} "; fi; }

# --- the catalogue -----------------------------------------------------------
# Each entry: key|requirement|label|command|note. The requirement names which of
# the flags above has to be true, so a missing prerequisite is stated rather than
# discovered halfway through a run. The note is printed before the command and
# exists for one reason: several of these boot a simulator and then say nothing
# at all for minutes, which is indistinguishable from a hang.
entries=(
  "HEAD||Watch it fly"
  "everything|dds|Everything: scene, flight to the wall, stays up until Ctrl-C|scripts/demo.sh|Opens Gazebo and RViz, waits for ArduPilot, then flies. Holds position when it stops."
  "circuit|dds|Everything, in a closed room: it turns at the walls and keeps going|scripts/demo.sh --circuit|Opens Gazebo and RViz over room_test.sdf. It flies a leg, yaws towards the roomier side, and goes on."
  "explore|dds|Everything, in a cluttered room: it goes looking for what it has not seen|scripts/demo.sh --explore|Opens Gazebo and RViz over cluttered_room.sdf, building the map as it flies. Set RViz's Fixed Frame to map and add an Occupancy Map display on /openipc_cinewhoop/map to watch the room fill in, and the enclosure with it."
  "table|dds|Everything, in a room with a table: what one scan plane misses|scripts/demo.sh --table|Opens Gazebo and RViz over table_room.sdf and flies at 0.5 m, where the plane cuts the legs. Add --altitude 1.0 to fly over the table instead and watch it stay out of the map entirely."
  "demo|flight|Just the scene: Gazebo, SITL and RViz, no flight|ros2 launch openipc_cinewhoop_gazebo sitl_gazebo.launch.py gui:=true"
  "autonomy|dds|The autonomy node itself: arm, take off, creep, stop at the wall|__autonomy"
  "watchsweep|flight|Watch one rate-gain flight, the oscillating one|__watchsweep"
  "gazebo|workspace|Gazebo and the sensor bridge only, no ArduPilot|ros2 launch openipc_cinewhoop_gazebo gazebo.launch.py gui:=true"
  "rviz|workspace|The model in RViz only, no simulator|ros2 launch openipc_cinewhoop_description display.launch.py use_sim_time:=false"

  "HEAD||Measure"
  "sweep|flight|Rate-gain sweep, headless, about a minute per gain|__sweep|One simulator boot per gain, about a minute each, quiet in between."

  "HEAD||Check"
  "ci|workspace|Baseline CI, everything that runs without external/|scripts/ci.sh|Builds, tests and eight checks. Several minutes, output as it goes."
  "model|workspace|URDF and SDF describe the same drone|python3 scripts/check_model_consistency.py"
  "sensors|workspace|Sensor types, frames, cone and axes|scripts/check_sensor_interface.sh"
  "dropout|workspace|A dead lidar puts the demo nodes into a safe state|scripts/check_sensor_dropout.sh"
  "remap|workspace|Topics and services are remappable for hardware|scripts/check_topic_remap.sh"
  "lidar|workspace|Front lidar reaches the demo node|scripts/check_front_lidar.sh"
  "leaning|workspace|A pitched drone does not report the floor|scripts/check_leaning_scan.sh leaning_test|Boots Gazebo over a world holding the model nose-down. About a minute."
  "banked|workspace|A banked drone does not report the floor either|scripts/check_leaning_scan.sh banked_test 20|The one that exercises the roll term; a pitched world cannot. About a minute."

  "HEAD||Flight checks, need the external builds"
  "takeoff|flight|Guided takeoff: arm, climb, hold|scripts/check_guided_takeoff.sh|Headless. Headless and silent: it prints nothing until it finishes, a few minutes from now."
  "thrust|flight|Thrust stand: the rotors and lift model|scripts/check_thrust_stand.sh|Headless. Headless and silent: it prints nothing until it finishes, a few minutes from now."
  "forward|flight|Full autonomy flight, takeoff to wall|scripts/check_forward_flight.sh|Runs the whole demo without a window. Headless and silent: it prints nothing until it finishes, a few minutes from now."
  "unified|flight|One launch serves Gazebo, ArduPilot and TF|scripts/check_unified_launch.sh|Headless. Headless and silent: it prints nothing until it finishes, a few minutes from now."
  "attitude|flight|ArduPilot reports the attitude the vehicle really has|scripts/check_attitude_estimate.sh|Parks the vehicle on a ramp and compares three numbers. Nothing arms and nothing flies; under a minute."
  "circuitcheck|flight|The demo turns at a wall and flies on, rather than stopping|scripts/check_room_circuit.sh|Two minutes of flight in a closed room, headless and silent until it finishes."
  "mapcheck|flight|The map the vehicle builds is the room it flew round|scripts/check_room_mapping.sh|The same circuit with occupancy_mapper running, then the map is measured against the walls in the world file."
  "mapframe|flight|map -> base_link is where the vehicle really is|scripts/check_map_frame.sh|The circuit with pose_tf_broadcaster running, comparing the transform against Gazebo's ground truth in position and in yaw."
  "tablecheck|flight|The map holds what the scan plane met, and nothing else|scripts/check_table_height.sh 0.5|Flies the room with a table at 0.5 m, where the plane cuts the legs, and asserts they reach the map. Run it with no argument to fly at 1.0 m instead, where the geometry says the table cannot be in the map and the check asserts that it is not."
  "batterycheck|flight|It puts itself down when the pack runs out|scripts/check_low_battery_landing.sh|Flies a circuit, tells the running node its pack is flat, and asserts it says why, asks for LAND, reaches the floor and disarms there. About two minutes."
  "coveragecheck|flight|How much of a room with things in it the demo gets a look at|scripts/check_room_coverage.sh|The same circuit in a room with a pillar and a dogleg enclosure, measuring what reached the map and what stayed hidden. Over two minutes of flight, headless and silent until it finishes."

  "HEAD||Build"
  "colcon|always|Build the ROS workspace|colcon build"
  "actuator|always|Build the actuator bridge|scripts/build_actuator_bridge.sh"
  "ddsws|always|Build the DDS workspace and the Agent|scripts/build_dds_workspace.sh"
  "sitlbuild|always|Build ArduPilot SITL with DDS|scripts/build_sitl_dds.sh"
)

requirement_met() {
  case "$1" in
    always) return 0 ;;
    workspace) $have_workspace ;;
    flight) $flight_ready && $have_workspace ;;
    dds) $have_dds && $flight_ready ;;
    *) return 0 ;;
  esac
}

missing_reason() {
  case "$1" in
    workspace) echo "needs colcon build" ;;
    flight) $have_workspace || { echo "needs colcon build"; return; }
            echo "needs the external/ ArduPilot builds" ;;
    dds) echo "needs external/dds_ws and the ArduPilot builds" ;;
  esac
}

# --- the runnable specials ---------------------------------------------------
run_sweep() {
  local gains gui=""
  read -rp "Gains [0.009 0.0135 0.018 0.027 0.036]: " gains
  [ -z "$gains" ] && gains="0.009 0.0135 0.018 0.027 0.036"
  # shellcheck disable=SC2086
  scripts/sweep_rate_gains.sh $gains
}

run_watchsweep() {
  local gain
  read -rp "Gain to watch [0.05, which is past the onset and visibly hunts]: " gain
  [ -z "$gain" ] && gain="0.05"
  echo "${dim}The window costs real time factor, so treat these numbers as a look, not a measurement.${reset}"
  GUI=1 scripts/sweep_rate_gains.sh "$gain"
}

run_autonomy() {
  echo "${dim}This needs the simulator already running: pick 'Full demo in Gazebo' in another terminal first.${reset}"
  local altitude
  read -rp "Takeoff altitude in metres [1.0]: " altitude
  [ -z "$altitude" ] && altitude="1.0"
  # The autonomy node needs ardupilot_msgs, which lives outside the Nix shell.
  set +u; source external/dds_ws/install/setup.bash; set -u
  ros2 run openipc_cinewhoop_demo simple_indoor_autonomy \
    --ros-args -p takeoff_altitude_m:="$altitude"
  # A leftover node keeps publishing /ap/cmd_vel and silently stops the *next*
  # run from ever taking off, so clean up on the way out rather than later.
  pkill -f "openipc_cinewhoop_demo/lib/openipc_cinewhoop_demo/simple_indoor_autonomy" \
    2>/dev/null || true
}

show_menu() {
  printf '\n%sOpenIPC cinewhoop%s   workspace %s   ArduPilot builds %s   DDS workspace %s\n' \
    "$bold" "$reset" "$(mark $have_workspace)" "$(mark $flight_ready)" "$(mark $have_dds)"
  local index=0
  for entry in "${entries[@]}"; do
    IFS='|' read -r key requirement label _ _ <<<"$entry"
    if [ "$key" = "HEAD" ]; then
      printf '\n  %s%s%s\n' "$dim" "$label" "$reset"
      continue
    fi
    index=$((index + 1))
    if requirement_met "$requirement"; then
      printf '   %2d) %s\n' "$index" "$label"
    else
      printf '   %s%2d) %s  — %s%s\n' "$dim" "$index" "$label" "$(missing_reason "$requirement")" "$reset"
    fi
  done
  printf '\n    q) quit\n\n'
}

pick() {
  local wanted="$1" index=0
  for entry in "${entries[@]}"; do
    IFS='|' read -r key requirement label command note <<<"$entry"
    [ "$key" = "HEAD" ] && continue
    index=$((index + 1))
    if [ "$index" = "$wanted" ]; then
      if ! requirement_met "$requirement"; then
        printf '%sThat one cannot run yet: %s%s\n' "$red" "$(missing_reason "$requirement")" "$reset"
        return 1
      fi
      printf '\n%s==> %s%s\n%s%s%s\n' "$bold" "$label" "$reset" "$dim" "$command" "$reset"
      [ -n "${note:-}" ] && printf '%s%s%s\n' "$dim" "$note" "$reset"
      printf '\n'
      case "$command" in
        __sweep) run_sweep ;;
        __watchsweep) run_watchsweep ;;
        __autonomy) run_autonomy ;;
        *) eval "$command" ;;
      esac
      local status=$?
      printf '\n%s==> finished with status %d%s\n' "$bold" "$status" "$reset"
      return 0
    fi
  done
  printf '%sNo such entry.%s\n' "$red" "$reset"
  return 1
}

if [ "${1:-}" = "--list" ]; then
  show_menu
  exit 0
fi

if [ $# -gt 0 ]; then
  pick "$1"
  exit $?
fi

while true; do
  show_menu
  read -rp "Pick one: " choice
  case "$choice" in
    q|Q|"") echo "Bye."; exit 0 ;;
    *) pick "$choice" ;;
  esac
  read -rp $'\nEnter to return to the menu, q to quit: ' again
  [ "$again" = "q" ] && { echo "Bye."; exit 0; }
done
