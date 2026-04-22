//=============================================================================
// hal/ios/display_ios.cc: iOS-specific Display implementation
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// Pulled in via gfx/display.cc when WF_TARGET_IOS is defined. The GL/Android
// Display class owns the windowing (mesa.cc / android_window.cc) AND the
// per-frame clear + buffer swap. On iOS neither of those is Display's job —
// WFMetalView (hal/ios/metal_view.mm) already owns the CAMetalLayer, drawable
// acquisition, clear, and present. So this impl is a thin timer + projection-
// setup wrapper over RendererBackendGet().
//
// Phase 2C-A scope: boot the engine main loop on a background thread and
// watch where it crashes. PageFlip currently just computes deltaTime + sleeps
// ~16ms; proper main-thread CADisplayLink sync lands when Phase 2C-B wires
// the Metal encoder handoff.
//=============================================================================

#include <hal/hal.h>
#include <memory/memory.hp>
#include <gfx/renderer_backend.hp>

#include <sys/time.h>
#include <unistd.h>
#include <cstdio>
#include <climits>

extern int _halWindowWidth;
extern int _halWindowHeight;

//==============================================================================

static inline Scalar
ConvertTimeToScalar(const struct timeval& tv)
{
    int16 whole = tv.tv_sec;
    uint16 frac;
    frac = uint16(float(tv.tv_usec) / 15.2587890625f);
    assert(tv.tv_sec < USHRT_MAX);
    whole = tv.tv_sec;
    return Scalar(whole, frac);
}

//==============================================================================

Display::Display(int /*orderTableSize*/,
                 int xPos, int yPos, int xSize, int ySize,
                 Memory& memory, bool /*interlace*/)
    : _drawPage(0)
    , _xPos(xPos)
    , _yPos(yPos)
    , _xSize(xSize)
    , _ySize(ySize)
    , _backgroundColorRed(0.0f)
    , _backgroundColorGreen(0.0f)
    , _backgroundColorBlue(0.0f)
    , _memory(memory)
{
    _memory.Validate();

    // Window size comes from hal/ios/platform.mm's WFIosSetSurfaceSize,
    // fed from the UIView's bounds * contentScaleFactor on layout.
    const int w = (_halWindowWidth  > 0) ? _halWindowWidth  : xSize;
    const int h = (_halWindowHeight > 0) ? _halWindowHeight : ySize;
    const float aspect = float(w) / float(h ? h : 1);

    RendererBackendGet().ResetModelView();
    RendererBackendGet().SetProjection(60.0f, aspect, 1.0f, 1000.0f);

    ResetTime();
}

//==============================================================================

Display::~Display()
{
    Validate();
}

//==============================================================================

void
Display::ResetTime()
{
    struct timeval tv;
    gettimeofday(&tv, nullptr);
    _clockLastTime = tv;
}

//==============================================================================

void
Display::RenderBegin()
{
    Validate();
    // Clear + drawable acquisition are WFMetalView's job; Display here just
    // sets per-frame renderer state.
    RendererBackendGet().SetLightingEnabled(true);
    RendererBackendGet().ResetModelView();
}

//==============================================================================

void
Display::RenderEnd()
{
    // Flush batched triangles into the current frame's Metal encoder (set up
    // by WFMetalView's CADisplayLink callback — Phase 2C-B wiring).
    RendererBackendGet().EndFrame();
}

//==============================================================================

Scalar
Display::PageFlip()
{
    // Phase 2C-A: no vsync sync yet — just rate-limit to ~60 fps and return
    // the measured deltaTime. Phase 2C-B swaps this for a semaphore wait
    // signaled by the main-thread CADisplayLink callback.
    usleep(16000);

    struct timeval tvNow;
    gettimeofday(&tvNow, nullptr);
    const Scalar now  = ConvertTimeToScalar(tvNow);
    const Scalar prev = ConvertTimeToScalar(_clockLastTime);
    _clockLastTime = tvNow;
    return now - prev;
}

//==============================================================================

void
Display::SetBackgroundColor(const Color& color)
{
    _backgroundColor      = color;
    _backgroundColorRed   = float(color.Red())   / 255.0f;
    _backgroundColorGreen = float(color.Green()) / 255.0f;
    _backgroundColorBlue  = float(color.Blue())  / 255.0f;
}

//==============================================================================

void
Display::Validate() const
{
    assert(_xSize > 0);
    assert(_ySize > 0);
}

//==============================================================================
