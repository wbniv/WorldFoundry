# Viewport doesn't resize on window maximize

## Context

When the user maximizes the wf_game window, the rendered content stays fixed at the initial size (640×480) in the top-left corner; the rest of the window is black. Two independent bugs cause this.

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

## Files

- `wfsource/source/gfx/gl/mesa.cc` lines 278–303
- `wfsource/source/gfx/gl/display.cc` lines 944 (signature), 976 (blit), 1162 (call site)

## Verification

1. `task build`
2. `task run-moon` (no recording) — maximize window, confirm rendering fills it
3. `WF_RECORD=1 task run-moon` — maximize window, confirm on-screen view fills window; recorded mp4 stays at original resolution
