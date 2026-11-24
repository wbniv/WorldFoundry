#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
source scripts/level-build.sh
wf_level_build "$0" "$@"
cargo build -q --release --offline --manifest-path wftools/wf_attr_edit/Cargo.toml
blender --background --python-exit-code 1 --python wflevels/mirror_haze/generate.py
bash wftools/wf_blender/build_level_binary.sh mirror_haze
python3 scripts/gen-settings-capabilities.py --oad wfsource/source/oas/mirrorhazesettings.oad \
    --inherited-oad wfsource/source/oas/actor.oad --actor-map wflevels/mirror_haze/actor-map.json \
    --actor-name MirrorHazeSettings --type MirrorHazeSettings --title "Mirror and Haze" \
    --out wflevels/mirror_haze/settings-capabilities.json
