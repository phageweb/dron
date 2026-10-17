#!/usr/bin/env bash
# Clone the OpenDrone boards at the pinned commits into external/opendrone,
# and run ERC and DRC on each with kicad-cli. Prints a count per check type;
# the full JSON reports land in external/opendrone/reports.
#
#   nix run ./dps#check          # or ./dps/check.sh inside `nix develop ./dps`
set -euo pipefail

# From the working directory: under `nix run` the script lives in the store.
root=$(git rev-parse --show-toplevel)
dest="$root/external/opendrone"
reports="$dest/reports"
mkdir -p "$dest" "$reports"

# repo  commit  project path inside the repo (-: library only)
boards=(
  "OpenESC-20x20    dba7828  hardware/4in1-mini"
  "OpenFC-Lite-Mini d8a10ee  hardware/OpenFC"
  "OpenAIO          986ce1e  hardware/OpenAIO"
  "KiCad-Library    a0173b7  -"
)

for line in "${boards[@]}"; do
  read -r repo commit project <<<"$line"
  dir="$dest/$repo"
  if [ ! -d "$dir/.git" ]; then
    git clone -q "https://github.com/OpenDrone-hw/$repo.git" "$dir"
  fi
  git -C "$dir" -c advice.detachedHead=false checkout -q "$commit"
  git -C "$dir" submodule -q update --init --recursive
  [ "$project" = "-" ] && continue

  name=$(basename "$project")
  echo "== $repo @ $commit"
  kicad-cli sch erc --severity-all --format json \
    -o "$reports/$name.erc.json" "$dir/$project.kicad_sch" >/dev/null
  kicad-cli pcb drc --severity-all --schematic-parity --refill-zones --format json \
    -o "$reports/$name.drc.json" "$dir/$project.kicad_pcb" >/dev/null

  jq -r '[.sheets[].violations[]] | group_by(.severity + " " + .type)
         | map("  ERC \(length)\t\(.[0].severity)\t\(.[0].type)") | .[]' \
    "$reports/$name.erc.json" | sort -k2,2 -k1,1nr
  jq -r '[.violations[], .unconnected_items[], .schematic_parity[]]
         | group_by(.severity + " " + .type)
         | map("  DRC \(length)\t\(.[0].severity)\t\(.[0].type)") | .[]' \
    "$reports/$name.drc.json" | sort -k2,2 -k1,1nr
done
