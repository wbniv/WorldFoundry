#!/bin/bash
set -euo pipefail

usage() {
    cat <<'EOF'
usage: scripts/macos/style-metal-ci.sh [-h|--help]

Codemagic macos-style-metal step: the Metal half of the reef plan's step 14
(docs/plans/2026-11-08-reef-tanks-finish.md, W4 "Shader gates").

  1. Sweep. Builds Debug Metal engines at the pre-style baseline and at the
     style candidate (tests/fixtures/renderer/style-scene.json "sweep"), runs
     every *-standalone.iff of the baseline tree on both, and captures frame
     20. With every new Camera field at its default the two must be
     pixel-identical.
  2. Shared style scene. Builds this checkout's engine and renders the
     scenes in style-scene.json ("scenes") for tests/test_style_shading_
     invariant.py to compare with Linux GL (within 1/255 per channel).

Engines are Debug, like macos-desktop-debug, whose captures these match.
(The Metal --capture-frame is not gated on DESIGNER_CHEATS; the Linux one is.)

Writes $OUT_DIR/style-metal/: sweep/<level>-{baseline,candidate}.png,
scene/<name>-metal.png, summary.json and per-run logs. Prints the verdicts
and exits 0; the gates are the pytest cases that read these files.

Environment:
  CM_BUILD_DIR   repo checkout (required; Codemagic sets it)
  OUT_DIR        where results go (default: $CM_BUILD_DIR)
  STYLE_SKIP_SWEEP=1   only render the shared scenes
EOF
}

case "${1:-}" in
    -h|--help) usage; exit 0 ;;
    "") ;;
    *) echo "unexpected argument: $1" >&2; usage >&2; exit 2 ;;
esac

: "${CM_BUILD_DIR:?CM_BUILD_DIR is required}"
OUT="${OUT_DIR:-$CM_BUILD_DIR}/style-metal"
FIXTURE="$CM_BUILD_DIR/tests/fixtures/renderer/style-scene.json"
COMPARE="$CM_BUILD_DIR/tests/compare_renderer_frames.py"
mkdir -p "$OUT/sweep" "$OUT/scene" "$OUT/logs"

json() { python3 -c "import json,sys; d=json.load(open('$FIXTURE')); print($1)"; }
stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }
# macOS has no coreutils timeout; perl's alarm kills a hung run.
limit() { local s=$1; shift; perl -e 'alarm shift; exec @ARGV or die "exec: $!"' "$s" "$@"; }

prepare_tree() {   # $1 = source tree: unpack Jolt the way the desktop workflow does
    local tree=$1
    if [ ! -d "$tree/engine/vendor/jolt-physics-5.5.0" ]; then
        ( cd "$tree/engine/vendor"
          tar -xzf jolt-physics-5.5.0.tar.gz
          extracted=$(tar -tzf jolt-physics-5.5.0.tar.gz | head -1 | cut -d/ -f1)
          mv "$extracted" jolt-physics-5.5.0 )
    fi
}

build_engine() {   # $1 = source tree, $2 = build dir, $3 = label; echoes the binary
    local tree=$1 build=$2 label=$3 started
    started=$(date +%s)
    prepare_tree "$tree"
    mkdir -p "$build"
    rm -rf "$build/CMakeCache.txt" "$build/CMakeFiles"
    ( cd "$build" && cmake -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_OSX_ARCHITECTURES=arm64 \
          -DWF_ASAN=OFF "$tree" >"$OUT/logs/configure-$label.log" 2>&1 \
      && ninja wf_game >"$OUT/logs/build-$label.log" 2>&1 ) \
      || { echo "$(stamp) BUILD FAILED: $label (see logs/{configure,build}-$label.log)" >&2
           tail -20 "$OUT/logs/configure-$label.log" "$OUT/logs/build-$label.log" >&2 2>/dev/null || true; return 1; }
    echo "$(stamp) built $label in $(( $(date +%s) - started )) s" >&2
    echo "$tree/engine/wf_game.app/Contents/MacOS/wf_game"
}

capture() {   # $1 engine, $2 game dir, $3 png, $4 log, rest: args
    local engine=$1 game=$2 png=$3 log=$4; shift 4
    ( cd "$game" && limit 300 "$engine" "$@" --capture-frame=20="$png" >"$log" 2>&1 ) || true
    [ -s "$png" ]
}

echo "$(stamp) style-metal: start (checkout $(git -C "$CM_BUILD_DIR" rev-parse --short HEAD))"
SUMMARY="$OUT/summary.tsv"
: >"$SUMMARY"

