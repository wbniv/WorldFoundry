//=============================================================================
// gfx/gl/host_gl_context.cc: Linux/X11 impl of the host-supplied GL context
// registry declared in gfx/host_gl_context.h.
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// Body is Linux-only. The directory gfx/gl is also in the Android WF_DIRS
// (CMakeLists.txt:80-88) so the file is globbed on Android — guard with
// __LINUX__ && !__ANDROID__ so Android picks up the no-op stubs from
// hal/android/lifecycle.cc instead and we don't double-define.
// iOS excludes gfx/gl entirely from WF_DIRS, so no guard needed there.
//=============================================================================

#if defined(__LINUX__) && !defined(__ANDROID__)

#include <gfx/host_gl_context.h>
#include <hal/lifecycle.h>

#include <atomic>

// File-scope registry. Editor writes once (from its setup thread) before
// constructing WFGame; mesa.cc reads on the engine thread thereafter.
// No cross-thread sharing of these handles → no atomic. _closeRequested
// IS atomic since it crosses the X11 event-handler boundary; defined in
// mesa.cc and exposed extern here so HALRequestClose can set it.
static HostGLContext g_hostCtx{};

extern std::atomic<int> _closeRequested;   // mesa.cc:57

extern "C" void
SetHostGLContext(const HostGLContext* h)
{
    if (h)
        g_hostCtx = *h;
    else
        g_hostCtx = HostGLContext{};
}

extern "C" HostGLContext
GetHostGLContext(void)
{
    return g_hostCtx;
}

extern "C" void
ClearHostGLContext(void)
{
    g_hostCtx = HostGLContext{};
}

// Host-driven close. Standalone path keeps using the X11 WM_DELETE_WINDOW
// handler in mesa.cc's ProcessXEvents. In host-owned mode the editor's
// window manager / close button calls HALRequestClose() from whichever
// thread it pleases; the engine's next HALWindowCloseRequested() poll
// returns nonzero and the normal shutdown path runs.
extern "C" void
HALRequestClose(void)
{
    _closeRequested.store(1);
}

#endif // __LINUX__ && !__ANDROID__
