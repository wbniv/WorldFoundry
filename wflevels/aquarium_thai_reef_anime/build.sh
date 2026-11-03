#!/usr/bin/env bash
set -euo pipefail
REEF_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REEF_ROOT"
source scripts/level-build.sh
wf_level_build "$0" "$@"

blender --background --python-exit-code 1 \
  --python wflevels/aquarium_thai_reef/generate.py -- \
  --repo "$REEF_ROOT" \
  --out "$REEF_ROOT/wflevels/aquarium_thai_reef_anime" \
  --level-id aquarium_thai_reef_anime --style anime --remesh-rocks --bake-light
bash wftools/wf_blender/build_level_binary.sh aquarium_thai_reef_anime
