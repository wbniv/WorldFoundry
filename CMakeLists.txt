cmake_minimum_required(VERSION 3.22)
project(wf_game VERSION 1.0.0 LANGUAGES CXX C)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# ─── Paths ────────────────────────────────────────────────────────────────────
set(SRC      ${CMAKE_SOURCE_DIR}/wfsource/source)
set(STUB_SRC ${CMAKE_SOURCE_DIR}/engine/stubs)
set(ENG_INC  ${CMAKE_SOURCE_DIR}/engine/include)
set(VENDOR   ${CMAKE_SOURCE_DIR}/engine/vendor)

# ─── Feature flags ────────────────────────────────────────────────────────────
option(WF_ENABLE_FENNEL   "Fennel (Lisp→Lua) scripting"  ON)
set(WF_LUA_ENGINE    "lua54"    CACHE STRING "lua54 | none")
set(WF_JS_ENGINE     "quickjs"  CACHE STRING "none | quickjs | jerryscript")
set(WF_WASM_ENGINE   "wamr"     CACHE STRING "none | wamr")
option(WF_ENABLE_WREN     "Wren scripting"                ON)
set(WF_FORTH_ENGINE  "zforth"   CACHE STRING "none | zforth | ficl | atlast | embed | libforth | pforth")
set(WF_PILOT_ENGINE  "builtin"  CACHE STRING "none | builtin")  # PILOT — from-scratch C++, no vendored lib
# Default ON when zforth is selected, OFF otherwise. cmake_dependent_option auto-tracks
# WF_FORTH_ENGINE so reconfiguring to a different Forth engine flips this off cleanly.
include(CMakeDependentOption)
cmake_dependent_option(WF_NEURAL_FORTH
    "Neural-forth AI library — fuzzy logic, neural networks, ∂4 trainable slots."
    ON
    "WF_FORTH_ENGINE STREQUAL \"zforth\""
    OFF)
set(WF_PHYSICS_ENGINE "jolt"    CACHE STRING "legacy | jolt")
option(WF_REST_API        "REST API box PoC (HTTP runtime-mutation debug)" ON)
option(WF_DEBUG_BRIDGE    "TCP/JSON debug bridge — level-design + AI-agent debugging (Blender live edit, etc.). Independent of WF_ENABLE_EDITOR." ON)
option(WF_ENABLE_STEAM    "Steamworks SDK"                OFF)
# AddressSanitizer + UBSan. Default **ON for host Debug builds** — Debug exists
# to catch bugs, computers are fast, and the whole engine+editor lifecycle is
# sanitizer-clean (verified 2026-05-20). Release / Android / iOS stay clean and
# uninstrumented. The "fast-debug" build (Debug symbols, no sanitizer tax) is
# `-DWF_ASAN=OFF` (see `task build-fast`). Overridable either way.
set(_WF_ASAN_DEFAULT OFF)
if(CMAKE_BUILD_TYPE STREQUAL "Debug" AND NOT ANDROID AND NOT IOS AND NOT EMSCRIPTEN)
    set(_WF_ASAN_DEFAULT ON)
endif()
option(WF_ASAN "AddressSanitizer + UBSan (default ON for host Debug; -DWF_ASAN=OFF = fast-debug)" ${_WF_ASAN_DEFAULT})

# Editor stack — collaborative editor app, CRDT bridge, replay UI, etc.
# Independent of WF_DEBUG_BRIDGE (the bridge is general-purpose debug
# infrastructure, used by level designers and AI agents alike; the editor is
# the collaborative-editing application). Default OFF — the "original game
# engine" is the common case. Editor stack is opt-in via `task build-editor`
# or `-DWF_ENABLE_EDITOR=ON`. Force OFF on Android/iOS where there is no
# editor host and the surface won't compile. See
# feedback_editor_code_compile_gate.md.
#
# Covers:
#   - engine/crdt/          (libwfcrdt.a wrapping libyrs.a via Corrosion+Cargo)
#   - future: DAP debugger, replay UI, scene-graph inspection, etc.
#
# wfmut:: lives at the UNION of WF_DEBUG_BRIDGE and WF_ENABLE_EDITOR — both
# consumers drive it (bridge for its SET_TRANSFORM / SET_PROP / SET_MAILBOX
# cases, editor for its CRDT bridge). See the per-source-list gate below.
option(WF_ENABLE_EDITOR   "Build the collaborative editor stack (CRDT + replay UI + DAP, etc.). OFF for shipped game-engine builds; ON for the editor application." OFF)

# Browser/WASM editor (wf_edit_web): the Dear ImGui editor compiled to
# Emscripten/WebGL2. Only meaningful under EMSCRIPTEN. When ON it re-enables the
# WF_ENABLE_EDITOR umbrella (so the CRDT lib builds) but the NATIVE wf_edit target
# stays out (it is gated `AND NOT EMSCRIPTEN`). v1 = co-edit + presence + chat;
# voice/video native libs are compiled out. See
# docs/plans/2026-06-12-wf-edit-in-the-browser.md.
option(WF_ENABLE_WEB_EDITOR "Build the browser/WASM collaborative editor (wf_edit_web). Requires EMSCRIPTEN." OFF)

# Mobile (Android + iOS): Forth-only, no scripting roster, no bridge/REST/editor.
# WAMR ships x86_64 assembly (invokeNative_em64.s) that fails on arm64 mobile.
if(ANDROID OR IOS)
    set(WF_LUA_ENGINE    "none"   CACHE STRING "" FORCE)
    set(WF_ENABLE_FENNEL OFF      CACHE BOOL   "" FORCE)
    set(WF_JS_ENGINE     "none"   CACHE STRING "" FORCE)
    set(WF_WASM_ENGINE   "none"   CACHE STRING "" FORCE)
    set(WF_ENABLE_WREN   OFF      CACHE BOOL   "" FORCE)
    set(WF_FORTH_ENGINE  "zforth" CACHE STRING "" FORCE)
    set(WF_PILOT_ENGINE  "none"   CACHE STRING "" FORCE)  # mobile = Forth-only scripting
    set(WF_REST_API      OFF      CACHE BOOL   "" FORCE)
    set(WF_DEBUG_BRIDGE  OFF      CACHE BOOL   "" FORCE)
    set(WF_ENABLE_STEAM  OFF      CACHE BOOL   "" FORCE)
    set(WF_ENABLE_EDITOR OFF      CACHE BOOL   "" FORCE)
elseif(EMSCRIPTEN)
    # Web (browser/wasm): Forth-only scripting, like mobile. WAMR ships x86-64
    # inline asm; bridge/REST are raw-TCP servers; no editor host, no Steam.
    # See docs/plans/2026-06-11-web-canvas-port.md (D5).
    set(WF_LUA_ENGINE    "none"   CACHE STRING "" FORCE)
    set(WF_ENABLE_FENNEL OFF      CACHE BOOL   "" FORCE)
    set(WF_JS_ENGINE     "none"   CACHE STRING "" FORCE)
    set(WF_WASM_ENGINE   "none"   CACHE STRING "" FORCE)
    set(WF_ENABLE_WREN   OFF      CACHE BOOL   "" FORCE)
    set(WF_FORTH_ENGINE  "zforth" CACHE STRING "" FORCE)
    set(WF_PILOT_ENGINE  "none"   CACHE STRING "" FORCE)
    set(WF_REST_API      OFF      CACHE BOOL   "" FORCE)
    set(WF_DEBUG_BRIDGE  OFF      CACHE BOOL   "" FORCE)
    set(WF_ENABLE_STEAM  OFF      CACHE BOOL   "" FORCE)
    # The browser editor (wf_edit_web) reuses the engine's CRDT lib (engine/crdt
    # → libwfcrdt.a → libyrs.a). WF_ENABLE_WEB_EDITOR flips the WF_ENABLE_EDITOR
    # umbrella back ON *only* for that subdir — the native wf_edit target is also
    # gated `AND NOT EMSCRIPTEN`, so it never enters the web build. yffi
    # cross-compiles to wasm via the rustup toolchain; pin the cargo target
    # because Corrosion's FindRust has no Emscripten branch and otherwise falls
    # back to the host triple under emcmake (see project_wasm_editor_rust_toolchain
    # + docs/plans/2026-06-12-wf-edit-in-the-browser.md Phase 0).
    if(WF_ENABLE_WEB_EDITOR)
        set(WF_ENABLE_EDITOR ON CACHE BOOL "" FORCE)
        if(NOT DEFINED Rust_CARGO_TARGET)
            set(Rust_CARGO_TARGET "wasm32-unknown-emscripten" CACHE STRING "" FORCE)
        endif()
    else()
        set(WF_ENABLE_EDITOR OFF CACHE BOOL "" FORCE)
    endif()
elseif(APPLE)
    # macOS desktop: full scripting roster (Lua/Fennel/QuickJS/Wren + zForth)
    # and debug bridge enabled. WAMR deferred (macOS arm64 unverified). Editor
    # and Steam not yet ported.
    set(WF_WASM_ENGINE   "none"   CACHE STRING "" FORCE)
    set(WF_ENABLE_EDITOR OFF      CACHE BOOL   "" FORCE)
    set(WF_ENABLE_STEAM  OFF      CACHE BOOL   "" FORCE)
    set(WF_FORTH_ENGINE  "zforth" CACHE STRING "" FORCE)
endif()

# Debug builds force the bridge ON. The Blender addon's "Live" features
# (debug_bridge.py / panels.py / operators.py — all default port 7777)
# rely on it; surprising them with an opt-in flag broke at least one
# user's workflow when the bridge briefly defaulted off. Mobile is already
# forced OFF above; the NOT(ANDROID OR IOS) guard preserves that.
if(NOT (ANDROID OR IOS OR EMSCRIPTEN) AND CMAKE_BUILD_TYPE STREQUAL "Debug")
    set(WF_DEBUG_BRIDGE ON CACHE BOOL "Debug build forces bridge on" FORCE)
endif()

# ─── Fennel/Lua consistency check ─────────────────────────────────────────────
if(WF_ENABLE_FENNEL AND NOT WF_LUA_ENGINE STREQUAL "lua54")
    message(WARNING "WF_ENABLE_FENNEL=ON but WF_LUA_ENGINE!=lua54; forcing WF_LUA_ENGINE=lua54")
    set(WF_LUA_ENGINE "lua54" CACHE STRING "" FORCE)
endif()

# ─── Accumulated lists (filled below) ─────────────────────────────────────────
set(WF_SOURCES)
set(WF_INCLUDES  ${SRC} ${SRC}/game ${ENG_INC} ${STUB_SRC}
                 ${CMAKE_SOURCE_DIR}/engine/mutation
                 ${VENDOR}/miniaudio-0.11.25 ${VENDOR}/tsf)
set(WF_DEFS)
set(WF_LINK_LIBS)

# ─── Platform definitions ─────────────────────────────────────────────────────
if(ANDROID)
    list(APPEND WF_DEFS WF_TARGET_ANDROID __ANDROID__
                        RENDERER_GLES RENDERER_PIPELINE_GLES SCALAR_TYPE_FLOAT)
elseif(IOS)
    # Phase 2B2: most of the engine (incl. game/physics) compiles; only gfx/gl +
    # gfx/glpipeline (X11/GLX, GL-only) stay out — iOS renders via hal/ios Metal.
    # No RENDERER_* define yet. Physics is Jolt (the Xcode-safe Jolt block below).
    list(APPEND WF_DEFS WF_TARGET_IOS SCALAR_TYPE_FLOAT)
elseif(APPLE)
    # macOS desktop — renderer-agnostic bring-up. No RENDERER_* (rendering is a
    # true no-op via engine/stubs/renderer_stub.cc); gfx/gl + gfx/glpipeline are
    # excluded like iOS. The real Metal renderer lands later, shared with iOS.
    list(APPEND WF_DEFS WF_TARGET_MACOS SCALAR_TYPE_FLOAT)
elseif(EMSCRIPTEN)
    # Web (browser/wasm): GLES3 renderer (WebGL 2) like Android; cf_linux.h
    # platform header like macOS — here __LINUX__ means "POSIX", and the
    # compiler-provided __EMSCRIPTEN__ guards the X11-vs-web splits.
    # See docs/plans/2026-06-11-web-canvas-port.md (D1).
    list(APPEND WF_DEFS WF_TARGET_WEB __LINUX__
                        RENDERER_GLES RENDERER_PIPELINE_GLES SCALAR_TYPE_FLOAT)
