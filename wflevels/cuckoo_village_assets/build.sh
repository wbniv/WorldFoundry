#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
source scripts/level-build.sh
wf_level_build "$0" "$@"
python3 wflevels/cuckoo_village_assets/atlas.py
blender --background --python-exit-code 1 --python wflevels/cuckoo_village_assets/generate.py
bash wftools/wf_blender/build_level_binary.sh cuckoo_village_assets
