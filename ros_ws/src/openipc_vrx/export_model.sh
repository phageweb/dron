#!/usr/bin/env bash
# Make the YOLO11n (COCO) model for detector_node in ONNX, once.
#
# Ultralytics and PyTorch are only needed for this step, in a temporary nix
# shell (~350 MB download); `nix-collect-garbage` removes them afterwards.
# The weights come from Ultralytics' GitHub and are AGPL-3.0, which is why
# the model stays out of the repository.
set -euo pipefail
out=${1:-$HOME/.cache/openipc_vrx/yolo11n.onnx}
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$(dirname "$out")"
cd "$work"
YOLO_CONFIG_DIR=$work nix shell --impure --expr \
  'let p = (builtins.getFlake "github:NixOS/nixpkgs/b5aa0fbd538984f6e3d201be0005b4463d8b09f8").legacyPackages.x86_64-linux;
   in p.python3.withPackages (q: [ q.ultralytics q.onnx ])' \
  -c python3 -c 'from ultralytics import YOLO; YOLO("yolo11n.pt").export(format="onnx", imgsz=640, opset=17, simplify=False, dynamic=False)'
mv yolo11n.onnx "$out"
echo "model: $out"
