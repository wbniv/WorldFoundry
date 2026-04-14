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

# Feature flag: compile in Fennel (Lisp → Lua) support. Default off so the
# default build stays Fennel-free (no ~145 KB embed, no `;`-sigil dispatch).
# Set to 1 to embed the vendored fennel.lua and enable runtime dispatch.
WF_ENABLE_FENNEL="${WF_ENABLE_FENNEL:-0}"

# Feature flag: optional JS engine for the `//` sigil. One of:
#   none        (default) — no JS compiled in, zero binary/asset delta vs. Lua-only.
#   quickjs     — QuickJS (~350 KB), modern ES2020.
#   jerryscript — JerryScript wf-minimal profile (~80-90 KB), ES5.1 subset.
# Multiple JS engines at once is deliberately forbidden; the sigil `//` is shared.
WF_JS_ENGINE="${WF_JS_ENGINE:-none}"
case "$WF_JS_ENGINE" in
    none|quickjs|jerryscript) ;;
    *) echo "error: WF_JS_ENGINE must be one of: none, quickjs, jerryscript (got: '$WF_JS_ENGINE')" >&2
       exit 2 ;;
esac
VENDOR="$REPO_ROOT/wftools/vendor"
QJS_DIR="$VENDOR/quickjs-v0.14.0"
JRY_DIR="$VENDOR/jerryscript-v3.0.0"

# Feature flag: optional WebAssembly engine for the `#` sigil. One of:
#   none    (default) — no wasm compiled in, zero binary delta vs. today.
#   wasm3   — wasm3 v0.5.0 (~65 KB), pure-C interpreter, MIT.
# Future: wamr, wamr-aot. Only one wasm runtime at a time; sigil is shared.
WF_WASM_ENGINE="${WF_WASM_ENGINE:-none}"
case "$WF_WASM_ENGINE" in
    none|wasm3) ;;
    *) echo "error: WF_WASM_ENGINE must be one of: none, wasm3 (got: '$WF_WASM_ENGINE')" >&2
       exit 2 ;;
esac
WASM3_DIR="$VENDOR/wasm3-v0.5.0"
LUA_DIR="$VENDOR/lua-5.4.8"
WASM3_WF_DIR="$VENDOR/wasm3-v0.5.0-wf"

mkdir -p "$OUT"

CXXFLAGS=(
    -std=c++17 -fpermissive -w -O0 -g
    -DWF_TARGET_LINUX -D__LINUX__ -DRENDERER_GL -DRENDERER_PIPELINE_GL -DSCALAR_TYPE_FLOAT
    -DBUILDMODE_DEBUG -DDO_ASSERTIONS=1 -DDO_DEBUGGING_INFO=1
    -DDO_IOSTREAMS=1 -DSW_DBSTREAM=1 -DDEBUG=1 -DDEBUG_VARIABLES=1
    -DDO_VALIDATION=0 -DDO_TEST_CODE=0 -DDO_DEBUG_FILE_SYSTEM=0
    -DPHYSICS_ENGINE_WF '-D__GAME__="wf_game"' "-DERR_DEBUG(x)="
    -I"$SRC" -I"$SRC/game" -I"$STUBS" -I"$LUA_DIR/src"
)

if [[ "$WF_ENABLE_FENNEL" == "1" ]]; then
    CXXFLAGS+=(-DWF_ENABLE_FENNEL)
fi

case "$WF_JS_ENGINE" in
    quickjs)     CXXFLAGS+=(-DWF_JS_ENGINE_QUICKJS -I"$QJS_DIR") ;;
    jerryscript) CXXFLAGS+=(-DWF_JS_ENGINE_JERRYSCRIPT -I"$JRY_DIR/jerry-core/include") ;;
    none)        : ;;
esac

case "$WF_WASM_ENGINE" in
    wasm3) CXXFLAGS+=(-DWF_WASM_ENGINE_WASM3 -I"$WASM3_DIR/source") ;;
    none)  : ;;
esac

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
# Vendored Lua 5.4 (C, not C++). Compile every .c in src/ except lua.c and
# luac.c (those are standalone-binary mains, not library TUs). LUA_USE_POSIX +
# LUA_USE_DLOPEN gives require()/dlopen() support without pulling in readline
# (which is only used by Lua's standalone REPL). Linked statically — no system
# liblua5.4 dependency.
LUA_CFLAGS=(-std=gnu99 -O2 -w -fno-strict-aliasing
            -DLUA_USE_POSIX -DLUA_USE_DLOPEN -I"$LUA_DIR/src")