else()
    list(APPEND WF_DEFS WF_TARGET_LINUX __LINUX__
                        RENDERER_GL RENDERER_PIPELINE_GL SCALAR_TYPE_FLOAT)
endif()

list(APPEND WF_DEFS
    BUILDMODE_DEBUG DO_ASSERTIONS=1 DO_DEBUGGING_INFO=1
    DO_IOSTREAMS=1 SW_DBSTREAM=1 DEBUG=1 DEBUG_VARIABLES=1
    DO_VALIDATION=0 DO_TEST_CODE=0 DO_DEBUG_FILE_SYSTEM=0
)

if(WF_ASAN AND NOT ANDROID AND NOT IOS)
    # vptr is excluded: the whole project builds -fno-rtti (Jolt, wfengine,
    # wf_game, wf_edit, the test harness), and UBSan's vptr check cannot validate
    # vtables without RTTI — it emits false "invalid vptr" runtime errors on every
    # polymorphic object (notably libdatachannel + std::future in wf-edit's WebRTC
    # path). vptr checking is meaningless under -fno-rtti, so turn it off.
    add_compile_options(-fsanitize=address,undefined -fno-sanitize=vptr -fno-omit-frame-pointer)
    # Static-link the sanitizer runtimes into each executable (no libasan.so.8 /
    # libubsan.so.1 in NEEDED). This makes the binaries self-contained — no
    # dependency on a matching system libasan, and the "ASan runtime does not come
    # first in initial library list" ordering check can never fire, including for
    # any forked/re-exec'd child (wf-edit re-execs itself + spawns helper procs).
    add_link_options(-fsanitize=address,undefined -fno-sanitize=vptr -static-libasan -static-libubsan)
    message(STATUS "WF_ASAN: AddressSanitizer + UBSan enabled, runtime static-linked (vptr excluded — project is -fno-rtti)")
endif()

# ─── Source directories ───────────────────────────────────────────────────────
if(ANDROID)
    set(WF_DIRS
        pigsys streams cpplib math memory iff mailbox
        hal hal/android
        gfx gfx/gl gfx/glpipeline
        input asset baseobject movement room physics
        anim timer scripting game ini loadfile
        profile renderassets savegame savegame/android
        menu particle audio/linux  # miniaudio impl is portable; dir name is legacy
    )
elseif(IOS)
    # Phase 2B2: most of the engine. gfx/gl (X11/GLX) and gfx/glpipeline
    # (GL-only backend) stay out; iOS renders through hal/ios/metal_view.mm
    # + (Phase 2B3) a Metal RendererBackend.
    # savegame/linux is reused — it's POSIX file I/O, works on Darwin too.
    set(WF_DIRS
        pigsys streams cpplib math memory iff mailbox
        hal hal/ios
        gfx
        input asset baseobject movement room physics
        anim timer scripting game ini loadfile
        profile renderassets savegame savegame/linux
        menu particle audio/linux
    )
elseif(APPLE)
    # macOS desktop — mirrors iOS: gfx/gl (X11/GLX) + gfx/glpipeline (GL backend)
    # excluded; rendering is a no-op. hal/macos provides the entry shell, the
    # headless Display, and GL/window stubs. The portable Linux HAL files
    # (platform_init/audio/input/lifecycle/asset_accessor_posix) are reused
    # explicitly in the macOS stub-sources block below. savegame/linux +
    # audio/linux are POSIX/miniaudio — Darwin-portable.
    set(WF_DIRS
        pigsys streams cpplib math memory iff mailbox
        hal hal/macos
        gfx
        input asset baseobject movement room physics
        anim timer scripting game ini loadfile
        profile renderassets savegame savegame/linux
        menu particle audio/linux
    )
elseif(EMSCRIPTEN)
    # Web: full GL stack like Linux (GLES branches like Android), hal/emscripten
    # for the entry shell. The portable Linux HAL files (platform_init, audio,
    # input, lifecycle, asset_accessor_posix) are reused explicitly in the
    # Emscripten extra-sources block below — same mechanism as macOS.
    # savegame/ dirs are vestigial on every platform (no such directory; the
    # GLOB is empty) — kept for symmetry.
    set(WF_DIRS
        pigsys streams cpplib math memory iff mailbox
        hal hal/emscripten
        gfx gfx/gl gfx/glpipeline
        input asset baseobject movement room physics
        anim timer scripting game ini loadfile
        profile renderassets savegame savegame/linux
        menu particle audio/linux
    )
else()
    set(WF_DIRS
        pigsys streams cpplib math memory iff mailbox
        hal hal/linux
        gfx gfx/gl gfx/glpipeline
        input asset baseobject movement room physics
        anim timer scripting game ini loadfile
        profile renderassets savegame savegame/linux
        menu particle audio/linux
    )
endif()

# ─── Skip list (relative to SRC) ──────────────────────────────────────────────
set(WF_SKIP
    physics/physicstest.cc      timer/testtime.cc
    anim/animtest.cc            anim/preview.cc         anim/test.cc
    streams/strtest.cc          math/mathtest.cc
    scripting/scriptingtest.cc  pigsys/psystest.cc      cpplib/cpptest.cc
    memory/memtest.cc           savegame/savetest.cc
    menu/font.cc                menu/menutest.cc
    particle/test.cc            gfx/gfxtest.cc          ini/initest.cc
    pigsys/scanf.cc
    gfx/gl/unused.cc            gfx/gl/wgl.cc           gfx/otable.cc
    attrib/
    # sub-files #included by parent .cc — not compiled directly
    gfx/gl/mesa.cc              gfx/gl/android_window.cc    gfx/gl/emscripten_window.cc
    gfx/gl/rendobj3.cc          gfx/gl/viewport.cc
    gfx/gl/display.cc
    gfx/glpipeline/rendobj3.cc
    math/matrix3t.cc            math/quat.cc            math/tables.cc
    cpplib/afftform.cc
    hal/dfoff.cc                hal/haltest.cc
    asset/assettest.cc          movement/movementtest.cc
    room/callbacks.cc
    # replaced by scripting_stub.cc
    scripting/scriptinterpreter.cc  scripting/tcl.cc
    scripting/perl/scriptinterpreter_perl.cc
)

# iOS: skip files that aren't standalone translation units.
#  - display_ios.cc: #included from gfx/display.cc when WF_TARGET_IOS is
#    defined (same pattern as gfx/gl/display.cc on Linux).
# audio.mm + input.mm are now needed once HALStart runs on iOS (Phase 2C).
if(IOS)
    list(APPEND WF_SKIP
        hal/ios/display_ios.cc
    )
elseif(APPLE)
    # display_macos.cc is #included from gfx/display.cc (same pattern as
    # display_ios.cc / gfx/gl/display.cc), not a standalone TU.
    list(APPEND WF_SKIP
        hal/macos/display_macos.cc
    )
elseif(EMSCRIPTEN)
    list(APPEND WF_SKIP
        # X11/GLX editor-host context registry — guard is __LINUX__ &&
        # !__ANDROID__, which matches the web build (D1 defines __LINUX__).
        gfx/gl/host_gl_context.cc
    )
endif()

# ─── Collect sources with skip filter ─────────────────────────────────────────
# .mm is Objective-C++, only used by hal/ios/ today. Globbing it unconditionally
# is safe — no other platform ships .mm sources.
foreach(dir ${WF_DIRS})
    file(GLOB dir_srcs "${SRC}/${dir}/*.cc" "${SRC}/${dir}/*.mm")
    foreach(src ${dir_srcs})
        file(RELATIVE_PATH rel ${SRC} ${src})
        set(_skip FALSE)
        foreach(pat ${WF_SKIP})
            if(rel STREQUAL pat OR rel MATCHES "^${pat}")
                set(_skip TRUE)
                break()
            endif()
        endforeach()
        if(NOT _skip)
            list(APPEND WF_SOURCES ${src})
        endif()
    endforeach()
endforeach()

# Always-compiled stubs
list(APPEND WF_SOURCES
    ${STUB_SRC}/scripting_stub.cc
    ${STUB_SRC}/platform_stubs.cc
)

# iOS: link stubs for the 8 GL-backend RenderObject3D::RenderPoly3D* methods
# that Material::Get3DRenderObjectPtr references unconditionally. Real impls
# land with the Metal backend in Phase 2B3.
#
# backend_factory.cc lives in gfx/glpipeline/ which is excluded from the
# iOS build (rest of glpipeline hard-depends on GLES), but it's
# backend-agnostic and picks Metal on iOS via a WF_TARGET_IOS #ifdef.
if(IOS)
    list(APPEND WF_SOURCES
        ${STUB_SRC}/renderpoly3d_stubs.cc
        ${SRC}/gfx/glpipeline/backend_factory.cc
    )
elseif(APPLE)
    # macOS desktop — renderer-agnostic bring-up. The 8 RenderPoly3D link stubs +
    # the no-op RendererBackend + backend_factory (picks the headless backend via
    # WF_TARGET_MACOS), plus the portable Linux HAL files reused verbatim
    # (hal/macos holds the macOS-specific shell, headless Display, GL/window stubs,
    # and the NSBundle asset accessor). platform_init.cc selects NSBundle vs POSIX
    # via WF_TARGET_MACOS guard; asset_accessor_posix.cc is NOT compiled on macOS.
    list(APPEND WF_SOURCES
        ${STUB_SRC}/renderpoly3d_stubs.cc
        ${STUB_SRC}/renderer_stub.cc
        ${SRC}/gfx/glpipeline/backend_factory.cc
        ${SRC}/hal/linux/platform_init.cc
        ${SRC}/hal/linux/audio.cc
        ${SRC}/hal/linux/input.cc
        ${SRC}/hal/linux/lifecycle.cc
        ${SRC}/hal/macos/asset_accessor_nsbundle.mm
    )
elseif(EMSCRIPTEN)
    # Web — the portable Linux HAL files are reused verbatim (the X11 code that
    # feeds them lives in gfx/gl/mesa.cc, which the web build never includes):
    #   platform_init.cc — POSIX init, FatalError, ParseWindowSwitches; selects
    #                      the POSIX asset accessor (reads from Emscripten MEMFS)
    #   audio.cc         — miniaudio init/term (miniaudio has a Web Audio backend)
    #   input.cc         — joystick-button state holder; hal/emscripten feeds it
    #                      via _HALSetJoystickButtons from DOM/Gamepad callbacks
    #   lifecycle.cc     — atomic suspend flag; visibilitychange toggles it
    list(APPEND WF_SOURCES
        ${SRC}/hal/linux/platform_init.cc
        ${SRC}/hal/linux/audio.cc
        ${SRC}/hal/linux/input.cc
        ${SRC}/hal/linux/lifecycle.cc
        ${SRC}/hal/linux/asset_accessor_posix.cc
    )
endif()

# ─── Lua 5.4 ──────────────────────────────────────────────────────────────────
set(LUA_DIR ${VENDOR}/lua-5.4.8)
if(WF_LUA_ENGINE STREQUAL "lua54")
    list(APPEND WF_SOURCES ${STUB_SRC}/scripting_lua.cc)
    list(APPEND WF_INCLUDES ${LUA_DIR}/src)
    list(APPEND WF_DEFS WF_ENABLE_LUA WF_LUA_ENGINE_LUA54)
    set(_lua_srcs
        lapi.c lauxlib.c lbaselib.c lcode.c lcorolib.c lctype.c ldblib.c
        ldebug.c ldo.c ldump.c lfunc.c lgc.c linit.c liolib.c llex.c
        lmathlib.c lmem.c loadlib.c lobject.c lopcodes.c loslib.c lparser.c
        lstate.c lstring.c lstrlib.c ltable.c ltablib.c ltm.c lundump.c
        lutf8lib.c lvm.c lzio.c
    )
    list(TRANSFORM _lua_srcs PREPEND "${LUA_DIR}/src/")
    add_library(lua54 STATIC ${_lua_srcs})
    target_compile_options(lua54 PRIVATE -std=gnu99 -O2 -w -fno-strict-aliasing)
    target_compile_definitions(lua54 PRIVATE LUA_USE_POSIX LUA_USE_DLOPEN)
    target_include_directories(lua54 PUBLIC ${LUA_DIR}/src)
    list(APPEND WF_LINK_LIBS lua54)
endif()

