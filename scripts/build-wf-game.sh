#!/usr/bin/env bash
# build-wf-game.sh: the one desktop engine build. Configures CMake with the dev initial
# cache (cmake/wf-game-dev.cmake: Debug, ASan, designer cheats, Lua + zForth + PILOT, Jolt)
# and builds wf_game, which CMake writes to engine/wf_game. `task build` runs this on the
# host; scripts/build-wf-game-container.sh --dev runs it in the Linux test container.
# Plan: docs/plans/2026-11-14-single-desktop-build.md (it replaced engine/build_game.sh).
set -euo pipefail

usage() {
    cat <<'EOF2'
Usage: scripts/build-wf-game.sh [-h|--help] [--build-dir DIR] [--editor] [--target T]... [-- CMAKE_ARGS...]

Configures (cmake -C cmake/wf-game-dev.cmake, Ninja) and builds the desktop dev engine.
  --build-dir DIR  CMake binary directory (default build-wf-game, or build-wf-game-dev
                   with --editor), relative to the repo root
  --editor         WF_ENABLE_EDITOR=ON: the editor/dev stack (wfmut, CRDT hooks); the
                   binary is engine/wf_game-dev, so it never overwrites engine/wf_game.
                   Configuring needs the cmake/Corrosion submodule (task vendor-unpack)
  --target T       build T instead of wf_game (repeatable), e.g. a ctest executable
  CMAKE_ARGS       extra configure flags, e.g. -- -DWF_ASAN=OFF or -- -DWF_LUA_ENGINE=none
                   (they stay in the build directory's cache)
Unpacks the vendored Jolt archive first if it is not expanded (task vendor-unpack-archives).
EOF2
}

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_dir="" editor=0 targets=() cmake_args=()
while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --build-dir) [ $# -ge 2 ] || { usage >&2; exit 2; }; build_dir="$2"; shift 2 ;;
        --editor) editor=1; shift ;;
        --target) [ $# -ge 2 ] || { usage >&2; exit 2; }; targets+=("$2"); shift 2 ;;
        --) shift; cmake_args=("$@"); break ;;
        *) echo "build-wf-game.sh: unknown argument $1" >&2; usage >&2; exit 2 ;;
    esac
done
if [ -z "$build_dir" ]; then
    build_dir=build-wf-game
    [ "$editor" = 0 ] || build_dir=build-wf-game-dev
fi
case "$build_dir" in /*) ;; *) build_dir="$root/$build_dir" ;; esac
[ "$editor" = 0 ] || cmake_args=(-DWF_ENABLE_EDITOR=ON "${cmake_args[@]}")
[ ${#targets[@]} -gt 0 ] || targets=(wf_game)

jolt="$root/engine/vendor/jolt-physics-5.5.0"
if [ ! -d "$jolt" ]; then
    tar -xzf "$jolt.tar.gz" --one-top-level="$jolt" --strip-components=1
fi

generator=()
if [ ! -f "$build_dir/CMakeCache.txt" ] && command -v ninja >/dev/null; then
    generator=(-G Ninja)
fi
cmake -S "$root" -B "$build_dir" ${generator[@]+"${generator[@]}"} \
    -C "$root/cmake/wf-game-dev.cmake" ${cmake_args[@]+"${cmake_args[@]}"}
cmake --build "$build_dir" --target "${targets[@]}"
if [ "${targets[*]}" = wf_game ]; then
    bin="$root/engine/wf_game"
    [ "$editor" = 0 ] || bin="$root/engine/wf_game-dev"
    echo "Built: $bin"
fi