for c in lapi.c lauxlib.c lbaselib.c lcode.c lcorolib.c lctype.c ldblib.c \
         ldebug.c ldo.c ldump.c lfunc.c lgc.c linit.c liolib.c llex.c \
         lmathlib.c lmem.c loadlib.c lobject.c lopcodes.c loslib.c lparser.c \
         lstate.c lstring.c lstrlib.c ltable.c ltablib.c ltm.c lundump.c \
         lutf8lib.c lvm.c lzio.c; do
    obj="$OUT/lua__${c%.c}.o"
    echo "  CC (vendor) lua/$c"
    gcc "${LUA_CFLAGS[@]}" -c "$LUA_DIR/src/$c" -o "$obj"
    OBJS+=("$obj")
done

echo "  CC (stub) scripting_stub.cc"
g++ "${CXXFLAGS[@]}" -c "$STUB_SRC/scripting_stub.cc" -o "$OUT/stubs__scripting_stub.o"
OBJS+=("$OUT/stubs__scripting_stub.o")

echo "  CC (stub) platform_stubs.cc"
g++ "${CXXFLAGS[@]}" -c "$STUB_SRC/platform_stubs.cc" -o "$OUT/stubs__platform_stubs.o"
OBJS+=("$OUT/stubs__platform_stubs.o")

# JS engine plug — compiled and linked only when a non-`none` flavour is selected.
declare -a JS_LINK_EXTRA=()
case "$WF_JS_ENGINE" in
    quickjs)
        echo "  CC (stub) scripting_quickjs.cc"
        g++ "${CXXFLAGS[@]}" -c "$STUB_SRC/scripting_quickjs.cc" -o "$OUT/stubs__scripting_quickjs.o"
        OBJS+=("$OUT/stubs__scripting_quickjs.o")
        # QuickJS core (C, not C++). Compile each TU once; -O2 to keep the JIT-less
        # interpreter tolerable. Warnings silenced — third-party code.
        QJS_CFLAGS=(-std=gnu11 -O2 -w -fno-strict-aliasing
                    -DQUICKJS_NG_BUILD -DCONFIG_VERSION='"0.14.0"' -I"$QJS_DIR")
        for c in quickjs.c libregexp.c libunicode.c dtoa.c; do
            obj="$OUT/qjs__${c%.c}.o"
            echo "  CC (vendor) quickjs/$c"
            gcc "${QJS_CFLAGS[@]}" -c "$QJS_DIR/$c" -o "$obj"
            OBJS+=("$obj")
        done
        ;;
    jerryscript)
        echo "  CC (stub) scripting_jerryscript.cc"
        g++ "${CXXFLAGS[@]}" -c "$STUB_SRC/scripting_jerryscript.cc" -o "$OUT/stubs__scripting_jerryscript.o"
        OBJS+=("$OUT/stubs__scripting_jerryscript.o")
        # Build JerryScript libs via upstream cmake (idempotent; skip if already built).
        JRY_BUILD="$JRY_DIR/build"
        if [[ ! -f "$JRY_BUILD/lib/libjerry-core.a" ]]; then
            echo "  CMAKE jerryscript (wf-minimal profile)"
            cmake -S "$JRY_DIR" -B "$JRY_BUILD" \
                  -DJERRY_CMDLINE=OFF \
                  -DJERRY_PROFILE="$JRY_DIR/jerry-core/profiles/wf-minimal.profile" \
                  -DJERRY_ERROR_MESSAGES=ON \
                  -DJERRY_LINE_INFO=ON \
                  -DENABLE_LTO=OFF \
                  > "$OUT/jry_cmake.log" 2>&1 \
                  || { echo "  *** jerryscript cmake failed; see $OUT/jry_cmake.log" >&2; exit 1; }
            cmake --build "$JRY_BUILD" -j --target jerry-core --target jerry-port-default \
                  >> "$OUT/jry_cmake.log" 2>&1 \
                  || { echo "  *** jerryscript build failed; see $OUT/jry_cmake.log" >&2; exit 1; }
        fi
        JS_LINK_EXTRA+=("$JRY_BUILD/lib/libjerry-core.a"
                        "$JRY_BUILD/lib/libjerry-port.a")
        ;;
esac

