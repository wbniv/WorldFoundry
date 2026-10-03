//=============================================================================
// hal/android/lifecycle.cc: suspend/resume state for Android
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// NativeActivity wrapper (Phase 3 step 2) calls HALNotifySuspend / Resume
// from the UI thread as it handles onPause / onResume; the main loop reads
// HALIsSuspended to skip rendering. Atomic bool — identical to the Linux
// copy, kept separate because hal/linux/ is not compiled on Android.
//=============================================================================

#include <hal/lifecycle.h>
#include <hal/android/wf_android_export.hp>
#include <gfx/host_gl_context.h>

#include <atomic>

namespace {
std::atomic<bool> g_suspended{false};
std::atomic<unsigned int> g_lifecycleGeneration{0};
}

extern "C" WF_ANDROID_EXPORT void
HALNotifySuspend(void)
{
    g_lifecycleGeneration.fetch_add(1, std::memory_order_acq_rel);
    g_suspended.store(true, std::memory_order_release);
}

extern "C" WF_ANDROID_EXPORT void
HALNotifyResume(void)
{
    g_lifecycleGeneration.fetch_add(1, std::memory_order_acq_rel);
    g_suspended.store(false, std::memory_order_release);
}

extern "C" WF_ANDROID_EXPORT unsigned int
HALLifecycleGeneration(void)
{
    return g_lifecycleGeneration.load(std::memory_order_acquire);
}

// Defined in hal/android/native_app_entry.cc: 1 while an EGL surface exists.
extern "C" int WFAndroidHasWindow(void);

// Suspended = paused by the OS, OR resumed but the window has not come back yet (Home then reopen delivers
// APP_CMD_RESUME before APP_CMD_INIT_WINDOW; drawing with no surface aborts). The suspended loop keeps
// pumping events (HALPumpSuspendedEvents), so INIT_WINDOW arrives and the game carries on.
extern "C" WF_ANDROID_EXPORT int
HALIsSuspended(void)
{
    return (g_suspended.load(std::memory_order_acquire) || !WFAndroidHasWindow()) ? 1 : 0;
}

// Defined in hal/android/native_app_entry.cc — ALooper_pollOnce(0, ...).
extern "C" void WFAndroidPumpEvents(void);

extern "C" WF_ANDROID_EXPORT void
HALPumpSuspendedEvents(void)
{
    // Drain the ALooper so APP_CMD_RESUME (+ any input events queued during
    // suspension) reach our handlers. Without this the game loop's
    // HALIsSuspended() check stays true forever and the app is visibly
    // stuck on resume.
    WFAndroidPumpEvents();
}

// NativeActivity destruction must unwind the shared level/menu loops.
extern "C" int WFAndroidCloseRequested(void);
extern "C" void WFAndroidRequestClose(void);
extern "C" WF_ANDROID_EXPORT int
HALWindowCloseRequested(void)
{
    return WFAndroidCloseRequested();
}

// No native window to tear down from the app side on Android.
extern "C" WF_ANDROID_EXPORT void
HALCloseWindow(void)
{
}

// Mobile is single-window standalone; host-supplied GL context isn't a
// concept here. Stubs satisfy the cross-platform symbol set so editor
// code that links the engine library compiles on every platform; the
// editor itself runs on Linux for v1.

extern "C" WF_ANDROID_EXPORT void
SetHostGLContext(const HostGLContext* /*h*/)
{
}

extern "C" WF_ANDROID_EXPORT HostGLContext
GetHostGLContext(void)
{
    return HostGLContext{};   // valid = false
}

extern "C" WF_ANDROID_EXPORT void
ClearHostGLContext(void)
{
}

extern "C" WF_ANDROID_EXPORT void
HALRequestClose(void)
{
    WFAndroidRequestClose();
}
