#!/usr/bin/env bash
# engine/build_game.sh — build the WF game engine executable from source
#
# Run from this directory. Output: wf_game (lean game engine) or wf_game-dev
# (editor/dev stack, when WF_ENABLE_EDITOR=1) — the two binaries coexist.
# To run: cd wfsource/source/game && DISPLAY=:0 ../../../engine/wf_game
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC="$REPO_ROOT/wfsource/source"
STUBS="$REPO_ROOT/engine/include"
STUB_SRC="$REPO_ROOT/engine/stubs"
OUT="$SCRIPT_DIR/objs_game"

# Feature flag: compile in Fennel (Lisp → Lua) support. Default on.
# Set to 0 to drop the ~145 KB embed and `;`-sigil dispatch.
WF_ENABLE_FENNEL="${WF_ENABLE_FENNEL:-1}"

# Feature flag: optional JS engine for the `//` sigil. One of:
#   none        (default) — no JS compiled in, zero binary/asset delta vs. Lua-only.
#   quickjs     — QuickJS (~350 KB), modern ES2020.
#   jerryscript — JerryScript wf-minimal profile (~237 KB .text), ES5.1 subset.
# Multiple JS engines at once is deliberately forbidden; the sigil `//` is shared.
WF_JS_ENGINE="${WF_JS_ENGINE:-quickjs}"
case "$WF_JS_ENGINE" in
    none|quickjs|jerryscript) ;;
    *) echo "error: WF_JS_ENGINE must be one of: none, quickjs, jerryscript (got: '$WF_JS_ENGINE')" >&2
       exit 2 ;;
esac
VENDOR="$REPO_ROOT/engine/vendor"
QJS_DIR="$VENDOR/quickjs-v0.14.0"
JRY_DIR="$VENDOR/jerryscript-v3.0.0"

# Feature flag: Wren scripting engine for the `//wren\n` sigil.
# Checked before generic `//` (JS) in dispatch order. Default on.
#   0 — no Wren compiled in.
#   1 — Wren 0.4.0 amalgamation (~420 KB source, ~150 KB .text).
WF_ENABLE_WREN="${WF_ENABLE_WREN:-1}"
WREN_DIR="$VENDOR/wren-0.4.0"

# Feature flag: optional Forth engine for the `\` sigil. Default: zforth. One of:
#   none     — no Forth compiled in.
#   zforth   — zForth 4 KB core (MIT); default.
#   ficl     — ficl ~100 KB (BSD-2); ANS Forth + OOP.
#   atlast   — Atlast ~30 KB (public domain); Autodesk-pedigree.
#   embed    — embed ~5 KB VM (MIT); 16-bit cells; correct on fixed-point target.
#   libforth — libforth ~50 KB (MIT).
#   pforth   — pForth ~120 KB (0-BSD); strong float; proven on 40+ platforms.
# Only one Forth engine at a time; sigil `\` is shared across all backends.
WF_FORTH_ENGINE="${WF_FORTH_ENGINE:-zforth}"
case "$WF_FORTH_ENGINE" in
    none|zforth|ficl|atlast|embed|libforth|pforth) ;;
    *) echo "error: WF_FORTH_ENGINE must be one of: none, zforth, ficl, atlast, embed, libforth, pforth (got: '$WF_FORTH_ENGINE')" >&2
       exit 2 ;;
esac
# PILOT — from-scratch C++ interpreter (engine/pilot), no vendored library.
# Default on; opt out with WF_PILOT_ENGINE=none.
WF_PILOT_ENGINE="${WF_PILOT_ENGINE:-builtin}"
case "$WF_PILOT_ENGINE" in
    none|builtin) ;;
    *) echo "error: WF_PILOT_ENGINE must be one of: none, builtin (got: '$WF_PILOT_ENGINE')" >&2
       exit 2 ;;
esac
PILOT_DIR="$REPO_ROOT/engine/pilot"
ZFORTH_DIR="$VENDOR/zforth-41db72d1"
FICL_DIR="$VENDOR/ficl-3.06"
ATLAST_DIR="$VENDOR/atlast-08ff0e1a/atlast-64"
EMBED_DIR="$VENDOR/embed-154aeb2f"
LIBFORTH_DIR="$VENDOR/libforth-b851c6a2"
PFORTH_DIR="$VENDOR/pforth-63d4a418"

# Feature flag: optional WebAssembly engine for the `#b64\n` sigil. Default: wamr. One of:
#   none    — no wasm compiled in, zero binary delta vs. Lua-only.
#   wamr    — WAMR 2.2.0 classic interpreter (~520 KB), Apache-2.0; default.
#             Supports host-supplied (global …) imports for INDEXOF_* constants.
# Only one wasm runtime at a time; the `#b64\n` sigil is shared.
WF_WASM_ENGINE="${WF_WASM_ENGINE:-wamr}"
case "$WF_WASM_ENGINE" in
    none|wamr) ;;
    *) echo "error: WF_WASM_ENGINE must be one of: none, wamr (got: '$WF_WASM_ENGINE')" >&2
       exit 2 ;;
