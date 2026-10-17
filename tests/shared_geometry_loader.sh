#!/usr/bin/env bash
# Build and run tests/shared_geometry_loader.cc against the objects of an
# engine/build_game.sh build (the CMake target shared_geometry_loader_test is
# the same test linked against wfengine).
#
#   tests/shared_geometry_loader.sh [OBJS_DIR] [OUT_BINARY]
#
# OBJS_DIR defaults to engine/objs_game. Build it first with the desktop
# configuration, e.g. WF_ASAN=0 bash engine/build_game.sh. The objects must be
# a non-ASAN build: the test is compiled and linked without sanitizers.
set -euo pipefail
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OBJS="${1:-$ROOT/engine/objs_game}"
BIN="${2:-$OBJS/shared_geometry_loader_test}"
SRC="$ROOT/wfsource/source"
[[ -d "$OBJS" ]] || { echo "error: no objects at $OBJS (run engine/build_game.sh)" >&2; exit 1; }

# Defines and includes as engine/build_game.sh compiles the engine (layouts must match).
CXXFLAGS=(
    -std=c++17 -fpermissive -w -O0 -fno-rtti
    -DWF_TARGET_LINUX -D__LINUX__ -DRENDERER_GL -DRENDERER_PIPELINE_GL -DSCALAR_TYPE_FLOAT
    -DBUILDMODE_DEBUG -DDO_ASSERTIONS=1 -DDO_DEBUGGING_INFO=1 -DDESIGNER_CHEATS=1
    -DDO_IOSTREAMS=1 -DSW_DBSTREAM=1 -DDEBUG=1 -DDEBUG_VARIABLES=1
    -DDO_VALIDATION=0 -DDO_TEST_CODE=1 -DDO_DEBUG_FILE_SYSTEM=0
    '-D__GAME__="wf_game"' "-DERR_DEBUG(x)="
    -I"$SRC" -I"$SRC/game" -I"$ROOT/engine/include" -I"$ROOT/engine/stubs"
)

# Every engine object except the ones defining main().
mapfile -t objects < <(find "$OBJS/" -maxdepth 1 -name '*.o' | sort)
link=()
for o in "${objects[@]}"; do
    if nm -g --defined-only "$o" 2>/dev/null | grep -qE ' T main$'; then continue; fi
    link+=("$o")
done
extra=()
[[ -f "$OBJS/jolt_build/libJolt.a" ]] && extra+=("$OBJS/jolt_build/libJolt.a")
[[ -f "$OBJS/libwf_attr_edit.a" ]] && extra+=("$OBJS/libwf_attr_edit.a")

g++ "${CXXFLAGS[@]}" -c "$ROOT/tests/shared_geometry_loader.cc" -o "$BIN.o"
g++ "$BIN.o" "${link[@]}" "${extra[@]}" -lGL -lGLU -lX11 -lm -lpthread -ldl -o "$BIN"
rm -f "$BIN.o"
ulimit -c 0
"$BIN" "$ROOT/tests/fixtures/shared_geometry"
