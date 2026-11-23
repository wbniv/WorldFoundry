#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
source scripts/level-build.sh
wf_level_build "$0" "$@"
cargo build -q --release --offline --manifest-path wftools/wf_attr_edit/Cargo.toml
blender --background --python-exit-code 1 --python wflevels/anamorphic_shards/generate.py
bash wftools/wf_blender/build_level_binary.sh anamorphic_shards
python3 scripts/gen-settings-capabilities.py --oad wfsource/source/oas/anamorphicshardssettings.oad \
    --inherited-oad wfsource/source/oas/actor.oad --actor-map wflevels/anamorphic_shards/actor-map.json \
    --actor-name AnamorphicShardsSettings --type AnamorphicShardsSettings --title "Anamorphic Shards" \
    --out android/screensaver/src/clocks/assets/anamorphic-shards-settings.json
