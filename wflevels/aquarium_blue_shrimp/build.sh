#!/usr/bin/env bash
set -euo pipefail
SHRIMP_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$SHRIMP_ROOT"
blender --background --python-exit-code 1 --python wflevels/aquarium_blue_shrimp/blender_create_aquarium_blue_shrimp.py
bash wftools/wf_blender/build_level_binary.sh aquarium_blue_shrimp
