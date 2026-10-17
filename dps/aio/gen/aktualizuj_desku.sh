#!/usr/bin/env bash
# Run aktualizuj_desku.py with the Python that KiCad's pcbnew module was built for.
set -euo pipefail
base=$(grep -o '/nix/store/[a-z0-9]*-kicad-base[^/:" ]*' "$(readlink -f "$(command -v kicad-cli)")" | head -1)
py=$(nix-store -q --references "$base" | grep -m1 -- '-python3-.*-env$')/bin/python3
fp=$(nix-store -q --requisites "$(readlink -f "$(command -v kicad-cli)")" | grep -m1 -- '-kicad-footprints-[^.]*$' || true)
export PYTHONPATH="$(echo "$base"/lib/python3*/site-packages)"
export KICAD10_FOOTPRINT_DIR="${KICAD10_FOOTPRINT_DIR:-$fp/share/kicad/footprints}"
# swig reports every removed item as a leak on exit; that is noise
"$py" "$(dirname "$0")/aktualizuj_desku.py" "$@" 2>&1 | grep -v -e "swig/python detected" -e "Font .* not found"
