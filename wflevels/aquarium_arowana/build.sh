#!/usr/bin/env bash
set -euo pipefail
TANK_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$TANK_ROOT"
# One-button remote plus desktop depth keys; touch can still be selected explicitly.
export TANK_PROFILE="${TANK_PROFILE:-remote}"
blender --background --python-exit-code 1 --python wflevels/aquarium_arowana/generate.py
bash wftools/wf_blender/build_level_binary.sh aquarium_arowana