esac
WAMR_DIR="$VENDOR/wamr-2.2.0"
LUA_DIR="$VENDOR/lua-5.4.8"

# Feature flag: Lua scripting engine for the plain-text (fallthrough) sigil.
# Fennel depends on Lua; enabling Fennel forces this to lua54.
#   lua54   — Lua 5.4.x (default).
#   none    — no Lua compiled in; also disables Fennel.
WF_LUA_ENGINE="${WF_LUA_ENGINE:-lua54}"
if [[ "$WF_ENABLE_FENNEL" == "1" && "$WF_LUA_ENGINE" == "none" ]]; then
    echo "warning: WF_LUA_ENGINE=none conflicts with WF_ENABLE_FENNEL=1; forcing WF_LUA_ENGINE=lua54" >&2
    WF_LUA_ENGINE="lua54"
fi
case "$WF_LUA_ENGINE" in
    lua54|none) ;;
    *) echo "error: WF_LUA_ENGINE must be one of: lua54, none (got: '$WF_LUA_ENGINE')" >&2
       exit 2 ;;
esac

HTTPLIB_DIR="$VENDOR/cpp-httplib-v0.20.0"
STEAM_DIR="$VENDOR/steamworks"

# Feature flag: Steamworks SDK integration. Default off.
# Requires SDK unpacked at engine/vendor/steamworks/ (see README there).
# Build: WF_ENABLE_STEAM=1 ./build_game.sh
WF_ENABLE_STEAM="${WF_ENABLE_STEAM:-0}"

# Feature flag: physics backend. One of:
#   legacy  (default) — WF's own kinematic collision engine (-DPHYSICS_ENGINE_WF).
#             No library overhead, identical to all prior builds.
#   jolt    — Jolt Physics v5.5.0 (~1 MB stripped) via CMake static lib.
#             Enables CharacterVirtual, shape casts, and removes the
#             reinterpret_cast in movecam.cc. Requires a C++17 toolchain
#             (already required by the rest of the build).
# Only one physics backend at a time.
WF_PHYSICS_ENGINE="${WF_PHYSICS_ENGINE:-jolt}"
case "$WF_PHYSICS_ENGINE" in
    legacy|jolt) ;;
    *) echo "error: WF_PHYSICS_ENGINE must be one of: legacy, jolt (got: '$WF_PHYSICS_ENGINE')" >&2
       exit 2 ;;
esac
JOLT_DIR="$VENDOR/jolt-physics-5.5.0"
JOLT_WF_DIR="$VENDOR/jolt-physics-5.5.0-wf"

# Feature flag: embed a minimal HTTP REST API for runtime box manipulation.
# Requires cpp-httplib (single-header, vendored). Default on for dev builds.
WF_REST_API="${WF_REST_API:-1}"

# Feature flag: TCP/JSON debug bridge for live Blender ↔ engine editing.
# Independent of WF_ENABLE_EDITOR — level designers and AI agents debugging
# alike depend on it. Default on for desktop dev builds; mobile forces off.
WF_DEBUG_BRIDGE="${WF_DEBUG_BRIDGE:-1}"

# Editor stack — collaborative editor application, CRDT, replay UI, DAP.
# Default OFF; build via `WF_ENABLE_EDITOR=1 task build` or `task build-editor`.
# The wfmut:: mutation API is compiled when EITHER WF_DEBUG_BRIDGE or
# WF_ENABLE_EDITOR is set (both consumers drive it).
WF_ENABLE_EDITOR="${WF_ENABLE_EDITOR:-0}"

# AddressSanitizer + UBSan. Default ON for this debug build (-O0 -g): Debug
# exists to catch bugs, computers are fast, and the engine+editor lifecycle is
# sanitizer-clean (verified 2026-05-20). Set WF_ASAN=0 for a fast-debug build
# (debug symbols, no instrumentation tax). Mirrors the CMake WF_ASAN
# default-for-Debug. Only the engine TUs are instrumented; vendored C libs
# (Lua/QuickJS/Wren/zForth/WAMR) + prebuilt Jolt link uninstrumented (fine).
WF_ASAN="${WF_ASAN:-1}"

mkdir -p "$OUT"

