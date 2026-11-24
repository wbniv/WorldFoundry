#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
source scripts/level-build.sh
wf_level_build "$0" "$@"
cargo build -q --release --offline --manifest-path wftools/wf_attr_edit/Cargo.toml
blender --background --python-exit-code 1 --python wflevels/moon_lantern/generate.py
bash wftools/wf_blender/build_level_binary.sh moon_lantern
python3 scripts/gen-settings-capabilities.py --oad wfsource/source/oas/moonlanternsettings.oad \
    --inherited-oad wfsource/source/oas/actor.oad --actor-map wflevels/moon_lantern/actor-map.json \
    --actor-name MoonLanternSettings --type MoonLanternSettings --title "Moon Lantern" \
    --out wflevels/moon_lantern/settings-capabilities.json
