#!/usr/bin/env bash
# Copy the LidarCam recordings from the phone (USB debugging on) to lidar/sessions/ (or $1).
# Only finished recordings (with meta.json) that are not here yet are copied.
set -euo pipefail
pkg=cz.dron.lidarcam
src=/sdcard/Android/data/$pkg/files/sessions
dest="${1:-$(dirname "$0")/sessions}"
mkdir -p "$dest"

if ! adb get-state >/dev/null 2>&1; then
    echo "telefon není připojený (adb devices je prázdné)" >&2
    exit 1
fi

new=0
for s in $(adb shell "cd $src 2>/dev/null && for d in *; do [ -f \"\$d/meta.json\" ] && echo \"\$d\"; done" | tr -d '\r'); do
    [ -f "$dest/$s/meta.json" ] && continue
    echo "stahuji $s"
    if ! adb pull "$src/$s" "$dest/" >/dev/null 2>&1; then
        # Some Android versions hide Android/data from the shell; the app's own user can still read it.
        mkdir -p "$dest/$s"
        adb exec-out run-as "$pkg" tar -c -C "$src/$s" . | tar -x -C "$dest/$s"
    fi
    new=$((new + 1))
done
echo "nových záznamů: $new"
