#!/usr/bin/env bash
set -euo pipefail
TANK_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$TANK_ROOT"
blender --background --python-exit-code 1 --python wflevels/aquarium_tanks/generate.py -- aquarium_jellyfish
bash wftools/wf_blender/build_level_binary.sh aquarium_jellyfish