# ---- 1. sweep: baseline vs candidate on Metal ------------------------------------------
if [ "${STYLE_SKIP_SWEEP:-0}" != 1 ]; then
    BASE_REV=$(json "d['sweep']['baseline_rev']")
    CAND_REV=$(json "d['sweep']['candidate_rev']")
    if [ "$(git -C "$CM_BUILD_DIR" rev-parse --is-shallow-repository)" = true ]; then
        git -C "$CM_BUILD_DIR" fetch --quiet --unshallow origin || true
    fi
    git -C "$CM_BUILD_DIR" cat-file -e "$BASE_REV^{commit}" 2>/dev/null \
        || git -C "$CM_BUILD_DIR" fetch --quiet origin "$BASE_REV" "$CAND_REV"
    WT="$CM_BUILD_DIR/.style-trees"
    rm -rf "$WT"; git -C "$CM_BUILD_DIR" worktree prune
    git -C "$CM_BUILD_DIR" worktree add --quiet --detach "$WT/baseline" "$BASE_REV"
    git -C "$CM_BUILD_DIR" worktree add --quiet --detach "$WT/candidate" "$CAND_REV"
    # A worktree starts with empty submodules (third_party/glfw and friends).
    for tree in "$WT/baseline" "$WT/candidate"; do
        git -C "$tree" submodule update --init --recursive --quiet
    done
    # git-lfs or not, the cooked levels are ordinary blobs in this repo.
    BASE_BIN=$(build_engine "$WT/baseline" "$WT/build-baseline" baseline)
    CAND_BIN=$(build_engine "$WT/candidate" "$WT/build-candidate" candidate)
    GAME="$WT/baseline/wfsource/source/game"
    read -r -a SWEEP_ARGS <<<"$(json "' '.join(d['sweep']['args'])")"
    identical=0; differs=0; missing=0
    for level in "$WT"/baseline/wflevels/*-standalone.iff; do
        name=$(basename "$level" -standalone.iff)
        extra=()
        vram=$(json "' '.join(map(str, d['sweep']['vram'].get('$name', [])))")
        if [ -n "$vram" ]; then
            read -r w h s p <<<"$vram"
            extra+=("--vram-width=$w" "--vram-height=$h" "--vram-slot-width=$s" "--vram-slot-height=$s"
                    "--vram-perm-width=1024" "--vram-perm-height=$p")
        fi
        while IFS= read -r arg; do
            [ -n "$arg" ] && extra+=("$arg")
        done < <(json "'\n'.join(d['sweep']['extra'].get('$name', []))")
        ok=1
        for side in baseline candidate; do
            bin=$BASE_BIN; [ "$side" = candidate ] && bin=$CAND_BIN
            capture "$bin" "$GAME" "$OUT/sweep/$name-$side.png" "$OUT/logs/sweep-$name-$side.log" \
                "${SWEEP_ARGS[@]}" ${extra[@]+"${extra[@]}"} "-L$level" || ok=0
        done
        if [ "$ok" = 0 ]; then
            verdict=missing; missing=$((missing + 1))
        elif python3 "$COMPARE" "$OUT/sweep/$name-baseline.png" "$OUT/sweep/$name-candidate.png" \
                >"$OUT/logs/compare-$name.log" 2>&1; then
            verdict=identical; identical=$((identical + 1))
        else
            verdict=differs; differs=$((differs + 1))
        fi
        printf 'sweep\t%s\t%s\n' "$name" "$verdict" | tee -a "$SUMMARY"
    done
    echo "$(stamp) SWEEP: identical=$identical differs=$differs missing=$missing"
fi

# ---- 2. shared style scene on this checkout's engine ------------------------------------
HEAD_BIN=$(build_engine "$CM_BUILD_DIR" "$CM_BUILD_DIR/build-macos" head)
read -r -a SCENE_ARGS <<<"$(json "' '.join(d['common_args'])")"
while IFS=$'\t' read -r name level; do
    if capture "$HEAD_BIN" "$CM_BUILD_DIR/wfsource/source/game" "$OUT/scene/$name-metal.png" \
            "$OUT/logs/scene-$name.log" "${SCENE_ARGS[@]}" "-L$CM_BUILD_DIR/$level"; then
        printf 'scene\t%s\tcaptured\n' "$name" | tee -a "$SUMMARY"
    else
        printf 'scene\t%s\tmissing\n' "$name" | tee -a "$SUMMARY"
    fi
done < <(json "'\n'.join(k + '\t' + v for k, v in d['scenes'].items())")

python3 - "$SUMMARY" "$OUT/summary.json" "$(git -C "$CM_BUILD_DIR" rev-parse HEAD)" <<'PY'
import json, sys
rows = [line.rstrip('\n').split('\t') for line in open(sys.argv[1]) if line.strip()]
out = {'checkout': sys.argv[3], 'sweep': {}, 'scene': {}}
for kind, name, verdict in rows:
    out[kind][name] = verdict
json.dump(out, open(sys.argv[2], 'w'), indent=2)
PY
echo "$(stamp) style-metal: done; results in $OUT"
