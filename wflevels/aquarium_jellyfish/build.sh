#!/usr/bin/env bash
set -euo pipefail
TANK_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$TANK_ROOT"
# Runs in the Blender container (scripts/level-build.sh); WF_LEVEL_BUILD_HOST=1 for the host.
source scripts/level-build.sh
wf_level_build "$0" "$@"
export TANK_PROFILE="${TANK_PROFILE:-remote}"
blender --background --python-exit-code 1 --python wflevels/aquarium_tanks/generate.py -- aquarium_jellyfish
bash wftools/wf_blender/build_level_binary.sh aquarium_jellyfish
cargo build --release --offline --manifest-path wftools/wf_attr_edit/Cargo.toml
cargo build --release --offline --manifest-path wftools/oas2oad-rs/Cargo.toml
bash wftools/prep/build.sh
wftools/oas2oad-rs/target/release/oas2oad \
  --types="$TANK_ROOT/wfsource/source/oas/types3ds.s" \
  --prep="$TANK_ROOT/wftools/prep/prep" \
  -o "$TANK_ROOT/wflevels/aquarium_jellyfish/settings.oad" "$TANK_ROOT/wflevels/aquarium_jellyfish/settings.oas"
python3 scripts/build-object-properties.py \
  --oad wflevels/aquarium_jellyfish/settings.oad \
  --bindings wflevels/aquarium_jellyfish/settings-bindings.json \
  --actor-map wflevels/aquarium_jellyfish/actor-map.json \
  --out wflevels/aquarium_jellyfish/settings.rprp \
  --level wflevels/aquarium_jellyfish-standalone.iff
