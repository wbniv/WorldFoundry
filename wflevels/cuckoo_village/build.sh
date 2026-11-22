#!/usr/bin/env bash
# Build the Cuckoo Village level: Blender (container) -> cuckoo_village.lev -> .lvl/.iff.
#   bash wflevels/cuckoo_village/build.sh
set -euo pipefail
case "${1:-}" in
    -h|--help)
        sed -n '2,3p' "$0" | sed 's/^# \{0,1\}//'
        echo "Runs in the Blender container (scripts/level-build.sh); WF_LEVEL_BUILD_HOST=1 for the host."
        exit 0 ;;
esac
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
# shellcheck source=scripts/level-build.sh
source scripts/level-build.sh
wf_level_build "$0" "$@"
blender --background --python-exit-code 1 --python wflevels/cuckoo_village/blender_create_cuckoo_village.py
# CANDLE_FLAMES=deform (flicker plan, Option B): bind each tree's flames to ten DFRM curves in the exported meshes
if [ "${CANDLE_FLAMES:-static}" = deform ]; then python3 wflevels/cuckoo_village/flame_rig.py; fi
bash wftools/wf_blender/build_level_binary.sh cuckoo_village
