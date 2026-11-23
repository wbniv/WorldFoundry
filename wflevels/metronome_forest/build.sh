#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
source scripts/level-build.sh
wf_level_build "$0" "$@"
cargo build -q --release --offline --manifest-path wftools/wf_attr_edit/Cargo.toml
blender --background --python-exit-code 1 --python wflevels/metronome_forest/generate.py
bash wftools/wf_blender/build_level_binary.sh metronome_forest
python3 scripts/gen-settings-capabilities.py --oad wfsource/source/oas/metronomeforestsettings.oad \
    --inherited-oad wfsource/source/oas/actor.oad --actor-map wflevels/metronome_forest/actor-map.json \
    --actor-name MetronomeForestSettings --type MetronomeForestSettings --title "Metronome Forest" \
    --out wflevels/metronome_forest/settings-capabilities.json
