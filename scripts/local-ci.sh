#!/usr/bin/env bash
# local-ci.sh: the local CI. Builds wf_game and runs the renderer-freshness and snowgoons
# arena-faces tests on one commit, in a throwaway sparse clone, in the Linux test container.
# Plan: docs/plans/2026-11-14-local-ci.md. Installed as a systemd user timer by
# scripts/install-local-ci.sh (which runs this with --poll).
set -euo pipefail

usage() {
    cat <<'EOF2'
Usage: scripts/local-ci.sh [-h|--help] [--poll] [--tests-from REV] [--builder B] [--keep N] [--no-notify] [COMMIT]

Builds wf_game and runs the CI tests on COMMIT (default: origin/2026-new-level, fetched
first) in a throwaway sparse clone under ~/.cache/wf-local-ci-scratch, never in this
checkout. Every build and test runs in the wf-linux-test container.

Steps:   build            the engine, by --builder (below)
         arena-faces-up   tests/test_snowgoons_arena_faces_up.py
         renderer-fresh   tests/test_renderer_references_fresh.py (under xvfb-run)
A pytest skip counts as a failure.

Options:
  --poll            timer mode: do nothing if COMMIT is the one the last --poll took
  --tests-from REV  run REV's copies of the tests and their harness against COMMIT
                    (proves the guards catch a bug that predates them)
  --builder B       dev (default): build-wf-game-container.sh --dev, the engine `task build`
                    builds (cmake/wf-game-dev.cmake: Debug, ASan, WF_DESIGNER_CHEATS, so the
                    Linux GL --capture-frame the freshness test needs works)
                    release: build-wf-game-container.sh (CMake Release; no Linux capture,
                    so renderer-fresh fails on it)
                    build_game and cmake are the old names of dev and release
  --keep N          keep the newest N result directories (default 20)
  --no-notify       no desktop notification on failure

The build scripts (scripts/build-wf-game.sh, build-wf-game-container.sh,
in-linux-container.sh) always come from this checkout; cmake/wf-game-dev.cmake comes
from it only when the commit has none. When the commit's CMakeLists.txt predates
WF_DESIGNER_CHEATS, the dev builder passes -DCMAKE_CXX_FLAGS=-DDESIGNER_CHEATS=1 instead.

Results: build-docker/local-ci/<sha12>[-tests-<rev12>]/ (summary.txt, result.tsv, one log
per step), and build-docker/local-ci/latest (a copy of the newest summary).
Exit: 0 all passed, nothing new, or another run holds the lock; 1 a step failed;
      2 usage or preflight error (e.g. less than WF_CI_MIN_FREE_GB + WF_CI_BUILD_GB free).

Environment:
  WF_CI_MIN_FREE_GB   free-disk floor in GB (default 15) that the run must not cross
  WF_CI_BUILD_GB      what one run takes at its peak, in GB (default 5: the clone, its
                      container copy and the dev engine's ASan build measured 4.0 GB);
                      a run starts only with WF_CI_MIN_FREE_GB + WF_CI_BUILD_GB free
  WF_CI_SCRATCH       clone parent (default ~/.cache/wf-local-ci-scratch; disk-hygiene
                      ages out anything a killed run leaves there)
  WF_CI_RESULTS       results directory (default <repo>/build-docker/local-ci)
  WF_CI_BRANCH        branch polled on origin (default 2026-new-level)
  WF_CI_BUILDER       default for --builder (dev)
  WF_CONTAINER_MEMORY container memory cap (default here 8g)
EOF2
}

poll=0 tests_from="" builder="${WF_CI_BUILDER:-dev}" keep=20 notify=1 commit=""
while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --poll) poll=1; shift ;;
        --tests-from) [ $# -ge 2 ] || { usage >&2; exit 2; }; tests_from="$2"; shift 2 ;;
        --builder) [ $# -ge 2 ] || { usage >&2; exit 2; }; builder="$2"; shift 2 ;;
        --keep) [ $# -ge 2 ] || { usage >&2; exit 2; }; keep="$2"; shift 2 ;;
        --no-notify) notify=0; shift ;;
        -*) echo "local-ci: unknown option $1" >&2; usage >&2; exit 2 ;;
        *) [ -z "$commit" ] || { usage >&2; exit 2; }; commit="$1"; shift ;;
    esac