# ─── Fennel embed ─────────────────────────────────────────────────────────────
if(WF_ENABLE_FENNEL)
    list(APPEND WF_DEFS WF_ENABLE_FENNEL)
    set(_fennel_min ${CMAKE_BINARY_DIR}/fennel.min.lua)
    set(_fennel_cc  ${CMAKE_BINARY_DIR}/fennel_source.cc)
    add_custom_command(
        OUTPUT ${_fennel_cc}
        COMMAND python3 ${CMAKE_SOURCE_DIR}/scripts/minify_lua.py
                        ${STUB_SRC}/fennel.lua ${_fennel_min}
        COMMAND ${CMAKE_SOURCE_DIR}/scripts/gen_fennel_source.sh
                        ${_fennel_min} ${_fennel_cc}
        DEPENDS ${STUB_SRC}/fennel.lua
                ${CMAKE_SOURCE_DIR}/scripts/minify_lua.py
                ${CMAKE_SOURCE_DIR}/scripts/gen_fennel_source.sh
        COMMENT "Generating fennel_source.cc"
    )
    list(APPEND WF_SOURCES ${_fennel_cc})
endif()

# ─── JS engine ────────────────────────────────────────────────────────────────
set(QJS_DIR ${VENDOR}/quickjs-v0.14.0)
set(JRY_DIR ${VENDOR}/jerryscript-v3.0.0)
if(WF_JS_ENGINE STREQUAL "quickjs")
    list(APPEND WF_SOURCES ${STUB_SRC}/scripting_quickjs.cc)
    list(APPEND WF_INCLUDES ${QJS_DIR})
    list(APPEND WF_DEFS WF_WITH_JS WF_JS_ENGINE_QUICKJS)
    add_library(quickjs STATIC
        ${QJS_DIR}/quickjs.c ${QJS_DIR}/libregexp.c
        ${QJS_DIR}/libunicode.c ${QJS_DIR}/dtoa.c
    )
    target_compile_options(quickjs PRIVATE -std=gnu11 -O2 -w -fno-strict-aliasing)
    target_compile_definitions(quickjs PRIVATE
        QUICKJS_NG_BUILD "CONFIG_VERSION=\"0.14.0\"")
    target_include_directories(quickjs PUBLIC ${QJS_DIR})
    list(APPEND WF_LINK_LIBS quickjs)
elseif(WF_JS_ENGINE STREQUAL "jerryscript")
    list(APPEND WF_SOURCES ${STUB_SRC}/scripting_jerryscript.cc)
    list(APPEND WF_INCLUDES ${JRY_DIR}/jerry-core/include)
    list(APPEND WF_DEFS WF_WITH_JS WF_JS_ENGINE_JERRYSCRIPT)
    set(JERRY_CMDLINE        OFF CACHE BOOL   "" FORCE)
    set(JERRY_PROFILE        "${JRY_DIR}/jerry-core/profiles/wf-minimal.profile"
                                 CACHE STRING "" FORCE)
    set(JERRY_ERROR_MESSAGES ON  CACHE BOOL   "" FORCE)
    set(JERRY_LINE_INFO      ON  CACHE BOOL   "" FORCE)
    set(ENABLE_LTO           OFF CACHE BOOL   "" FORCE)
    add_subdirectory(${JRY_DIR} ${CMAKE_BINARY_DIR}/jerryscript)
    list(APPEND WF_LINK_LIBS jerry-core jerry-port-default)
endif()

# ─── WASM engine (WAMR) ───────────────────────────────────────────────────────
set(WAMR_DIR ${VENDOR}/wamr-2.2.0)
if(WF_WASM_ENGINE STREQUAL "wamr")
    list(APPEND WF_SOURCES ${STUB_SRC}/scripting_wamr.cc)
    list(APPEND WF_INCLUDES ${WAMR_DIR}/core/iwasm/include)
    list(APPEND WF_DEFS WF_WITH_WASM WF_WASM_ENGINE_WAMR)
    set(WAMR_ROOT_DIR        ${WAMR_DIR})
    # macOS desktop (arm64) and Android arm64 use Darwin/AARCH64; Linux uses linux/X86_64.
    # (macOS and iOS currently force WF_WASM_ENGINE=none above so this block is
    # only reached on Linux today; the platform/target vars are correct for when
    # macOS re-enables WAMR once the headless bring-up is verified green.)
    if(APPLE)
        set(WAMR_BUILD_PLATFORM  "darwin")
        set(WAMR_BUILD_TARGET    "AARCH64")
    elseif(ANDROID AND CMAKE_ANDROID_ARCH_ABI STREQUAL "arm64-v8a")
        set(WAMR_BUILD_PLATFORM  "android")
        set(WAMR_BUILD_TARGET    "AARCH64")
    else()
        set(WAMR_BUILD_PLATFORM  "linux")
        set(WAMR_BUILD_TARGET    "X86_64")
    endif()
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
    include(${WAMR_DIR}/build-scripts/runtime_lib.cmake)
    add_library(wamr_vmlib STATIC ${WAMR_RUNTIME_LIB_SOURCE})
    target_include_directories(wamr_vmlib PUBLIC ${WAMR_DIR}/core/iwasm/include)
    target_compile_options(wamr_vmlib PRIVATE -w)
    list(APPEND WF_LINK_LIBS wamr_vmlib)
endif()

# ─── Wren ─────────────────────────────────────────────────────────────────────
set(WREN_DIR ${VENDOR}/wren-0.4.0)
if(WF_ENABLE_WREN)
    list(APPEND WF_SOURCES ${STUB_SRC}/scripting_wren.cc)
    list(APPEND WF_INCLUDES ${WREN_DIR})
    list(APPEND WF_DEFS WF_ENABLE_WREN)
    add_library(wren STATIC ${WREN_DIR}/wren.c)
    target_compile_options(wren PRIVATE -std=gnu11 -O2 -w -fno-strict-aliasing)
    target_include_directories(wren PUBLIC ${WREN_DIR})
    list(APPEND WF_LINK_LIBS wren)
endif()

# ─── Forth engines ────────────────────────────────────────────────────────────
set(ZFORTH_DIR   ${VENDOR}/zforth-41db72d1)
set(FICL_DIR     ${VENDOR}/ficl-3.06)
set(ATLAST_DIR   ${VENDOR}/atlast-08ff0e1a/atlast-64)
set(EMBED_DIR    ${VENDOR}/embed-154aeb2f)
set(LIBFORTH_DIR ${VENDOR}/libforth-b851c6a2)
set(PFORTH_DIR   ${VENDOR}/pforth-63d4a418)

# ─── PILOT engine ─────────────────────────────────────────────────────────────
# From-scratch C++ interpreter; no vendored library, no editor dependency.
set(PILOT_DIR ${CMAKE_SOURCE_DIR}/engine/pilot)
if(WF_PILOT_ENGINE STREQUAL "builtin")
    list(APPEND WF_SOURCES ${STUB_SRC}/scripting_pilot.cc ${PILOT_DIR}/pilot_core.cc)
    list(APPEND WF_INCLUDES ${PILOT_DIR})
    list(APPEND WF_DEFS WF_WITH_PILOT WF_PILOT_ENGINE_BUILTIN)
endif()

if(NOT WF_FORTH_ENGINE STREQUAL "none")
    list(APPEND WF_DEFS WF_WITH_FORTH)
    if(WF_FORTH_ENGINE STREQUAL "zforth")
        list(APPEND WF_SOURCES ${STUB_SRC}/scripting_zforth.cc)
        list(APPEND WF_INCLUDES ${ZFORTH_DIR}/src/zforth)
        list(APPEND WF_DEFS WF_FORTH_ENGINE_ZFORTH)
        add_library(zforth STATIC ${ZFORTH_DIR}/src/zforth/zforth.c)
        target_compile_options(zforth PRIVATE -std=gnu11 -O2 -w -fno-strict-aliasing)
        target_include_directories(zforth PUBLIC ${STUB_SRC} ${ZFORTH_DIR}/src/zforth)
        list(APPEND WF_LINK_LIBS zforth)
    elseif(WF_FORTH_ENGINE STREQUAL "ficl")
        list(APPEND WF_SOURCES ${STUB_SRC}/scripting_ficl.cc)
        list(APPEND WF_INCLUDES ${FICL_DIR})
        list(APPEND WF_DEFS WF_FORTH_ENGINE_FICL)
        set(_ficl_srcs dict.c dpmath.c ficl.c fileaccess.c float.c prefix.c
                       search.c stack.c sysdep.c tools.c vm.c words.c)
        list(TRANSFORM _ficl_srcs PREPEND "${FICL_DIR}/")
        add_library(ficl STATIC ${_ficl_srcs})
        target_compile_options(ficl PRIVATE -std=gnu11 -O2 -w -fno-strict-aliasing)
        target_include_directories(ficl PUBLIC ${FICL_DIR})
        list(APPEND WF_LINK_LIBS ficl)
    elseif(WF_FORTH_ENGINE STREQUAL "atlast")
        list(APPEND WF_SOURCES ${STUB_SRC}/scripting_atlast.cc)
        list(APPEND WF_INCLUDES ${ATLAST_DIR})
        list(APPEND WF_DEFS WF_FORTH_ENGINE_ATLAST)
        add_library(atlast STATIC ${ATLAST_DIR}/atlast.c)
        target_compile_options(atlast PRIVATE -std=gnu11 -O2 -w -fno-strict-aliasing)
        target_compile_definitions(atlast PRIVATE EXPORT)
        target_include_directories(atlast PUBLIC ${ATLAST_DIR})
        list(APPEND WF_LINK_LIBS atlast)
    elseif(WF_FORTH_ENGINE STREQUAL "embed")
        list(APPEND WF_SOURCES ${STUB_SRC}/scripting_embed.cc)
        list(APPEND WF_INCLUDES ${EMBED_DIR})
        list(APPEND WF_DEFS WF_FORTH_ENGINE_EMBED)
        add_library(embed STATIC ${EMBED_DIR}/embed.c ${EMBED_DIR}/image.c)
        target_compile_options(embed PRIVATE -std=gnu11 -O2 -w -fno-strict-aliasing)
        target_include_directories(embed PUBLIC ${EMBED_DIR})
        list(APPEND WF_LINK_LIBS embed)
    elseif(WF_FORTH_ENGINE STREQUAL "libforth")
        list(APPEND WF_SOURCES ${STUB_SRC}/scripting_libforth.cc)
        list(APPEND WF_INCLUDES ${LIBFORTH_DIR})
        list(APPEND WF_DEFS WF_FORTH_ENGINE_LIBFORTH)
        add_library(libforth_lib STATIC ${LIBFORTH_DIR}/libforth.c)
        target_compile_options(libforth_lib PRIVATE -std=gnu11 -O2 -w -fno-strict-aliasing)
        target_include_directories(libforth_lib PUBLIC ${LIBFORTH_DIR})
        list(APPEND WF_LINK_LIBS libforth_lib)
    elseif(WF_FORTH_ENGINE STREQUAL "pforth")
        list(APPEND WF_SOURCES ${STUB_SRC}/scripting_pforth.cc)
        list(APPEND WF_INCLUDES ${PFORTH_DIR}/csrc)
        list(APPEND WF_DEFS WF_FORTH_ENGINE_PFORTH
                            "PFORTH_FTH_DIR=\"${PFORTH_DIR}/fth\"")
        set(_pforth_srcs
            pf_clib.c pfcompil.c pf_core.c pf_inner.c pf_io.c
            pf_mem.c pf_save.c pf_text.c pf_words.c
            posix/pf_io_posix.c stdio/pf_fileio_stdio.c
        )
        list(TRANSFORM _pforth_srcs PREPEND "${PFORTH_DIR}/csrc/")
        # pf_cglue.c and pfcustom.c need per-file flags
        set(_pforth_cglue   ${PFORTH_DIR}/csrc/pf_cglue.c)
        set(_pforth_custom  ${PFORTH_DIR}/csrc/pfcustom.c)
        add_library(pforth STATIC ${_pforth_srcs} ${_pforth_cglue} ${_pforth_custom})
        target_compile_options(pforth PRIVATE -std=gnu11 -O2 -w -fno-strict-aliasing)
        set_source_files_properties(${_pforth_custom} PROPERTIES
            COMPILE_DEFINITIONS PF_USER_CUSTOM=1)
        target_include_directories(pforth PUBLIC
            ${PFORTH_DIR}/csrc ${PFORTH_DIR}/csrc/posix ${PFORTH_DIR}/csrc/stdio)
        list(APPEND WF_LINK_LIBS pforth)
    endif()
