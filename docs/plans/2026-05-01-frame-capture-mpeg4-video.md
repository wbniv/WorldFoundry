# Plan: Frame-capture → MPEG4 video

**Context:** The engine has a dormant `-record_tga` flag (`bRecordTGA` in `main.cc`) with no capture code behind it. This plan wires it up by piping raw frames directly into ffmpeg via `popen()` — no intermediate files, no cleanup step, one MP4 on exit.

**Status:** OPEN — design complete; the `-record_video` flag rename + ffmpeg-pipe capture not implemented (`-record_tga` still present).

---

## Design decisions

**Pipe to ffmpeg instead of TGA files:** `popen("ffmpeg ... -i pipe:0 ...", "w")` + `fwrite` per frame eliminates intermediate disk files entirely. No TGA headers, no `frames/` directory, no assembly script. GL_BGR from `glReadPixels` feeds directly as `bgr24` raw video.

**Rename to `-record_video` / `bRecordVideo`:** The old name encoded the implementation (TGA files). The new name captures the intent (record video). All four references in `main.cc` and one `extern` in `display.cc` get updated.

**`popen` is Linux-only and we don't care:** This is a dev tool, already guarded by `#if DESIGNER_CHEATS && defined(__LINUX__)`. No portability concern.

**Capture before `glXSwapBuffers`, after `glFlush()`:** `glFlush()` ensures all queued commands are complete. `glReadPixels` reads `GL_BACK` by default in a double-buffered context. Must be before `glXSwapBuffers`.

**`#if DESIGNER_CHEATS && defined(__LINUX__)`:** Release builds set `-DDESIGNER_CHEATS=0` (not undefined), so the guard must check the *value* with `#if DESIGNER_CHEATS`, not `#if defined(DESIGNER_CHEATS)`.

---

## Files to modify

- `wfsource/source/game/main.cc` — rename variable + switch (4 spots)
- `wfsource/source/gfx/gl/display.cc` — popen-based capture implementation

## Files to create

- `docs/plans/2026-05-01-frame-capture.md` — plan doc

---

## Changes to `main.cc`

Four spots:
1. Declaration: `bool bRecordTGA = false;` → `bool bRecordVideo = false;`
2. Usage string: `-record_tga` → `-record_video`, update description
3. `strcmp` check: `"record_tga"` → `"record_video"`
4. Assignment: `bRecordTGA = true;` → `bRecordVideo = true;`

---

## Changes to `display.cc`

### New includes (after existing `#include <unistd.h>` block)

```cpp
#if DESIGNER_CHEATS && defined(__LINUX__)
#  include <cstdio>
#  include <cstdlib>
#endif
```

### Helper + pipe handle before `Display::PageFlip()`

```cpp
#if DESIGNER_CHEATS && defined(__LINUX__)

extern bool bRecordVideo;

static FILE* gCapturePipe = nullptr;

static void
CaptureFrameOpen(int xSize, int ySize)
{
    char cmd[256];
    snprintf(cmd, sizeof(cmd),
        "ffmpeg -f rawvideo -pixel_format bgr24 "
        "-video_size %dx%d -framerate 30 "
        "-i pipe:0 -c:v libx264 -pix_fmt yuv420p output.mp4",
        xSize, ySize);
    gCapturePipe = popen(cmd, "w");
}

static void
CaptureFrame(int xSize, int ySize)
{
    if (!gCapturePipe)
        CaptureFrameOpen(xSize, ySize);
    if (!gCapturePipe)
        return;

    const int pixelBytes = xSize * ySize * 3;
    uint8_t* pixels = (uint8_t*)malloc(pixelBytes);
    if (!pixels)
        return;

    glReadPixels(0, 0, xSize, ySize, GL_BGR, GL_UNSIGNED_BYTE, pixels);
    fwrite(pixels, 1, pixelBytes, gCapturePipe);
    free(pixels);
}

#endif // DESIGNER_CHEATS && __LINUX__
```

### Call site in `PageFlip()` (after `glFlush()`, before `glXSwapBuffers`)

```cpp
#if DESIGNER_CHEATS && defined(__LINUX__)
    if (bRecordVideo)
        CaptureFrame(_xSize, _ySize);
#endif
```

---

## Verification

```bash
# Build
cd engine && bash build_game.sh

# Run — output.mp4 appears in wfsource/source/game/ on exit
cd wfsource/source/game
./worldfoundry -record_video

# Check output
ffprobe output.mp4    # expect: h264, yuv420p, 640x480
vlc output.mp4
```

**Note:** ffmpeg must be installed. `pclose(gCapturePipe)` happens implicitly when the process exits — ffmpeg sees EOF on its stdin and finalizes the MP4. If the game crashes without a clean exit, the MP4 may be truncated/corrupt.
