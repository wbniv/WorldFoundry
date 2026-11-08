#!/usr/bin/env bash
# R0 Pixel bundles: each probe's reef style as menu row 0, so the coordinator's scene=clownfish (index 0)
# launches it on the phone (scripted keys are TV-only). Runs cdpack in the Blender container.
set -euo pipefail
case "${1:-}" in -h|--help) echo "Usage: bash build-docker/r0/build_pixel.sh  (re-execs in the Blender container)"; exit 0;; esac
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
source scripts/level-build.sh
wf_level_build "$0" "$@"
R0="$ROOT/build-docker/r0"
for probe in P0 P1 P2 P3; do
  for style in aquarium_thai_reef aquarium_thai_reef_anime; do
    m="$R0/pixel-$probe-$style.manifest"
    { echo "title WF Aquarium"; echo "prompt Choose a tank"; echo "level $R0/$probe/$style-standalone.iff | R0 $probe $style";
      grep '^level ' "$R0/$probe.manifest"; } > "$m"
    wftools/cdpack-rs/target/release/cdpack wfsource/source/game/shell-menu.fth --manifest "$m" -o "$R0/pixel-$probe-$style-cd.iff" | head -1
  done
done