done
case "$keep" in ''|*[!0-9]*) echo "local-ci: --keep needs a number" >&2; exit 2 ;; esac
case "$builder" in
    dev|release) ;;
    build_game) builder=dev ;;      # engine/build_game.sh retired (docs/plans/2026-11-14-single-desktop-build.md)
    cmake) builder=release ;;
    *) echo "local-ci: --builder is dev or release" >&2; exit 2 ;;
esac

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
branch="${WF_CI_BRANCH:-2026-new-level}"
results="${WF_CI_RESULTS:-$root/build-docker/local-ci}"
scratch="${WF_CI_SCRATCH:-$HOME/.cache/wf-local-ci-scratch}"
min_free="${WF_CI_MIN_FREE_GB:-15}"
build_gb="${WF_CI_BUILD_GB:-5}"
export WF_CONTAINER_MEMORY="${WF_CONTAINER_MEMORY:-8g}"
export WF_CONTAINER_LABELS="org.wbniv.project=WorldFoundry-wbniv org.wbniv.purpose=local-ci org.wbniv.source=scripts/local-ci.sh"
unset WF_CONTAINER_IMAGE   # the default, linux-test

log() { printf '%s local-ci: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { log "ERROR: $*" >&2; exit 2; }

# ── Preflight: disk and Docker, before taking anything ───────────────────────────────
mkdir -p "$results" "$scratch"
for dir in "$results" "$scratch"; do
    free="$(df -BG --output=avail "$dir" | tail -1 | tr -dc '0-9')"
    # The floor must hold at the run's peak, not only at its start.
    [ "$free" -ge $((min_free + build_gb)) ] ||
        die "only ${free} GB free on the filesystem of $dir (need ${min_free} GB floor + ${build_gb} GB for the run: WF_CI_MIN_FREE_GB, WF_CI_BUILD_GB)"
done
docker info >/dev/null 2>&1 || die "Docker is not reachable (docker info failed)"

# ── Lock: one run at a time ──────────────────────────────────────────────────────────
exec 9>"$results/.lock"
if ! flock -n 9; then
    log "another run holds the lock (pid $(cat "$results/.lock.pid" 2>/dev/null || echo '?')); exiting"
    exit 0
fi
echo $$ >"$results/.lock.pid"

# ── Resolve the commit ───────────────────────────────────────────────────────────────
git -C "$root" fetch -q origin "$branch"
commit="${commit:-origin/$branch}"
sha="$(git -C "$root" rev-parse --verify -q "$commit^{commit}")" || die "no such commit: $commit"
if [ "$poll" = 1 ]; then
    if [ "$(cat "$results/last-polled" 2>/dev/null || true)" = "$sha" ]; then
        log "nothing new: origin/$branch is still ${sha:0:12}"
        exit 0
    fi
    echo "$sha" >"$results/last-polled"
fi
rev=""
if [ -n "$tests_from" ]; then
    rev="$(git -C "$root" rev-parse --verify -q "$tests_from^{commit}")" || die "no such commit: $tests_from"
fi
subject="$(git -C "$root" log -1 --format=%s "$sha")"
name="${sha:0:12}${rev:+-tests-${rev:0:12}}"
[ "$builder" = dev ] || name="$name-$builder"
out="$results/$name"
rm -rf "$out"
mkdir -p "$out"
started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
t0=$SECONDS
log "testing ${sha:0:12} ($subject)${rev:+ with the tests of ${rev:0:12}}, builder $builder; results in $out"

# ── Throwaway sparse clone, deleted on exit whatever happens ─────────────────────────
wt="$scratch/$name-$$"
cleanup() {
    rm -rf "$wt"
    rm -f "$results/.lock.pid"
}
trap cleanup EXIT
git clone -q --local --no-checkout "$root" "$wt"
{
    git -C "$wt" sparse-checkout set --no-cone '/*' \
        '!/docs/plans/' '!/docs/diagnostics/' '!/docs/papers/' '!/docs/reference/' \
        '/docs/**/*.iff' '/docs/**/*.c' '/docs/**/*.cc' '/docs/**/*.cpp' \
        '/docs/**/*.h' '/docs/**/*.hpp' '/docs/**/*.inc'
    git -C "$wt" checkout -q --detach "$sha"
} >"$out/checkout.log" 2>&1 || { tail -20 "$out/checkout.log" >&2; die "checkout of ${sha:0:12} failed"; }
if [ -n "$rev" ]; then
    # The tests and their helpers must exist in REV. (The build harness is the runner's; below.)
    for path in tests/test_snowgoons_arena_faces_up.py tests/test_renderer_references_fresh.py \
                tests/compare_renderer_frames.py scripts/audit_face_hand.py; do
        git -C "$root" cat-file -e "$rev:$path" 2>/dev/null || die "$path is not in ${rev:0:12}"
        mkdir -p "$(dirname "$wt/$path")"
        git -C "$root" show "$rev:$path" >"$wt/$path"
        case "$path" in *.sh) chmod +x "$wt/$path" ;; esac
    done
    log "overlaid the CI tests from ${rev:0:12}"
