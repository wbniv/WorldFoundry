#!/usr/bin/env bash
# Build the Dutch Cuckoo Village level: Blender (container) -> dutch_cuckoo_village.lev -> .lvl/.iff.
#   bash wflevels/dutch_cuckoo_village/build.sh
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
if [[ ! -x wftools/wf_attr_edit/target/release/catalog ]]; then
    cargo build -q --release --locked --manifest-path wftools/wf_attr_edit/Cargo.toml --bin catalog
fi
blender --background --python-exit-code 1 --python wflevels/dutch_cuckoo_village/generate.py
bash wftools/wf_blender/build_level_binary.sh dutch_cuckoo_village
python3 scripts/gen-settings-capabilities.py --oad wfsource/source/oas/dutchcuckoovillagesettings.oad \
    --inherited-oad wfsource/source/oas/actor.oad --actor-map wflevels/dutch_cuckoo_village/actor-map.json \
    --actor-name DutchCuckooVillageSettings --type DutchCuckooVillageSettings --title "Dutch Cuckoo Village" \
    --out wflevels/dutch_cuckoo_village/settings-capabilities.json
