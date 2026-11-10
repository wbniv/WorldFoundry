#pragma once

// The authoring switch is absent from shipped and mobile builds.
#if defined(BUILDMODE_DEBUG) && !defined(__ANDROID__) && !defined(WF_TARGET_IOS) && !defined(__EMSCRIPTEN__)
#define WF_RUNTIME_EDIT_ALL 1
namespace wfprops {
inline bool& editAllEnabled() { static bool enabled = false; return enabled; }
}
#endif
