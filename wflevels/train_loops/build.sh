#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
source scripts/level-build.sh
wf_level_build "$0" "$@"
cargo build -q --release --offline --manifest-path wftools/wf_attr_edit/Cargo.toml
blender --background --python-exit-code 1 --python wflevels/train_loops/generate.py
bash wftools/wf_blender/build_level_binary.sh train_loops
python3 scripts/gen-settings-capabilities.py --oad wfsource/source/oas/trainloopssettings.oad \
    --inherited-oad wfsource/source/oas/actor.oad --actor-map wflevels/train_loops/actor-map.json \
    --actor-name TrainLoopsSettings --type TrainLoopsSettings --title "Train Loops" \
    --out wflevels/train_loops/settings-capabilities.json