fi
# The build scripts belong to the runner (this checkout), so the CI can build, and so
# back-test, commits older than them or than their current options. The dev engine's
# configuration, cmake/wf-game-dev.cmake, is the commit's when it has one.
for path in scripts/build-wf-game.sh scripts/build-wf-game-container.sh scripts/in-linux-container.sh; do
    mkdir -p "$(dirname "$wt/$path")"
    cp "$root/$path" "$wt/$path"
done
if [ ! -e "$wt/cmake/wf-game-dev.cmake" ]; then
    mkdir -p "$wt/cmake"
    cp "$root/cmake/wf-game-dev.cmake" "$wt/cmake/wf-game-dev.cmake"
    log "backfilled cmake/wf-game-dev.cmake from the runner (not in ${sha:0:12})"
fi

# ── Steps ────────────────────────────────────────────────────────────────────────────
printf 'step\tresult\tseconds\n' >"$out/result.tsv"
failed=()
record() {   # name result seconds
    printf '%s\t%s\t%s\n' "$1" "$2" "$3" >>"$out/result.tsv"
    log "$1: $2 (${3} s)"
    case "$2" in PASS) ;; *) failed+=("$1") ;; esac
}
# A pytest step passes only on exit 0 with at least one pass and no skip.
pytest_verdict() {   # rc logfile
    local summary
    summary="$(grep -E '^=+ .* in [0-9.]+s' "$2" | tail -1 || true)"
    if [ "$1" -ne 0 ]; then echo FAIL
    elif [[ "$summary" == *skipped* ]]; then echo "FAIL (skipped)"
    elif [[ "$summary" != *passed* ]]; then echo "FAIL (nothing passed)"
    else echo PASS
    fi
}
in_container() { (cd "$wt" && scripts/in-linux-container.sh "$@"); }

s=$SECONDS rc=0
if [ "$builder" = release ]; then
    engine=/build/wf-game/src/engine/wf_game host_engine="$wt/build-docker/wf-game/src/engine/wf_game"
    in_container scripts/build-wf-game-container.sh >"$out/build.log" 2>&1 || rc=$?
