cmake_minimum_required(VERSION 3.22)
project(wf_game CXX C)

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
set(WF_PHYSICS_ENGINE "jolt"    CACHE STRING "legacy | jolt")
option(WF_REST_API        "REST API box PoC (HTTP runtime-mutation debug)" ON)
option(WF_DEBUG_BRIDGE    "TCP/JSON debug bridge — level-design + AI-agent debugging (Blender live edit, etc.). Independent of WF_ENABLE_EDITOR." ON)
option(WF_ENABLE_STEAM    "Steamworks SDK"                OFF)
option(WF_ASAN            "AddressSanitizer + UBSan (Linux dev only)" OFF)

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

# Mobile (Android + iOS): Forth-only scripting, no Steam, no editor stack,
# no debug bridge, no REST API.
# Matches build_game.sh Android flags. WAMR in particular ships x86_64 assembly
# (`invokeNative_em64.s`) that fails to build on arm64 mobile targets.
if(ANDROID OR IOS)
    set(WF_LUA_ENGINE    "none"   CACHE STRING "" FORCE)
    set(WF_ENABLE_FENNEL OFF      CACHE BOOL   "" FORCE)
    set(WF_JS_ENGINE     "none"   CACHE STRING "" FORCE)
    set(WF_WASM_ENGINE   "none"   CACHE STRING "" FORCE)
    set(WF_ENABLE_WREN   OFF      CACHE BOOL   "" FORCE)
    set(WF_FORTH_ENGINE  "zforth" CACHE STRING "" FORCE)
    set(WF_REST_API      OFF      CACHE BOOL   "" FORCE)
    set(WF_DEBUG_BRIDGE  OFF      CACHE BOOL   "" FORCE)
    set(WF_ENABLE_STEAM  OFF      CACHE BOOL   "" FORCE)
    set(WF_ENABLE_EDITOR OFF      CACHE BOOL   "" FORCE)
endif()

# Debug builds force the bridge ON. The Blender addon's "Live" features
# (debug_bridge.py / panels.py / operators.py — all default port 7777)
# rely on it; surprising them with an opt-in flag broke at least one
# user's workflow when the bridge briefly defaulted off. Mobile is
# already forced OFF above and the NOT(ANDROID OR IOS) guard preserves that.
if(NOT (ANDROID OR IOS) AND CMAKE_BUILD_TYPE STREQUAL "Debug")
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
    # Phase 1: core runtime + HAL only. No RENDERER_* yet — gfx/game/physics
    # dirs are excluded from the iOS build until Phase 2 lands the Metal backend.
    list(APPEND WF_DEFS WF_TARGET_IOS SCALAR_TYPE_FLOAT)
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
    add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)
    add_link_options(-fsanitize=address,undefined)
    message(STATUS "WF_ASAN: AddressSanitizer + UBSan enabled")
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
    gfx/gl/mesa.cc              gfx/gl/android_window.cc
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

# ─── Jolt Physics ─────────────────────────────────────────────────────────────
set(JOLT_DIR ${VENDOR}/jolt-physics-5.5.0)
# iOS/Xcode: Jolt's add_library(Jolt ...) does not produce a target our scope
# can modify under -G Xcode + CMAKE_SYSTEM_NAME=iOS (symptom: "Cannot specify
# compile options for target 'Jolt' which is not built by this project").
# TODO(ios): investigate Jolt + Xcode generator and re-enable. Until then,
# fall back to the legacy physics backend for the iOS target.
if(IOS AND WF_PHYSICS_ENGINE STREQUAL "jolt")
    message(STATUS "iOS: forcing WF_PHYSICS_ENGINE=legacy (Jolt+Xcode integration deferred)")
    set(WF_PHYSICS_ENGINE "legacy" CACHE STRING "" FORCE)
endif()
if(WF_PHYSICS_ENGINE STREQUAL "jolt")
    list(APPEND WF_SOURCES
        ${STUB_SRC}/physics_jolt.cc
        ${SRC}/physics/jolt/jolt_backend.cc
    )
    list(APPEND WF_INCLUDES ${JOLT_DIR})
    list(APPEND WF_DEFS PHYSICS_ENGINE_JOLT NDEBUG)
    set(PHYSICS_REPO_ROOT ${JOLT_DIR})
    include(${JOLT_DIR}/Jolt/Jolt.cmake)
    # -fno-rtti: Jolt uses its own RTTI macro system (Jolt/Core/RTTI.h), zero
    # C++ dynamic_cast/typeid in its sources — safe to drop the type_info tables.
    target_compile_options(Jolt PRIVATE -O2 -w -fno-rtti)
    # Force NDEBUG into Jolt's own TUs and PUBLIC-propagate to consumers.
    # Without this, Jolt.a was built without NDEBUG (the auto-set NDEBUG in
    # Jolt.cmake:515 only applies in Release configs), which made JPH_DEBUG
    # / JPH_ENABLE_ASSERTS define-ON inside Jolt — while wfengine's TUs
    # (which set NDEBUG via WF_DEFS) see them as define-OFF. The macro
    # `JPH_IF_ENABLE_ASSERTS` then expands differently across TUs and
    # `ConstraintManager` even has a ctor that exists only when asserts
    # are enabled (ConstraintManager.h:32) — silent ODR violation. The
    # external harness (wf_host_gl_e2e_test) trips SIGTRAP in
    # `BodyManager::Init` because its stack-resident `PhysicsSystem` was
    # half-initialised by wfengine's view of the ctor and then asserted-
    # against by Jolt.a's view of the body. wf_game happens to dodge the
    # SIGTRAP because its stack pattern leaves mActiveBodies[1] as zero;
    # the harness's stack has the 0xa9-fill that trips it. The fix:
    # consistent NDEBUG / JPH_ENABLE_ASSERTS state across all TUs.
    target_compile_definitions(Jolt PUBLIC NDEBUG)
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
    "$<$<CONFIG:Release>:-O3;-flto=thin;-ffunction-sections;-fdata-sections;-fvisibility=hidden;-fno-exceptions;-fno-unwind-tables;-fno-asynchronous-unwind-tables>"
)
if(ANDROID OR IOS)
    # Legacy `register` keyword is C++17-removed; WF's pigsys/endian.cc still
    # uses it. Silence to match the Linux build's permissive stance.
    target_compile_options(wfengine PRIVATE -Wno-register)
