#!/usr/bin/env bash
# Build the Minute Machine level: Blender (container) -> minute_machine.lev -> .lvl/.iff.
#   bash wflevels/minute_machine/build.sh            (task minute-machine-level)
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
blender --background --python-exit-code 1 --python wflevels/minute_machine/blender_create_minute_machine.py
bash wftools/wf_blender/build_level_binary.sh minute_machine
