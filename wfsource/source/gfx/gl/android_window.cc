//=============================================================================
// gfx/gl/android_window.cc: Android EGL + ANativeWindow glue
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//==============================================================================
// Peer of gl/mesa.cc for the Android target. Exports the same surface that
// display.cc expects (OpenMainWindow, InitWindow, XEventLoop,
// SetX11AutoRepeat) plus AndroidSwapBuffers() and an internal
// WFAndroidCreateEglContext(window) used by native_app_entry.cc.
//============================================================================

// Body is compiled only when included by gl/display.cc on the Android build.
// If a build system (e.g. build_game.sh) sweeps the directory and compiles
// this TU directly on desktop, skip it: everything it defines is needed only
// inside display.cc's translation unit.
#if defined(__ANDROID__)

#include <EGL/egl.h>
#include <android/log.h>
#include <android/native_window.h>

#include <cstdio>

namespace
{

EGLDisplay gEglDisplay = EGL_NO_DISPLAY;
EGLSurface gEglSurface = EGL_NO_SURFACE;
EGLContext gEglContext = EGL_NO_CONTEXT;
EGLConfig  gEglConfig  = nullptr;
ANativeWindow* gNativeWindow = nullptr;

#define WF_LOG_TAG "wf_game"
#define WFLOG(fmt, ...) __android_log_print(ANDROID_LOG_INFO, WF_LOG_TAG, fmt, ##__VA_ARGS__)
#define WFLOGE(fmt, ...) __android_log_print(ANDROID_LOG_ERROR, WF_LOG_TAG, fmt, ##__VA_ARGS__)

}  // namespace

// Feeds _halWindow{Width,Height} in hal/android/platform.cc once the surface
// dimensions are known.
extern "C" void WFAndroidSetSurfaceSize(int w, int h);

// Driven by native_app_entry.cc on APP_CMD_INIT_WINDOW / TERM_WINDOW.
// Returns true when GL context is live and current.
extern "C" bool WFAndroidEglInit(ANativeWindow* window);
extern "C" void WFAndroidEglTerm();

extern "C" bool
WFAndroidEglInit(ANativeWindow* window)
{
    if (!window)
    {
        WFLOGE("WFAndroidEglInit: null window");
        return false;
    }
    gNativeWindow = window;

    const EGLint configAttribs[] = {
        EGL_SURFACE_TYPE, EGL_WINDOW_BIT,
        EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT,
        EGL_RED_SIZE,   8,
        EGL_GREEN_SIZE, 8,
        EGL_BLUE_SIZE,  8,
        EGL_DEPTH_SIZE, 16,
        EGL_NONE
    };

    gEglDisplay = eglGetDisplay(EGL_DEFAULT_DISPLAY);
    if (gEglDisplay == EGL_NO_DISPLAY)
    {
        WFLOGE("eglGetDisplay failed");
        return false;
    }
    if (!eglInitialize(gEglDisplay, nullptr, nullptr))
    {
        WFLOGE("eglInitialize failed: 0x%x", eglGetError());
        return false;
    }

    EGLint numConfigs = 0;
    if (!eglChooseConfig(gEglDisplay, configAttribs, &gEglConfig, 1, &numConfigs)
        || numConfigs < 1)
    {
        WFLOGE("eglChooseConfig failed: 0x%x", eglGetError());
        return false;
    }

    EGLint format = 0;
    eglGetConfigAttrib(gEglDisplay, gEglConfig, EGL_NATIVE_VISUAL_ID, &format);
    ANativeWindow_setBuffersGeometry(window, 0, 0, format);

    gEglSurface = eglCreateWindowSurface(gEglDisplay, gEglConfig, window, nullptr);
    if (gEglSurface == EGL_NO_SURFACE)
    {
        WFLOGE("eglCreateWindowSurface failed: 0x%x", eglGetError());
        return false;
    }

    const EGLint contextAttribs[] = {
        EGL_CONTEXT_CLIENT_VERSION, 3,
        EGL_NONE
    };
    gEglContext = eglCreateContext(gEglDisplay, gEglConfig, EGL_NO_CONTEXT, contextAttribs);
    if (gEglContext == EGL_NO_CONTEXT)
    {
        WFLOGE("eglCreateContext failed: 0x%x", eglGetError());
        return false;
    }

    if (!eglMakeCurrent(gEglDisplay, gEglSurface, gEglSurface, gEglContext))
    {
        WFLOGE("eglMakeCurrent failed: 0x%x", eglGetError());
        return false;
    }

    EGLint w = 0, h = 0;
    eglQuerySurface(gEglDisplay, gEglSurface, EGL_WIDTH,  &w);
    eglQuerySurface(gEglDisplay, gEglSurface, EGL_HEIGHT, &h);
    WFAndroidSetSurfaceSize(w, h);
    WFLOG("EGL context ready: %dx%d", w, h);
    return true;
}

extern "C" void
WFAndroidEglTerm()
{
    if (gEglDisplay != EGL_NO_DISPLAY)
    {
        eglMakeCurrent(gEglDisplay, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
        if (gEglContext != EGL_NO_CONTEXT)
            eglDestroyContext(gEglDisplay, gEglContext);
        if (gEglSurface != EGL_NO_SURFACE)
            eglDestroySurface(gEglDisplay, gEglSurface);
        eglTerminate(gEglDisplay);
    }
    gEglDisplay   = EGL_NO_DISPLAY;
    gEglSurface   = EGL_NO_SURFACE;
    gEglContext   = EGL_NO_CONTEXT;
    gEglConfig    = nullptr;
    gNativeWindow = nullptr;
}

// ---- API surface that gl/display.cc expects ---------------------------------

void OpenMainWindow(char* /*title*/)
{
    // NativeActivity owns the window — it's been created (or will be) via
    // WFAndroidEglInit. Nothing to do here.
}

bool InitWindow(int /*xPos*/, int /*yPos*/, int /*xSize*/, int /*ySize*/)
{
    return gEglDisplay != EGL_NO_DISPLAY;
}

// Polled once per frame by Display::PageFlip. native_app_entry.cc sets the
// pumping hook below; if unset, this is a no-op.
extern "C" void WFAndroidPumpEvents();

void XEventLoop()
{
    WFAndroidPumpEvents();
}

void SetX11AutoRepeat(int /*state*/) {}

void AndroidSwapBuffers()
{
    if (gEglDisplay != EGL_NO_DISPLAY && gEglSurface != EGL_NO_SURFACE)
        eglSwapBuffers(gEglDisplay, gEglSurface);
}

#endif  // __ANDROID__
