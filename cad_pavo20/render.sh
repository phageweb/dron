#!/usr/bin/env bash
set -euo pipefail
d="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
m="$d/drone.scad"
cache="${XDG_CACHE_HOME:-/tmp/cad_pavo20-font-cache}"; mkdir -p "$cache"

# OpenSCAD potrebuje pro export PNG OpenGL kontext. Virtualni displej je
# spolehlivejsi nez $DISPLAY: na Waylandu ukazuje na Xwayland, ktere GLX
# kontext nemusi dat, a openscad pak skonci na "GLEW Error: No GLX display".
# Proto se po $DISPLAY saha az posledni, ne prvni.
if command -v xvfb-run >/dev/null 2>&1; then
  run=(xvfb-run -a)
elif command -v nix >/dev/null 2>&1; then
  run=(nix shell nixpkgs#xvfb-run -c xvfb-run -a)
elif [[ -n "${DISPLAY:-}" ]]; then
  run=()
else
  printf 'Neni xvfb-run, nix ani DISPLAY - PNG se vyrenderovat neda.\n' >&2
  exit 1
fi

# Ve virtualnim displeji neni GPU; llvmpipe je jedina cesta, jak dostat GL.
export LIBGL_ALWAYS_SOFTWARE=1

common=(--imgsize=1500,1125 --projection=o --autocenter --viewall
        --colorscheme=Tomorrow --view=edges)

# Kazdy pohled zapina jen sve vrstvy; jinak se prekryvy prekresli navzajem.
XDG_CACHE_HOME="$cache" "${run[@]}" openscad "${common[@]}" \
  -D show_props=false -D show_scan=false -D show_cg=false -D show_collision=true \
  --camera=250,-250,190,0,0,26 -o "$d/isometric.png" "$m"

XDG_CACHE_HOME="$cache" "${run[@]}" openscad "${common[@]}" \
  -D show_props=true -D show_scan=false -D show_cg=false -D show_collision=false \
  --camera=0,0,460,0,0,0 -o "$d/top.png" "$m"

XDG_CACHE_HOME="$cache" "${run[@]}" openscad "${common[@]}" \
  -D show_props=false -D show_scan=true -D show_cg=true -D show_collision=true \
  --camera=0,-460,30,0,0,28 -o "$d/side.png" "$m"

printf 'Rendered: %s %s %s\n' "$d/isometric.png" "$d/top.png" "$d/side.png"
