#!/usr/bin/env bash
# Run the material/primitive atlas-addressing regression (tests/texture_atlas_address_test.cc)
# built against the desktop dev engine (scripts/build-wf-game.sh, cmake/wf-game-dev.cmake).
# ctest runs the same executable as `texture_atlas_address`.
set -euo pipefail
case "${1:-}" in -h|--help) echo "Usage: tests/test-texture-atlas.sh   (builds and runs texture_atlas_address_test in build-wf-game/)"; exit 0 ;; esac
root="$(cd "$(dirname "$0")/.." && pwd)"
bash "$root/scripts/build-wf-game.sh" --target texture_atlas_address_test >/tmp/wf-texture-atlas-build.log 2>&1 ||
    { tail -30 /tmp/wf-texture-atlas-build.log >&2; exit 1; }
"$root/build-wf-game/texture_atlas_address_test"