CXXFLAGS=(
    -std=c++17 -fpermissive -w -O0 -g
    -fno-rtti   # WF dispatches via kind()/EActorKind, never dynamic_cast (no-RTTI constraint).
                # Safe here: WAMR links as a prebuilt lib, its RTTI-needing C++ AOT TUs aren't compiled.
    -DWF_TARGET_LINUX -D__LINUX__ -DRENDERER_GL -DRENDERER_PIPELINE_GL -DSCALAR_TYPE_FLOAT
    -DBUILDMODE_DEBUG -DDO_ASSERTIONS=1 -DDO_DEBUGGING_INFO=1 -DDESIGNER_CHEATS=1
    -DDO_IOSTREAMS=1 -DSW_DBSTREAM=1 -DDEBUG=1 -DDEBUG_VARIABLES=1
    -DDO_VALIDATION=0 -DDO_TEST_CODE=1 -DDO_DEBUG_FILE_SYSTEM=0
    '-D__GAME__="wf_game"' "-DERR_DEBUG(x)="
    -I"$SRC" -I"$SRC/game" -I"$STUBS" -I"$STUB_SRC"
    -I"$REPO_ROOT/engine/mutation"
    -I"$VENDOR/miniaudio-0.11.25"
    -I"$VENDOR/tsf"
)

# AddressSanitizer + UBSan (see WF_ASAN above). Instrument the engine TUs and
# carry -fsanitize onto the final link so the runtime is pulled in.
declare -a SANITIZE_LINK=()
if [[ "$WF_ASAN" == "1" ]]; then
    CXXFLAGS+=(-fsanitize=address,undefined -fno-omit-frame-pointer)
    SANITIZE_LINK+=(-fsanitize=address,undefined)
fi

# Physics engine compile-time selection — must come before any other flag block
# that might read CXXFLAGS so the -DPHYSICS_ENGINE_* define is always present.
case "$WF_PHYSICS_ENGINE" in
    legacy) CXXFLAGS+=(-DPHYSICS_ENGINE_WF) ;;
    jolt)   CXXFLAGS+=(-DPHYSICS_ENGINE_JOLT -I"$JOLT_DIR") ;;
esac

if [[ "$WF_ENABLE_FENNEL" == "1" ]]; then
    CXXFLAGS+=(-DWF_ENABLE_FENNEL)
fi

case "$WF_LUA_ENGINE" in
    lua54) CXXFLAGS+=(-DWF_ENABLE_LUA -DWF_LUA_ENGINE_LUA54 -I"$LUA_DIR/src") ;;
    none)  : ;;
esac

case "$WF_JS_ENGINE" in
    quickjs)     CXXFLAGS+=(-DWF_WITH_JS -DWF_JS_ENGINE_QUICKJS -I"$QJS_DIR") ;;
    jerryscript) CXXFLAGS+=(-DWF_WITH_JS -DWF_JS_ENGINE_JERRYSCRIPT -I"$JRY_DIR/jerry-core/include") ;;
    none)        : ;;
esac

case "$WF_WASM_ENGINE" in
    wamr) CXXFLAGS+=(-DWF_WITH_WASM -DWF_WASM_ENGINE_WAMR -I"$WAMR_DIR/core/iwasm/include") ;;
    none) : ;;
esac

if [[ "$WF_ENABLE_WREN" == "1" ]]; then
    CXXFLAGS+=(-DWF_ENABLE_WREN -I"$WREN_DIR")
fi

WF_NEURAL_FORTH="${WF_NEURAL_FORTH:-auto}"   # auto → ON when zforth, OFF otherwise
case "$WF_FORTH_ENGINE" in
    zforth)   CXXFLAGS+=(-DWF_WITH_FORTH -DWF_FORTH_ENGINE_ZFORTH   -I"$STUB_SRC" -I"$ZFORTH_DIR/src/zforth")
              if [[ "$WF_NEURAL_FORTH" == "auto" || "$WF_NEURAL_FORTH" == "1" || "$WF_NEURAL_FORTH" == "ON" ]]; then
                  WF_NEURAL_FORTH=1
                  CXXFLAGS+=(-DWF_NEURAL_FORTH -I"$SCRIPT_DIR/neural-forth")
              else
                  WF_NEURAL_FORTH=0
              fi ;;
    ficl)     CXXFLAGS+=(-DWF_WITH_FORTH -DWF_FORTH_ENGINE_FICL     -I"$FICL_DIR"); WF_NEURAL_FORTH=0 ;;
    atlast)   CXXFLAGS+=(-DWF_WITH_FORTH -DWF_FORTH_ENGINE_ATLAST   -I"$ATLAST_DIR"); WF_NEURAL_FORTH=0 ;;
    embed)    CXXFLAGS+=(-DWF_WITH_FORTH -DWF_FORTH_ENGINE_EMBED    -I"$EMBED_DIR"); WF_NEURAL_FORTH=0 ;;
    libforth) CXXFLAGS+=(-DWF_WITH_FORTH -DWF_FORTH_ENGINE_LIBFORTH -I"$LIBFORTH_DIR"); WF_NEURAL_FORTH=0 ;;
    pforth)   CXXFLAGS+=(-DWF_WITH_FORTH -DWF_FORTH_ENGINE_PFORTH   -I"$PFORTH_DIR/csrc"
                         "-DPFORTH_FTH_DIR=\"$PFORTH_DIR/fth\"")
              WF_NEURAL_FORTH=0 ;;
    none)     WF_NEURAL_FORTH=0 ;;
