#!/usr/bin/env bash
# Build the Tide Harbour level: Blender (container) -> tide_harbour.lev -> .lvl/.iff -> wflevels/tide_harbour-standalone.iff.
#   bash wflevels/tide_harbour/build.sh            (task tide-harbour-level)
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
# The build asks the catalog tool for TideHarbourSettings' field indices (as aquarium_sea_stars does).
cargo build -q --release --offline --manifest-path wftools/wf_attr_edit/Cargo.toml
blender --background --python-exit-code 1 --python wflevels/tide_harbour/blender_create_tide_harbour.py
bash wftools/wf_blender/build_level_binary.sh tide_harbour
# The phone's Dream form and the coordinator read the same fields from this capabilities asset (plan D13, step 4).
python3 scripts/gen-settings-capabilities.py --oad wfsource/source/oas/tideharboursettings.oad \
    --inherited-oad wfsource/source/oas/actor.oad --actor-map wflevels/tide_harbour/actor-map.json \
    --actor-name TideHarbourSettings --type TideHarbourSettings --title "Tide Harbour" \
    --out android/screensaver/src/clocks/assets/tide-harbour-settings.json
