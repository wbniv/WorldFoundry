# Initial cache for the desktop dev engine: what `task build` (scripts/build-wf-game.sh)
# builds, and what the local CI's dev builder builds. The one place this configuration
# lives; plan docs/plans/2026-11-14-single-desktop-build.md.
#
#   cmake -S . -B build-wf-game -C cmake/wf-game-dev.cmake
#
# Debug brings the rest from CMakeLists.txt's own defaults: the debug defines (asserts,
# DBSTREAM), WF_DESIGNER_CHEATS and WF_TEST_CODE, ASan + UBSan, the debug bridge, the REST
# API. A -D on the command line wins over these (an initial cache never overrides a value
# already in the cache).
set(CMAKE_BUILD_TYPE  Debug   CACHE STRING "")

# Scripting roster: Lua (the MobDebug step debugger needs a host), zForth (+ neural-forth),
# PILOT. No Fennel, JavaScript, WebAssembly or Wren, which CMake otherwise turns on.
set(WF_LUA_ENGINE     lua54   CACHE STRING "")
set(WF_ENABLE_FENNEL  OFF     CACHE BOOL   "")
set(WF_JS_ENGINE      none    CACHE STRING "")
set(WF_WASM_ENGINE    none    CACHE STRING "")
set(WF_ENABLE_WREN    OFF     CACHE BOOL   "")
set(WF_FORTH_ENGINE   zforth  CACHE STRING "")
set(WF_PILOT_ENGINE   builtin CACHE STRING "")
set(WF_PHYSICS_ENGINE jolt    CACHE STRING "")
