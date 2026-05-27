//==============================================================================
// hal/macos/window_macos.cc — window-lifecycle stubs for the headless macOS
// desktop bring-up.
//
// On Linux these three live in gfx/gl/mesa.cc (X11 window + WM_DELETE_WINDOW);
// on iOS/Android they come from the UIKit / NativeActivity lifecycle. The
// renderer-agnostic macOS build has no window, so they are trivial: the engine
// loop polls HALWindowCloseRequested() and exits via its frame count (or
// LevelDone), while a host that wants to stop early can call HALRequestClose().
//
// The suspend/resume trio (HALNotifySuspend/Resume/IsSuspended/Pump) is reused
// verbatim from hal/linux/lifecycle.cc — desktop never suspends, so it returns
// "not suspended" exactly as on Linux.
//==============================================================================

#include <hal/lifecycle.h>

#include <atomic>

namespace {
std::atomic<int> g_closeRequested{0};
}

extern "C" int
HALWindowCloseRequested(void)
{
    return g_closeRequested.load(std::memory_order_acquire);
}

extern "C" void
HALRequestClose(void)
{
    g_closeRequested.store(1, std::memory_order_release);
}

extern "C" void
HALCloseWindow(void)
{
    // No window to close in the headless bring-up.
}