endif()

# ─── Neural-forth AI library ──────────────────────────────────────────────────
if(WF_NEURAL_FORTH)
    if(NOT WF_FORTH_ENGINE STREQUAL "zforth")
        message(FATAL_ERROR "WF_NEURAL_FORTH requires WF_FORTH_ENGINE=zforth")
    endif()
    set(NF_DIR ${CMAKE_SOURCE_DIR}/engine/neural-forth)
    list(APPEND WF_SOURCES
        ${NF_DIR}/dictionary.c
        ${NF_DIR}/tensor.c
        ${NF_DIR}/autograd.c
        ${NF_DIR}/fuzzy.c
        ${NF_DIR}/nn.c
        ${NF_DIR}/slot.c)
    list(APPEND WF_INCLUDES ${NF_DIR})
    list(APPEND WF_DEFS WF_NEURAL_FORTH)
endif()

# ─── Jolt Physics ─────────────────────────────────────────────────────────────
set(JOLT_DIR ${VENDOR}/jolt-physics-5.5.0)
if(WF_PHYSICS_ENGINE STREQUAL "jolt")
    list(APPEND WF_SOURCES
        ${STUB_SRC}/physics_jolt.cc
        ${SRC}/physics/jolt/jolt_backend.cc
    )
    list(APPEND WF_INCLUDES ${JOLT_DIR})
    list(APPEND WF_DEFS PHYSICS_ENGINE_JOLT NDEBUG)
    set(PHYSICS_REPO_ROOT ${JOLT_DIR})
    include(${JOLT_DIR}/Jolt/Jolt.cmake)  # populates JOLT_PHYSICS_SRC_FILES + add_library(Jolt ...)

    # Apply Jolt's build modifiers via SOURCE-FILE properties, NOT
    # target_compile_*(Jolt ...). Under -G Xcode + CMAKE_SYSTEM_NAME=iOS the
    # target_* form errors ("Cannot specify compile options for target 'Jolt'
    # which is not built by this project") because Jolt's own cmake deliberately
    # avoids global per-target flags under Xcode's multi-arch builds
    # (Jolt/Jolt.cmake:637). Source-file properties are honored by every
    # generator including Xcode and stay scoped to Jolt's own TUs — no leak onto
    # wfengine/wf_game, which keep their Debug -O0 -g. This lets iOS build Jolt
    # like every other target; the old workaround force-flipped iOS to legacy
    # physics, which is being deleted.
    #
    # NDEBUG is LOAD-BEARING: Jolt.cmake:515 only auto-defines NDEBUG in
    # Release-family configs, so in Debug Jolt's TUs would build WITHOUT it while
    # wfengine's TUs (which set NDEBUG via WF_DEFS, above) build WITH it. That
    # makes JPH_ENABLE_ASSERTS expand differently across TUs, and
    # `ConstraintManager` has a ctor that exists only when asserts are enabled
    # (ConstraintManager.h:32) — a silent ODR violation. The external harness
    # (wf_host_gl_e2e_test) then trips SIGTRAP in `BodyManager::Init` because its
    # stack-resident `PhysicsSystem` was half-initialised by wfengine's view of
    # the ctor and asserted against by Jolt.a's view. The fix is consistent
    # NDEBUG / JPH_ENABLE_ASSERTS state across all TUs. The consumer side already
    # gets NDEBUG from WF_DEFS, so a per-file define (vs the old PUBLIC) suffices.
    #
    # -O2: keep Jolt fast even in Debug. -w: silence vendored warnings.
    # -fno-rtti: Jolt uses its own RTTI macro system (Jolt/Core/RTTI.h), zero
    # C++ dynamic_cast/typeid — safe to drop the type_info tables (size only).
    set_source_files_properties(${JOLT_PHYSICS_SRC_FILES} PROPERTIES
        COMPILE_DEFINITIONS "NDEBUG"
        COMPILE_OPTIONS     "-O2;-w;-fno-rtti"
    )
    if(EMSCRIPTEN)
        # Jolt.cmake unconditionally enables a PCH, but the source-file
        # properties above (-O2 -fno-rtti) don't apply to the PCH compile.
        # GCC silently ignores a flag-mismatched PCH; emcc (clang) hard-errors
        # ("run-time type information was enabled in precompiled file").
        # Disable the PCH for the web build — flags then match per-TU.
        set_target_properties(Jolt PROPERTIES DISABLE_PRECOMPILE_HEADERS ON)
    endif()
    list(APPEND WF_LINK_LIBS Jolt)
else()
    list(APPEND WF_DEFS PHYSICS_ENGINE_WF)
endif()

# ─── REST API ─────────────────────────────────────────────────────────────────
set(HTTPLIB_DIR ${VENDOR}/cpp-httplib-v0.20.0)
if(WF_REST_API)
    list(APPEND WF_SOURCES ${STUB_SRC}/rest_api.cc)
    list(APPEND WF_INCLUDES ${HTTPLIB_DIR})
    list(APPEND WF_DEFS WF_REST_API)
endif()

# ─── Debug bridge ─────────────────────────────────────────────────────────────
# Independent of the editor stack — level designers and AI agents depend on
# the bridge for live debug/iteration. Default ON (off only on mobile).
if(WF_DEBUG_BRIDGE)
    list(APPEND WF_SOURCES ${STUB_SRC}/debug_server.cc)
    list(APPEND WF_DEFS WF_DEBUG_BRIDGE)
endif()

# ─── Editor stack umbrella define ─────────────────────────────────────────────
# WF_ENABLE_EDITOR is its own #ifdef gate for editor-app code (CRDT, replay,
# DAP). The wfmut:: mutation API sits at the UNION below.
if(WF_ENABLE_EDITOR)
    list(APPEND WF_DEFS WF_ENABLE_EDITOR)
endif()

# ─── Engine mutation API (wfmut::) ────────────────────────────────────────────
# Used by BOTH consumers:
#   - debug_server.cc (step-6 refactor — bridge SET_TRANSFORM / SET_PROP /
#     SET_MAILBOX cases route through wfmut)
#   - editor's CRDT bridge (when WF_ENABLE_EDITOR is on)
# So we compile wfmut sources at the UNION: bridge ON OR editor ON.
# See docs/plans/2026-05-19-engine-mutation-api.md.
if(WF_DEBUG_BRIDGE OR WF_ENABLE_EDITOR)
    set(OAS_INC_DIR ${CMAKE_SOURCE_DIR}/wfsource/source/oas)
    set(KPROPMAP_OUT ${CMAKE_SOURCE_DIR}/engine/mutation/kpropmap_generated.inc)
    set(NAMEPATH_OUT ${CMAKE_SOURCE_DIR}/engine/wf_edit/name_to_path_generated.inc)
    add_custom_command(
        OUTPUT  ${KPROPMAP_OUT} ${NAMEPATH_OUT}
        COMMAND bash wfsource/source/oas/regen-headers.sh
        DEPENDS ${OAS_INC_DIR}/regen-headers.sh
                ${OAS_INC_DIR}/common.inc
                ${OAS_INC_DIR}/movebloc.inc
                ${OAS_INC_DIR}/mesh.inc
                ${OAS_INC_DIR}/common.oas
                ${OAS_INC_DIR}/movebloc.oas
                ${OAS_INC_DIR}/mesh.oas
        WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
        COMMENT "Regenerating OAS headers and generated maps"
    )
    add_custom_target(gen_oas_headers DEPENDS ${KPROPMAP_OUT} ${NAMEPATH_OUT})
    # wfmut.cpp #includes kpropmap_generated.inc — tell CMake explicitly so
    # a schema change triggers a recompile even without a clean build.
    set_source_files_properties(${CMAKE_SOURCE_DIR}/engine/mutation/wfmut.cpp
        PROPERTIES OBJECT_DEPENDS ${KPROPMAP_OUT})

    list(APPEND WF_SOURCES ${CMAKE_SOURCE_DIR}/engine/mutation/wfmut.cpp
                           ${CMAKE_SOURCE_DIR}/engine/mutation/wfmut_smoke.cpp)
endif()

# ─── Steam ────────────────────────────────────────────────────────────────────
set(STEAM_DIR ${VENDOR}/steamworks)
if(WF_ENABLE_STEAM)
    if(NOT EXISTS ${STEAM_DIR}/public/steam)
        message(FATAL_ERROR
            "WF_ENABLE_STEAM=ON but SDK not found at ${STEAM_DIR}. "
            "See engine/vendor/steamworks/README.md")
    endif()
    list(APPEND WF_SOURCES ${SRC}/hal/linux/steam.cc)
    list(APPEND WF_INCLUDES ${STEAM_DIR}/public)
    list(APPEND WF_DEFS WF_ENABLE_STEAM)
endif()

# ─── android_native_app_glue (Android only) ──────────────────────────────────
# Lives in the wf_game executable shell, not the wfengine library — it provides
# ANativeActivity_onCreate, the Android app entry point. The library exposes
# its include path (Android engine sources include android_native_app_glue.h).
if(ANDROID)
    set(APP_GLUE_DIR ${ANDROID_NDK}/sources/android/native_app_glue)
    list(APPEND WF_INCLUDES ${APP_GLUE_DIR})
endif()

# ─── Platform-shell sources (entry points go in wf_game, not wfengine) ────────
# Phase 0a (2026-05-18): the engine compiles into a libwfengine.a static library
# and wf_game is a thin per-platform executable that provides the entry point
# (main / android_main) and links wfengine. This lets future hosts (e.g. the
# collaborative editor) link wfengine and supply their own main, without
# colliding with wf_game's. The library's calls to FatalError /
# _PlatformSpecificInit / _PlatformSpecificUnInit / etc. (defined in the
# platform-shell files) are resolved at executable link time as usual for
# static libraries with unresolved references. See
# docs/investigations/2026-05-18-collaborative-level-editor-design.md
# § Engine linkability.
set(WF_PLATFORM_SHELL_SOURCES)
if(ANDROID)
    list(APPEND WF_PLATFORM_SHELL_SOURCES
        ${SRC}/hal/android/native_app_entry.cc
        ${APP_GLUE_DIR}/android_native_app_glue.c)
elseif(IOS)
    list(APPEND WF_PLATFORM_SHELL_SOURCES
        ${SRC}/hal/ios/native_app_entry.mm)
elseif(APPLE)
    # macOS desktop — thin main() shell (Linux-minus-X11), HALStart on the main
    # thread. platform_init.cc (engine-needed helpers + globals) is reused from
    # hal/linux and compiled into libwfengine.a via the stub-sources block.
    list(APPEND WF_PLATFORM_SHELL_SOURCES
        ${SRC}/hal/macos/platform_main.cc)
elseif(EMSCRIPTEN)
    # Web — thin main() shell (Linux-minus-X11), HALStart on the browser main
    # thread. platform_init.cc is reused from hal/linux via the extra-sources
    # block above.
    list(APPEND WF_PLATFORM_SHELL_SOURCES
        ${SRC}/hal/emscripten/platform_main.cc)
else()
    # Linux: only platform_main.cc (just main()) goes in the shell.
    # platform_init.cc (FatalError, _PlatformSpecificInit, FPEHandler,
    # ParseWindowSwitches, _halWindow* globals) compiles into libwfengine.a
    # via the hal/linux glob so hosts (editor, host-GL e2e test) can link the
    # library and supply their own main. Split landed 2026-05-18 (editor
    # Phase 0b sub-task 3).
    list(APPEND WF_PLATFORM_SHELL_SOURCES
        ${SRC}/hal/linux/platform_main.cc)
endif()
# Remove shell sources from the library's source list (the directory glob above
# would otherwise pick them up — they live alongside engine-library files).
list(REMOVE_ITEM WF_SOURCES ${WF_PLATFORM_SHELL_SOURCES})