esac

case "$WF_PILOT_ENGINE" in
    builtin) CXXFLAGS+=(-DWF_WITH_PILOT -DWF_PILOT_ENGINE_BUILTIN -I"$PILOT_DIR") ;;
    none)    : ;;
esac

if [[ "$WF_REST_API" == "1" ]]; then
    CXXFLAGS+=(-DWF_REST_API -I"$HTTPLIB_DIR")
fi

if [[ "$WF_DEBUG_BRIDGE" == "1" ]]; then
    CXXFLAGS+=(-DWF_DEBUG_BRIDGE)
fi

if [[ "$WF_ENABLE_EDITOR" == "1" ]]; then
    CXXFLAGS+=(-DWF_ENABLE_EDITOR)
fi

if [[ "$WF_ENABLE_STEAM" == "1" ]]; then
    if [[ ! -d "$STEAM_DIR/public/steam" ]]; then
        echo "error: WF_ENABLE_STEAM=1 but Steamworks SDK not found at $STEAM_DIR" >&2
        echo "       See engine/vendor/steamworks/README.md" >&2
        exit 1
    fi
    CXXFLAGS+=(-DWF_ENABLE_STEAM -I"$STEAM_DIR/public")
fi

OBJS=()

FAILED_SRCS=()

# compile_stub src obj [extra_flags...] — one-shot files (stubs, generated .cc).
# Uses the same depfile-driven staleness check as compile() so that header
# changes (e.g. scripting_stub.cc → mailbox/mailbox.inc) trigger a rebuild.
# Earlier this was a plain source-mtime check, which meant mailbox.inc edits
# silently went unnoticed and the script had to be touched manually — fixed
# while wiring up the moon position-display HUD overlay 2026-05-31.
compile_stub() {
    local src="$1" obj="$2"; shift 2
    local dep="${obj%.o}.d"

    if [[ -f "$obj" && -f "$dep" ]]; then
        local stale=0
        local prereqs
        prereqs=$(tr '\\\n' '  ' < "$dep" | sed 's/[^:]*://')
        for prereq in $prereqs; do
            [[ -z "$prereq" ]] && continue
            [[ -f "$prereq" && "$prereq" -nt "$obj" ]] && { stale=1; break; }
        done
        if [[ $stale -eq 0 ]]; then
            echo "  skip $src"
            OBJS+=("$obj")
            return
        fi
    elif [[ -f "$obj" && ! "$src" -nt "$obj" ]]; then
        # No depfile yet (first build after upgrade) — fall back to mtime check.
        echo "  skip $src"
        OBJS+=("$obj")
        return
    fi

    echo "  CC $src"
    if g++ "${CXXFLAGS[@]}" "$@" -MMD -MP -MF "$dep" -c "$src" -o "$obj" 2>&1; then
        OBJS+=("$obj")
    else
        echo "  *** FAILED: $src"
        FAILED_SRCS+=("$src")
    fi
}

compile() {
    local src="$1"
    # encode directory in object name to avoid basename collisions
    local rel="${src#$SRC/}"
    local obj="$OUT/${rel//\//__}.o"
    local dep="${obj%.o}.d"

    # Incremental: skip if .o is up-to-date w.r.t. source + all transitive headers.
    # -MMD -MP wrote $dep on the previous compile; it lists every included header.
    if [[ -f "$obj" && -f "$dep" ]]; then
        local stale=0
        # Flatten backslash-continued lines, strip the "target:" prefix, split on spaces.
        local prereqs
        prereqs=$(tr '\\\n' '  ' < "$dep" | sed 's/[^:]*://')
        for prereq in $prereqs; do
            [[ -z "$prereq" ]] && continue
            [[ -f "$prereq" && "$prereq" -nt "$obj" ]] && { stale=1; break; }
        done
        if [[ $stale -eq 0 ]]; then
            echo "  skip $src"
            OBJS+=("$obj")
            return
        fi
    fi

    echo "  CC $src"
    # -MMD -MP: write dependency file $dep listing all headers this TU includes.
    if g++ "${CXXFLAGS[@]}" -MMD -MP -MF "$dep" -c "$src" -o "$obj" 2>&1; then
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
    gfx/gl/android_window.cc
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

# Lua engine plug — compiled only when WF_LUA_ENGINE=lua54.
case "$WF_LUA_ENGINE" in
    lua54)
        compile_stub "$STUB_SRC/scripting_lua.cc" "$OUT/stubs__scripting_lua.o"
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
        ;;
    none) : ;;
