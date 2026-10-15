#!/usr/bin/env bash
# The OSD scan link in SITL, without a VTX: simulated LD06 on SERIAL5 ->
# scan_osd.lua -> osd:write -> MSP DisplayPort on SERIAL2 (TCP 5772) ->
# osdscan.py. Prints what arrived. Run in the project's dev shell.
#
#   lidar/osd/sitl_check.sh [seconds]
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
project_root="$(cd "$here/../.." && pwd)"
ap="$project_root/external/ardupilot"
sitl_bin="$ap/build/sitl/bin/arducopter"
seconds="${1:-30}"

work="$(mktemp -d)"
trap 'kill "${sitl_pid:-}" 2>/dev/null || true; rm -rf "$work"' EXIT
mkdir -p "$work/scripts"
cp "$here/scan_osd.lua" "$work/scripts/"
cat > "$work/osd.parm" <<'EOF'
OSD_TYPE 5
OSD1_TXT_RES 1
SERIAL2_PROTOCOL 42
SERIAL2_BAUD 115
SCR_ENABLE 1
SERIAL5_PROTOCOL 28
SERIAL5_BAUD 230
PRX1_TYPE 15
EOF

cd "$work"
"$sitl_bin" --model quad --speedup 1 -I0 \
    --defaults "$ap/Tools/autotest/default_params/copter.parm,osd.parm" \
    --serial0=udpclient:127.0.0.1:14550 --serial2=tcp:5772 --serial5=sim:ld06 \
    > sitl.log 2>&1 &
sitl_pid=$!

for _ in $(seq 50); do
    grep -q "SERIAL2 on TCP port 5772" sitl.log && break
    sleep 0.2
done
# the script starts once the vehicle is up
sleep 5
python3 "$here/osdscan.py" --msp tcp:127.0.0.1:5772 --seconds "$seconds" ${OSDSCAN_ARGS:-}
