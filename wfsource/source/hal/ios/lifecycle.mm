//=============================================================================
// hal/ios/lifecycle.mm: suspend/resume state for iOS
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// AppDelegate / UIViewController lifecycle callbacks (native_app_entry.mm)
// call HALNotifySuspend / Resume on applicationWillResignActive /
// viewWillDisappear and applicationDidBecomeActive / viewDidAppear; the game
// loop reads HALIsSuspended to skip rendering. Atomic bool — identical shape to hal/android/lifecycle.cc.
//=============================================================================

#include <hal/lifecycle.h>
#include <gfx/host_gl_context.h>

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

// An iOS app has no window-close button (the user leaves via the home gesture,
// which arrives as the suspend callbacks above). These stubs satisfy the shared
// main loop (game.cc, main.cc), exactly as hal/android/lifecycle.cc does.
extern "C" int
HALWindowCloseRequested(void)
{
    return 0;
}

extern "C" void
HALCloseWindow(void)
{
}

// Android needs this (0b19119): its events are drained on the game thread,
// so while the suspended loop slept, APP_CMD_RESUME was never delivered and
// the app stayed stuck. On iOS UIKit delivers lifecycle and touch events on
// the main thread, independent of the engine thread that runs this loop, and
// HALNotifyResume is a plain atomic store — so there is nothing to pump and
// the stuck-on-resume failure cannot occur. The Android fix's other half,
// no input state surviving a suspend, is WFIosInputSuspend (input.mm), which
// releases every held touch bit.
extern "C" void
HALPumpSuspendedEvents(void)
{
}

// Mobile is single-window standalone; host-supplied GL context isn't a
// concept here. Stubs satisfy the cross-platform symbol set so editor
// code that links the engine library compiles on every platform; the
// editor itself runs on Linux for v1.

extern "C" void
SetHostGLContext(const HostGLContext* /*h*/)
{
}

extern "C" HostGLContext
GetHostGLContext(void)
{
    return HostGLContext{};   // valid = false
}

extern "C" void
ClearHostGLContext(void)
{
}

extern "C" void
HALRequestClose(void)
{
}