esac

compile_stub "$STUB_SRC/scripting_stub.cc" "$OUT/stubs__scripting_stub.o"

# PILOT engine plug + core — pure C++, no vendored library, no editor deps.
case "$WF_PILOT_ENGINE" in
    builtin)
        compile_stub "$STUB_SRC/scripting_pilot.cc" "$OUT/stubs__scripting_pilot.o"
        compile_stub "$PILOT_DIR/pilot_core.cc"     "$OUT/pilot__pilot_core.o"
        ;;
    none) : ;;
esac
compile_stub "$STUB_SRC/platform_stubs.cc" "$OUT/stubs__platform_stubs.o"

# JS engine plug — compiled and linked only when a non-`none` flavour is selected.
declare -a JS_LINK_EXTRA=()
case "$WF_JS_ENGINE" in
    quickjs)
        compile_stub "$STUB_SRC/scripting_quickjs.cc" "$OUT/stubs__scripting_quickjs.o"
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
        compile_stub "$STUB_SRC/scripting_jerryscript.cc" "$OUT/stubs__scripting_jerryscript.o"
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
                  -DCMAKE_C_FLAGS="-w" \
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

# wasm engine plug — compiled and linked based on WF_WASM_ENGINE.
case "$WF_WASM_ENGINE" in
    wamr)
        compile_stub "$STUB_SRC/scripting_wamr.cc" "$OUT/stubs__scripting_wamr.o"
        # WAMR 2.2.0 classic interpreter — build via CMake into a static lib.
        # The build output is cached in OUT/wamr_build so subsequent runs skip cmake.
        WAMR_BUILD="$OUT/wamr_build"
        WAMR_LIB="$WAMR_BUILD/libvmlib.a"
        if [[ ! -f "$WAMR_LIB" ]]; then
            WAMR_CMAKE="$WAMR_BUILD/CMakeLists.txt"
            mkdir -p "$WAMR_BUILD"
            cat > "$WAMR_CMAKE" << 'WAMRCMAKE'
cmake_minimum_required(VERSION 3.14)
project(wamr_wf C)
set(WAMR_BUILD_PLATFORM  "linux")
set(WAMR_BUILD_TARGET    "X86_64")
set(WAMR_BUILD_INTERP    1)
set(WAMR_BUILD_AOT       0)
set(WAMR_BUILD_JIT       0)
set(WAMR_BUILD_FAST_JIT  0)
set(WAMR_BUILD_FAST_INTERP 1)
set(WAMR_BUILD_LIBC_BUILTIN 0)
set(WAMR_BUILD_LIBC_WASI 0)
set(WAMR_BUILD_SIMD      0)
set(WAMR_BUILD_MULTI_MODULE 0)
set(WAMR_BUILD_LIB_PTHREAD 0)
set(WAMR_BUILD_WASM_C_API 1)
include(${WAMR_ROOT_DIR}/build-scripts/runtime_lib.cmake)
add_library(vmlib STATIC ${WAMR_RUNTIME_LIB_SOURCE})
target_include_directories(vmlib PUBLIC ${WAMR_ROOT_DIR}/core/iwasm/include)
WAMRCMAKE
            echo "  CMAKE wamr"
            cmake -S "$WAMR_BUILD" -B "$WAMR_BUILD/out" \
                  -DWAMR_ROOT_DIR="$WAMR_DIR" \
                  -DCMAKE_BUILD_TYPE=MinSizeRel \
                  -DCMAKE_C_FLAGS="-w" \
                  > "$OUT/wamr_cmake.log" 2>&1 \
                  || { echo "  *** wamr cmake failed; see $OUT/wamr_cmake.log" >&2; exit 1; }
            cmake --build "$WAMR_BUILD/out" -j --target vmlib \
                  >> "$OUT/wamr_cmake.log" 2>&1 \
                  || { echo "  *** wamr build failed; see $OUT/wamr_cmake.log" >&2; exit 1; }
            cp "$WAMR_BUILD/out/libvmlib.a" "$WAMR_LIB"
        fi
        OBJS+=("$WAMR_LIB")
        ;;
    none) : ;;
esac

