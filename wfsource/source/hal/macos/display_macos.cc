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
#include <gfx/metal/metal_offscreen.h>

#include <sys/time.h>
#include <unistd.h>
#include <cstdio>
#include <climits>
#include <cstdlib>
#include <cstring>
#include <vector>

#include "../../../../engine/vendor/stb/stb_image_write.h"

extern int _halWindowWidth;
extern int _halWindowHeight;

// --capture-frame=N=<path.png>, parsed in game/main.cc. 0 = no capture.
extern int         gCaptureFrame;
extern const char* gCapturePath;

//==============================================================================
// Frame accounting.
//
// Phase 1 found 29 backend frames for 30 engine steps and could not say which
// step was skipped, because the only counter lived on EndFrame. The render
// block in WFGame::StepFrame is gated on camera()->ValidView() (game.cc:584),
// so a step that has no valid view renders nothing and never reaches EndFrame.
// MeasureAndAdvance below runs exactly once per StepFrame (via PageFlip or
// MeasureDelta), so counting here gives the other half of the pair and makes
// "engine stepped N, backend rendered M" directly observable.
//==============================================================================
static unsigned long s_stepFrames = 0;

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
    // No window and no CAMetalDrawable: the frame is rendered into an
    // engine-owned offscreen MTLTexture instead (gfx/metal/metal_offscreen.h).
    // wf_metal::BeginFrame opens the command buffer + encoder and hands the
    // encoder to the Metal backend, so the DrawTriangle batches that follow
    // have somewhere real to go. If Metal is unavailable the draws still run
    // and the backend drops them — the smoke must not abort on a GPU-less box.
    const int w = (_halWindowWidth  > 0) ? _halWindowWidth  : _xSize;
    const int h = (_halWindowHeight > 0) ? _halWindowHeight : _ySize;
    wf_metal::BeginFrame(w, h);

    RendererBackendGet().SetLightingEnabled(true);
    RendererBackendGet().ResetModelView();
}

//==============================================================================

void
Display::RenderEnd()
{
    // Flush the batch into the live encoder FIRST, then close the frame —
    // EndFrame() is what issues the draw call, so committing before it would
    // present an empty target.
    RendererBackendGet().EndFrame();
    wf_metal::EndFrame();

    if (gCaptureFrame > 0 &&
        (int)wf_metal::RenderedFrameCount() == gCaptureFrame &&
        gCapturePath)
    {
        const int w = (_halWindowWidth  > 0) ? _halWindowWidth  : _xSize;
        const int h = (_halWindowHeight > 0) ? _halWindowHeight : _ySize;
        std::vector<unsigned char> rgba((size_t)w * (size_t)h * 4);
        if (wf_metal::ReadbackRGBA8(rgba.data(), w, h))
        {
            const int ok = stbi_write_png(gCapturePath, w, h, 4,
                                          rgba.data(), w * 4);
            // Report a non-black pixel count too. A PNG that exists but is
            // uniformly the clear colour is the single most likely way this
            // milestone gets called green while rendering nothing.
            unsigned long lit = 0;
            for (size_t i = 0; i < rgba.size(); i += 4)
                if (rgba[i] | rgba[i+1] | rgba[i+2]) ++lit;
            std::printf("macos: capture frame %d -> %s (%dx%d) %s, "
                        "non-black pixels %lu/%lu\n",
                        gCaptureFrame, gCapturePath, w, h,
                        ok ? "written" : "stbi_write_png FAILED",
                        lit, (unsigned long)(rgba.size() / 4));
        }
        else
        {
            std::printf("macos: capture frame %d FAILED — no readable "
                        "offscreen frame at %dx%d\n", gCaptureFrame, w, h);
        }
        std::fflush(stdout);
    }
}

//==============================================================================

static Scalar
MeasureAndAdvance(struct timeval& clockLastTime)
{
    struct timeval tvNow;
    gettimeofday(&tvNow, nullptr);

    // Compute delta as timeval before converting — absolute tv_sec is ~1.7B
    // which overflows Scalar's 16-bit integer part. Only the delta is small.
    struct timeval delta;
    delta.tv_sec  = tvNow.tv_sec  - clockLastTime.tv_sec;
    delta.tv_usec = tvNow.tv_usec - clockLastTime.tv_usec;
    if (delta.tv_usec < 0) {
        delta.tv_usec += 1000000;
        delta.tv_sec--;
    }

    clockLastTime = tvNow;

    // One line per engine step, carrying both counters (see the note at the top
    // of this file). "rendered" lagging "step" is the ValidView gate, not a
    // dropped draw call.
    ++s_stepFrames;
    std::printf("macos: step=%lu rendered=%lu triangles=%lu (total %lu)\n",
                s_stepFrames,
                wf_metal::RenderedFrameCount(),
                wf_metal::TrianglesLastFrame(),
                wf_metal::TrianglesTotal());
    std::fflush(stdout);

    return ConvertTimeToScalar(delta);
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
