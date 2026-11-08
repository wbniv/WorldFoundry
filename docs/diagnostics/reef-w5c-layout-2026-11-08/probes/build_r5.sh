#!/usr/bin/env bash
# W5c device probe R5: the W5c levels with ReefSettings defaults flipped to Layout Random, Rocks 5,
# Colonies Dense (Seed 0: a new reef each entry), catalog re-attached, packed with the HEAD tanks.
set -euo pipefail
case "${1:-}" in -h|--help) echo "Usage: bash build-docker/r0/build_r5.sh  (re-execs in the Blender container)"; exit 0;; esac
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
source scripts/level-build.sh
wf_level_build "$0" "$@"
R0="$ROOT/build-docker/r0"
for style in aquarium_thai_reef aquarium_thai_reef_anime; do
  dir="$R0/R5/$style"
  python3 scripts/build-object-properties.py --oad "$dir/settings.oad" --bindings "$dir/settings-bindings.json" \
    --actor-map "$dir/actor-map.json" --out "$dir/settings.rprp" --level "$R0/R5/$style-standalone.iff"
done
sed -e "s#^level aquarium_thai_reef-standalone.iff#level $R0/R5/aquarium_thai_reef-standalone.iff#" \
    -e "s#^level aquarium_thai_reef_anime-standalone.iff#level $R0/R5/aquarium_thai_reef_anime-standalone.iff#" \
    -e "s#^level \(aquarium[a-z_]*-standalone.iff\)#level $ROOT/wflevels/\1#" wflevels/aquarium-menu.manifest > "$R0/R5.manifest"
wftools/cdpack-rs/target/release/cdpack wfsource/source/game/shell-menu.fth --manifest "$R0/R5.manifest" -o "$R0/R5-cd.iff" | head -1