# Forth engine plug — compiled only when WF_FORTH_ENGINE is not `none`.
FORTH_VENDOR_CFLAGS=(-std=gnu11 -O2 -w -fno-strict-aliasing)
case "$WF_FORTH_ENGINE" in
    zforth)
        compile_stub "$STUB_SRC/scripting_zforth.cc" "$OUT/stubs__scripting_zforth.o"
        # zForth core (C). Two source files; -O2; warnings silenced (vendor).
        # zfconf.h is provided by STUB_SRC (listed first in CXXFLAGS -I flags).
        ZF_CFLAGS=(-std=gnu11 -O2 -w -fno-strict-aliasing
                   -I"$STUB_SRC" -I"$ZFORTH_DIR/src/zforth")
        obj="$OUT/zforth__zforth.o"
        echo "  CC (vendor) zforth/zforth.c"
        gcc "${ZF_CFLAGS[@]}" -c "$ZFORTH_DIR/src/zforth/zforth.c" -o "$obj"
        OBJS+=("$obj")
        # Neural-forth AI library — ON by default when zforth is the Forth engine.
        # Six C sources: fuzzy logic, neural networks, autograd tape, ∂4 slots.
        if [[ "$WF_NEURAL_FORTH" == "1" ]]; then
            NF_DIR="$SCRIPT_DIR/neural-forth"
            NF_CFLAGS=(-std=gnu11 -O2 -Wall -Wextra
                       -DWF_NEURAL_FORTH -DWF_FORTH_ENGINE_ZFORTH
                       -I"$NF_DIR" -I"$ZFORTH_DIR/src/zforth" -I"$STUB_SRC")
            for nf_src in dictionary.c tensor.c autograd.c fuzzy.c nn.c slot.c; do
                obj="$OUT/nf__${nf_src%.c}.o"
                echo "  CC neural-forth/$nf_src"
                gcc "${NF_CFLAGS[@]}" -c "$NF_DIR/$nf_src" -o "$obj"
                OBJS+=("$obj")
            done
        fi
        ;;
    ficl)
        compile_stub "$STUB_SRC/scripting_ficl.cc" "$OUT/stubs__scripting_ficl.o"
        # ficl-3.06 core (C). Compile the non-test, non-platform-specific files.
        # Exclude: testmain.c, unity.c (test framework), wasm_main.c (wasm host).
        FICL_CFLAGS=("${FORTH_VENDOR_CFLAGS[@]}" -I"$FICL_DIR")
        for ficl_src in dict.c dpmath.c ficl.c fileaccess.c float.c prefix.c \
                        search.c stack.c sysdep.c tools.c vm.c words.c; do
            obj="$OUT/ficl__${ficl_src%.c}.o"
            echo "  CC (vendor) ficl/$ficl_src"
            gcc "${FICL_CFLAGS[@]}" -c "$FICL_DIR/$ficl_src" -o "$obj"
            OBJS+=("$obj")
        done
        ;;
    atlast)
        compile_stub "$STUB_SRC/scripting_atlast.cc" "$OUT/stubs__scripting_atlast.o"
        # atlast-64: single source file. -DEXPORT makes internal globals
        # non-static so scripting_atlast.cc can access stack pointers via
        # atldef.h macros (stk/stackbot/S0/Pop/Push = atl__sp etc.).
        ATLAST_CFLAGS=("${FORTH_VENDOR_CFLAGS[@]}" -DEXPORT -I"$ATLAST_DIR")
        obj="$OUT/atlast__atlast.o"
        echo "  CC (vendor) atlast-64/atlast.c"
        gcc "${ATLAST_CFLAGS[@]}" -c "$ATLAST_DIR/atlast.c" -o "$obj"
        OBJS+=("$obj")
        ;;
    embed)
        compile_stub "$STUB_SRC/scripting_embed.cc" "$OUT/stubs__scripting_embed.o"
        # embed: embed.c (VM + built-in ROM image) and image.c (image utilities).
        # Exclude main.c and util.c (standalone tool, not needed for embedding).
        EMBED_CFLAGS=("${FORTH_VENDOR_CFLAGS[@]}" -I"$EMBED_DIR")
        for embed_src in embed.c image.c; do
            obj="$OUT/embed__${embed_src%.c}.o"
            echo "  CC (vendor) embed/$embed_src"
            gcc "${EMBED_CFLAGS[@]}" -c "$EMBED_DIR/$embed_src" -o "$obj"
            OBJS+=("$obj")
        done
        ;;
    libforth)
        compile_stub "$STUB_SRC/scripting_libforth.cc" "$OUT/stubs__scripting_libforth.o"
        # libforth: single source file. Exclude main.c (standalone REPL).
        LIBFORTH_CFLAGS=("${FORTH_VENDOR_CFLAGS[@]}" -I"$LIBFORTH_DIR")
        obj="$OUT/libforth__libforth.o"
        echo "  CC (vendor) libforth/libforth.c"
        gcc "${LIBFORTH_CFLAGS[@]}" -c "$LIBFORTH_DIR/libforth.c" -o "$obj"
        OBJS+=("$obj")
        ;;
    pforth)
        compile_stub "$STUB_SRC/scripting_pforth.cc" "$OUT/stubs__scripting_pforth.o"
        # pForth csrc/ files. Exclude:
        #   pf_main.c      — standalone main()
        #   pf_io_none.c   — alternate I/O stub (conflicts with pf_io.c)
        #   pfcustom.c     — default glue body; scripting_pforth.cc provides
        #                    CustomFunctionTable/CompileCustomFunctions instead.
        # pfcglue.c is compiled with -DPF_USER_CUSTOM=1 to suppress the
        # default implementations; scripting_pforth.cc provides them.
        PFORTH_CFLAGS=("${FORTH_VENDOR_CFLAGS[@]}" -I"$PFORTH_DIR/csrc")
        for pf_src in pf_cglue.c pf_clib.c pfcompil.c pf_core.c pf_inner.c \
                      pf_io.c pf_mem.c pf_save.c pf_text.c pf_words.c; do
            obj="$OUT/pforth__${pf_src%.c}.o"
            echo "  CC (vendor) pforth/csrc/$pf_src"
            gcc "${PFORTH_CFLAGS[@]}" -c "$PFORTH_DIR/csrc/$pf_src" -o "$obj"
            OBJS+=("$obj")
        done
        # POSIX terminal I/O backend (provides sdTerminalOut/In/Init/Flush etc.)
        obj="$OUT/pforth__posix__pf_io_posix.o"
        echo "  CC (vendor) pforth/csrc/posix/pf_io_posix.c"
        gcc "${PFORTH_CFLAGS[@]}" -I"$PFORTH_DIR/csrc/posix" \
            -c "$PFORTH_DIR/csrc/posix/pf_io_posix.c" -o "$obj"
        OBJS+=("$obj")
        # stdio file I/O backend (provides sdResizeFile, sdOpenFile, etc.)
        obj="$OUT/pforth__stdio__pf_fileio_stdio.o"
        echo "  CC (vendor) pforth/csrc/stdio/pf_fileio_stdio.c"
        gcc "${PFORTH_CFLAGS[@]}" -I"$PFORTH_DIR/csrc/stdio" \
            -c "$PFORTH_DIR/csrc/stdio/pf_fileio_stdio.c" -o "$obj"
        OBJS+=("$obj")
        # pfcustom.c compiled with -DPF_USER_CUSTOM=1 to suppress default body.
        obj="$OUT/pforth__pfcustom.o"
        echo "  CC (vendor) pforth/csrc/pfcustom.c (PF_USER_CUSTOM=1)"
        gcc "${PFORTH_CFLAGS[@]}" -DPF_USER_CUSTOM=1 -c "$PFORTH_DIR/csrc/pfcustom.c" -o "$obj"
        OBJS+=("$obj")
        ;;
    none) : ;;
