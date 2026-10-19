add_library(wf_dream SHARED
    "${CMAKE_SOURCE_DIR}/android/screensaver/src/main/cpp/dream_host.cc")
target_link_libraries(wf_dream PRIVATE wfengine)
target_compile_options(wf_dream PRIVATE
    -fpermissive -w -fno-rtti
    "-D__GAME__=\"wf_dream\""
    "-DERR_DEBUG(x)=")
