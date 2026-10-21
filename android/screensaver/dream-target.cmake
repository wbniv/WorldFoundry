add_library(wf_dream SHARED
    "${CMAKE_SOURCE_DIR}/android/screensaver/src/main/cpp/dream_host.cc"
    "${CMAKE_SOURCE_DIR}/android/screensaver/src/main/cpp/planted_bridge.cc")
target_link_libraries(wf_dream PRIVATE wfengine)
# runtime_properties.hpp, for the Planted Tank launch-override adapter in dream_host.cc.
target_include_directories(wf_dream PRIVATE "${CMAKE_SOURCE_DIR}/engine")
target_compile_options(wf_dream PRIVATE
    -fpermissive -w -fno-rtti
    "-D__GAME__=\"wf_dream\""
    "-DERR_DEBUG(x)=")