esac

# Wren engine plug — compiled only when WF_ENABLE_WREN=1.
if [[ "$WF_ENABLE_WREN" == "1" ]]; then
    compile_stub "$STUB_SRC/scripting_wren.cc" "$OUT/stubs__scripting_wren.o"
    # Wren 0.4.0 amalgamation (C, not C++). Single TU; -O2; warnings silenced.
    WREN_CFLAGS=(-std=gnu11 -O2 -w -fno-strict-aliasing -I"$WREN_DIR")
    obj="$OUT/wren__wren.o"
    echo "  CC (vendor) wren/wren.c"
    gcc "${WREN_CFLAGS[@]}" -c "$WREN_DIR/wren.c" -o "$obj"
    OBJS+=("$obj")
fi

# Steam plug — compiled only when WF_ENABLE_STEAM=1.
declare -a STEAM_LINK_EXTRA=()
if [[ "$WF_ENABLE_STEAM" == "1" ]]; then
    compile_stub "$SRC/hal/linux/steam.cc" "$OUT/hal__linux__steam.o"
    STEAM_LINK_EXTRA+=("-L$STEAM_DIR/redistributable_bin/linux64" "-lsteam_api"
                       "-Wl,-rpath,\$ORIGIN")
fi

# REST API plug — compiled only when WF_REST_API=1.
if [[ "$WF_REST_API" == "1" ]]; then
    compile_stub "$STUB_SRC/rest_api.cc" "$OUT/stubs__rest_api.o" -O1
fi

# Debug bridge plug — compiled only when WF_DEBUG_BRIDGE=1.
if [[ "$WF_DEBUG_BRIDGE" == "1" ]]; then
    compile_stub "$STUB_SRC/debug_server.cc" "$OUT/stubs__debug_server.o" -O1
fi

