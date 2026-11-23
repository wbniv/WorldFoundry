#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
source scripts/level-build.sh
wf_level_build "$0" "$@"
cargo build -q --release --offline --manifest-path wftools/wf_attr_edit/Cargo.toml
blender --background --python-exit-code 1 --python wflevels/lighthouse/generate.py
bash wftools/wf_blender/build_level_binary.sh lighthouse
python3 scripts/gen-settings-capabilities.py --oad wfsource/source/oas/lighthousesettings.oad \
    --inherited-oad wfsource/source/oas/actor.oad --actor-map wflevels/lighthouse/actor-map.json \
    --actor-name LighthouseSettings --type LighthouseSettings --title "Lighthouse" \
    --out wflevels/lighthouse/settings-capabilities.json