# ─── wfengine library target ──────────────────────────────────────────────────
# Static library containing all engine code except the platform entry-point
# shell. Linked by wf_game (below) and, in future, by the collaborative editor.
add_library(wfengine STATIC ${WF_SOURCES})
target_include_directories(wfengine PUBLIC ${WF_INCLUDES})
target_compile_definitions(wfengine PUBLIC ${WF_DEFS})
target_compile_options(wfengine PRIVATE
    -fpermissive -w
    -fno-rtti   # WF uses kind()/EActorKind dispatch, never dynamic_cast (no-RTTI constraint)
    "-D__GAME__=\"wf_game\""
    "-DERR_DEBUG(x)="
    "$<$<OR:$<CONFIG:Debug>,$<CONFIG:RelWithDebInfo>>:-O0;-g>"
    "$<$<AND:$<CONFIG:Release>,$<CXX_COMPILER_ID:Clang>>:-O3;-flto=thin;-ffunction-sections;-fdata-sections;-fvisibility=hidden;-fno-exceptions;-fno-unwind-tables;-fno-asynchronous-unwind-tables>"
)
if(ANDROID OR IOS OR APPLE OR EMSCRIPTEN)
    # Legacy `register` keyword is C++17-removed; WF's pigsys/endian.cc still
    # uses it. Silence to match the Linux build's permissive stance. (APPLE
    # covers both iOS and macOS desktop; Emscripten's emcc is also Clang.)
    target_compile_options(wfengine PRIVATE -Wno-register)
endif()

# iOS: miniaudio.h (included via audio/linux/audio_internal.hp) pulls in
# AVFoundation.framework headers on Darwin, which contain Objective-C syntax.
# The audio/linux/*.cc files would fail to parse as plain C++, so compile them
# as Objective-C++ on iOS. (Linux/Android stay on plain C++ — no AVFoundation.)
if(APPLE)
    # OBJCXX is only needed on Apple: miniaudio.h pulls in AVFoundation (ObjC)
    # on Darwin. Ninja doesn't auto-enable it the way Xcode does, so we enable
    # it explicitly here. Linux/Android use plain C++ — gobjc++ not required.
    enable_language(OBJCXX)
    # Both iOS and macOS desktop: miniaudio.h pulls in AVFoundation (ObjC) on
    # Darwin, so the audio/linux/*.cc TUs must compile as Objective-C++.
    foreach(_audio_src miniaudio_impl.cc music.cc buffer.cc device.cc)
        set_source_files_properties(
            ${SRC}/audio/linux/${_audio_src}
            PROPERTIES LANGUAGE OBJCXX
        )
    endforeach()
endif()

# ─── wf_game target ───────────────────────────────────────────────────────────
# Thin per-platform executable: provides the entry point (main / android_main)
# and links wfengine. The platform-shell file also defines symbols the engine
# library references but doesn't define (FatalError, _PlatformSpecificInit,
# _PlatformSpecificUnInit) — those resolve at link time.
if(ANDROID)
    add_library(wf_game SHARED ${WF_PLATFORM_SHELL_SOURCES})
    # ANativeActivity_onCreate lives in android_native_app_glue.c and is the
    # Android loader's entry point. Without -u the linker garbage-collects it.
    target_link_options(wf_game PRIVATE -u ANativeActivity_onCreate)
elseif(IOS)
    # MACOSX_BUNDLE makes this an .app directory rather than a bare Mach-O.
    # Phase 1C fills in the Info.plist + launch screen via target properties.
    add_executable(wf_game MACOSX_BUNDLE ${WF_PLATFORM_SHELL_SOURCES})
elseif(APPLE)
    # macOS desktop — MACOSX_BUNDLE packages wf_game as a proper .app. Assets
    # (cd.iff, level0.mid, soundfont) are bundled into Contents/Resources/ and
    # accessed via the NSBundle accessor installed by platform_init.cc. The
    # Codemagic smoke test runs the binary inside the bundle directly with -L so
    # it bypasses the cd.iff AssetAccessor path entirely.
    add_executable(wf_game MACOSX_BUNDLE ${WF_PLATFORM_SHELL_SOURCES})
else()
    add_executable(wf_game ${WF_PLATFORM_SHELL_SOURCES})
    # wf_game always keeps its name as the game-engine runtime. The editor is
    # its own `wf-edit` application target (see the WF_ENABLE_EDITOR block
    # below), not a renamed engine binary.
endif()

# wf_game's shell file inherits include dirs + compile definitions from
# wfengine via target_link_libraries (PUBLIC propagation). Compile options
# don't propagate; re-apply the engine flags to wf_game's shell so it compiles
# with the same -fpermissive / __GAME__ / etc. as engine sources.
target_compile_options(wf_game PRIVATE
    -fpermissive -w
    -fno-rtti   # see wfengine block — no-RTTI constraint
    "-D__GAME__=\"wf_game\""
    "-DERR_DEBUG(x)="
    "$<$<OR:$<CONFIG:Debug>,$<CONFIG:RelWithDebInfo>>:-O0;-g>"
    "$<$<AND:$<CONFIG:Release>,$<CXX_COMPILER_ID:Clang>>:-O3;-flto=thin;-ffunction-sections;-fdata-sections;-fvisibility=hidden;-fno-exceptions;-fno-unwind-tables;-fno-asynchronous-unwind-tables>"
)
# These are native GNU ld / LLVM lld link flags. Emscripten's wasm-ld rejects
# --icf and --export-dynamic-symbol (unknown arguments), and ANativeActivity_onCreate
# is Android-only. The web build gets its own -flto=thin in the EMSCRIPTEN link
# block below instead. (emcc is Clang, so without this guard the generator
# expression fires for the web build and wasm-ld errors out — see plan Phase 1.)
if(NOT EMSCRIPTEN)
    target_link_options(wf_game PRIVATE
        "$<$<AND:$<CONFIG:Release>,$<CXX_COMPILER_ID:Clang>>:-flto=thin;-Wl,--gc-sections;-Wl,--icf=safe;-Wl,-O2;-Wl,--export-dynamic-symbol=ANativeActivity_onCreate>"
    )
endif()
if(ANDROID OR IOS OR APPLE OR EMSCRIPTEN)
    target_compile_options(wf_game PRIVATE -Wno-register)
endif()

if(ANDROID)
    # Bump Jolt + zforth to -O3 in Release to match main target. (Jolt is ~36%
    # of .text so even +10% speed here moves the needle.) Jolt has no `throw`
    # in its source, so -fno-exceptions is a drop-in win — removes all the
    # .eh_frame / .gcc_except_table entries that C++ template-heavy code
    # generates by default.
    if(TARGET Jolt)
        target_compile_options(Jolt PRIVATE "$<$<AND:$<CONFIG:Release>,$<CXX_COMPILER_ID:Clang>>:-O3;-flto=thin;-ffunction-sections;-fdata-sections;-fvisibility=hidden;-fno-exceptions;-fno-unwind-tables;-fno-asynchronous-unwind-tables>")
    endif()
    if(TARGET zforth)
        target_compile_options(zforth PRIVATE "$<$<AND:$<CONFIG:Release>,$<CXX_COMPILER_ID:Clang>>:-O3;-flto=thin;-ffunction-sections;-fdata-sections>")
    endif()
endif()

# ─── Platform link libraries ──────────────────────────────────────────────────
# OS-level libraries the engine code calls into. PUBLIC on wfengine so they
# propagate transitively — wf_game (and any future host like the editor) just
# `target_link_libraries(... wfengine)` and gets them automatically.
if(ANDROID)
    list(APPEND WF_LINK_LIBS EGL GLESv3 android log m OpenSLES)
elseif(IOS)
    # Metal/MetalKit added 2026-04-22 for Phase 2A (MetalView in hal/ios/
    # drives a CAMetalLayer clear via CADisplayLink). Phase 2B wires this to
    # the engine RendererBackend proper.
    # AVFoundation + AudioToolbox + CoreAudio are pulled in by miniaudio's
    # iOS backend (AVAudioSession, route-change notifications, etc.).
    list(APPEND WF_LINK_LIBS
        "-framework Foundation"
        "-framework UIKit"
        "-framework QuartzCore"
        "-framework CoreFoundation"
        "-framework Metal"
        "-framework MetalKit"
        "-framework AVFoundation"
        "-framework AudioToolbox"
        "-framework CoreAudio"
    )
elseif(APPLE)
    # macOS desktop — renderer-agnostic bring-up. miniaudio uses CoreAudio (it
    # pulls AVFoundation + AudioToolbox on Darwin). NO Metal/MetalKit/QuartzCore
    # yet (rendering is a no-op), NO OpenGL.framework (GL entry points are
    # stubbed in hal/macos/gl_stubs.cc), NO X11.
    list(APPEND WF_LINK_LIBS
        "-framework Foundation"
        "-framework CoreFoundation"
        "-framework CoreAudio"
        "-framework AudioToolbox"
        "-framework AVFoundation"
        m pthread
    )
elseif(EMSCRIPTEN)
    # Browser: no native libs — GL resolves to WebGL via Emscripten's GLES3
    # emulation. v2 (plan Phase 7) drives the loop with emscripten_set_main_loop
    # (game.cc RunLevelWeb/WebTick) and no longer links -sASYNCIFY: the per-frame
    # emscripten_sleep yield is gone, which strips the ASYNCIFY instrumentation
    # bulk from the wasm. See docs/plans/2026-06-11-web-canvas-port.md Phase 7.
    target_link_options(wf_game PRIVATE
        -sMIN_WEBGL_VERSION=2
        -sMAX_WEBGL_VERSION=2
        -sALLOW_MEMORY_GROWTH=1
        -sEXIT_RUNTIME=0
        # callMain: the shell gates engine start on a click (Module.noInitialRun);
        # requestFullscreen: the shell's fullscreen button. Both must be exported.
        -sEXPORTED_RUNTIME_METHODS=callMain,requestFullscreen
        -lidbfs.js                                  # IDBFS for persistent hi-scores (P6.1)
        # wfengine.a objects are thin-LTO bitcode (Release+Clang compile flags);
        # match at link so wasm-ld LTO-compiles them, and run binaryen -O3 over
        # the final wasm.
        "$<$<CONFIG:Release>:-O3;-flto=thin>"
        # The custom shell (web/shell.html) selects the level via ?level=<name>.
        "SHELL:--shell-file ${CMAKE_SOURCE_DIR}/web/shell.html"
    )
    # Preloaded demo levels — the "-standalone" L-chunk variants (complete
    # L-chunks the -L path loads directly), NOT the LVAS asset-bundle .iff. To add
    # a demo: add a slug here AND a switcher entry on the worldfoundry.org
    # /v2/play page. moon is the only heavy one and also needs the --vram-* args
    # the shell's LEVEL_ARGS passes.
    set(WF_WEB_LEVELS
        moon_site01-standalone  snowgoons-standalone      qbert_practice-standalone
        smb_w1_1-standalone     smb_w1_2-standalone        smb_w1_3-standalone
        smb_w1_4-standalone     marble-madness-standalone  pilot_demo-standalone
    )
    foreach(_lvl ${WF_WEB_LEVELS})
        target_link_options(wf_game PRIVATE
            "SHELL:--preload-file ${CMAKE_SOURCE_DIR}/wflevels/${_lvl}.iff@/${_lvl}.iff")
    endforeach()
    set_target_properties(wf_game PROPERTIES SUFFIX ".html")
else()
    list(APPEND WF_LINK_LIBS GL GLU X11 m pthread dl)
    # wf_game-specific link option (noexecstack on the final exe, not on the
    # library — static libraries don't have a stack to mark).
    target_link_options(wf_game PRIVATE -Wl,-z,noexecstack)
    if(WF_ENABLE_STEAM)
        target_link_directories(wf_game PRIVATE
            ${STEAM_DIR}/redistributable_bin/linux64)
        list(APPEND WF_LINK_LIBS steam_api)
        target_link_options(wf_game PRIVATE "-Wl,-rpath,$$ORIGIN")
    endif()
endif()

target_link_libraries(wfengine PUBLIC ${WF_LINK_LIBS})
target_link_libraries(wf_game  PRIVATE wfengine)

