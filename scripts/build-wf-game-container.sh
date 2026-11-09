#!/usr/bin/env bash
# build-wf-game-container.sh: build the desktop engine (wf_game, Release, no ASan) INSIDE
# the Linux test container, from a copy of the checkout, so the result links against the
# container's own glibc and Mesa and the host's engine/wf_game is never overwritten.
#
#   scripts/in-linux-container.sh scripts/build-wf-game-container.sh
#   -> /build/wf-game/src/engine/wf_game   (build-docker/wf-game/src/engine/wf_game on the host)
#
# Used by scripts/check-thai-reef.py --container (the reef's desktop reaction test).
set -euo pipefail

usage() {
    cat <<'EOF2'
Usage: scripts/build-wf-game-container.sh [-h|--help] [--out DIR]

Inside the Linux test container: copy /src (the engine sources only; no .git, android,
build trees, and from docs/ and wflevels/ only the C/C++ sources and .inc files CMake uses) to DIR/src, configure CMake (Release, WF_ASAN=OFF)
in DIR/build and build the wf_game target. The binary lands in DIR/src/engine/wf_game,
because CMake writes wf_game next to its own sources. Incremental on reruns.
  --out DIR   work directory (default /build/wf-game)
EOF2
}
out=/build/wf-game
while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --out) out="$2"; shift 2 ;;
        *) usage >&2; exit 2 ;;
    esac
done
[ -d /src/engine ] || { echo "run inside the container (repo at /src)" >&2; exit 2; }

mkdir -p "$out/src" "$out/build"
rsync -a -m --delete \
    --exclude '/.git' --exclude '/.worktrees' --exclude '/.claude' --exclude '/build*' \
    --exclude '/cmake-build-*' --exclude '/android' \
    --include '/docs/' --include '/docs/**/' --include '/wflevels/' --include '/wflevels/**/' \
    --include='/docs/**/*.'{c,cc,cpp,h,hpp,inc} --include='/wflevels/**/*.'{c,cc,cpp,h,hpp,inc} \
    --exclude '/docs/**' --exclude '/wflevels/**' \
    --exclude '/engine/wf_game' --exclude 'target/' --exclude 'node_modules/' \
    /src/ "$out/src/"

# Jolt ships as a tarball (what `task vendor-unpack` does).
if [ ! -d "$out/src/engine/vendor/jolt-physics-5.5.0" ]; then
    tar -xzf "$out/src/engine/vendor/jolt-physics-5.5.0.tar.gz" -C "$out/src/engine/vendor"
    extracted="$(find "$out/src/engine/vendor" -maxdepth 1 -type d -name 'jrouwe-JoltPhysics-*' | head -n 1)"
    mv "$extracted" "$out/src/engine/vendor/jolt-physics-5.5.0"
fi

cmake -S "$out/src" -B "$out/build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DWF_ASAN=OFF \
    >"$out/configure.log" 2>&1 || { tail -30 "$out/configure.log"; exit 1; }
if ! cmake --build "$out/build" --target wf_game >"$out/build.log" 2>&1; then
    grep -m1 -A20 '^FAILED' "$out/build.log" || tail -30 "$out/build.log"
    exit 1
fi
tail -1 "$out/build.log"
ls -la "$out/src/engine/wf_game"
