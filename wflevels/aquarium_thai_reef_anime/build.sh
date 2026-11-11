#!/usr/bin/env bash
set -euo pipefail
REEF_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REEF_ROOT"
source scripts/level-build.sh
wf_level_build "$0" "$@"
cargo build --release --offline --manifest-path wftools/wf_attr_edit/Cargo.toml

blender --background --python-exit-code 1 \
  --python wflevels/aquarium_thai_reef/generate.py -- \
  --repo "$REEF_ROOT" \
  --out "$REEF_ROOT/wflevels/aquarium_thai_reef_anime" \
  --level-id aquarium_thai_reef_anime --style anime --remesh-rocks --bake-light
bash wftools/wf_blender/build_level_binary.sh aquarium_thai_reef_anime
# Static and Room #0 slot budgets for the kit (plan 2026-11-08 W5b); fails the build.
python3 wflevels/aquarium_thai_reef/report_budget.py --cooked --level aquarium_thai_reef_anime
