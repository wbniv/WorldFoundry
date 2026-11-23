#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
source scripts/level-build.sh
wf_level_build "$0" "$@"
cargo build -q --release --offline --manifest-path wftools/wf_attr_edit/Cargo.toml
blender --background --python-exit-code 1 --python wflevels/globe_sun_ring/generate.py
bash wftools/wf_blender/build_level_binary.sh globe_sun_ring
python3 scripts/gen-settings-capabilities.py --oad wfsource/source/oas/globesunringsettings.oad \
    --inherited-oad wfsource/source/oas/actor.oad --actor-map wflevels/globe_sun_ring/actor-map.json \
    --actor-name GlobeSunRingSettings --type GlobeSunRingSettings --title "Globe Sun Ring" \
    --out wflevels/globe_sun_ring/settings-capabilities.json
