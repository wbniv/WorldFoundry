//=============================================================================
// gfx/gl/android_window.cc: Android EGL + ANativeWindow glue (stub)
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//==============================================================================
// Peer of gl/mesa.cc for the Android target. Phase 3 step 1 stubs: functions
// exist so gfx/gl/display.cc compiles unchanged, but actual window/context
// creation is deferred to when the NativeActivity wrapper lands and feeds us
// an ANativeWindow.
//
// Exports the same API surface that mesa.cc does:
//   - OpenMainWindow(const char* title)
//   - InitWindow(int, int, int, int) → bool
//   - XEventLoop()
//   - SetX11AutoRepeat(int) — no-op
// Plus AndroidSwapBuffers() which display.cc calls in place of glXSwapBuffers.
//============================================================================

// Body is compiled only when included by gl/display.cc on the Android build.
// If a build system (e.g. build_game.sh) sweeps the directory and compiles
// this TU directly on desktop, skip it: everything it defines is needed only
// inside display.cc's translation unit.
#if defined(__ANDROID__)

#include <EGL/egl.h>
#include <android/native_window.h>
#include <cstdio>

namespace
{

EGLDisplay gEglDisplay = EGL_NO_DISPLAY;
EGLSurface gEglSurface = EGL_NO_SURFACE;
EGLContext gEglContext = EGL_NO_CONTEXT;
ANativeWindow* gNativeWindow = nullptr;

}  // namespace

// NativeActivity wrapper (Phase 3 step 2) will call this once the window
// arrives. Until then, the engine can compile but won't have a live context.
void WFAndroidSetNativeWindow(ANativeWindow* window)
{
    gNativeWindow = window;
    // TODO(phase-3-step-2): eglGetDisplay, eglInitialize, eglChooseConfig,
    // eglCreateWindowSurface, eglCreateContext, eglMakeCurrent.
}

void OpenMainWindow(char* /*title*/)
{
    // NativeActivity owns the window — nothing to open here.
}

bool InitWindow(int /*xPos*/, int /*yPos*/, int /*xSize*/, int /*ySize*/)
{
    OpenMainWindow(nullptr);
    return true;
}

void XEventLoop()
{
    // Android event pump lives in the NativeActivity glue; no-op here.
}

void SetX11AutoRepeat(int /*state*/)
{
    // No equivalent on Android.
}

void AndroidSwapBuffers()
{
    if (gEglDisplay != EGL_NO_DISPLAY && gEglSurface != EGL_NO_SURFACE)
        eglSwapBuffers(gEglDisplay, gEglSurface);
}

#endif  // __ANDROID__
