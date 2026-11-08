#!/usr/bin/env bash
set -euo pipefail
REEF_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REEF_ROOT"
source scripts/level-build.sh
wf_level_build "$0" "$@"

blender --background --python-exit-code 1 \
  --python wflevels/aquarium_thai_reef/generate.py -- \
  --repo "$REEF_ROOT" --out "$REEF_ROOT/wflevels/aquarium_thai_reef" --remesh-rocks --bake-light
bash wftools/wf_blender/build_level_binary.sh aquarium_thai_reef
# Static and Room #0 slot budgets for the kit (plan 2026-11-08 W5b); fails the build.
python3 wflevels/aquarium_thai_reef/report_budget.py --cooked --level aquarium_thai_reef

# Level settings object (plan 2026-11-08 W5a): ReefSettings, owned by the Director.
cargo build --release --offline --manifest-path wftools/wf_attr_edit/Cargo.toml
cargo build --release --offline --manifest-path wftools/oas2oad-rs/Cargo.toml
bash wftools/prep/build.sh
wftools/oas2oad-rs/target/release/oas2oad \
  --types="$REEF_ROOT/wfsource/source/oas/types3ds.s" \
  --prep="$REEF_ROOT/wftools/prep/prep" \
  -o "$REEF_ROOT/wflevels/aquarium_thai_reef/settings.oad" "$REEF_ROOT/wflevels/aquarium_thai_reef/settings.oas"
python3 scripts/build-object-properties.py \
  --oad wflevels/aquarium_thai_reef/settings.oad \
  --bindings wflevels/aquarium_thai_reef/settings-bindings.json \
  --actor-map wflevels/aquarium_thai_reef/actor-map.json \
  --out wflevels/aquarium_thai_reef/settings.rprp \
  --level wflevels/aquarium_thai_reef-standalone.iff
