#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
source scripts/level-build.sh
wf_level_build "$0" "$@"
cargo build -q --release --offline --manifest-path wftools/wf_attr_edit/Cargo.toml
blender --background --python-exit-code 1 --python wflevels/bamboo_tipper_pond/generate.py
bash wftools/wf_blender/build_level_binary.sh bamboo_tipper_pond
python3 scripts/gen-settings-capabilities.py --oad wfsource/source/oas/bamboopondsettings.oad \
    --inherited-oad wfsource/source/oas/actor.oad --actor-map wflevels/bamboo_tipper_pond/actor-map.json \
    --actor-name BambooPondSettings --type BambooPondSettings --title "Bamboo Tipper and Pond" \
    --out wflevels/bamboo_tipper_pond/settings-capabilities.json
