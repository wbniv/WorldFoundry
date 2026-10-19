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
// Phase 2C-B: the engine thread owns the frame, like hal/macos/display_macos.cc.
// RenderBegin acquires the layer's next drawable and hands the backend an
// encoder (wf_metal::BeginFrameToLayer); RenderEnd flushes the batch and
// presents (wf_metal::EndFrameToLayer); PageFlip waits for the main-thread
// CADisplayLink tick (hal/ios/metal_view.mm) instead of sleeping.
//=============================================================================

#include <hal/hal.h>
#include <memory/memory.hp>
#include <gfx/renderer_backend.hp>
#include <gfx/metal/metal_offscreen.h>

#include <sys/time.h>
#include <unistd.h>
#include <cstdio>
#include <climits>

extern int _halWindowWidth;
extern int _halWindowHeight;

// hal/ios/metal_view.mm
extern "C" void* WFIosMetalLayer(void);
extern "C" bool  WFIosWaitForVSync(int timeout_ms);

// Surface size the projection was last built for; re-derived when the view
// lays out after the Display was constructed (rotation, or a layout that
// lands after the engine thread got here).
static int s_projW = 0;
static int s_projH = 0;

static void
IosUpdateProjection(int fallbackW, int fallbackH)
{
    const int w = (_halWindowWidth  > 0) ? _halWindowWidth  : fallbackW;
    const int h = (_halWindowHeight > 0) ? _halWindowHeight : fallbackH;
    if (w == s_projW && h == s_projH) return;
    s_projW = w;
    s_projH = h;
    RendererBackendGet().SetProjection(60.0f, float(w) / float(h ? h : 1),
                                       1.0f, 1000.0f);
}

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

// Process-wide single active Display, mirroring gfx/gl/display.cc. Set in the
// ctor, cleared in the dtor. Backs Display::GetActive() (level.cc's bitmap
// label presenter needs it since 1d90c3be).
static Display* gActiveDisplay = nullptr;

Display* Display::GetActive() { return gActiveDisplay; }

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
    RendererBackendGet().ResetModelView();
    s_projW = s_projH = 0;
    IosUpdateProjection(xSize, ySize);

    gActiveDisplay = this;
    ResetTime();
}

//==============================================================================

Display::~Display()
{
    Validate();
    if (gActiveDisplay == this) gActiveDisplay = nullptr;
}

void Display::GetSurfaceSize(int& w, int& h) const
{
    w = (_halWindowWidth > 0) ? _halWindowWidth : _xSize;
    h = (_halWindowHeight > 0) ? _halWindowHeight : _ySize;
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
    IosUpdateProjection(_xSize, _ySize);
    // No drawable (pool exhausted, or no layer yet): the backend drops this
    // frame's triangles because no encoder is set, and RenderEnd is a no-op.
    wf_metal::BeginFrameToLayer(WFIosMetalLayer(), _halWindowWidth, _halWindowHeight);
    RendererBackendGet().SetLightingEnabled(true);
    RendererBackendGet().ResetModelView();
}

//==============================================================================

void
Display::RenderEnd()
{
    // Flush the batch into the live encoder FIRST, then present — EndFrame()
    // issues the draw call, so presenting before it would show an empty frame.
    RendererBackendGet().EndFrame();
    wf_metal::EndFrameToLayer();
}

//==============================================================================

// Time since the last call, advancing `last`; shared by PageFlip and MeasureDelta.
static Scalar
MeasureAndAdvance(struct timeval& last)
{
    struct timeval tvNow;
    gettimeofday(&tvNow, nullptr);

    struct timeval delta;
    delta.tv_sec  = tvNow.tv_sec  - last.tv_sec;
    delta.tv_usec = tvNow.tv_usec - last.tv_usec;
    if (delta.tv_usec < 0) {
        delta.tv_usec += 1000000;
        --delta.tv_sec;
    }

    last = tvNow;
    return ConvertTimeToScalar(delta);
}

Scalar
Display::PageFlip()
{
    // Pace to the display: wait for the CADisplayLink tick. The timeout keeps
    // the loop alive when the link is paused (app backgrounded) or not yet
    // created; it then degrades to the old ~16 ms rate limit.
    if (!WFIosWaitForVSync(100))
        usleep(16000);
    return MeasureAndAdvance(_clockLastTime);
}

// Same delta PageFlip returns, without the sleep or a swap: WFGame::StepFrame
// (the stepped/`-rate` path) calls it on every platform, so iOS must define it.
Scalar
Display::MeasureDelta()
{
    return MeasureAndAdvance(_clockLastTime);
}

//==============================================================================

// SetBackgroundColor + Validate are already inlined in gfx/display.hpi; do
// not redefine them here (the GL display.cc doesn't either).

//==============================================================================
