#!/usr/bin/env bash
# blender-matrix.sh: run the wf_blender add-on export test against several upstream Blender
# releases, on demand. It replaced the matrix in .github/workflows/blender-addon-tests.yml
# (retired 2026-11-27). Run it before widening the worldfoundry-blender-addons apt pin.
# The local CI's blender-addon step covers only the Blender image's own Blender.
#
# Everything runs in the Blender image (WF_CONTAINER_IMAGE=blender): the official tarballs
# download, verify and unpack there (scripts/install-blender.sh) into
# ~/.cache/blender-matrix-scratch/blender-<version>, which disk-hygiene ages out after
# 7 days. The wf_core wheel is built once with maturin, then the test runs once per version.
# Plan: docs/plans/2026-11-27-retire-github-actions.md (Phase 1, D2)
#
# usage: blender-matrix.sh [VERSION ...]     (default: 4.0.2 4.2.21 4.5.10 5.0.1)
#        blender-matrix.sh -h|--help
# exit:  0 every version passed; 1 at least one failed or skipped; 2 usage
set -euo pipefail
case "${1-}" in
    -h|--help) sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "blender-matrix.sh: unknown option $1" >&2; exit 2 ;;
esac
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
versions=("$@")
[ ${#versions[@]} -gt 0 ] || versions=(4.0.2 4.2.21 4.5.10 5.0.1)
cache="$HOME/.cache/blender-matrix-scratch"
mkdir -p "$cache" "$HOME/.cache/wf-local-ci-cargo"
export WF_CONTAINER_IMAGE=blender
export WF_CONTAINER_MOUNTS="$cache:/opt/blender-matrix $HOME/.cache/wf-local-ci-cargo:/tmp/cargo"
export WF_CONTAINER_LABELS="org.wbniv.project=WorldFoundry-wbniv org.wbniv.purpose=blender-matrix org.wbniv.source=scripts/blender-matrix.sh"
log() { printf '%s blender-matrix: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

log "building the wf_core wheel"
(cd "$repo" && scripts/in-linux-container.sh bash -c 'cd wftools/wf_py && maturin build --release --quiet')

declare -A verdict
for v in "${versions[@]}"; do
    log "Blender $v"
    rc=0
    (cd "$repo" && WF_CONTAINER_ENV="BL=$v" scripts/in-linux-container.sh bash -c 'set -euo pipefail
        bash scripts/install-blender.sh "$BL" "/opt/blender-matrix/blender-$BL"
        BLENDER_BIN="/opt/blender-matrix/blender-$BL/blender" \
            python3 -m pytest -v -rs -p no:cacheprovider tests/test_blender_addon_export.py') \
        >"$cache/blender-$v.log" 2>&1 || rc=$?
    summary="$(grep -E '^=+ .* in [0-9.]+s' "$cache/blender-$v.log" | tail -1 || true)"
    if [ "$rc" -eq 0 ] && [[ "$summary" == *passed* ]] && [[ "$summary" != *skipped* ]]; then
        verdict[$v]=PASS
    else
        verdict[$v]="FAIL (log: $cache/blender-$v.log)"
    fi
    log "Blender $v: ${verdict[$v]}"
done

echo
status=0
for v in "${versions[@]}"; do
    printf '  %-8s %s\n' "$v" "${verdict[$v]}"
    [ "${verdict[$v]}" = PASS ] || status=1
done
exit "$status"
