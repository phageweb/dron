#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
scad_bin="${1:-openscad}"
common=(--imgsize=1400,1050 --viewall --autocenter)
"$scad_bin" "${common[@]}" --camera=0,0,0,60,0,35,350 -o drone_with_d500.png pavo20_pro_assembly.scad
"$scad_bin" "${common[@]}" --camera=0,0,0,60,0,35,350 -D 'lidar_enabled=false' -o drone_without_d500.png pavo20_pro_assembly.scad
"$scad_bin" "${common[@]}" --camera=0,0,0,70,0,215,220 -D 'part="assembly"' -D 'show_hardware=false' -D 'show_cg=false' -o holder_rear.png pavo20_pro_assembly.scad
"$scad_bin" "${common[@]}" --camera=0,0,0,65,0,35,220 -D 'part="assembly"' -D 'lidar_enabled=false' -D 'show_cg=false' -o holder_front.png pavo20_pro_assembly.scad
"$scad_bin" "${common[@]}" --camera=0,0,0,90,0,90,350 -D 'show_cg=false' -o drone_side.png pavo20_pro_assembly.scad
cp -- holder_front.png preview.png