endif()

# iOS: miniaudio.h (included via audio/linux/audio_internal.hp) pulls in
# AVFoundation.framework headers on Darwin, which contain Objective-C syntax.
# The audio/linux/*.cc files would fail to parse as plain C++, so compile them
# as Objective-C++ on iOS. (Linux/Android stay on plain C++ — no AVFoundation.)
if(IOS)
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
    "$<$<CONFIG:Release>:-O3;-flto=thin;-ffunction-sections;-fdata-sections;-fvisibility=hidden;-fno-exceptions;-fno-unwind-tables;-fno-asynchronous-unwind-tables>"
)
target_link_options(wf_game PRIVATE
    "$<$<CONFIG:Release>:-flto=thin;-Wl,--gc-sections;-Wl,--icf=safe;-Wl,-O2;-Wl,--export-dynamic-symbol=ANativeActivity_onCreate>"
)
if(ANDROID OR IOS)
    target_compile_options(wf_game PRIVATE -Wno-register)
endif()

if(ANDROID)
    # Bump Jolt + zforth to -O3 in Release to match main target. (Jolt is ~36%
    # of .text so even +10% speed here moves the needle.) Jolt has no `throw`
    # in its source, so -fno-exceptions is a drop-in win — removes all the
    # .eh_frame / .gcc_except_table entries that C++ template-heavy code
    # generates by default.
    if(TARGET Jolt)
        target_compile_options(Jolt PRIVATE "$<$<CONFIG:Release>:-O3;-flto=thin;-ffunction-sections;-fdata-sections;-fvisibility=hidden;-fno-exceptions;-fno-unwind-tables;-fno-asynchronous-unwind-tables>")
    endif()
    if(TARGET zforth)
        target_compile_options(zforth PRIVATE "$<$<CONFIG:Release>:-O3;-flto=thin;-ffunction-sections;-fdata-sections>")
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
if(NOT ANDROID AND NOT IOS)
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
        "$<$<CONFIG:Release>:-O3;-flto=thin>"
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

# ─── Output location matches build_game.sh ────────────────────────────────────
if(NOT ANDROID)
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
if(WF_ENABLE_EDITOR AND NOT ANDROID AND NOT IOS)
    # GLFW — editor-owned X11/GLX window + context (lean build, X11 only).
    set(GLFW_BUILD_DOCS     OFF CACHE BOOL "" FORCE)
    set(GLFW_BUILD_TESTS    OFF CACHE BOOL "" FORCE)
    set(GLFW_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
    set(GLFW_BUILD_WAYLAND  OFF CACHE BOOL "" FORCE)
    add_subdirectory(third_party/glfw)

    set(IMGUI_DIR ${CMAKE_SOURCE_DIR}/third_party/imgui)
    add_executable(wf_edit
        engine/wf_edit/main.cc
        engine/wf_edit/level_doc.cc            # M4: levtree -> wfcrdt::Doc
        ${IMGUI_DIR}/imgui.cpp
        ${IMGUI_DIR}/imgui_draw.cpp
        ${IMGUI_DIR}/imgui_tables.cpp
        ${IMGUI_DIR}/imgui_widgets.cpp
        ${IMGUI_DIR}/backends/imgui_impl_glfw.cpp
        ${IMGUI_DIR}/backends/imgui_impl_opengl3.cpp
    )
    set_target_properties(wf_edit PROPERTIES OUTPUT_NAME "wf-edit")
    target_include_directories(wf_edit PRIVATE
        ${IMGUI_DIR} ${IMGUI_DIR}/backends
        ${CMAKE_SOURCE_DIR}/engine/crdt              # wfcrdt.hpp (read-only Y.Doc)
        ${CMAKE_SOURCE_DIR}/third_party/json)        # <nlohmann/json.hpp>
    # main.cc compiles against engine headers, so the target needs the engine's
    # flags (mirrors wf_host_gl_e2e_test). Harmless for the ImGui TUs alongside.
    target_compile_options(wf_edit PRIVATE
        -fpermissive -w -fno-rtti
        "-D__GAME__=\"wf-edit\""
        "-DERR_DEBUG(x)="
        "$<$<OR:$<CONFIG:Debug>,$<CONFIG:RelWithDebInfo>>:-O0;-g>"
        "$<$<CONFIG:Release>:-O3;-flto=thin>"
    )
    # Link the engine (host-GL embed via SetHostGLContext + StepFrame) and
    # wfcrdt (M4 read-only Y.Doc; pulls in libyrs.a from the editor build).
    target_link_libraries(wf_edit PRIVATE wfengine wfcrdt glfw GL)
endif()