# Engine mutation API + smoke — compiled when EITHER consumer flag is on
# (bridge consumes wfmut after the step-6 refactor; editor consumes it from
# the CRDT bridge). See docs/plans/2026-05-19-engine-mutation-api.md.
if [[ "$WF_DEBUG_BRIDGE" == "1" || "$WF_ENABLE_EDITOR" == "1" ]]; then
    compile_stub "$REPO_ROOT/engine/mutation/wfmut.cpp" "$OUT/mutation__wfmut.o" -O1
    compile_stub "$REPO_ROOT/engine/mutation/wfmut_smoke.cpp" "$OUT/mutation__wfmut_smoke.o" -O1
fi

# Jolt physics plug — compiled and linked only when WF_PHYSICS_ENGINE=jolt.
# Jolt is built via CMake into a static library (cached in OUT/jolt_build).
# The physics_jolt.cc stub owns JoltRuntimeInit/Shutdown and the selftest.
declare -a JOLT_LINK_EXTRA=()
if [[ "$WF_PHYSICS_ENGINE" == "jolt" ]]; then
    compile_stub "$STUB_SRC/physics_jolt.cc" "$OUT/stubs__physics_jolt.o" -O2 -DNDEBUG
    compile_stub "$SRC/physics/jolt/jolt_backend.cc" "$OUT/physics__jolt__jolt_backend.o" -O2 -DNDEBUG

    JOLT_BUILD="$OUT/jolt_build"
    JOLT_LIB="$JOLT_BUILD/libJolt.a"
    if [[ ! -f "$JOLT_LIB" ]]; then
        JOLT_CMAKE="$JOLT_BUILD/CMakeLists.txt"
        mkdir -p "$JOLT_BUILD"
        cat > "$JOLT_CMAKE" << 'JOLTCMAKE'
cmake_minimum_required(VERSION 3.16)
project(jolt_wf CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Jolt.cmake creates the Jolt target and alias Jolt::Jolt itself.
# We only need to point it at the source root and configure the target after.
set(PHYSICS_REPO_ROOT "$ENV{JOLT_DIR}")

# Use only NDEBUG — Jolt's own headers suppress the profiler, debug renderer,
# and assertions based on NDEBUG.  Explicit JPH_*=0 defines cause a
# JPH_VERSION_ID mismatch (the macro is then "defined" even though its value
# is 0, so Jolt's #ifdef checks fire differently in the lib vs. the stub).
add_compile_definitions(NDEBUG)

include(${PHYSICS_REPO_ROOT}/Jolt/Jolt.cmake)

# Jolt.cmake has now created the Jolt static-library target.
# Apply WF-specific compiler options to it.
target_compile_options(Jolt PRIVATE -O2 -w)
JOLTCMAKE

        echo "  CMAKE jolt"
        JOLT_DIR="$JOLT_DIR" cmake -S "$JOLT_BUILD" -B "$JOLT_BUILD/out" \
              -DCMAKE_BUILD_TYPE=MinSizeRel \
              > "$OUT/jolt_cmake.log" 2>&1 \
              || { echo "  *** jolt cmake failed; see $OUT/jolt_cmake.log" >&2; exit 1; }
        cmake --build "$JOLT_BUILD/out" -j --target Jolt \
              >> "$OUT/jolt_cmake.log" 2>&1 \
              || { echo "  *** jolt build failed; see $OUT/jolt_cmake.log" >&2; exit 1; }
        cp "$JOLT_BUILD/out/libJolt.a" "$JOLT_LIB"
    fi
    JOLT_LINK_EXTRA+=("$JOLT_LIB")
fi

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
    compile_stub "$FENNEL_CC" "$OUT/fennel_source.o"
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

# Editor/dev builds emit a separate binary (wf_game-dev) so they never overwrite
# the lean game-engine output (wf_game). Both can coexist side-by-side; the
# shipped game uses wf_game. (NB: the GUI desktop editor is a different program,
# CMake target wf_edit → build-editor/wf-edit — not this binary.)
if [[ "$WF_ENABLE_EDITOR" == "1" ]]; then
    WF_BIN_NAME="wf_game-dev"
else
    WF_BIN_NAME="wf_game"
fi

g++ "${SANITIZE_LINK[@]}" "${OBJS[@]}" "${JS_LINK_EXTRA[@]}" "${JOLT_LINK_EXTRA[@]}" "${STEAM_LINK_EXTRA[@]}" \
    -lGL -lGLU -lX11 -lm -lpthread -ldl \
    -Wl,-z,noexecstack \
    -o "$SCRIPT_DIR/$WF_BIN_NAME"

echo ""
echo "Built: $SCRIPT_DIR/$WF_BIN_NAME"
echo "Run:   cd $SRC/game && DISPLAY=:0 $SCRIPT_DIR/$WF_BIN_NAME"
