#!/usr/bin/env bash
# Fly the same roll step at several rate gains and put the results side by side.
#
# The gains in ardupilot_params.parm were derived from one authority calculation
# rather than measured. This is the measurement: each value gets a fresh SITL, an
# identical square wave in roll, and the same metrics out, so the choice can be
# made from numbers instead of from whether a run "looked" stable.
#
# Opt-in and slow: about a minute per gain, because every point boots Gazebo,
# the actuator bridge and SITL from scratch to keep the runs independent.
#
#   scripts/sweep_rate_gains.sh                    the default five gains
#   scripts/sweep_rate_gains.sh 0.027 0.05         only these
#   GUI=1 scripts/sweep_rate_gains.sh 0.05         watch it, one gain at a time
#   EXTRA_PARAMS="ATC_ACCEL_R_MAX 400000" ...      append parameters to every run
#   OPENIPC_AIRFRAME=pavo20 scripts/sweep_rate_gains.sh    sweep the other frame
#
# The airframe matters here more than anywhere else in the project, because the
# onset this measures is a property of the frame and not of the parameter file.
# Sweeping one airframe and carrying the answer to the other is exactly the
# substitution ardupilot_params_pavo20.parm makes an argument for rather than a
# measurement; this flag is what lets that argument be settled.
set -eo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

sitl_bin="external/ardupilot/build/sitl/bin/arducopter"
bridge_bin="build/ap_actuator_bridge/ap_actuator_bridge"
plugin_dir="build/ardupilot_gazebo"
world_path="ros_ws/src/openipc_cinewhoop_gazebo/worlds/indoor_test.sdf"
# Which airframe to sweep. The variants are separate model directories holding a
# model of the same name, so the world needs no change; the same selection as
# scripts/check_guided_takeoff.sh.
airframe="${OPENIPC_AIRFRAME:-cinewhoop}"
if [ "$airframe" = "cinewhoop" ]; then
  models_dir="models"
  params_name="ardupilot_params.parm"
else
  models_dir="models_$airframe"
  params_name="ardupilot_params_$airframe.parm"
fi
base_params="ros_ws/src/openipc_cinewhoop_gazebo/config/$params_name"

for required_path in "$sitl_bin" "$bridge_bin" "$plugin_dir/libArduPilotPlugin.so" \
  "$world_path" "$base_params"; do
  if [ ! -e "$required_path" ]; then
    echo "Rate sweep prerequisite unavailable: $required_path" >&2
    exit 2
  fi
done

# Two simulators cannot share UDP 9002, 14550 and 5762. When a second one starts
# anyway, SITL logs "bind failed" into a file nobody reads and the run fails much
# later with "Vehicle never armed", which points at the wrong thing entirely.
# Refuse up front and say what to stop.
stray="$(pgrep -f "$sitl_bin" 2>/dev/null || true)"
if [ -n "$stray" ]; then
  echo "ArduPilot SITL is already running (pid $(echo "$stray" | tr '\n' ' '))." >&2
  echo "Another flight check or sweep has not finished. Wait for it, or stop it:" >&2
  echo "  pkill -f $sitl_bin" >&2
  exit 1
fi
if command -v ss >/dev/null 2>&1 && ss -lunp 2>/dev/null | grep -q ":14550 "; then
  echo "UDP 14550 is already bound; something else is talking MAVLink." >&2
  exit 1
fi