else
    engine=/build/wf-game-dev/src/engine/wf_game host_engine="$wt/build-docker/wf-game-dev/src/engine/wf_game"
    cmake_args=()
    if ! grep -q WF_DESIGNER_CHEATS "$wt/CMakeLists.txt"; then
        # A commit from before the option: define the switch directly, as style-gl-sweep.sh does.
        cmake_args=(-DCMAKE_CXX_FLAGS=-DDESIGNER_CHEATS=1)
        log "CMakeLists.txt of ${sha:0:12} predates WF_DESIGNER_CHEATS: passing ${cmake_args[*]}"
    fi
    in_container scripts/build-wf-game-container.sh --dev -- ${cmake_args[@]+"${cmake_args[@]}"} \
        >"$out/build.log" 2>&1 || rc=$?
fi
if [ "$rc" -eq 0 ] && [ -x "$host_engine" ]; then
    record build PASS $((SECONDS - s))
    built=1
else
    record build FAIL $((SECONDS - s))
    built=0
fi

s=$SECONDS rc=0
in_container python3 -m pytest -v -rs -p no:cacheprovider tests/test_snowgoons_arena_faces_up.py \
    >"$out/arena-faces-up.log" 2>&1 || rc=$?
record arena-faces-up "$(pytest_verdict "$rc" "$out/arena-faces-up.log")" $((SECONDS - s))

if [ "$built" = 1 ]; then
    s=$SECONDS rc=0
    # bash -c keeps xvfb-run from being PID 1; the trailing exit keeps bash from exec-ing it.
    WF_CONTAINER_ENV="WF_GAME=$engine" in_container bash -c 'set -euo pipefail; rc=0
        xvfb-run -a -s "-screen 0 1280x720x24" \
            python3 -m pytest -v -rs -p no:cacheprovider tests/test_renderer_references_fresh.py || rc=$?
        exit "$rc"' >"$out/renderer-fresh.log" 2>&1 || rc=$?
    record renderer-fresh "$(pytest_verdict "$rc" "$out/renderer-fresh.log")" $((SECONDS - s))
else
    echo "not run: the engine build failed" >"$out/renderer-fresh.log"
    record renderer-fresh "SKIP (no engine)" 0
fi

# ── Results ──────────────────────────────────────────────────────────────────────────
verdict=PASS
[ ${#failed[@]} -eq 0 ] || verdict=FAIL
{
    printf '%-14s%s\n' "WF local CI" "$verdict"
    printf '%-14s%s  %s\n' commit "${sha:0:12}" "$subject"
    [ -z "$rev" ] || printf '%-14s%s\n' "tests from" "${rev:0:12}"
    printf '%-14s%s\n' builder "$builder"
    printf '%-14s%s\n' started "$started"
    printf '%-14s%s   (%s s)\n' finished "$(date -u +%Y-%m-%dT%H:%M:%SZ)" $((SECONDS - t0))
    printf '%-14s%s\n' results "$out"
    echo
    awk -F'\t' '{ printf "%-20s %-22s %s\n", $1, $2, $3 }' "$out/result.tsv"
    for step in ${failed[@]+"${failed[@]}"}; do
        echo
        echo "──── $step: last 25 lines ────"
        tail -25 "$out/$step.log"
    done
} >"$out/summary.txt"
cp "$out/summary.txt" "$results/latest"
cat "$out/summary.txt"

if [ "$verdict" = FAIL ] && [ "$notify" = 1 ]; then
    title="WF local CI FAILED on ${sha:0:8}"
    body="Failing: ${failed[*]}. ${sha:0:8} ${subject:0:60}. See $results/latest"
    if command -v notify-send >/dev/null && notify-send -u critical -a wf-local-ci "$title" "$body"; then
        log "notified: $title | $body"
    else
        log "could not notify (notify-send missing or no session bus): $title"
    fi
fi

# Keep the newest $keep result directories.
mapfile -t old < <(cd "$results" && ls -1dt -- */ 2>/dev/null | tail -n +$((keep + 1)) || true)
for dir in ${old[@]+"${old[@]}"}; do
    rm -rf -- "${results:?}/${dir%/}"
    log "pruned old result ${dir%/}"
done

[ "$verdict" = PASS ]
