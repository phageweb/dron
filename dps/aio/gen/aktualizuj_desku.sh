#!/usr/bin/env bash
# Run aktualizuj_desku.py with the Python that KiCad's pcbnew module was built for.
set -euo pipefail
base=$(grep -o '/nix/store/[a-z0-9]*-kicad-base[^/:" ]*' "$(readlink -f "$(command -v kicad-cli)")" | head -1)
py=$(nix-store -q --references "$base" | grep -m1 -- '-python3-.*-env$')/bin/python3
fp=$(nix-store -q --requisites "$(readlink -f "$(command -v kicad-cli)")" | grep -m1 -- '-kicad-footprints-[^.]*$' || true)
export PYTHONPATH="$(echo "$base"/lib/python3*/site-packages)"
export KICAD10_FOOTPRINT_DIR="${KICAD10_FOOTPRINT_DIR:-$fp/share/kicad/footprints}"
# swig reports every removed item as a leak on exit; that is noise
run() { "$py" "$@" 2>&1 | { grep --line-buffered -v -e "swig/python detected" -e "Font .* not found" -e "Debug: Adding duplicate" || true; }; }
if [ "${1:-}" = "--auto" ]; then
  shift
  run "$(dirname "$0")/automat.py" "$@"
  exit
elif [ "${1:-}" = "--python" ]; then
  shift
  run "$@"
  exit
fi
if [ "${1:-}" = "--vycisti" ]; then
  pcb="${2:-$(dirname "$0")/../aio.kicad_pcb}"
  for i in $(seq 1 30); do
    out=$(run "$(dirname "$0")/vycisti_med.py" "$pcb")
    echo "round $i: $out"
    echo "$out" | grep -q "^removed 0 tracks and vias" && break
  done
elif [ "${1:-}" = "--vyved" ]; then
  pcb="${2:-$(dirname "$0")/../aio.kicad_pcb}"
  run "$(dirname "$0")/vyved_bga.py" "$pcb"
  # the new copper cuts the zones: refill them, or every zone reports a clearance error
  kicad-cli pcb drc --refill-zones --save-board -o /dev/null "$pcb" >/dev/null
elif [ "${1:-}" = "--zbytky" ]; then
  pcb="${2:-$(dirname "$0")/../aio.kicad_pcb}"
  for i in $(seq 1 30); do
    out=$(run "$(dirname "$0")/vycisti_zbytky.py" "$pcb" ${3:+"$3"})
    echo "round $i: $out"
    echo "$out" | grep -q "^removed 0 " && break
  done
  kicad-cli pcb drc --refill-zones --save-board -o /dev/null "$pcb" >/dev/null
elif [ "${1:-}" = "--trasuj" ]; then
  pcb="${2:-$(dirname "$0")/../aio.kicad_pcb}"
  # the plane check reads the GND fills: they must be up to date
  kicad-cli pcb drc --refill-zones --save-board -o /dev/null "$pcb" >/dev/null
  run "$(dirname "$0")/trasuj.py" "$pcb" ${3:+"$3"}
  kicad-cli pcb drc --refill-zones --save-board -o /dev/null "$pcb" >/dev/null
elif [ "${1:-}" = "--okoli" ]; then
  shift
  run "$(dirname "$0")/okoli.py" "$@"
elif [ "${1:-}" = "--prosij" ]; then
  pcb="${2:-$(dirname "$0")/../aio.kicad_pcb}"
  kicad-cli pcb drc --refill-zones --save-board -o /dev/null "$pcb" >/dev/null
  run "$(dirname "$0")/prosij.py" "$pcb"
  kicad-cli pcb drc --refill-zones --save-board -o /dev/null "$pcb" >/dev/null
elif [ "${1:-}" = "--rucne" ]; then
  pcb="${2:-$(dirname "$0")/../aio.kicad_pcb}"
  run "$(dirname "$0")/rucne.py" "$pcb"
  kicad-cli pcb drc --refill-zones --save-board -o /dev/null "$pcb" >/dev/null