# Around the 0.040 both parameter files now fly: half, three quarters, as flown,
# one and a half, double. This used to be centred on 0.018 and said so, which
# stopped being true when the LD06 went on the mast and the gains were measured
# again - a sweep centred two and a half times below the flown value cannot find
# the onset above it.
gains=("$@")
if [ ${#gains[@]} -eq 0 ]; then
  gains=(0.020 0.030 0.040 0.060 0.080)
fi

export GZ_PARTITION="${GZ_PARTITION:-openipc_cinewhoop}"
export GZ_IP="${GZ_IP:-127.0.0.1}"
export GZ_SIM_SYSTEM_PLUGIN_PATH="$project_root/$plugin_dir${GZ_SIM_SYSTEM_PLUGIN_PATH:+:$GZ_SIM_SYSTEM_PLUGIN_PATH}"
export GZ_SIM_RESOURCE_PATH="$project_root/ros_ws/src/openipc_cinewhoop_gazebo/$models_dir:$project_root/ros_ws/src/openipc_cinewhoop_gazebo/worlds${GZ_SIM_RESOURCE_PATH:+:$GZ_SIM_RESOURCE_PATH}"

# The airframe is in the path because two sweeps of different frames produce the
# same filenames otherwise, and the numbers are only comparable within one frame.
run_dir="logs/rate_sweep/$airframe-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$run_dir"
results="$run_dir/summary.jsonl"
: >"$results"

gazebo_pid=""
gui_pid=""
bridge_pid=""
sitl_pid=""

stop_stack() {
  # ArduCopter ignores SIGINT while waiting on its JSON peer, so never block on
  # `wait`: a stray SITL holds UDP/9002 and breaks the next point silently.
  for pid in "$sitl_pid" "$bridge_pid" "$gui_pid" "$gazebo_pid"; do
    [ -n "$pid" ] && kill -INT "$pid" 2>/dev/null || true
  done
  sleep 1
  for pid in "$sitl_pid" "$bridge_pid" "$gui_pid" "$gazebo_pid"; do
    [ -n "$pid" ] && kill -9 "$pid" 2>/dev/null || true
  done
  pkill -9 -f "$project_root/$sitl_bin" 2>/dev/null || true
  gazebo_pid=""; gui_pid=""; bridge_pid=""; sitl_pid=""
  sleep 2
}
trap stop_stack EXIT

for gain in "${gains[@]}"; do
  echo "==> ATC_RAT_RLL_P = $gain"
  params="$run_dir/params-$gain.parm"
  cp "$base_params" "$params"
  # Pitch moves with roll: the airframe is symmetric and leaving them different
  # would measure two things at once.
  {
    echo "ATC_RAT_RLL_P $gain"
    echo "ATC_RAT_PIT_P $gain"
    # EXTRA_PARAMS lets a run change the surrounding configuration, which is how
    # the acceleration limit above the rate loop gets taken out of the way.
    if [ -n "${EXTRA_PARAMS:-}" ]; then
      printf '%s\n' "$EXTRA_PARAMS"
    fi
  } >>"$params"

  gz sim -s -r -v 3 "$world_path" >"$run_dir/gazebo-$gain.log" 2>&1 &
  gazebo_pid=$!
  disown
  sleep 6

  # GUI=1 opens the Gazebo window so the roll steps can be watched rather than
  # only read off the table. The client has to wait for the server to register
  # the world, or it hangs on the world-selection screen. Watching costs real
  # time factor, so a run made for measuring should leave it off.
  if [ -n "${GUI:-}" ]; then
    gz sim -g >"$run_dir/gui-$gain.log" 2>&1 &
    gui_pid=$!
    disown
    sleep 4
  fi

  # Everything below waits on simulated time, and the window slows that down.
  # The first watched run failed to arm on timeouts that are ample headless.
  settle=20
  patience=1
  if [ -n "${GUI:-}" ]; then
    settle=45
    patience=4
  fi
  "$project_root/$bridge_bin" >"$run_dir/bridge-$gain.log" 2>&1 &
  bridge_pid=$!
  disown
  sleep 1
  (
    cd external/ardupilot/ArduCopter
    exec "$project_root/$sitl_bin" --wipe --model JSON --speedup 1 --slave 0 -I0 \
      --sim-address=127.0.0.1 --sim-port-out=9002 \
      --serial0=udpclient:127.0.0.1:14550 \
      --defaults "$project_root/$params"
  ) >"$run_dir/sitl-$gain.log" 2>&1 &
  sitl_pid=$!
  disown
  sleep "$settle"

  if python3 scripts/rate_step_response.py \
      --csv "$run_dir/trace-$gain.csv" --label "$gain" --patience "$patience" \
      >"$run_dir/result-$gain.json" 2>"$run_dir/error-$gain.log"; then
    cat "$run_dir/result-$gain.json" >>"$results"
    python3 -c "
import json, sys
r = json.load(open('$run_dir/result-$gain.json'))
print('    overshoot {overshoot_pct:5.1f} %   rise {rise_s:5.2f} s   '
      'settle {settle_s:5.2f} s   rms {rms_error_deg:5.2f} deg   '
      'sign changes {sign_changes:3d}'.format(**r))
"
  else
    echo "    FAILED:"
    sed 's/^/      /' "$run_dir/error-$gain.log"
    echo "{\"label\": \"$gain\", \"failed\": true}" >>"$results"
  fi

  stop_stack
done

echo
python3 - "$results" <<'PY'
import json
import sys

rows = [json.loads(line) for line in open(sys.argv[1]) if line.strip()]
header = f"{'ATC_RAT_RLL_P':>14} {'overshoot %':>12} {'rise s':>8} {'settle s':>9} {'rms deg':>8} {'ringing':>8}"
print(header)
print("-" * len(header))
for row in rows:
    if row.get("failed"):
        print(f"{row['label']:>14} {'did not fly':>12}")
        continue
    print(f"{row['label']:>14} {row['overshoot_pct']:>12.1f} {row['rise_s']:>8.2f} "
          f"{row['settle_s']:>9.2f} {row['rms_error_deg']:>8.2f} {row['sign_changes']:>8d}")
PY
echo
echo "Traces and logs: $run_dir"
