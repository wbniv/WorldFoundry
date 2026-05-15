# Plan — capture frames via FBO so `-record_video` survives window occlusion

**Date:** 2026-05-11
**Status:** In progress.

## Problem

`qbert-2-rounds.mp4` (the recording from commit `9c6695f`) renders normally for the first ~11 s, then cuts to solid black for the remainder of the file even though the engine is still rendering Q✱bert correctly and the walker is still issuing hops.

Root cause: `CaptureFrame()` in [`wfsource/source/gfx/gl/display.cc:396-422`](../../wfsource/source/gfx/gl/display.cc) calls `glReadPixels(0, 0, xSize, ySize, GL_BGR, …)` against the **default framebuffer**. On Linux/X11 without a compositor (or with a compositor that excludes the wf_game window), the back buffer is part of the X drawable, so occluded regions read back whatever the obscuring window painted there — or nothing.

Re-running today's exact walker after deliberately not occluding the window produced a clean 193 s mp4 with no blackouts, confirming the diagnosis.

## Fix

When `-record_video` is set, render to an off-screen FBO that lives in GPU memory and is immune to X11 clipping/occlusion. At each `PageFlip()`:

1. Blit the FBO → back buffer so the user still sees the game on screen.
2. `glReadPixels` from the FBO (still bound as `GL_READ_FRAMEBUFFER`) → ffmpeg pipe.
3. Swap buffers as today.

When `-record_video` is **off**, the code path is unchanged: render straight to the back buffer, no FBO bind, no blit.

## Critical files

| File | Change |
|---|---|
| `wfsource/source/gfx/gl/display.cc` | Add FBO + color/depth renderbuffer creation, lazy-initialised on first `CaptureFrame`. Bind in `Display::RenderBegin()` when `bRecordVideo`. Blit-and-read in `CaptureFrame()`. Cleanup hooked into the existing `CaptureCleanup` signal handler. |

No other source files touched. No engine API change visible to game code or scripts.

## Sketch

```cpp
// new globals alongside gCapturePipe
static GLuint gCaptureFBO  = 0;
static GLuint gCaptureColor = 0;
static GLuint gCaptureDepth = 0;

static void
EnsureCaptureFBO(int w, int h)
{
    if (gCaptureFBO) return;
    glGenFramebuffers(1, &gCaptureFBO);
    glGenRenderbuffers(1, &gCaptureColor);
    glGenRenderbuffers(1, &gCaptureDepth);

    glBindRenderbuffer(GL_RENDERBUFFER, gCaptureColor);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_RGB8, w, h);

    glBindRenderbuffer(GL_RENDERBUFFER, gCaptureDepth);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, w, h);

    glBindFramebuffer(GL_FRAMEBUFFER, gCaptureFBO);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                              GL_RENDERBUFFER, gCaptureColor);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT,
                              GL_RENDERBUFFER, gCaptureDepth);
    assert(glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE);
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
}
```

`Display::RenderBegin()` (or equivalent — the call at the top of each render pass) gains:

```cpp
if (bRecordVideo) {
    EnsureCaptureFBO(_xSize, _ySize);
    glBindFramebuffer(GL_FRAMEBUFFER, gCaptureFBO);
}
```

`CaptureFrame()` body becomes:

```cpp
if (bRecordVideo) {
    glBindFramebuffer(GL_READ_FRAMEBUFFER, gCaptureFBO);
    glBindFramebuffer(GL_DRAW_FRAMEBUFFER, 0);
    glBlitFramebuffer(0, 0, xSize, ySize, 0, 0, xSize, ySize,
                      GL_COLOR_BUFFER_BIT, GL_NEAREST);
    // FBO still bound as READ; glReadPixels reads from it
    glReadPixels(0, 0, xSize, ySize, GL_BGR, GL_UNSIGNED_BYTE, pixels);
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
}
fwrite(pixels, 1, pixelBytes, gCapturePipe);
```

`CaptureCleanup` deletes the FBO/renderbuffers when the pipe closes.

## Cost

- One full-screen blit per frame at 512×384 — sub-millisecond on any GPU.
- ~1 MB GPU memory for the two renderbuffers.
- Zero overhead when `-record_video` is not set (entire path is `if (bRecordVideo)` gated).

## Verification

1. Rebuild: `engine/build_game.sh`.
2. Record a 2-round walker run with the wf_game window visible — output.mp4 should be clean (matches today's baseline).
3. Re-record with another window dragged on top of wf_game mid-game — output.mp4 should still be clean (the failure case before this fix).
4. Run without `-record_video` and confirm framerate is unchanged from the prior build (rough eyeball + the engine's `delta` log lines).

## What I am NOT doing

- No change to the engine's general rendering pipeline.
- No change to the walker / level script / mailboxes.
- No FBO when recording is off.