elif [ "${1:-}" = "--vyjednej" ]; then
  # negotiate: route what is left, letting a pair rip up the signal copper in its way; the ripped
  # nets come back in the next run, with the crossed cells dearer (TRASUJ_HIST); the best board stays
  pcb="${2:-$(dirname "$0")/../aio.kicad_pcb}"
  passes="${3:-6}"
  [[ "$passes" =~ ^[1-9][0-9]*$ ]] || { echo "passes must be a positive integer" >&2; exit 2; }
  work=$(mktemp -d)
  cp "$pcb" "$work/best.kicad_pcb"
  trap 'cp "$work/best.kicad_pcb" "$pcb"; rm -rf "$work"' EXIT
  kicad-cli pcb drc --refill-zones --save-board --format json -o "$work/drc.json" "$pcb" >/dev/null
  best=$(jq '.unconnected_items | length' "$work/drc.json")
  echo "start: $best unconnected"
  for i in $(seq 1 "$passes"); do
    TRASUJ_RIP=1 TRASUJ_PASS="$i" TRASUJ_HIST="$work/hist.json" run "$(dirname "$0")/trasuj.py" "$pcb" > "$work/log"
    grep -e "^-- " -e "ripping" "$work/log" || true
    kicad-cli pcb drc --refill-zones --save-board --format json -o "$work/drc.json" "$pcb" >/dev/null
    left=$(jq '.unconnected_items | length' "$work/drc.json")
    errors=$(jq '[.violations[] | select(.severity == "error")] | length' "$work/drc.json")
    echo "pass $i: DRC $errors errors, $left unconnected (best $best)"
    if [ "$errors" -eq 0 ] && [ "$left" -lt "$best" ]; then
      best=$left
      cp "$pcb" "$work/best.kicad_pcb"
    fi
    [ "$left" -eq 0 ] && break
  done
  cp "$work/best.kicad_pcb" "$pcb"
elif [ "${1:-}" = "--pretrasuj" ]; then
  # route everything again, a few times: each pass takes off what the router placed and puts
  # the nets that earlier passes left first; the board of the best pass stays
  pcb="${2:-$(dirname "$0")/../aio.kicad_pcb}"
  passes="${3:-3}"
  [[ "$passes" =~ ^[1-9][0-9]*$ ]] || { echo "passes must be a positive integer" >&2; exit 2; }
  work=$(mktemp -d)
  cp "$pcb" "$work/best.kicad_pcb"
  # A tool failure must restore the best checkpoint too.
  trap 'cp "$work/best.kicad_pcb" "$pcb"; rm -rf "$work"' EXIT
  : > "$work/first"
  : > "$work/best.log"
  kicad-cli pcb drc --format json -o "$work/drc.json" "$pcb" >/dev/null
  best=$(jq '.unconnected_items | length' "$work/drc.json")
  for i in $(seq 1 "$passes"); do
    run "$(dirname "$0")/trasuj.py" "$pcb" --smaz >/dev/null
    kicad-cli pcb drc --refill-zones --save-board -o /dev/null "$pcb" >/dev/null
    TRASUJ_PRVNI="$work/first" run "$(dirname "$0")/trasuj.py" "$pcb" > "$work/log"
    kicad-cli pcb drc --refill-zones --save-board --format json -o "$work/drc.json" "$pcb" >/dev/null
    left=$(jq '.unconnected_items | length' "$work/drc.json")
    errors=$(jq '[.violations[] | select(.severity == "error")] | length' "$work/drc.json")
    echo "pass $i: DRC $errors errors, $left unconnected (best $best)"
    if [ "$errors" -eq 0 ] && [ "$left" -lt "$best" ]; then
      best=$left
      cp "$pcb" "$work/best.kicad_pcb"
      cp "$work/log" "$work/best.log"
    fi
    [ "$best" -eq 0 ] && break
    jq -r '.unconnected_items[].items[0].description | capture("\\[(?<net>.*?)\\]").net' \
      "$work/drc.json" >> "$work/first"
    sort -u -o "$work/first" "$work/first"
  done
  cp "$work/best.kicad_pcb" "$pcb"
  sed -n '/^-- /,$p' "$work/best.log"
elif [ "${1:-}" = "--rozmisti" ]; then
  shift
  pcb="$(dirname "$0")/../aio.kicad_pcb"
  if [[ "${1:-}" == *.kicad_pcb ]]; then pcb="$1"; shift; fi
  run "$(dirname "$0")/rozmisti.py" "$pcb" "$@"
else
  run "$(dirname "$0")/aktualizuj_desku.py" "$@"
fi
