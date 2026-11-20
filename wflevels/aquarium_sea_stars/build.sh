#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
source scripts/level-build.sh
wf_level_build "$0" "$@"
# --empty builds the static tank with no animated actors (the early cast1 gate,
# verification step 10). It overwrites this level's outputs; rebuild without it to restore.
EXTRA=()
for arg in "$@"; do
    case "$arg" in
        -h|--help) echo "Usage: bash $0 [--empty]"; exit 0 ;;
        --empty) EXTRA+=(--empty) ;;
        *) echo "unknown argument: $arg" >&2; exit 2 ;;
    esac
done
blender --background --python-exit-code 1 --python wflevels/aquarium_sea_stars/generate.py -- --repo "$ROOT" --out "$ROOT/wflevels/aquarium_sea_stars" "${EXTRA[@]}"
bash wftools/wf_blender/build_level_binary.sh aquarium_sea_stars
python3 wflevels/aquarium_sea_stars/report_budget.py
