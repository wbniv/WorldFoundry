#!/usr/bin/env bash
# Build close-up diagnostic variants of both reef styles centred on the
# Christmas tree worms (generate.py --verification-target worms): the fish
# far away (crowns open) and next to the worms (crowns retracted).
#
# Usage: bash docs/diagnostics/reef-worms-2026-11-08/build-worm-views.sh [-h]
#
# Runs in the Blender container. Variants are cooked in a symlinked mini-tree
# under build-docker/reef-worm-diag/<variant>/ so wflevels/ is never touched;
# each ends as build-docker/reef-worm-diag/<variant>/wflevels/<level>-standalone.iff.
set -euo pipefail
case "${1:-}" in -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;; esac

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
if [ -z "${WF_IN_CONTAINER:-}" ]; then
    WF_CONTAINER_IMAGE=blender WF_CONTAINER_NETWORK=host \
        exec "$ROOT/scripts/in-linux-container.sh" bash docs/diagnostics/reef-worms-2026-11-08/build-worm-views.sh "$@"
fi
cd "$ROOT"
WORK="$ROOT/build-docker/reef-worm-diag"

build() {   # variant level-id style far(0|1)
    local variant="$1" level="$2" style="$3" far="$4" tree
    tree="$WORK/$variant"
    rm -rf "$tree"
    mkdir -p "$tree/wflevels" "$tree/wftools/wf_blender"
    for link in wfsource wftools/iffcomp-rs wftools/levcomp-rs wftools/textile-rs; do
        ln -s "$ROOT/$link" "$tree/$link"
    done
    cp wftools/wf_blender/build_level_binary.sh "$tree/wftools/wf_blender/"
    # Static inputs the cook needs (standalone recipe, textile flags, configs).
    mkdir -p "$tree/wflevels/$level"
    find "wflevels/$level" -maxdepth 1 -type f \( -name '*.iff.txt' -o -name 'textile.flags' -o -name 'mesh.flags' \) \
        -exec cp {} "$tree/wflevels/$level/" \;
    local args=(--repo "$ROOT" --out "$tree/wflevels/$level" --level-id "$level" --style "$style"
                --remesh-rocks --bake-light --verification-target worms)
    [ "$far" = 1 ] && args+=(--verification-far)
    blender --background --python-exit-code 1 --python wflevels/aquarium_thai_reef/generate.py -- "${args[@]}"
    bash "$tree/wftools/wf_blender/build_level_binary.sh" "$level"
}

build realistic-far aquarium_thai_reef realistic 1
build realistic-near aquarium_thai_reef realistic 0
build anime-far aquarium_thai_reef_anime anime 1
build anime-near aquarium_thai_reef_anime anime 0
ls -la "$WORK"/*/wflevels/*-standalone.iff
