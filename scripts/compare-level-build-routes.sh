#!/usr/bin/env bash
# compare-level-build-routes.sh: build each aquarium tank twice, once with the host's
# blender (WF_LEVEL_BUILD_HOST=1, the pre-container route) and once in the Blender
# container, and compare every output file by sha256. Exits 1 if any tank differs.
# Plan: docs/plans/2026-10-16-blender-in-container.md (the byte-identical check).
set -euo pipefail

TANKS_DEFAULT=(aquarium_jellyfish aquarium_blue_shrimp aquarium_lionfish aquarium_betta
               aquarium_plants aquarium_arowana aquarium_tiger_barbs)

usage() {
    cat <<EOF
Usage: scripts/compare-level-build-routes.sh [-h|--help] [TANK ...]

Builds each TANK (default: all seven aquarium tanks) on the host and in the
container, hashes every file under wflevels/TANK/ plus wflevels/TANK.iff and
wflevels/TANK-standalone.iff after each build, prints a table and restores the
committed files. Refuses to run when those paths have uncommitted changes.
Logs and manifests go to build-docker/route-compare/.
EOF
}
case "${1:-}" in -h|--help) usage; exit 0 ;; esac

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
tanks=("$@")
[ ${#tanks[@]} -gt 0 ] || tanks=("${TANKS_DEFAULT[@]}")
out="$root/build-docker/route-compare"
mkdir -p "$out"

paths_of() { printf '%s\n' "wflevels/$1" "wflevels/$1.iff" "wflevels/$1-standalone.iff"; }

for t in "${tanks[@]}"; do
    [ -f "wflevels/$t/build.sh" ] || { echo "no wflevels/$t/build.sh" >&2; exit 2; }
    mapfile -t p < <(paths_of "$t")
    if [ -n "$(git status --porcelain -- "${p[@]}")" ]; then
        echo "wflevels/$t has uncommitted changes; commit or set them aside first" >&2
        exit 2
    fi
done

# manifest TANK ROUTE: sha256 of every file the tank's build can write, build.sh excluded.
manifest() {
    local t="$1" route="$2"
    { find "wflevels/$t" -type f ! -path '*/__pycache__/*' ! -name build.sh -print0
      printf '%s\0' "wflevels/$t.iff" "wflevels/$t-standalone.iff"; } \
        | sort -z | xargs -0 sha256sum > "$out/$t.$route.sha256"
}

status=0
printf '%-22s %-29s %-16s %-16s %s\n' tank file host container result
for t in "${tanks[@]}"; do
    mapfile -t p < <(paths_of "$t")
    failed=""
    for route in host container; do
        if [ "$route" = host ]; then
            WF_LEVEL_BUILD_HOST=1 bash "wflevels/$t/build.sh" >"$out/$t.$route.log" 2>&1 || failed+=" $route"
        else
            bash "wflevels/$t/build.sh" >"$out/$t.$route.log" 2>&1 || failed+=" $route"
        fi
        manifest "$t" "$route"
        git checkout -q -- "${p[@]}"
    done
    # A failed build leaves the committed files behind, so comparing would only compare
    # leftovers: report the failure and skip the tank.
    if [ -n "$failed" ]; then
        echo "$t: BUILD FAILED ($failed ), comparison skipped; see $out/$t.<route>.log"
        status=1
        continue
    fi
    for f in "wflevels/$t/$t.lvl" "wflevels/$t.iff" "wflevels/$t-standalone.iff"; do
        h=$(grep -F "  $f" "$out/$t.host.sha256" | cut -c1-16 || true)
        c=$(grep -F "  $f" "$out/$t.container.sha256" | cut -c1-16 || true)
        r=same; [ "$h" = "$c" ] || { r=DIFFERENT; status=1; }
        printf '%-22s %-29s %-16s %-16s %s\n' "$t" "${f#wflevels/}" "$h" "$c" "$r"
    done
    n=$(diff "$out/$t.host.sha256" "$out/$t.container.sha256" | grep -c '^<' || true)
    total=$(wc -l < "$out/$t.host.sha256")
    echo "$t: all files: $((total - n))/$total identical"
    [ "$n" = 0 ] || status=1
done
exit "$status"