# ─── Host-GL e2e test ────────────────────────────────────────────────────────
# Drives a real WFGame through Load/Step×N/Unload against a host-supplied
# X11/GLX context — proves the Phase 0a libwfengine.a split lets external
# hosts (the upcoming collaborative editor) supply their own main without
# duplicate-symbol errors, and proves the Phase B LIFO fixes in
# ~Level/~WFGame hold when driven from outside RunLevel.
# Linux/desktop only — host GL plumbing is X11/GLX specific.
if(NOT ANDROID AND NOT IOS AND NOT APPLE AND NOT EMSCRIPTEN)
    # macOS desktop is excluded here: these are X11/GLX host-GL + ctest targets
    # that don't apply to the headless bring-up. macOS verifies by running the
    # binary directly (--frame-step-smoke) in the Codemagic workflow. Re-add
    # once the real renderer + display land.
    # Same compile-options as wf_game's shell — Jolt's inline JPH_OVERRIDE_NEW_DELETE
    # operators have ODR sensitivity across translation units that compile with
    # different optimization levels; matching -O0/-g keeps the inlined op-new in
    # the harness binary-compatible with the engine library's calls into it.
    add_executable(wf_host_gl_e2e_test
        engine/wf_host_gl_test/host_gl_e2e_test.cc)
    target_link_libraries(wf_host_gl_e2e_test PRIVATE wfengine)
    target_compile_options(wf_host_gl_e2e_test PRIVATE
        -fpermissive -w
        -fno-rtti   # no-RTTI constraint applies to every TU, incl. test harness
        "-D__GAME__=\"wf_host_gl_e2e_test\""
        "-DERR_DEBUG(x)="
        "$<$<OR:$<CONFIG:Debug>,$<CONFIG:RelWithDebInfo>>:-O0;-g>"
        "$<$<AND:$<CONFIG:Release>,$<CXX_COMPILER_ID:Clang>>:-O3;-flto=thin>"
    )

    # ─── CTest cycle-stability tests ──────────────────────────────────────────
    # Three CLI-level tests at increasing cycle counts catch three failure
    # modes: cycle1 = basic unload regression gate (Phase B's LIFO fixes),
    # cycle2 = "second-cycle uses stale static state" (most common multi-
    # cycle bug), cycle5 = slow accumulation (one-entry-per-cycle leaks
    # that wouldn't show at cycle 2). Two host-GL harness tests prove the
    # external-host path stays clean and are labelled `gl` so headless CI
    # can exclude them via `ctest -LE gl`.
    enable_testing()
    set(WF_TEST_LEVEL
        ${CMAKE_SOURCE_DIR}/wflevels/qbert_practice/qbert_practice-standalone.iff)
    set(WF_TEST_SNOW_LEVEL
        ${CMAKE_SOURCE_DIR}/wflevels/snowgoons-blender/snowgoons-standalone.iff)
    set(WF_TEST_RUN_DIR
        ${CMAKE_SOURCE_DIR}/wfsource/source/game)  # so cd.iff resolves

    add_test(NAME wf_game_smoke_cycle1
        COMMAND $<TARGET_FILE:wf_game> --frame-step-smoke=30 --cycles=1 -L${WF_TEST_LEVEL}
        WORKING_DIRECTORY ${WF_TEST_RUN_DIR})
    add_test(NAME wf_game_smoke_cycle2
        COMMAND $<TARGET_FILE:wf_game> --frame-step-smoke=30 --cycles=2 -L${WF_TEST_LEVEL}
        WORKING_DIRECTORY ${WF_TEST_RUN_DIR})
    # cycle5 omitted from the default set — qbert's per-actor Forth dictionary
    # doesn't reset between cycles, so cycle 2+ logs "zforth error 7" without
    # crashing. Run by hand when investigating multi-cycle stability.

    add_test(NAME wf_game_smoke_snow_cycle1
        COMMAND $<TARGET_FILE:wf_game> --frame-step-smoke=30 --cycles=1 -L${WF_TEST_SNOW_LEVEL}
        WORKING_DIRECTORY ${WF_TEST_RUN_DIR})
    add_test(NAME wf_game_smoke_snow_cycle2
        COMMAND $<TARGET_FILE:wf_game> --frame-step-smoke=30 --cycles=2 -L${WF_TEST_SNOW_LEVEL}
        WORKING_DIRECTORY ${WF_TEST_RUN_DIR})

    add_test(NAME wf_host_gl_e2e_cycle1
        COMMAND $<TARGET_FILE:wf_host_gl_e2e_test> --frames=30 --cycles=1 --level=${WF_TEST_LEVEL}
        WORKING_DIRECTORY ${WF_TEST_RUN_DIR})
    add_test(NAME wf_host_gl_e2e_cycle2
        COMMAND $<TARGET_FILE:wf_host_gl_e2e_test> --frames=30 --cycles=2 --level=${WF_TEST_LEVEL}
        WORKING_DIRECTORY ${WF_TEST_RUN_DIR})
    add_test(NAME wf_host_gl_e2e_snow_cycle1
        COMMAND $<TARGET_FILE:wf_host_gl_e2e_test> --frames=30 --cycles=1 --level=${WF_TEST_SNOW_LEVEL}
        WORKING_DIRECTORY ${WF_TEST_RUN_DIR})
    add_test(NAME wf_host_gl_e2e_snow_cycle2
        COMMAND $<TARGET_FILE:wf_host_gl_e2e_test> --frames=30 --cycles=2 --level=${WF_TEST_SNOW_LEVEL}
        WORKING_DIRECTORY ${WF_TEST_RUN_DIR})
    set_tests_properties(wf_host_gl_e2e_cycle1 wf_host_gl_e2e_cycle2
                         wf_host_gl_e2e_snow_cycle1 wf_host_gl_e2e_snow_cycle2
        PROPERTIES LABELS "gl" ENVIRONMENT "DISPLAY=:0")

    # ─── wfmut mutation-API tests ─────────────────────────────────────────────
    # The default CMake build has WF_DEBUG_BRIDGE=ON, so wf_game carries the
    # --wfmut-smoke flag (wfmut sits at the bridge∪editor union). Both tests
    # need a GL context (they load a level) → labelled "gl", DISPLAY=:0, so
    # headless CI excludes them via `ctest -LE gl`. See
    # docs/plans/2026-05-19-engine-mutation-api.md.
    set(WF_TEST_SMB_LEVEL
        ${CMAKE_SOURCE_DIR}/wflevels/smb_w1_1-standalone.iff)

    add_test(NAME wfmut_smoke
        COMMAND $<TARGET_FILE:wf_game> -L${WF_TEST_SMB_LEVEL} --wfmut-smoke
        WORKING_DIRECTORY ${WF_TEST_RUN_DIR})

    # Live TCP-bridge regression. The Python harness launches its own wf_game
    # subprocess (it points at engine/wf_game), so it depends on the binary
    # being built first; it picks a private port (7798).
    add_test(NAME wfmut_bridge
        COMMAND python3 ${CMAKE_SOURCE_DIR}/tests/verify_wfmut_bridge.py
        WORKING_DIRECTORY ${CMAKE_SOURCE_DIR})

    # X5 cross-thread guard death-test: drives wfmut from a non-game thread;
    # the guard's AssertMsg must fire and abort. The process dies via SIGABRT,
    # which CTest's PASS_REGULAR_EXPRESSION does NOT override (it reports
    # "Subprocess aborted"). So wrap in a shell that greps the guard message
    # out of the (captured) output and exits 0 on match — the grep is the
    # test command, so the upstream abort doesn't fail it.
    add_test(NAME wfmut_thread_guard
        COMMAND sh -c "$<TARGET_FILE:wf_game> -L${WF_TEST_SMB_LEVEL} --wfmut-thread-test 2>&1 | grep -q 'must be called on the game thread'"
        WORKING_DIRECTORY ${WF_TEST_RUN_DIR})

    set_tests_properties(wfmut_smoke wfmut_bridge wfmut_thread_guard
        PROPERTIES LABELS "gl" ENVIRONMENT "DISPLAY=:0")
endif()

# ─── iOS .app bundle resources ────────────────────────────────────────────────
if(IOS)
    set(IOS_DIR ${CMAKE_SOURCE_DIR}/ios)
    set_target_properties(wf_game PROPERTIES
        BUNDLE                                         TRUE
        MACOSX_BUNDLE_INFO_PLIST                       ${IOS_DIR}/Info.plist
        MACOSX_BUNDLE_GUI_IDENTIFIER                   org.worldfoundry.wf-game
        MACOSX_BUNDLE_BUNDLE_NAME                      wf_game
        XCODE_ATTRIBUTE_PRODUCT_BUNDLE_IDENTIFIER      org.worldfoundry.wf-game
        XCODE_ATTRIBUTE_IPHONEOS_DEPLOYMENT_TARGET     "13.0"
        XCODE_ATTRIBUTE_TARGETED_DEVICE_FAMILY         "1,2"
        # No signing in Phase 1 — Simulator only, no provisioning needed.
        XCODE_ATTRIBUTE_CODE_SIGN_IDENTITY             ""
        XCODE_ATTRIBUTE_CODE_SIGNING_REQUIRED          "NO"
        XCODE_ATTRIBUTE_CODE_SIGNING_ALLOWED           "NO"
    )
    # Launch storyboard needs to be a bundle resource. Any assets (cd.iff,
    # level0.mid, sf2) that exist at configure time get bundled alongside.
    set(IOS_RESOURCES ${IOS_DIR}/LaunchScreen.storyboard)
    foreach(asset cd.iff level0.mid florestan-subset.sf2)
        set(path ${CMAKE_SOURCE_DIR}/wfsource/source/game/${asset})
        if(EXISTS ${path})
            list(APPEND IOS_RESOURCES ${path})
        endif()
    endforeach()
    target_sources(wf_game PRIVATE ${IOS_RESOURCES})
    set_source_files_properties(${IOS_RESOURCES} PROPERTIES
        MACOSX_PACKAGE_LOCATION Resources)
endif()

# ─── macOS .app bundle resources ─────────────────────────────────────────────
if(APPLE AND NOT IOS)
    set(MACOS_DIR ${CMAKE_SOURCE_DIR}/macos)
    set_target_properties(wf_game PROPERTIES
        BUNDLE                       TRUE
        MACOSX_BUNDLE_INFO_PLIST     ${MACOS_DIR}/Info.plist
        MACOSX_BUNDLE_GUI_IDENTIFIER org.worldfoundry.wf-game-macos
        MACOSX_BUNDLE_BUNDLE_NAME    WorldFoundry
        # Deployment target — matches LSMinimumSystemVersion in Info.plist.
        CMAKE_OSX_DEPLOYMENT_TARGET  "12.0"
    )
    # Bundle any assets that exist at configure time (cd.iff, level0.mid, sf2).
    # The smoke test bypasses cd.iff via -L, so missing assets don't fail CI;
    # they are needed for a normal launch.
    set(MACOS_RESOURCES)
    foreach(asset cd.iff level0.mid florestan-subset.sf2)
        set(path ${CMAKE_SOURCE_DIR}/wfsource/source/game/${asset})
        if(EXISTS ${path})
            list(APPEND MACOS_RESOURCES ${path})
        endif()
    endforeach()
    if(MACOS_RESOURCES)
        target_sources(wf_game PRIVATE ${MACOS_RESOURCES})
        set_source_files_properties(${MACOS_RESOURCES} PROPERTIES
            MACOSX_PACKAGE_LOCATION Resources)
    endif()
endif()

# ─── Neural-forth unit test binary ───────────────────────────────────────────
# Standalone executable that links against zforth + the neural-forth C files.
# Provides its own zf_host_* callbacks; does not depend on wf_game.
# Excluded from the game build (neural_forth_test.cc is not in WF_SOURCES).
if(WF_NEURAL_FORTH AND NOT ANDROID AND NOT IOS AND NOT APPLE AND NOT EMSCRIPTEN)
    add_executable(nf_test
        ${NF_DIR}/neural_forth_test.cc
        ${NF_DIR}/dictionary.c
        ${NF_DIR}/tensor.c
        ${NF_DIR}/autograd.c
        ${NF_DIR}/fuzzy.c
        ${NF_DIR}/nn.c
        ${NF_DIR}/slot.c)
    target_include_directories(nf_test PRIVATE
        ${NF_DIR}
        ${ZFORTH_DIR}/src/zforth
        ${STUB_SRC}
        ${ENG_INC})
    target_compile_options(nf_test PRIVATE -Wall -Wextra -O2)
    target_compile_definitions(nf_test PRIVATE WF_NEURAL_FORTH WF_FORTH_ENGINE_ZFORTH)
    target_link_libraries(nf_test PRIVATE zforth)
    add_test(NAME neural_forth_unit COMMAND nf_test)
endif()

# ─── Output location matches build_game.sh ────────────────────────────────────
if(NOT ANDROID AND NOT EMSCRIPTEN)
    # Emscripten keeps its .html/.js/.wasm/.data set in build-web/ — engine/ is
    # for native binaries.
    set_target_properties(wf_game PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/engine)
