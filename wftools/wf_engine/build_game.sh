#!/usr/bin/env bash
# wf_engine/build_game.sh — build the WF game engine executable from source
#
# Run from this directory. Output: wf_game binary here.
# To run: cd wfsource/source/game && DISPLAY=:0 ../../../wftools/wf_engine/wf_game
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SRC="$REPO_ROOT/wfsource/source"
STUBS="$REPO_ROOT/wftools/wf_viewer/include"
STUB_SRC="$REPO_ROOT/wftools/wf_viewer/stubs"
OUT="$SCRIPT_DIR/objs_game"

mkdir -p "$OUT"

CXXFLAGS=(
    -std=c++17 -fpermissive -w -O0 -g
    -DWF_TARGET_LINUX -D__LINUX__ -DRENDERER_GL -DRENDERER_PIPELINE_GL -DSCALAR_TYPE_FLOAT
    -DBUILDMODE_DEBUG -DDO_ASSERTIONS=1 -DDO_DEBUGGING_INFO=1
    -DDO_IOSTREAMS=1 -DSW_DBSTREAM=1 -DDEBUG=1 -DDEBUG_VARIABLES=1
    -DDO_VALIDATION=0 -DDO_TEST_CODE=0 -DDO_DEBUG_FILE_SYSTEM=0
    -DPHYSICS_ENGINE_WF '-D__GAME__="wf_game"' "-DERR_DEBUG(x)="
    -I"$SRC" -I"$SRC/game" -I"$STUBS"
)

OBJS=()

FAILED_SRCS=()

compile() {
    local src="$1"
    # encode directory in object name to avoid basename collisions
    local rel="${src#$SRC/}"
    local obj="$OUT/${rel//\//__}.o"
    echo "  CC $src"
    if g++ "${CXXFLAGS[@]}" -c "$src" -o "$obj" 2>&1; then
        OBJS+=("$obj")
    else
        echo "  *** FAILED: $src"
        FAILED_SRCS+=("$src")
    fi
}

echo "=== Compiling source files ==="

# Files to skip (test harnesses, Windows-only, replaced by stubs)
SKIP=(
    # test files
    physics/physicstest.cc
    timer/testtime.cc
    anim/animtest.cc
    anim/preview.cc
    anim/test.cc
    streams/strtest.cc
    math/mathtest.cc
    scripting/scriptingtest.cc
    pigsys/psystest.cc
    cpplib/cpptest.cc
    memory/memtest.cc
    savegame/savetest.cc
    menu/font.cc
    menu/menutest.cc
    particle/test.cc
    gfx/gfxtest.cc
    ini/initest.cc
    # platform-specific replacements (system versions used instead)
    pigsys/scanf.cc
    # Windows/PSX/unused
    gfx/gl/unused.cc
    gfx/gl/wgl.cc
    gfx/otable.cc
    attrib
    # sub-files included by parent .cc (not compiled directly)
    gfx/gl/mesa.cc
    gfx/gl/rendobj3.cc
    gfx/gl/viewport.cc
    gfx/gl/display.cc
    gfx/glpipeline/rendobj3.cc
    # also not needed (only used by afftform.cc which is skipped)
    math/matrix3t.cc
    math/quat.cc
    math/tables.cc
    cpplib/afftform.cc
    # dfhd and dfoff both define HalInitFileSubsystem; dfhd also has DiskFileHD methods
    # skip dfoff (it's just a no-op HalInitFileSubsystem, same as dfhd on Linux)
    hal/dfoff.cc
    # test files with their own PIGSMain that conflict with game/main.cc
    hal/haltest.cc
    asset/assettest.cc
    movement/movementtest.cc
    # room/callbacks.cc duplicates RoomCallbacks::Validate defined in room/room.cc
    room/callbacks.cc
    # replaced by scripting_stub.cc below
    scripting/scriptinterpreter.cc
    scripting/tcl.cc
    scripting/perl/scriptinterpreter_perl.cc
)

is_skipped() {
    local f="$1"
    # strip SRC prefix
    local rel="${f#$SRC/}"
    for skip in "${SKIP[@]}"; do
        # directory skip: rel starts with it
        if [[ "$rel" == "$skip"* ]]; then
            return 0
        fi
    done
    return 1
}

# Source directories to compile (order doesn't matter for .o files)
DIRS=(
    pigsys
    streams
    cpplib
    math
    memory
    iff
    mailbox
    hal
    hal/linux
    gfx
    gfx/gl
    gfx/glpipeline
    input
    asset
    baseobject
    movement
    room
    physics
    anim
    timer
    scripting
    game
    ini
    loadfile
    profile
    renderassets
    savegame
    savegame/linux
    menu
    particle
    audio/linux
)

for dir in "${DIRS[@]}"; do
    full="$SRC/$dir"
    [[ -d "$full" ]] || continue
    for f in "$full"/*.cc; do
        [[ -e "$f" ]] || continue
        if is_skipped "$f"; then
            echo "  SKIP $f"
            continue
        fi
        compile "$f"
    done
done

# Compile stubs
echo "  CC (stub) scripting_stub.cc"
g++ "${CXXFLAGS[@]}" -c "$STUB_SRC/scripting_stub.cc" -o "$OUT/stubs__scripting_stub.o"
OBJS+=("$OUT/stubs__scripting_stub.o")

echo "  CC (stub) platform_stubs.cc"
g++ "${CXXFLAGS[@]}" -c "$STUB_SRC/platform_stubs.cc" -o "$OUT/stubs__platform_stubs.o"
OBJS+=("$OUT/stubs__platform_stubs.o")

echo ""
if [[ ${#FAILED_SRCS[@]} -gt 0 ]]; then
    echo "=== COMPILE FAILURES (${#FAILED_SRCS[@]}) ==="
    for f in "${FAILED_SRCS[@]}"; do echo "  FAIL $f"; done
    echo ""
    echo "Fix the above before linking."
    exit 1
fi

echo "=== Linking ==="
g++ "${OBJS[@]}" \
    -lGL -lGLU -lX11 -llua5.4 -lm -lpthread \
    -o "$SCRIPT_DIR/wf_game"

echo ""
echo "Built: $SCRIPT_DIR/wf_game"
echo "Run:   cd $SRC/game && DISPLAY=:0 $SCRIPT_DIR/wf_game"
