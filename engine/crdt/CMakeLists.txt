# engine/crdt/CMakeLists.txt
#
# Yrs/y-crdt C ABI binding. Built only when WF_ENABLE_CRDT=ON (default OFF).
# See docs/plans/2026-05-18-yrs-c-abi-binding.md.
#
# Artifacts:
#   - libyrs.a       — vendored from wftools/y-crdt/yffi via Corrosion+Cargo.
#                       Despite the workspace name "yffi", the crate's [lib]
#                       name is "yrs", so the static library is libyrs.a.
#   - libwfcrdt.a   — thin wrapper target this dir owns. Re-exports the yffi
#                       C ABI (libyrs.h) to consumers. Editor will link this,
#                       NOT libwfengine.a. See TODO.md.
#   - wfcrdt_smoke  — executable smoke test exercising Doc/Map/Array
#                       round-trip + Yjs wire-format compat + observer fire.

corrosion_import_crate(
    MANIFEST_PATH ${CMAKE_SOURCE_DIR}/wftools/y-crdt/yffi/Cargo.toml
    CRATE_TYPES staticlib
    PROFILE release
)

# The yffi crate's lib name is "yrs", so Corrosion creates a CMake target
# named "yrs" that points at target/release/libyrs.a.

add_library(wfcrdt STATIC
    wfcrdt_stub.c
    wfcrdt.cpp)
target_compile_features(wfcrdt PUBLIC cxx_std_17)
target_link_libraries(wfcrdt PUBLIC yrs)
target_include_directories(wfcrdt PUBLIC
    ${CMAKE_SOURCE_DIR}/wftools/y-crdt/tests-ffi/include
    ${CMAKE_CURRENT_SOURCE_DIR})

# Smoke-test target added in step 5 (wfcrdt_smoke.c).
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/wfcrdt_smoke.c)
    add_executable(wfcrdt_smoke wfcrdt_smoke.c)
    target_link_libraries(wfcrdt_smoke PRIVATE wfcrdt)
endif()

# C++ RAII wrapper test (plan: 2026-05-19-wfcrdt-cpp-raii-wrapper.md).
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/wfcrdt_wrapper_test.cc)
    add_executable(wfcrdt_wrapper_test wfcrdt_wrapper_test.cc)
    target_link_libraries(wfcrdt_wrapper_test PRIVATE wfcrdt)
endif()

# Sync / observeUpdates convergence test (plan: 2026-05-21-realtime-coediting.md Phase 0).
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/wfcrdt_sync_test.cpp)
    add_executable(wfcrdt_sync wfcrdt_sync_test.cpp)
    target_link_libraries(wfcrdt_sync PRIVATE wfcrdt)
endif()
