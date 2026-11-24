#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
source scripts/level-build.sh
wf_level_build "$0" "$@"
cargo build -q --release --offline --manifest-path wftools/wf_attr_edit/Cargo.toml
python3 wflevels/corolla_gauge/palette_assets.py
blender --background --python-exit-code 1 --python wflevels/corolla_gauge/generate.py
bash wftools/wf_blender/build_level_binary.sh corolla_gauge
python3 scripts/attach_indexed_palette.py wflevels/corolla_gauge-standalone.iff wflevels/corolla_gauge/tulip-palettes.bin wflevels/corolla_gauge-standalone.iff
python3 scripts/gen-settings-capabilities.py --oad wfsource/source/oas/corollagaugesettings.oad \
    --inherited-oad wfsource/source/oas/actor.oad --actor-map wflevels/corolla_gauge/actor-map.json \
    --actor-name CorollaGaugeSettings --type CorollaGaugeSettings --title "Corolla Gauge" \
    --out wflevels/corolla_gauge/settings-capabilities.json
