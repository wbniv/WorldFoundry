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

#include <atomic>

namespace {
std::atomic<bool> g_suspended{false};
}

extern "C" WF_ANDROID_EXPORT void
HALNotifySuspend(void)
{
    g_suspended.store(true, std::memory_order_release);
}

extern "C" WF_ANDROID_EXPORT void
HALNotifyResume(void)
{
    g_suspended.store(false, std::memory_order_release);
}

extern "C" WF_ANDROID_EXPORT int
HALIsSuspended(void)
{
    return g_suspended.load(std::memory_order_acquire) ? 1 : 0;
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
