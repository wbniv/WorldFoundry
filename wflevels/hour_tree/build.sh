#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
source scripts/level-build.sh
wf_level_build "$0" "$@"
cargo build -q --release --offline --manifest-path wftools/wf_attr_edit/Cargo.toml
blender --background --python-exit-code 1 --python wflevels/hour_tree/generate.py
bash wftools/wf_blender/build_level_binary.sh hour_tree
python3 scripts/gen-settings-capabilities.py --oad wfsource/source/oas/hourtreesettings.oad \
    --inherited-oad wfsource/source/oas/actor.oad --actor-map wflevels/hour_tree/actor-map.json \
    --actor-name HourTreeSettings --type HourTreeSettings --title "Hour Tree" \
    --out wflevels/hour_tree/settings-capabilities.json