# wasm3 engine plug — compiled and linked only when WF_WASM_ENGINE=wasm3.
case "$WF_WASM_ENGINE" in
    wasm3)
        echo "  CC (stub) scripting_wasm3.cc"
        g++ "${CXXFLAGS[@]}" -c "$STUB_SRC/scripting_wasm3.cc" -o "$OUT/stubs__scripting_wasm3.o"
        OBJS+=("$OUT/stubs__scripting_wasm3.o")
        # wasm3 core (C, not C++). Mirrors upstream source/CMakeLists.txt
        # minus the WASI / tracer / UVWASI surface we don't want.
        M3_CFLAGS=(-std=gnu11 -O2 -w -fno-strict-aliasing
                   -Dd_m3HasWASI=0 -Dd_m3HasMetaWASI=0 -Dd_m3HasTracer=0
                   -Dd_m3HasUVWASI=0 -I"$WASM3_DIR/source")
        for c in m3_api_libc.c m3_bind.c m3_code.c m3_compile.c \
                 m3_core.c m3_emit.c m3_env.c m3_exec.c m3_function.c \
                 m3_info.c m3_module.c m3_parse.c; do
            obj="$OUT/m3__${c%.c}.o"
            echo "  CC (vendor) wasm3/$c"
            gcc "${M3_CFLAGS[@]}" -c "$WASM3_DIR/source/$c" -o "$obj"
            OBJS+=("$obj")
        done
        # Embed selftest.wasm as a byte array so the runtime can run the
        # smoke test at startup without touching a filesystem.
        echo "  GEN wasm_selftest.cc (xxd)"
        WASM_CC="$OUT/wasm_selftest.cc"
        {
            echo '// AUTO-GENERATED from selftest.wasm by build_game.sh; do not edit.'
            ( cd "$WASM3_WF_DIR" && xxd -i selftest.wasm ) \
                | sed -E 's/^unsigned char selftest_wasm\[\]/extern "C" const unsigned char kWasmSelftest[]/;
                          s/^unsigned int selftest_wasm_len/extern "C" const unsigned int kWasmSelftestLen/'
        } > "$WASM_CC"
        echo "  CC wasm_selftest.cc"
        g++ "${CXXFLAGS[@]}" -c "$WASM_CC" -o "$OUT/wasm_selftest.o"
        OBJS+=("$OUT/wasm_selftest.o")
        ;;
    none) : ;;
esac

# Embed minified fennel.lua as a byte array when Fennel is enabled. The
# engine targets platforms without host filesystems, so fennel.lua can't be
# an external asset; it has to live in .rodata. Minification shrinks the
# embed by ~15% (165 KB -> 143 KB) without touching runtime semantics.
if [[ "$WF_ENABLE_FENNEL" == "1" ]]; then
    echo "  GEN fennel_source.cc (minify + xxd)"
    FENNEL_MIN="$OUT/fennel.min.lua"
    FENNEL_CC="$OUT/fennel_source.cc"
    python3 "$REPO_ROOT/scripts/minify_lua.py" \
        "$STUB_SRC/fennel.lua" "$FENNEL_MIN"
    {
        echo '// AUTO-GENERATED from fennel.lua by build_game.sh; do not edit.'
        ( cd "$(dirname "$FENNEL_MIN")" && xxd -i "$(basename "$FENNEL_MIN")" ) \
            | sed -E 's/^unsigned char fennel_min_lua\[\]/extern "C" const char kFennelSource[]/;
                      s/^unsigned int fennel_min_lua_len/extern "C" const unsigned int kFennelSourceLen/'
    } > "$FENNEL_CC"
    echo "  CC fennel_source.cc"
    g++ "${CXXFLAGS[@]}" -c "$FENNEL_CC" -o "$OUT/fennel_source.o"
    OBJS+=("$OUT/fennel_source.o")
fi

echo ""
if [[ ${#FAILED_SRCS[@]} -gt 0 ]]; then
    echo "=== COMPILE FAILURES (${#FAILED_SRCS[@]}) ==="
    for f in "${FAILED_SRCS[@]}"; do echo "  FAIL $f"; done
    echo ""
    echo "Fix the above before linking."
    exit 1
fi

echo "=== Linking ==="
g++ "${OBJS[@]}" "${JS_LINK_EXTRA[@]}" \
    -lGL -lGLU -lX11 -lm -lpthread -ldl \
    -o "$SCRIPT_DIR/wf_game"

echo ""
echo "Built: $SCRIPT_DIR/wf_game"
echo "Run:   cd $SRC/game && DISPLAY=:0 $SCRIPT_DIR/wf_game"
