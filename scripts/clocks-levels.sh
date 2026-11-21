#!/usr/bin/env bash
# clocks-levels.sh: regenerate the committed WF Clocks outputs, or check that they are fresh.
# The aquarium's recipe (scripts/aquarium-levels.sh) for the clocks: `check` runs `regenerate` on a
# clean copy of the committed inputs and compares every tracked output with the commit.
#
#   regenerate  in the Blender container (docker/Dockerfile.blender, scripts/in-linux-container.sh):
#               every clock of wflevels/clocks-menu.manifest with its wflevels/<id>/build.sh, then
#               wflevels/clocks-cd.iff with cdpack (scripts/pack-clocks-bundle.py). It writes the
#               tracked wflevels/ files in this tree.
#   check       git archive of REF's inputs into a scratch directory, `regenerate` there, then
#               scripts/level-outputs-compare.py: exits 1 with the list of stale tracked files.
#
# Why (plan docs/plans/2026-11-21-tide-harbour-clock.md, Q12): the clocks commit their built levels
# and bundle as the aquarium does, so a changed input (exporter, schema, generator, director) cannot
# ship a stale bundle.
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: scripts/clocks-levels.sh [-h|--help] regenerate
       scripts/clocks-levels.sh [-h|--help] check [--ref REF] [--keep]

  regenerate    rebuild every clock of wflevels/clocks-menu.manifest and wflevels/clocks-cd.iff in
                the Blender container and write the tracked wflevels/ outputs here
                (task clocks-regenerate); commit what changes
  check         rebuild REF's committed inputs (default HEAD) in a scratch copy under
                build-docker/level-check/ and compare every tracked output with REF;
                exit 1 and list the stale files (task clocks-check)
    --ref REF   the commit to check (default HEAD)
    --keep      keep the scratch copy (default: removed when the check ends)

Environment: those of scripts/in-linux-container.sh (WF_BLENDER_DOCKERFILE=Dockerfile.blender.public
where the lab registry is unreachable).
EOF
}

# The committed inputs a rebuild reads (git pathspecs); check archives exactly these. Minute Machine still
# imports the Snowgoons scaffold (its baseline retrofit is a TODO item), so that level is an input too.
INPUTS=(wftools wfsource/source scripts docker wflevels/snowgoons-blender wflevels/clocks-menu.manifest
        wflevels/clock_common wflevels/minute_machine wflevels/tide_harbour
        ':(glob)wflevels/minute_machine*.iff' ':(glob)wflevels/tide_harbour*.iff' wflevels/clocks-cd.iff)
REGENERATE_CMD="task clocks-regenerate"

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) clocks-levels: $*" >&2; }

step() {
    local logf="$root/build-docker/clocks-levels.log"
    "$@" >>"$logf" 2>&1 || { local rc=$?; tail -30 "$logf" >&2; log "FAILED ($rc): $*"; return "$rc"; }
}

regenerate_in_container() {
    cd "$root"
    mkdir -p build-docker; : > build-docker/clocks-levels.log
    # shellcheck source=scripts/level-build.sh
    source scripts/level-build.sh
    log "tools (cargo, $(cargo --version | cut -d' ' -f2)); $(blender --version | head -1)"
    step wf_level_build_tools "$root"
    step cargo build -q --release --locked --manifest-path wftools/cdpack-rs/Cargo.toml
    local id
    for id in $(python3 -c 'import sys; sys.path.insert(0, "scripts"); import level_manifest; print(" ".join(level_manifest.read("wflevels/clocks-menu.manifest").ids))'); do
        log "$id"
        step bash "wflevels/$id/build.sh"
    done
    log "bundle: wflevels/clocks-cd.iff"
    step env WF_CDPACK=wftools/cdpack-rs/target/release/cdpack python3 scripts/pack-clocks-bundle.py
    log "done"
}

regenerate() {
    if [ -n "${WF_IN_CONTAINER:-}" ]; then
        regenerate_in_container
        return
    fi
    WF_CONTAINER_IMAGE=blender WF_CONTAINER_NETWORK=host WF_CONTAINER_ENV="CARGO_HOME=/build/cargo-home" \
        "$root/scripts/in-linux-container.sh" bash scripts/clocks-levels.sh regenerate
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
    scratch="$(mktemp -d "$root/build-docker/level-check/clocks-${sha:0:12}.XXXXXX")"
    if [ "$keep" = 0 ]; then
        # shellcheck disable=SC2064  # expand now: the trap must remove this scratch copy
        trap "rm -rf '$scratch'" EXIT
    fi
    log "check ${sha:0:12} ($ref) in $scratch"
    git -C "$root" archive "$sha" -- "${INPUTS[@]}" | tar -x -C "$scratch"
    bash "$scratch/scripts/clocks-levels.sh" regenerate
    python3 "$root/scripts/level-outputs-compare.py" --repo "$root" --ref "$sha" --tree "$scratch" \
        --regenerate "$REGENERATE_CMD" -- "${INPUTS[@]}"
}

case "${1:-}" in
    -h|--help) usage; exit 0 ;;
    regenerate) shift; [ $# -eq 0 ] || { usage >&2; exit 2; }; regenerate ;;
    check) shift; check "$@" ;;
    *) usage >&2; exit 2 ;;
esac
