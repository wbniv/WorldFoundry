#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
usage: scripts/style-gl-sweep.sh [-h|--help] [REV ...]

GL half of the reef plan's step 14 (docs/diagnostics/reef-style-metal-2026-11-09):
with every style field at 0, every *-standalone.iff of the pre-style baseline tree
must render pixel-identically on the baseline engine and on each REV (default:
the style commit and HEAD).

Host side: extracts each revision's engine sources (git archive, plus this
checkout's submodules) to build-docker/style-gl/<n>/src. Then, in the linux-test
container: builds Debug engines with -DDESIGNER_CHEATS=1 (Linux --capture-frame
needs it), renders frame 20 with the Metal sweep's flags and VRAM table
(tests/fixtures/renderer/style-scene.json) and compares. Writes
build-docker/style-gl/out/ and prints one line per level; exits 1 if any differ.
EOF
}
case "${1:-}" in -h|--help) usage; exit 0 ;; esac

ROOT=$(cd "$(dirname "$0")/.." && pwd)
FIX=$ROOT/tests/fixtures/renderer/style-scene.json
BASE=$(python3 -c "import json;print(json.load(open('$FIX'))['sweep']['baseline_rev'])")
REVS=("$@")
[ ${#REVS[@]} -gt 0 ] || REVS=("$(python3 -c "import json;print(json.load(open('$FIX'))['sweep']['candidate_rev'])")" HEAD)
WORK=$ROOT/build-docker/style-gl

extract() {   # rev name
    local out=$WORK/$2/src
    rm -rf "$out"; mkdir -p "$out"
    git -C "$ROOT" archive "$1" -- . ':(exclude)wflevels' ':(exclude)docs' ':(exclude)android' ':(exclude)build-docker' | tar -x -C "$out"
    git -C "$ROOT" ls-tree -r --name-only "$1" -- docs wflevels | grep -E '\.(inc|cc|h|hpp|cpp|c)$' \
        | (cd "$ROOT" && xargs git archive "$1") | tar -x -C "$out"
    git -C "$ROOT" ls-tree --name-only "$1" wflevels/ | grep -- '-standalone.iff$' \
        | (cd "$ROOT" && xargs git archive "$1") | tar -x -C "$out" || true
    for sm in third_party/glfw third_party/imgui wftools/y-crdt cmake/Corrosion; do
        rm -rf "${out:?}/$sm"; cp -a "$ROOT/$sm" "$out/$sm"
    done
    git -C "$ROOT" rev-parse "$1" > "$WORK/$2/REV"
}

names=(baseline)
extract "$BASE" baseline
i=0
for rev in "${REVS[@]}"; do i=$((i + 1)); extract "$rev" "rev$i"; names+=("rev$i"); done

"$ROOT/scripts/in-linux-container.sh" bash -c '
set -euo pipefail
ulimit -c 0
W=/build/style-gl; FIX=/src/tests/fixtures/renderer/style-scene.json
for name in '"${names[*]}"'; do
    src=$W/$name/src
    if [ ! -d "$src/engine/vendor/jolt-physics-5.5.0" ]; then
        tar -xzf "$src/engine/vendor/jolt-physics-5.5.0.tar.gz" -C "$src/engine/vendor"
        mv "$(find "$src/engine/vendor" -maxdepth 1 -type d -name "jrouwe-JoltPhysics-*" | head -n 1)" "$src/engine/vendor/jolt-physics-5.5.0"
    fi
    cmake -S "$src" -B "$W/$name/build" -G Ninja -DCMAKE_BUILD_TYPE=Debug -DWF_ASAN=OFF \
        -DCMAKE_CXX_FLAGS=-DDESIGNER_CHEATS=1 -DCMAKE_C_FLAGS=-DDESIGNER_CHEATS=1 >"$W/$name/configure.log" 2>&1
    cmake --build "$W/$name/build" --target wf_game >"$W/$name/build.log" 2>&1
done
Xvfb :9 -screen 0 1280x1024x24 >/dev/null 2>&1 &
sleep 2
export DISPLAY=:9
OUT=$W/out; rm -rf "$OUT"; mkdir -p "$OUT"
mapfile -t ARGS < <(python3 -c "import json;[print(a) for a in json.load(open(\"$FIX\"))[\"sweep\"][\"args\"]]")
GAME=$W/baseline/src/wfsource/source/game
status=0
for level in $W/baseline/src/wflevels/*-standalone.iff; do
    name=$(basename "$level" -standalone.iff)
    mapfile -t EXTRA < <(python3 - "$name" "$FIX" <<"PY"
import json, sys
d = json.load(open(sys.argv[2]))["sweep"]; n = sys.argv[1]; v = d["vram"].get(n)
if v:
    print("\n".join([f"--vram-width={v[0]}", f"--vram-height={v[1]}", f"--vram-slot-width={v[2]}",
                     f"--vram-slot-height={v[2]}", "--vram-perm-width=1024", f"--vram-perm-height={v[3]}"]))
for a in d["extra"].get(n, []):
    print(a)
PY
)
    line=$name
    for engine in '"${names[*]}"'; do
        ( cd "$GAME" && LD_LIBRARY_PATH=$W/$engine/src/engine/libs timeout 300 "$W/$engine/src/engine/wf_game" "${ARGS[@]}" \
            ${EXTRA[@]+"${EXTRA[@]}"} --capture-frame=20="$OUT/$name-$engine.png" "-L$level" >"$OUT/$name-$engine.log" 2>&1 ) || true
        [ "$engine" = baseline ] && continue
        if [ ! -s "$OUT/$name-baseline.png" ] || [ ! -s "$OUT/$name-$engine.png" ]; then verdict=missing
        elif python3 /src/tests/compare_renderer_frames.py "$OUT/$name-baseline.png" "$OUT/$name-$engine.png" >/dev/null 2>&1; then verdict=identical
        else verdict=differs; status=1; fi
        line="$line $engine=$verdict"
    done
    echo "$line" | tee -a "$OUT/summary.txt"
done
exit $status
'
