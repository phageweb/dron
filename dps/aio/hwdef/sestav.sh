#!/usr/bin/env bash
# Build the bootloader and ArduCopter for the Pavo20AIO hwdef.
#
#   nix develop ./dps#firmware -c dps/aio/hwdef/sestav.sh [outdir]
#
# Builds in a hard-linked copy of external/ardupilot, so the SITL build there
# keeps its configured board. waf's lock files are removed from the copy
# first: they are hard links and waf would rewrite the original's.
set -euo pipefail

root=$(git rev-parse --show-toplevel)
src="$root/external/ardupilot"
out=${1:-"$root/build/pavo20aio"}
work="$out/ardupilot"

rm -rf "$work"
mkdir -p "$work"
(cd "$src" && find . -path ./build -prune -o -print0 | cpio -0pdlm --quiet "$work")
rm -f "$work"/.lock-waf*
cp -r "$root/dps/aio/hwdef/Pavo20AIO" "$work/libraries/AP_HAL_ChibiOS/hwdef/"

cd "$work"
python3 Tools/scripts/build_bootloaders.py Pavo20AIO
# build_bootloaders.py exits 0 even when the board fails
test -f Tools/bootloaders/Pavo20AIO_bl.bin || { echo "bootloader build failed" >&2; exit 1; }
./waf configure --board Pavo20AIO --no-submodule-update
./waf copter

cp build/Pavo20AIO/bin/arducopter.apj build/Pavo20AIO/bin/arducopter_with_bl.hex \
   Tools/bootloaders/Pavo20AIO_bl.bin "$out/"
echo "ArduPilot $(git -C "$src" rev-parse --short HEAD) for Pavo20AIO in $out"
