#!/usr/bin/env bash
set -euo pipefail
# Planted Tank screensaver level: Blender generates the plants-only scene and exports the
# .lev, then scripts/build-aquarium-screensaver-levels.py planted compiles it, attaches the
# PlantedTankSettings catalog and packs wflevels/planted-screensaver-cd.iff.
TANK_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$TANK_ROOT"
# Runs in the Blender container (scripts/level-build.sh); WF_LEVEL_BUILD_HOST=1 for the host.
source scripts/level-build.sh
wf_level_build "$0" "$@"
export TANK_PROFILE="${TANK_PROFILE:-remote}"
blender --background --python-exit-code 1 --python wflevels/aquarium_tanks/generate.py -- planted_tank_screensaver
cargo build --release --offline --manifest-path wftools/wf_attr_edit/Cargo.toml
cargo build --release --offline --manifest-path wftools/oas2oad-rs/Cargo.toml
cargo build --release --offline --manifest-path wftools/cdpack-rs/Cargo.toml
# prep is a C++ tool; build it here so it matches the libstdc++ it runs against.
bash wftools/prep/build.sh
python3 scripts/build-aquarium-screensaver-levels.py planted
