#!/usr/bin/env bash
# aquarium-levels.sh: regenerate the committed Aquarium level outputs, or check that
# they are fresh. One recipe for both: `check` runs `regenerate` on a clean copy of
# the committed inputs and compares every tracked file with the commit.
#
#   regenerate  in the Blender container (docker/Dockerfile.blender, scripts/in-linux-container.sh):
#               the eight tanks of wflevels/aquarium-menu.manifest (the clownfish
#               `aquarium` with task aquarium-level's recipe, the seven others with their
#               build.sh), then wflevels/aquarium-cd.iff and wflevels/aquarium-menu-cd.iff
#               with cdpack. It writes the tracked wflevels/ files in this tree.
#   check       git archive of REF's inputs into a scratch directory, `regenerate` there,
#               then scripts/level-outputs-compare.py: exits 1 with the list of stale
#               tracked files and the command that regenerates them.
#
# Why: a level's committed .lvl/.iff/actor-map.json silently went stale when an input
# changed (exporter, schema, generator, Forth script) and nobody rebuilt it.
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: scripts/aquarium-levels.sh [-h|--help] regenerate
       scripts/aquarium-levels.sh [-h|--help] check [--ref REF] [--keep]

  regenerate    rebuild the eight Aquarium tanks and both aquarium bundles in the
                Blender container and write the tracked wflevels/ outputs here
                (task aquarium-regenerate); commit what changes
  check         rebuild REF's committed inputs (default HEAD) in a scratch copy under
                build-docker/level-check/ and compare every tracked file with REF;
                exit 1 and list the stale files (task aquarium-check)
    --ref REF   the commit to check (default HEAD)
    --keep      keep the scratch copy (default: removed when the check ends)

Generator knobs (TANK_*, AQUARIUM_*, ...) are not forwarded: both commands build
the canonical committed levels. Environment: those of scripts/in-linux-container.sh
(WF_BLENDER_DOCKERFILE=Dockerfile.blender.public where the lab registry is unreachable).
EOF
}

# The committed inputs a rebuild reads (git pathspecs); check archives exactly these.
INPUTS=(wftools wfsource/source scripts docker wflevels/snowgoons-blender
        wflevels/aquarium-menu.manifest ':(glob)wflevels/aquarium*/**' ':(glob)wflevels/aquarium*.iff')
# The seven tanks that have their own build.sh (scripts/level-build.sh).
TANKS=(aquarium_blue_shrimp aquarium_betta aquarium_jellyfish aquarium_lionfish
       aquarium_plants aquarium_arowana aquarium_tiger_barbs)
REGENERATE_CMD="task aquarium-regenerate"

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) aquarium-levels: $*" >&2; }

# Build steps log to build-docker/aquarium-levels.log; a failing step prints its tail.
step() {
    local logf="$root/build-docker/aquarium-levels.log"
    "$@" >>"$logf" 2>&1 || { local rc=$?; tail -30 "$logf" >&2; log "FAILED ($rc): $*"; return "$rc"; }
}

regenerate_in_container() {
    cd "$root"
    mkdir -p build-docker; : > build-docker/aquarium-levels.log
    # shellcheck source=scripts/level-build.sh
    source scripts/level-build.sh
    log "tools (cargo, $(cargo --version | cut -d' ' -f2)); $(blender --version | head -1)"
    step wf_level_build_tools "$root"
    step cargo build -q --release --locked --manifest-path wftools/cdpack-rs/Cargo.toml
    # The clownfish tank: task aquarium-level's recipe (keyboard profile), here in the container.
    log "aquarium (clownfish)"
    step env AQUARIUM_PROFILE=keyboard blender --background --python-exit-code 1 \
        --python wflevels/aquarium/blender_create_aquarium.py
    test -s wflevels/aquarium/aquarium.lev
    step bash wftools/wf_blender/build_level_binary.sh aquarium
    local t
    for t in "${TANKS[@]}"; do
        log "$t"
        step bash "wflevels/$t/build.sh"
    done
    log "bundles: wflevels/aquarium-cd.iff, wflevels/aquarium-menu-cd.iff"
    step wftools/cdpack-rs/target/release/cdpack wfsource/source/game/shell.fth wflevels/aquarium-standalone.iff \
        -o wflevels/aquarium-cd.iff
    step wftools/cdpack-rs/target/release/cdpack wfsource/source/game/shell-menu.fth \
        --manifest wflevels/aquarium-menu.manifest -o wflevels/aquarium-menu-cd.iff
    log "done"
}

regenerate() {
    if [ -n "${WF_IN_CONTAINER:-}" ]; then
        regenerate_in_container
        return
    fi
    # Same container settings as scripts/level-build.sh: crate cache in build-docker/,
    # host networking for a missing locked crate. No generator knobs are forwarded.
    WF_CONTAINER_IMAGE=blender WF_CONTAINER_NETWORK=host WF_CONTAINER_ENV="CARGO_HOME=/build/cargo-home" \
        "$root/scripts/in-linux-container.sh" bash scripts/aquarium-levels.sh regenerate
}

check() {
    local ref=HEAD keep=0
    while [ $# -gt 0 ]; do
        case "$1" in
            --ref) ref="${2:?--ref needs a commit}"; shift 2 ;;
            --keep) keep=1; shift ;;
            *) usage >&2; exit 2 ;;
        esac
    done
    local sha
    sha="$(git -C "$root" rev-parse --verify "$ref^{commit}")"
    mkdir -p "$root/build-docker/level-check"
    local scratch
    scratch="$(mktemp -d "$root/build-docker/level-check/${sha:0:12}.XXXXXX")"
    if [ "$keep" = 0 ]; then
        # shellcheck disable=SC2064  # expand now: the trap must remove this scratch copy
        trap "rm -rf '$scratch'" EXIT
    fi
    log "check ${sha:0:12} ($ref) in $scratch"
    git -C "$root" archive "$sha" -- "${INPUTS[@]}" | tar -x -C "$scratch"
    bash "$scratch/scripts/aquarium-levels.sh" regenerate
    python3 "$root/scripts/level-outputs-compare.py" --repo "$root" --ref "$sha" --tree "$scratch" \
        --regenerate "$REGENERATE_CMD" -- "${INPUTS[@]}"
}

case "${1:-}" in
    -h|--help) usage; exit 0 ;;
    regenerate) shift; [ $# -eq 0 ] || { usage >&2; exit 2; }; regenerate ;;
    check) shift; check "$@" ;;
    *) usage >&2; exit 2 ;;
esac
