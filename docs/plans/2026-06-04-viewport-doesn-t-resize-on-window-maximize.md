# Viewport doesn't resize on window maximize

**Status:** Done — 2026-06-04. Three bugs fixed across `mesa.cc` and `display.cc`; verified working.

## Context

When the user maximized the wf_game window, the rendered content stayed fixed at 640×480 in the top-left corner with the rest of the window black. A second symptom (zoomed-in scene after the first fix) revealed a third bug. Three independent bugs were fixed.

## Bug 1 — Wrong viewport math in ConfigureNotify (`mesa.cc:278–295`)

The handler tries to inscribe a square viewport but the math is wrong:
```cpp
if(eW >= eH) { vY = (eH - eW) >> 1; vW = vH = eW; }  // vY negative when eW>eH
```
For a 1920×1080 window this gives `glViewport(0, -420, 1920, 1920)` — mostly off-screen.

**Fix:** Fill the window directly:
```cpp
glViewport(0, 0, eW, eH);
AssertGLOK();
if (auto* d = Display::GetActive())
    d->SetLiveWindowSize(eW, eH);
```
Remove the dead letter-boxing block entirely.

## Bug 2 — FBO blit ignores live window size (`display.cc:976`)

`CaptureFrame(int xSize, int ySize)` blits the capture FBO to the back buffer at the fixed capture resolution:
```cpp
glBlitFramebuffer(0, 0, xSize, ySize, 0, 0, xSize, ySize, ...);
```
When the window is larger, only the top-left `xSize×ySize` pixels get content; the rest is black.

**Fix:** Pass live window dimensions to `CaptureFrame` from `PageFlip` (where `_liveWidth`/`_liveHeight` are accessible), and use them as the blit destination:

```cpp
// PageFlip (display.cc:1162):
CaptureFrame(_xSize, _ySize, _liveWidth, _liveHeight);

// CaptureFrame signature:
static void CaptureFrame(int xSize, int ySize, int liveW, int liveH)

// Blit (display.cc:976):
glBlitFramebuffer(0, 0, xSize, ySize, 0, 0, liveW, liveH,
                  GL_COLOR_BUFFER_BIT, GL_LINEAR);
```

The captured video stream stays at `xSize×ySize` (unchanged); only the on-screen preview scales up.

## Before / After

**Before (maximize 1920×1080):**
```
┌─────────────────────────────────────────┐
│┌──────────┐                             │
││ game     │  (black)                    │
││ 640×480  │                             │
│└──────────┘                             │
│                                         │
│             (black)                     │
│                                         │
└─────────────────────────────────────────┘
  viewport at (0,−420,1920,1920) — off screen
```

**After (maximize 1920×1080):**
```
┌─────────────────────────────────────────┐
│                                         │
│                                         │
│       game fills full window            │
│           1920×1080                     │
│                                         │
│                                         │
└─────────────────────────────────────────┘
  glViewport(0, 0, 1920, 1080)
```

**Recording — FBO blit before fix:**
```
capture FBO                  back buffer (1920×1080)
┌──────────┐   blit 1:1  ┌─────────────────────────┐
│ rendered │ ──────────► │ rendered │               │
│ 640×480  │             │ 640×480  │    black      │
└──────────┘             │          │               │
                         └─────────────────────────┘
```

**Recording — FBO blit after fix:**
```
capture FBO                  back buffer (1920×1080)
┌──────────┐  blit scaled ┌─────────────────────────┐
│ rendered │ ───────────► │                         │
│ 640×480  │              │  scaled to 1920×1080    │
└──────────┘              │                         │
  (video file unchanged)  └─────────────────────────┘
```

## Bug 3 — Projection matrix never updated on resize (`display.cc` `WFInitGL`)

`WFInitGL()` calls `SetProjection(60°, 640/480, ...)` once at startup and never again. After Bug 1 fixed the viewport, the 3D scene appeared zoomed in — the projection still encoded a 4:3 aspect ratio regardless of window size.

**Fix:** Move viewport + projection setup into `RenderBegin()` so it recomputes every frame from `GetSurfaceSize()`:

```cpp
// In RenderBegin(), after FBO bind:
int suw, suh;
GetSurfaceSize(suw, suh);
glViewport(0, 0, suw, suh);
RendererBackendGet().SetProjection(60.0f, float(suw)/float(suh), 1.0f, 1000.0f);
```

When recording, `GetSurfaceSize` returns `_xSize`/`_ySize` (fixed capture size); otherwise returns live window size. Both paths stay correct.

## Files

- `wfsource/source/gfx/gl/mesa.cc` — ConfigureNotify handler
- `wfsource/source/gfx/gl/display.cc` — `CaptureFrame` signature+blit, `RenderBegin` projection update

## Commits

- `bd11eafb` fix(display): viewport fills window on resize; FBO blit scales to live window size
- `74b1b4a2` fix(display): recompute viewport+projection every frame — fixes zoom on resize

## Verification

Confirmed working by user 2026-06-04.
