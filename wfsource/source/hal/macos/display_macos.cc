//=============================================================================
// hal/macos/display_macos.cc: macOS desktop Display implementation (headless)
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// Pulled in via gfx/display.cc when WF_TARGET_MACOS is defined. Clone of
// hal/ios/display_ios.cc. The GL/Android Display class owns the windowing
// (mesa.cc / android_window.cc) AND the per-frame clear + buffer swap. On the
// renderer-agnostic macOS bring-up there is NO window and NO renderer — the
// RendererBackend is a true no-op (engine/stubs/renderer_stub.cc). So this
// impl is a thin timer + projection-setup wrapper that lets WFGame's ctor and
// the frame loop run with no drawing.
//
// When the real Metal renderer + window land, this becomes the macOS analogue
// of metal_view.mm (AppKit NSWindow + CAMetalLayer + CVDisplayLink).
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
    // No clear / drawable acquisition — no window. Just per-frame renderer
    // state (all no-ops against the headless backend).
    RendererBackendGet().SetLightingEnabled(true);
    RendererBackendGet().ResetModelView();
}

//==============================================================================

void
Display::RenderEnd()
{
    RendererBackendGet().EndFrame();
}

//==============================================================================

static Scalar
MeasureAndAdvance(struct timeval& clockLastTime)
{
    struct timeval tvNow;
    gettimeofday(&tvNow, nullptr);
    const Scalar now  = ConvertTimeToScalar(tvNow);
    const Scalar prev = ConvertTimeToScalar(clockLastTime);
    clockLastTime = tvNow;
    return now - prev;
}

Scalar
Display::PageFlip()
{
    // No vsync / swap — rate-limit to ~60 fps and return the measured delta.
    usleep(16000);
    return MeasureAndAdvance(_clockLastTime);
}

//==============================================================================

Scalar
Display::MeasureDelta()
{
    return MeasureAndAdvance(_clockLastTime);
}

//==============================================================================

// SetBackgroundColor + Validate are inlined in gfx/display.hpi; do not redefine
// them here (neither the GL nor the iOS display.cc does either).

//==============================================================================
