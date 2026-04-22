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
option(WF_REST_API        "REST API box PoC"              ON)
option(WF_ENABLE_STEAM    "Steamworks SDK"                OFF)

# Mobile (Android + iOS): Forth-only scripting, no Steam, no REST API.
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
    set(WF_ENABLE_STEAM  OFF      CACHE BOOL   "" FORCE)
endif()

# ─── Fennel/Lua consistency check ─────────────────────────────────────────────
if(WF_ENABLE_FENNEL AND NOT WF_LUA_ENGINE STREQUAL "lua54")
    message(WARNING "WF_ENABLE_FENNEL=ON but WF_LUA_ENGINE!=lua54; forcing WF_LUA_ENGINE=lua54")
    set(WF_LUA_ENGINE "lua54" CACHE STRING "" FORCE)
endif()

# ─── Accumulated lists (filled below) ─────────────────────────────────────────
set(WF_SOURCES)
set(WF_INCLUDES  ${SRC} ${SRC}/game ${ENG_INC} ${STUB_SRC}
                 ${VENDOR}/miniaudio-0.11.25 ${VENDOR}/tsf)
set(WF_DEFS)
set(WF_LINK_LIBS)

# ─── Platform definitions ─────────────────────────────────────────────────────
if(ANDROID)
    list(APPEND WF_DEFS WF_TARGET_ANDROID __ANDROID__
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

# ─── Collect sources with skip filter ─────────────────────────────────────────
foreach(dir ${WF_DIRS})
    file(GLOB dir_srcs "${SRC}/${dir}/*.cc")
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
    target_compile_options(Jolt PRIVATE -O2 -w)
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
if(ANDROID)
    set(APP_GLUE_DIR ${ANDROID_NDK}/sources/android/native_app_glue)
    list(APPEND WF_SOURCES ${APP_GLUE_DIR}/android_native_app_glue.c)
    list(APPEND WF_INCLUDES ${APP_GLUE_DIR})
endif()

# ─── wf_game target ───────────────────────────────────────────────────────────
if(ANDROID)
    add_library(wf_game SHARED ${WF_SOURCES})
    # ANativeActivity_onCreate lives in android_native_app_glue.c and is the
    # Android loader's entry point. Without -u the linker garbage-collects it.
    target_link_options(wf_game PRIVATE -u ANativeActivity_onCreate)
else()
    add_executable(wf_game ${WF_SOURCES})
endif()

target_include_directories(wf_game PRIVATE ${WF_INCLUDES})
target_compile_definitions(wf_game PRIVATE ${WF_DEFS})
# -fpermissive and tricky macro defines go in compile_options (not definitions).
# Optimisation is config-dependent: Debug / RelWithDebInfo stay at -O0 -g so
# the debugger shows real source; Release cranks up -O3 + LTO + section GC.
target_compile_options(wf_game PRIVATE
    -fpermissive -w
    "-D__GAME__=\"wf_game\""
    "-DERR_DEBUG(x)="
    "$<$<OR:$<CONFIG:Debug>,$<CONFIG:RelWithDebInfo>>:-O0;-g>"
    "$<$<CONFIG:Release>:-O3;-flto=thin;-ffunction-sections;-fdata-sections;-fvisibility=hidden;-fno-exceptions;-fno-unwind-tables;-fno-asynchronous-unwind-tables>"
)
target_link_options(wf_game PRIVATE
    "$<$<CONFIG:Release>:-flto=thin;-Wl,--gc-sections;-Wl,--icf=safe;-Wl,-O2;-Wl,--export-dynamic-symbol=ANativeActivity_onCreate>"
)

if(ANDROID)
    target_compile_options(wf_game PRIVATE -Wno-register)
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
if(ANDROID)
    list(APPEND WF_LINK_LIBS EGL GLESv3 android log m OpenSLES)
else()
    list(APPEND WF_LINK_LIBS GL GLU X11 m pthread dl)
    target_link_options(wf_game PRIVATE -Wl,-z,noexecstack)
    if(WF_ENABLE_STEAM)
        target_link_directories(wf_game PRIVATE
            ${STEAM_DIR}/redistributable_bin/linux64)
        list(APPEND WF_LINK_LIBS steam_api)
        target_link_options(wf_game PRIVATE "-Wl,-rpath,$$ORIGIN")
    endif()
endif()

target_link_libraries(wf_game PRIVATE ${WF_LINK_LIBS})

# ─── Output location matches build_game.sh ────────────────────────────────────
if(NOT ANDROID)
    set_target_properties(wf_game PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/engine)
endif()
