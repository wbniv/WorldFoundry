//=============================================================================
// hal/ios/lifecycle.mm: suspend/resume state for iOS
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// AppDelegate / UIViewController lifecycle callbacks (native_app_entry.mm)
// call HALNotifySuspend / Resume on applicationWillResignActive /
// applicationDidBecomeActive; the game loop reads HALIsSuspended to skip
// rendering. Atomic bool — identical shape to hal/android/lifecycle.cc.
//=============================================================================

#include <hal/lifecycle.h>

#include <atomic>

namespace {
std::atomic<bool> g_suspended{false};
}

extern "C" void
HALNotifySuspend(void)
{
    g_suspended.store(true, std::memory_order_release);
}

extern "C" void
HALNotifyResume(void)
{
    g_suspended.store(false, std::memory_order_release);
}

extern "C" int
HALIsSuspended(void)
{
    return g_suspended.load(std::memory_order_acquire) ? 1 : 0;
}

// Phase 3 will drive this from the CADisplayLink / UIApplication run loop so
// queued events reach their handlers on resume. For Phase 1 there's nothing
// to pump — the game loop isn't running yet.
extern "C" void
HALPumpSuspendedEvents(void)
{
}
