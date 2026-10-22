add_library(wf_dream SHARED
    "${CMAKE_SOURCE_DIR}/android/screensaver/src/main/cpp/dream_host.cc"
    "${CMAKE_SOURCE_DIR}/android/screensaver/src/main/cpp/planted_bridge.cc")
target_link_libraries(wf_dream PRIVATE wfengine)
# NDK r26 defaults to 4 KiB LOAD segments; support 16 KiB page-size devices.
target_link_options(wf_dream PRIVATE
    "-Wl,-z,max-page-size=16384"
    "-Wl,-z,common-page-size=16384")
# runtime_properties.hpp, for the Planted Tank launch-override adapter in dream_host.cc.
target_include_directories(wf_dream PRIVATE "${CMAKE_SOURCE_DIR}/engine")
target_compile_options(wf_dream PRIVATE
    -fpermissive -w -fno-rtti
    "-D__GAME__=\"wf_dream\""
    "-DERR_DEBUG(x)=")
