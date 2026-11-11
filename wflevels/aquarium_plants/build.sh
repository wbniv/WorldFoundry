#!/usr/bin/env bash
set -euo pipefail
TANK_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$TANK_ROOT"
# Runs in the Blender container (scripts/level-build.sh); WF_LEVEL_BUILD_HOST=1 for the host.
source scripts/level-build.sh
wf_level_build "$0" "$@"
export TANK_PROFILE="${TANK_PROFILE:-remote}"
cargo build --release --offline --manifest-path wftools/wf_attr_edit/Cargo.toml
blender --background --python-exit-code 1 --python wflevels/aquarium_tanks/generate.py -- aquarium_plants
bash wftools/wf_blender/build_level_binary.sh aquarium_plants
