#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
source scripts/level-build.sh
wf_level_build "$0" "$@"
convert wflevels/cuckoo_village_layout/carved-wood-source.png -resize 1024x1024! -type TrueColor wflevels/cuckoo_village_layout/tower-carved-wood.tga
blender --background --python-exit-code 1 --python wflevels/cuckoo_village_layout/generate.py
bash wftools/wf_blender/build_level_binary.sh cuckoo_village_layout
