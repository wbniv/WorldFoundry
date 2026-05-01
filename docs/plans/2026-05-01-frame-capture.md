# Frame-capture → MPEG4 video

**Status:** Complete
**Branch:** 2026-new-level

## What

Wires the dormant `-record_tga` flag (renamed to `-record_video`) to actually capture gameplay footage. Each rendered frame is piped as raw video into an ffmpeg subprocess, which encodes directly to `output.mp4` in the CWD.

## Usage

```bash
cd wfsource/source/game
./worldfoundry -record_video        # produces output.mp4 on exit
ffprobe output.mp4                  # h264, yuv420p, 640x480 @ 30fps
```

Requires ffmpeg installed on the dev machine.

## Build and run

```bash
cd engine && bash build_game.sh
cd wfsource/source/game
/home/will/WorldFoundry.2026-new-level/engine/wf_game -record_video -L<level.iff>
# output.mp4 written to CWD on exit (or crash)
```

## Design decisions

**`-vf vflip`:** `glReadPixels` returns rows bottom-up (OpenGL origin is bottom-left); ffmpeg's `vflip` filter corrects this during encode with no extra CPU copy.

**Pipe to ffmpeg (`popen`) instead of TGA files:** eliminates intermediate disk files, TGA headers, `frames/` directory, and an assembly script. `GL_BGR` from `glReadPixels` feeds directly as ffmpeg's `bgr24` pixel format — no byte swap. One MP4 on exit.

**Renamed `-record_tga` → `-record_video` / `bRecordTGA` → `bRecordVideo`:** the old name encoded the implementation. The new name captures the intent.

**Capture after `glFlush()`, before `glXSwapBuffers()`:** `glFlush()` ensures all queued commands are complete and the back buffer holds the finished frame. `glReadPixels` reads `GL_BACK` by default. After swap the back buffer content is undefined.

**`#if DESIGNER_CHEATS && defined(__LINUX__)`:** `GL_BGR` and `popen` are both desktop-Linux-only. Release builds set `-DDESIGNER_CHEATS=0` (not undefined) so the guard checks the value, not just existence.

**Not portable and doesn't need to be:** this is a dev tool.

## Files changed

- `wfsource/source/gfx/gl/display.cc` — `CaptureFrame()` + `CaptureFrameOpen()` helpers, call site in `PageFlip()`
- `wfsource/source/game/main.cc` — rename variable + switch

## Crash resilience

Two layers:

**Signal handler (`SIGABRT`/`SIGSEGV`):** registered when the pipe opens. Calls `pclose(gCapturePipe)` to give ffmpeg a proper EOF before re-raising the signal for the default handler (core dump etc.).

**Fragmented MP4 (`-movflags frag_keyframe+empty_moov`):** standard MP4 writes its index atom at the very end — a crash before that produces an unplayable file. Fragmented MP4 commits each keyframe interval as a self-contained chunk; even a truncated file is playable up to the last complete fragment.

## Known limitations

- ffmpeg must be on `$PATH`
- Output is always `output.mp4` in CWD (overwritten each run)
- `glReadPixels` stalls the GPU pipeline — game runs slower during capture, but output video plays at the specified 30fps regardless
