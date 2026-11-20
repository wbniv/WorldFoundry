#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
source scripts/level-build.sh
wf_level_build "$0" "$@"
blender --background --python-exit-code 1 --python wflevels/aquarium_sea_stars/generate.py -- --repo "$ROOT" --out "$ROOT/wflevels/aquarium_sea_stars"
bash wftools/wf_blender/build_level_binary.sh aquarium_sea_stars
python3 wflevels/aquarium_sea_stars/report_budget.py