endif()

# ─── CRDT support library (under WF_ENABLE_EDITOR umbrella) ──────────────────
# Yrs/y-crdt binding for the collaborative level editor. Default OFF via the
# WF_ENABLE_EDITOR master switch — when OFF, Corrosion / Cargo / rustc never
# enter the build graph, so the shipped game binaries (wf_game / Android /
# iOS / Codemagic CI) stay Rust-free and their build configurations are
# bit-identical to a no-editor build.
#
# When ON, builds libwfcrdt.a (thin C wrapper over libyrs.a from
# wftools/y-crdt's yffi crate). The editor — not the engine — will link this
# library. libwfcrdt.a must NEVER be linked into libwfengine.a; the editor
# owns the Y.Doc and the engine exposes a plain C++ mutation API (wfmut::).
if(WF_ENABLE_EDITOR)
    add_subdirectory(cmake/Corrosion)
    add_subdirectory(engine/crdt)
endif()

# ─── Editor application (wf-edit) ─────────────────────────────────────────────
# The collaborative level editor: a Dear ImGui app that (from M2) embeds the
# engine viewport via the host-GL-context handshake, and (M4) reads a level
# into a wfcrdt::Doc to drive the outliner. Linux/X11 only; gated on
# WF_ENABLE_EDITOR. See docs/plans/2026-05-20-editor-app-shell.md.
# Windowing: GLFW owns the X11/GLX window + context (its X11 backend needs the
# libxrandr/xinerama/xcursor/xi -dev packages — declared in the
# worldfoundry-editor-dev metapackage). M2 extracts GLFW's native X11/GLX
# handles and registers them via SetHostGLContext so the engine renders into
# this context.
if(WF_ENABLE_EDITOR AND NOT ANDROID AND NOT IOS AND NOT EMSCRIPTEN)
    # Opus + VP8 for in-editor voice/video chat.
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(OPUS REQUIRED opus)
    pkg_check_modules(VPX  REQUIRED vpx)

    # OpenSSL for wss:// relay TLS (ws_client wss:// support).
    find_package(OpenSSL REQUIRED)

    # libdatachannel — WebRTC (ICE + DTLS-SRTP + RTP tracks) for Phase 2 voice/video.
    # Fetched from source; build artifacts kept out of the repo per [[feedback_no_giant_vendor]].
    include(FetchContent)
    FetchContent_Declare(
        libdatachannel
        GIT_REPOSITORY https://github.com/paullouisageneau/libdatachannel.git
        GIT_TAG        v0.21.2
        GIT_SUBMODULES "deps/libjuice" "deps/libsrtp" "deps/usrsctp" "deps/plog" "deps/json"
        GIT_SHALLOW    TRUE
    )
    set(NO_EXAMPLES   ON  CACHE BOOL "" FORCE)
    set(NO_TESTS      ON  CACHE BOOL "" FORCE)
    set(NO_WEBSOCKET  ON  CACHE BOOL "" FORCE)
    FetchContent_MakeAvailable(libdatachannel)

    # GLFW — editor-owned X11/GLX window + context (lean build, X11 only).
    set(GLFW_BUILD_DOCS     OFF CACHE BOOL "" FORCE)
    set(GLFW_BUILD_TESTS    OFF CACHE BOOL "" FORCE)
    set(GLFW_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
    set(GLFW_BUILD_WAYLAND  OFF CACHE BOOL "" FORCE)
    add_subdirectory(third_party/glfw)

    set(IMGUI_DIR ${CMAKE_SOURCE_DIR}/third_party/imgui)
    set(IMGUIZMO_DIR ${CMAKE_SOURCE_DIR}/third_party/imguizmo)  # 3D translate/rotate gizmo
    set(IMGUI_MARKDOWN_DIR ${CMAKE_SOURCE_DIR}/third_party/imgui_markdown)  # header-only chat markdown
    add_executable(wf_edit
        engine/wf_edit/main.cc
        engine/wf_edit/level_doc.cc            # M4: levtree -> wfcrdt::Doc
        engine/wf_edit/property_panel.cc       # Phase 2: OAD-driven Properties panel
        engine/wf_edit/oad_reader.cc           # Phase 2: clean OadEntry adapter
        engine/wf_edit/engine_bridge.cc        # Option C: CRDT -> engine (wfmut) bridge
        engine/wf_edit/gizmo.cc                # viewport translate/rotate gizmo (ImGuizmo)
        engine/wf_edit/level_save.cc           # save round-trip: Doc -> .lev
        engine/wf_edit/collab_session.cc       # UDP multicast peer discovery
        engine/wf_edit/voice_track.cc          # Opus voice chat
        engine/wf_edit/video_track.cc          # VP8 video chat + V4L2 capture
        engine/wf_edit/collab_panel.cc         # Collaborators ImGui panel
        engine/wf_edit/ws_client.cc           # WebSocket transport client (co-edit relay)
        engine/wf_edit/webrtc_session.cc      # WebRTC PeerConnection per peer (Phase 2)
        wftools/oaddump/oad.cc                 # shared OAD reader (editor-gated only)
        ${IMGUI_DIR}/imgui.cpp
        ${IMGUI_DIR}/imgui_draw.cpp
        ${IMGUI_DIR}/imgui_tables.cpp
        ${IMGUI_DIR}/imgui_widgets.cpp
        ${IMGUI_DIR}/misc/cpp/imgui_stdlib.cpp   # InputText(std::string&) — editable widgets
        ${IMGUI_DIR}/backends/imgui_impl_glfw.cpp
        ${IMGUI_DIR}/backends/imgui_impl_opengl3.cpp
        ${IMGUIZMO_DIR}/ImGuizmo.cpp             # 3D manipulation gizmo
    )
    add_dependencies(wf_edit gen_oas_headers)
    # engine_bridge.cc #includes name_to_path_generated.inc — explicit dep so a
    # schema change recompiles it even without a clean build.
    set_source_files_properties(${CMAKE_SOURCE_DIR}/engine/wf_edit/engine_bridge.cc
        PROPERTIES OBJECT_DEPENDS ${NAMEPATH_OUT})
    set_target_properties(wf_edit PROPERTIES OUTPUT_NAME "wf-edit")
    target_include_directories(wf_edit PRIVATE
        ${IMGUI_DIR} ${IMGUI_DIR}/backends
        ${IMGUIZMO_DIR}                              # ImGuizmo.h
        ${IMGUI_MARKDOWN_DIR}                        # imgui_markdown.h (chat rendering)
        ${CMAKE_SOURCE_DIR}/engine/crdt              # wfcrdt.hpp (read-only Y.Doc)
        ${CMAKE_SOURCE_DIR}/engine/mutation          # wfmut.hpp (M3 CRDT->engine bridge)
        ${CMAKE_SOURCE_DIR}/third_party/json         # <nlohmann/json.hpp>
        ${CMAKE_SOURCE_DIR}/wftools/oaddump          # oad.hp (Phase 2 OAD reader)
        ${CMAKE_SOURCE_DIR}/engine/vendor/miniaudio-0.11.25  # <miniaudio/miniaudio.h>
        ${OPUS_INCLUDE_DIRS}
        ${VPX_INCLUDE_DIRS}
        ${libdatachannel_SOURCE_DIR}/include         # <rtc/rtc.hpp>
    )
    # main.cc compiles against engine headers, so the target needs the engine's
    # flags (mirrors wf_host_gl_e2e_test). Harmless for the ImGui TUs alongside.
    target_compile_options(wf_edit PRIVATE
        -fpermissive -w -fno-rtti
        "-D__GAME__=\"wf-edit\""
        "-DERR_DEBUG(x)="
        "$<$<OR:$<CONFIG:Debug>,$<CONFIG:RelWithDebInfo>>:-O0;-g>"
        "$<$<AND:$<CONFIG:Release>,$<CXX_COMPILER_ID:Clang>>:-O3;-flto=thin>"
    )
    # Link the engine (host-GL embed via SetHostGLContext + StepFrame) and
    # wfcrdt (M4 read-only Y.Doc; pulls in libyrs.a from the editor build).
    target_link_libraries(wf_edit PRIVATE wfengine wfcrdt glfw GL
        ${OPUS_LIBRARIES} ${VPX_LIBRARIES}
        OpenSSL::SSL OpenSSL::Crypto
        datachannel-static
        pthread)

    # Relay connect retry policy — pure, header-only (connect_retry.h), no GL /
    # no sockets, so it's a fast standalone unit test. Fault-injects a scripted
    # connector + fake clock to pin fail-fast (NXDOMAIN/4xx → 1 attempt), budget,
    # backoff, and abort. The regression guard from the 2026-06-01 critique (⑦).
    add_executable(connect_retry_test engine/wf_edit/connect_retry_test.cc)
    target_include_directories(connect_retry_test PRIVATE ${CMAKE_SOURCE_DIR}/engine/wf_edit)
    add_test(NAME wf_edit_connect_retry COMMAND connect_retry_test)

    # Close-button regression (2026-06-01 critique ③): point the editor at a dead
    # relay port so it enters the retry/connect modal, then WF_EDIT_ABORT_CONNECT_AFTER
    # simulates a window-close a few frames in — the editor must bail and print
    # "connect cancelled by user" promptly rather than spinning out the 15 s budget.
    # GL + DISPLAY (opens the connect modal window).
    add_test(NAME wf_edit_connect_abort
        COMMAND sh -c "WF_EDIT_ABORT_CONNECT_AFTER=5 $<TARGET_FILE:wf_edit> --relay=ws://127.0.0.1:9 --room=abort-test --leveltree=${CMAKE_SOURCE_DIR}/wflevels/snowgoons-blender/snowgoons-blender.lev --frames 100000 2>&1 | tee /dev/stderr | grep -q 'connect cancelled by user'"
        WORKING_DIRECTORY ${WF_TEST_RUN_DIR})
    set_tests_properties(wf_edit_connect_abort
        PROPERTIES LABELS "gl" ENVIRONMENT "DISPLAY=:0")

    # SpawnActor runtime-path confirmation: loads snowgoons, finds the first
    # valid template, spawns it, checks the result. Confirms the Jolt
    # position-sync fix (commit 0adf1d4) works end-to-end. Needs GL + DISPLAY.
    add_test(NAME wf_edit_spawn_confirm
        COMMAND sh -c "WF_EDIT_SPAWN_CONFIRM_TEST=1 $<TARGET_FILE:wf_edit> --frames 5 --level=${WF_TEST_SNOW_LEVEL} 2>&1 | tee /dev/stderr | grep -q '\\[spawn-test\\] PASS'"
        WORKING_DIRECTORY ${WF_TEST_RUN_DIR})
    set_tests_properties(wf_edit_spawn_confirm
        PROPERTIES LABELS "gl" ENVIRONMENT "DISPLAY=:0")

    # Native undo/redo logic — CPU-only (exits before GL), so no DISPLAY needed.
    # Drives a field edit + dup + del through the UndoManager and asserts the Doc
    # state returns to each checkpoint on undo/redo. Runs from the repo root so
    # FindLevtree() resolves the levtree binary's relative path.
    add_test(NAME wf_edit_undo
        COMMAND sh -c "WF_EDIT_UNDO_TEST='field:Mass|DATA|2.5;undo;redo;dup:0;undo;del:1;undo' $<TARGET_FILE:wf_edit> --select=0 --leveltree=${CMAKE_SOURCE_DIR}/wflevels/snowgoons-blender/snowgoons-blender.lev 2>&1 | tee /dev/stderr | grep -q '\\[undo\\] all PASS'"
        WORKING_DIRECTORY ${CMAKE_SOURCE_DIR})

    # Add-actor logic — CPU-only (exits before GL), no DISPLAY needed. Inserts a
    # brand-new statplat from OAD defaults and asserts actor count +1, Class Name
    # correct, and field count > 4 (OAD defaults populated). Runs from repo root.
    add_test(NAME wf_edit_add
        COMMAND sh -c "WF_EDIT_ADD_TEST=statplat $<TARGET_FILE:wf_edit> --leveltree=${CMAKE_SOURCE_DIR}/wflevels/snowgoons-blender/snowgoons-blender.lev 2>&1 | tee /dev/stderr | grep -q '\\[add\\].*PASS'"
        WORKING_DIRECTORY ${CMAKE_SOURCE_DIR})

    # ICE/TURN config + WebRTC connectivity (Phase 3). CPU/network-only — returns
    # before GL, no DISPLAY. Asserts ResolveIceConfig env precedence + a loopback
    # P2P connect. The force-relay-through-TURN leg runs only when WF_COLLAB_TURN
    # is set (a coturn box); see `task turn-test-relay`.
    add_test(NAME wf_edit_turn
        COMMAND sh -c "WF_EDIT_TURN_TEST=1 $<TARGET_FILE:wf_edit> 2>&1 | tee /dev/stderr | grep -q '\\[turn\\] all PASS'"
        WORKING_DIRECTORY ${CMAKE_SOURCE_DIR})

    # Headless 3-peer WebRTC mesh self-test (Phase 3 of the multi-peer plan).
    # Runs the wf_edit binary before GL, no DISPLAY: three in-process WebrtcSessions
    # shuttle each other's signalling and must all reach ConnectedPeerCount()==2 (a
    # complete mesh). The headless complement to tests/screenshot_three_peer_b2.sh.
    add_test(NAME wf_edit_mesh
        COMMAND sh -c "WF_EDIT_MESH_TEST=1 $<TARGET_FILE:wf_edit> 2>&1 | tee /dev/stderr | grep -q '\\[mesh\\] all PASS'"
        WORKING_DIRECTORY ${CMAKE_SOURCE_DIR})

    # Native VideoChat decoder-creation race (regression guard): a remote VP8
    # keyframe that arrives before the presence-driven SyncPeers registers the
    # peer must be decoded by the lazy-create path (EnsurePeer) rather than
    # dropped — else the decoder stays waiting_for_keyframe and the remote video
    # is blank. CPU-only (encodes one real keyframe via libvpx, exits before GL).
    add_test(NAME wf_edit_video_race
        COMMAND sh -c "WF_EDIT_VIDEO_RACE_TEST=1 $<TARGET_FILE:wf_edit> 2>&1 | tee /dev/stderr | grep -q '\\[video-race\\] all PASS'"
        WORKING_DIRECTORY ${CMAKE_SOURCE_DIR})

    # RTCP PLI (regression guard): PLI wire format + discrimination, the honor-side
    # force-keyframe decision, and the request-side trigger/throttle/activity gate.
    # CPU-only (encodes a real keyframe via libvpx, exits before GL).
    add_test(NAME wf_edit_pli
        COMMAND sh -c "WF_EDIT_PLI_TEST=1 $<TARGET_FILE:wf_edit> 2>&1 | tee /dev/stderr | grep -q '\\[pli\\] all PASS'"
        WORKING_DIRECTORY ${CMAKE_SOURCE_DIR})

    # wf-relay: standalone relay server binary (co-edit Phase 1).
    # Built via Cargo; not linked into wf_edit (avoids duplicate Rust runtime symbols).
    add_custom_target(wf_relay
        COMMAND cargo build --release --bin wf-relay
                --manifest-path ${CMAKE_SOURCE_DIR}/wftools/wf_collab/Cargo.toml
        COMMENT "Building wf-relay (co-edit relay server)"
        WORKING_DIRECTORY ${CMAKE_SOURCE_DIR})
endif()

# ─── Browser/WASM editor (wf_edit_web) ───────────────────────────────────────
# The Dear ImGui editor compiled to Emscripten/WebGL2. Reuses the portable
# editor sources; the native-only media/discovery stack (collab_session /
# voice_track / video_track / webrtc_session and the native ws_client) is
# replaced by no-op stubs (collab_stub_web.cc) + a browser WebSocket backend
# (ws_client_emscripten.cc). GLFW is Emscripten's built-in port (-sUSE_GLFW=3),
# so imgui_impl_glfw + imgui_impl_opengl3 work unchanged; the engine adopts the
# editor's single WebGL2 canvas context. v1 = co-edit + presence + chat;
# voice/video deferred. See docs/plans/2026-06-12-wf-edit-in-the-browser.md.
if(WF_ENABLE_WEB_EDITOR AND EMSCRIPTEN)
    set(IMGUI_DIR ${CMAKE_SOURCE_DIR}/third_party/imgui)
    set(IMGUIZMO_DIR ${CMAKE_SOURCE_DIR}/third_party/imguizmo)
    set(IMGUI_MARKDOWN_DIR ${CMAKE_SOURCE_DIR}/third_party/imgui_markdown)
    add_executable(wf_edit_web
        engine/wf_edit/main.cc
        engine/wf_edit/level_doc.cc
        engine/wf_edit/property_panel.cc
        engine/wf_edit/oad_reader.cc
        engine/wf_edit/engine_bridge.cc
        engine/wf_edit/gizmo.cc
        engine/wf_edit/level_save.cc
        engine/wf_edit/collab_panel.cc
        engine/wf_edit/collab_stub_web.cc       # relay-only peer discovery (web)
        engine/wf_edit/webrtc_web.cc            # browser-WebRTC A/V (RTCPeerConnection)
        engine/wf_edit/ws_client_emscripten.cc  # browser WebSocket relay backend
        wftools/oaddump/oad.cc
        ${IMGUI_DIR}/imgui.cpp
        ${IMGUI_DIR}/imgui_draw.cpp
        ${IMGUI_DIR}/imgui_tables.cpp
        ${IMGUI_DIR}/imgui_widgets.cpp
        ${IMGUI_DIR}/misc/cpp/imgui_stdlib.cpp
        ${IMGUI_DIR}/backends/imgui_impl_glfw.cpp
        ${IMGUI_DIR}/backends/imgui_impl_opengl3.cpp
        ${IMGUIZMO_DIR}/ImGuizmo.cpp
    )
    add_dependencies(wf_edit_web gen_oas_headers)

    # Web Doc-population: wasm has no popen, so the editor can't shell out to
    # `levtree parse <lev>` at runtime. Pre-parse the .lev with the NATIVE levtree
    # at build time and preload the JSON beside the .lev (<lev>.json) into MEMFS;
    # the web RunLevtreeParse reads that file instead (engine/wf_edit/level_doc.cc).
    set(_WF_WEB_LEV  ${CMAKE_SOURCE_DIR}/wflevels/snowgoons-blender/snowgoons-blender.lev)
    set(_WF_WEB_JSON ${CMAKE_CURRENT_BINARY_DIR}/snowgoons-blender.lev.json)
    set(_WF_LEVTREE  ${CMAKE_SOURCE_DIR}/wftools/levtree-rs/target/release/levtree)
    # Run at configure time (execute_process OUTPUT_FILE captures stdout cleanly —
    # add_custom_command can't redirect). The .lev is a static demo asset, so a
    # configure-time parse is fine; reconfigure if it changes.
    if(EXISTS ${_WF_LEVTREE})
        execute_process(COMMAND ${_WF_LEVTREE} parse ${_WF_WEB_LEV}
                        OUTPUT_FILE ${_WF_WEB_JSON} RESULT_VARIABLE _wf_lt_rc)
        if(NOT _wf_lt_rc EQUAL 0)
            message(WARNING "levtree parse failed (rc=${_wf_lt_rc}) — web Outliner will be empty")
        endif()
    else()
        message(WARNING "native levtree not built (${_WF_LEVTREE}) — web Outliner will be empty; "
                        "run: cargo build --release --manifest-path wftools/levtree-rs/Cargo.toml")
    endif()

    set_source_files_properties(${CMAKE_SOURCE_DIR}/engine/wf_edit/engine_bridge.cc
        PROPERTIES OBJECT_DEPENDS ${NAMEPATH_OUT})
    set_target_properties(wf_edit_web PROPERTIES OUTPUT_NAME "wf-edit" SUFFIX ".html")
    target_include_directories(wf_edit_web PRIVATE
        ${IMGUI_DIR} ${IMGUI_DIR}/backends
        ${IMGUIZMO_DIR}
        ${IMGUI_MARKDOWN_DIR}
        ${CMAKE_SOURCE_DIR}/engine/crdt
        ${CMAKE_SOURCE_DIR}/engine/mutation
        ${CMAKE_SOURCE_DIR}/third_party/json
        ${CMAKE_SOURCE_DIR}/wftools/oaddump
        ${CMAKE_SOURCE_DIR}/engine/vendor/miniaudio-0.11.25
    )
    # nlohmann/json (presence/chat parse in main.cc) uses try/catch, so the
    # editor TUs need exceptions even though the engine lib is -fno-exceptions.
    target_compile_options(wf_edit_web PRIVATE
        -fpermissive -w -fno-rtti -fexceptions
        -Wno-register   # engine headers (color.hpi) use 'register'; emcc/clang
                        # treats it as a hard C++17 error that -w doesn't downgrade
                        # (mirrors wf_game's web target).
        "-D__GAME__=\"wf-edit\""
        "-DERR_DEBUG(x)="
        "$<$<CONFIG:Release>:-O3>"
    )
    # One-click .lev Export (web): wasm has no popen, so we can't shell out to
    # `levtree print`. Instead link the levtree crate's C ABI (levtree_print_json,
    # crate-type staticlib) as a wasm static lib and convert JSON→.lev in-process.
    # Built via cargo (not Corrosion — the crate's lib and bin share the name
    # "levtree", which would collide as two CMake targets). The build inherits the
    # emcmake env (emsdk on PATH) + the Taskfile's RUSTUP_TOOLCHAIN/Rust_CARGO_TARGET.
    set(_WF_LEVTREE_WASM_A
        ${CMAKE_SOURCE_DIR}/wftools/levtree-rs/target/wasm32-unknown-emscripten/release/liblevtree.a)
    add_custom_command(
        OUTPUT ${_WF_LEVTREE_WASM_A}
        COMMAND cargo build --lib --release --target wasm32-unknown-emscripten
                --manifest-path ${CMAKE_SOURCE_DIR}/wftools/levtree-rs/Cargo.toml
        COMMENT "Building levtree wasm staticlib (one-click .lev export)"
        VERBATIM)
    add_custom_target(levtree_wasm_build DEPENDS ${_WF_LEVTREE_WASM_A})
    add_library(levtree_wasm STATIC IMPORTED GLOBAL)
    set_target_properties(levtree_wasm PROPERTIES IMPORTED_LOCATION ${_WF_LEVTREE_WASM_A})
    add_dependencies(wf_edit_web levtree_wasm_build)

    target_link_libraries(wf_edit_web PRIVATE wfengine wfcrdt levtree_wasm)
    target_link_options(wf_edit_web PRIVATE
        -sUSE_GLFW=3
        -sMIN_WEBGL_VERSION=2
        -sMAX_WEBGL_VERSION=2
        -sALLOW_MEMORY_GROWTH=1
        -sEXIT_RUNTIME=0
        # ImGui's recursive draw + the engine StepFrame run on one stack; the 64 KB
        # emscripten default overflows on the first editor frame. wf_game (shallower
        # per-frame depth) doesn't need this; the editor does. 8 MB ~ a desktop stack.
        -sSTACK_SIZE=8388608
        -fexceptions
        # stringToNewUTF8/UTF8ToString are used by webrtc_web.cc's EM_JS bridge
        # (DrainSignaling polls a JSON string out of JS; args arrive as char*).
        -sEXPORTED_RUNTIME_METHODS=callMain,requestFullscreen,stringToNewUTF8,UTF8ToString
        -lwebsocket.js          # emscripten/websocket.h (relay transport, Phase 2)
        -lidbfs.js              # persistence (save/identity)
        "$<$<CONFIG:Release>:-O3>"
        "SHELL:--shell-file ${CMAKE_SOURCE_DIR}/web/shell-edit.html"
        # Preloaded level into MEMFS: the .lev tree drives the CRDT Doc/Outliner
        # (LoadLevelTreeIntoDoc), the standalone .iff is the engine viewport (-L).
        # Both are the snowgoons demo (Doc + viewport are the same level).
        "SHELL:--preload-file ${CMAKE_SOURCE_DIR}/wflevels/snowgoons-blender@/level"
        "SHELL:--preload-file ${CMAKE_SOURCE_DIR}/wflevels/snowgoons-standalone.iff@/snowgoons-standalone.iff"
        # Pre-parsed .lev → JSON (built above) for web Doc-population (no popen on wasm).
        "SHELL:--preload-file ${_WF_WEB_JSON}@/level/snowgoons-blender.lev.json"
    )
endif()
