# Added at project(wf_game) by this app's Gradle configuration. The shared
# CMakeLists.txt remains unchanged; register this app target after it is read.
set(WF_DREAM_TARGET_FILE "${CMAKE_CURRENT_LIST_DIR}/dream-target.cmake")
cmake_language(DEFER CALL include "${WF_DREAM_TARGET_FILE}")
