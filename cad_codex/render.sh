#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
model="$script_dir/drone.scad"
font_cache="${XDG_CACHE_HOME:-/tmp/cad_codex-font-cache}"
mkdir -p "$font_cache"

if command -v xvfb-run >/dev/null 2>&1; then
  runner=(xvfb-run -a)
elif command -v nix >/dev/null 2>&1; then
  runner=(nix shell nixpkgs#xvfb-run -c xvfb-run -a)
elif [[ -n "${DISPLAY:-}" ]]; then
  runner=()
else
  printf 'No DISPLAY and no xvfb-run (or Nix) available for PNG rendering.\n' >&2
  exit 1
fi

common=(
  --imgsize=1600,1200
  --projection=o
  --autocenter
  --viewall
  --colorscheme=Tomorrow
  --view=edges
)

# Eye position followed by target position.  X is forward, Y left, Z up.
XDG_CACHE_HOME="$font_cache" "${runner[@]}" openscad "${common[@]}" \
  --camera=235,-235,175,0,0,14 \
  -o "$script_dir/isometric.png" "$model"
XDG_CACHE_HOME="$font_cache" "${runner[@]}" openscad "${common[@]}" \
  --camera=0,0,420,0,0,0 \
  -o "$script_dir/top.png" "$model"
XDG_CACHE_HOME="$font_cache" "${runner[@]}" openscad "${common[@]}" \
  --camera=0,-420,35,0,0,14 \
  -o "$script_dir/side.png" "$model"

printf 'Rendered: %s\n' \
  "$script_dir/isometric.png" "$script_dir/top.png" "$script_dir/side.png"
