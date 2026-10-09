#!/usr/bin/env bash
set -euo pipefail
TANK_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$TANK_ROOT"
export TANK_PROFILE="${TANK_PROFILE:-remote}"
blender --background --python-exit-code 1 --python wflevels/aquarium_tanks/generate.py -- aquarium_plants
bash wftools/wf_blender/build_level_binary.sh aquarium_plants
cargo build --release --offline --manifest-path wftools/wf_attr_edit/Cargo.toml
cargo build --release --offline --manifest-path wftools/oas2oad-rs/Cargo.toml
wftools/oas2oad-rs/target/release/oas2oad \
  --types="$TANK_ROOT/wfsource/source/oas/types3ds.s" \
  --prep="$TANK_ROOT/wftools/prep/prep" \
  -o "$TANK_ROOT/wflevels/aquarium_plants/settings.oad" "$TANK_ROOT/wflevels/aquarium_plants/settings.oas"
python3 scripts/build-object-properties.py \
  --oad wflevels/aquarium_plants/settings.oad \
  --bindings wflevels/aquarium_plants/settings-bindings.json \
  --actor-map wflevels/aquarium_plants/actor-map.json \
  --out wflevels/aquarium_plants/settings.rprp \
  --include wflevels/aquarium_plants/settings-catalog.inc \
  --level wflevels/aquarium_plants-standalone.iff
