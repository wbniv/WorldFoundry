#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
source scripts/level-build.sh
wf_level_build "$0" "$@"
cargo build -q --release --offline --manifest-path wftools/wf_attr_edit/Cargo.toml
blender --background --python-exit-code 1 --python wflevels/lava_lamp_digits/generate.py
bash wftools/wf_blender/build_level_binary.sh lava_lamp_digits
python3 scripts/gen-settings-capabilities.py --oad wfsource/source/oas/lavalampdigitssettings.oad \
    --inherited-oad wfsource/source/oas/actor.oad --actor-map wflevels/lava_lamp_digits/actor-map.json \
    --actor-name LavaLampDigitsSettings --type LavaLampDigitsSettings --title "Lava-lamp digits" \
    --out wflevels/lava_lamp_digits/settings-capabilities.json
