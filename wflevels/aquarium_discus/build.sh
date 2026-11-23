#!/usr/bin/env bash
set -euo pipefail
TANK_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$TANK_ROOT"
# Runs in the Blender container (scripts/level-build.sh); WF_LEVEL_BUILD_HOST=1 for the host.
# The Discus tank: the Tiger Barbs tank's school framework with the discus asset's mesh
# (wflevels/aquarium/discus_school.py). Plan: docs/plans/2026-11-22-discus-tank.md.
source scripts/level-build.sh
wf_level_build "$0" "$@"
export AQUARIUM_TANK=discus
export AQUARIUM_SCHOOL_N=29
export AQUARIUM_FOLLOWER_ASSET=discus
blender --background --python-exit-code 1 --python wflevels/aquarium/blender_create_aquarium.py
bash wftools/wf_blender/build_level_binary.sh aquarium_discus
python3 scripts/attach_indexed_palette.py wflevels/aquarium_discus-standalone.iff wflevels/aquarium_discus/discus-palettes.bin wflevels/aquarium_discus-standalone.iff
