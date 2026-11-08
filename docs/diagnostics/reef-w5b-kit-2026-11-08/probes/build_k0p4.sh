#!/usr/bin/env bash
# R0 probes K0 and P4 (plan W5b): compile the copied kit levels with the wflevels cook tools, attach
# the ReefSettings catalog, and pack one Aquarium menu cd.iff per probe. Runs in the Blender container.
set -euo pipefail
case "${1:-}" in -h|--help) echo "Usage: bash build-docker/r0/build_k0p4.sh  (re-execs in the Blender container)"; exit 0;; esac
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
source scripts/level-build.sh
wf_level_build "$0" "$@"
for crate in wf_attr_edit cdpack-rs; do cargo build -q --release --offline --manifest-path "wftools/$crate/Cargo.toml"; done
R0="$ROOT/build-docker/r0"
for probe in K0 P4; do
  for style in aquarium_thai_reef aquarium_thai_reef_anime; do
    dir="$R0/$probe/$style"
    R0_LEVEL_DIR="$dir" bash "$R0/build_level_binary_r0.sh" "$style" | tail -1
    python3 scripts/build-object-properties.py --oad "$dir/settings.oad" --bindings "$dir/settings-bindings.json" \
      --actor-map "$dir/actor-map.json" --out "$dir/settings.rprp" --level "$R0/$probe/$style-standalone.iff"
  done
  sed -e "s#^level aquarium_thai_reef-standalone.iff#level $R0/$probe/aquarium_thai_reef-standalone.iff#" \
      -e "s#^level aquarium_thai_reef_anime-standalone.iff#level $R0/$probe/aquarium_thai_reef_anime-standalone.iff#" \
      -e "s#^level \(aquarium[a-z_]*-standalone.iff\)#level $ROOT/wflevels/\1#" wflevels/aquarium-menu.manifest > "$R0/$probe.manifest"
  wftools/cdpack-rs/target/release/cdpack wfsource/source/game/shell-menu.fth --manifest "$R0/$probe.manifest" -o "$R0/$probe-cd.iff" | head -1
done
