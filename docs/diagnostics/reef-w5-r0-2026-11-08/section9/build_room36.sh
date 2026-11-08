#!/usr/bin/env bash
# R0 section 9: realistic P3 with the level's ROOM slot raised 32,000,000 -> 36,000,000 (confirmation probe).
set -euo pipefail
case "${1:-}" in -h|--help) echo "Usage: bash build-docker/r0/build_room36.sh  (re-execs in the Blender container)"; exit 0;; esac
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
source scripts/level-build.sh
wf_level_build "$0" "$@"
R0="$ROOT/build-docker/r0"; dir="$R0/P3room36/aquarium_thai_reef"
R0_LEVEL_DIR="$dir" bash "$R0/build_level_binary_r0.sh" aquarium_thai_reef | tail -2
python3 scripts/build-object-properties.py --oad "$dir/settings.oad" --bindings "$dir/settings-bindings.json" \
  --actor-map "$dir/actor-map.json" --out "$dir/settings.rprp" --level "$R0/P3room36/aquarium_thai_reef-standalone.iff"
sed -e "s#/P3/aquarium_thai_reef-standalone#/P3room36/aquarium_thai_reef-standalone#" "$R0/P3.manifest" > "$R0/P3room36.manifest"
wftools/cdpack-rs/target/release/cdpack wfsource/source/game/shell-menu.fth --manifest "$R0/P3room36.manifest" -o "$R0/P3room36-cd.iff" | head -1
