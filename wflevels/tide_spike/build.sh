#!/usr/bin/env bash
# Build the Tide Harbour spike levels a, b, c, d (Phase 0) and n, v, g (the night probe): Blender (container) -> .lev -> .lvl/.iff, one directory each.
#   bash wflevels/tide_spike/build.sh [variant ...]        (default: all seven)
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
variants=("$@")
[[ ${#variants[@]} -gt 0 ]] || variants=(a b c d n v g)
for v in "${variants[@]}"; do
    SPIKE_VARIANT="$v" TANK_SPIKE_SUN="${TANK_SPIKE_SUN:-50,70}" TANK_SPIKE_ROOMZ="${TANK_SPIKE_ROOMZ:--90}" blender --background --python-exit-code 1 --python wflevels/tide_spike/blender_create_tide_spike.py
    sed "s/tide_spike/tide_spike_$v/g" wflevels/tide_spike/tide_spike-standalone.iff.txt.in > "wflevels/tide_spike_$v/tide_spike_$v-standalone.iff.txt"
    bash wftools/wf_blender/build_level_binary.sh "tide_spike_$v"
done
