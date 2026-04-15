cmake_minimum_required(VERSION 3.16)
project(jolt_wf CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Jolt.cmake creates the Jolt target and alias Jolt::Jolt itself.
# We only need to point it at the source root and configure the target after.
set(PHYSICS_REPO_ROOT "$ENV{JOLT_DIR}")

# Compile without the debug renderer, profiler, and soft-body.
add_compile_definitions(
    JPH_PROFILE_ENABLED=0
    JPH_DEBUG_RENDERER=0
    NDEBUG
)

include(${PHYSICS_REPO_ROOT}/Jolt/Jolt.cmake)

# Jolt.cmake has now created the Jolt static-library target.
# Apply WF-specific compiler options to it.
target_compile_options(Jolt PRIVATE -O2 -w)
