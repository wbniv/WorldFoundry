#!/usr/bin/env bash
# Build the lava lamp clock: Blender authors the scene and the director, the exporter writes the .lev and the
# meshes (MRPH morph chunks included), build_level_binary.sh compiles lava_lamp.iff and the standalone, and the
# phone settings form is regenerated. Runs in the Blender container (scripts/level-build.sh).
# docs/plans/2026-11-26-lava-lamp.md
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
source scripts/level-build.sh
wf_level_build "$0" "$@"
cargo build -q --release --offline --manifest-path wftools/wf_attr_edit/Cargo.toml
blender --background --python-exit-code 1 --python wflevels/lava_lamp/generate.py
bash wftools/wf_blender/build_level_binary.sh lava_lamp
python3 scripts/gen-settings-capabilities.py --oad wfsource/source/oas/lavalampsettings.oad \
    --inherited-oad wfsource/source/oas/actor.oad --actor-map wflevels/lava_lamp/actor-map.json \
    --actor-name LavaLampSettings --type LavaLampSettings --title "Lava lamp" \
    --out wflevels/lava_lamp/settings-capabilities.json
