#!/usr/bin/env bash
set -euo pipefail
TANK_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$TANK_ROOT"
export AQUARIUM_TANK=tiger_barbs
export AQUARIUM_SCHOOL_N=49
export AQUARIUM_FOLLOWER_ASSET=barb_refined
blender --background --python-exit-code 1 --python wflevels/aquarium/blender_create_aquarium.py
bash wftools/wf_blender/build_level_binary.sh aquarium_tiger_barbs
