# Android GPU frame timing

Add `--gpu-profile` to the game's runtime arguments to log five-second `gpu-window` and `gpu-metric` records. The flag is off by default. It uses `GL_EXT_disjoint_timer_query` when the GLES driver supports it, with a bounded 256-query ring. `elapsed` measures GPU commands from `Display::RenderBegin` through the Android HUD, before `eglSwapBuffers`; it excludes game simulation, swap/compositor work and any GPU work outside that span. `frame-wall`, `frame-cpu` and `swap-wall` report separate CPU-side durations in milliseconds.

Check `gpu-capability: supported=1`, `issued`, `invalid`, `ring-full`, `missing` and `elapsed samples` before interpreting a window. A disjoint event invalidates outstanding queries. The timer does not call `glFinish`, so it does not deliberately serialize the GPU and CPU. On unsupported drivers, the other timing metrics still log and GPU `elapsed samples=0`.

This flag is diagnostic only; public builds should omit it from runtime arguments. A Cast1 test using the Finding Your Way g1 tour on 2026-10-14 measured 36.95 FPS with the timer on and 36.90 FPS with the same instrumented library and the timer off. The game repository records the analysis and raw-evidence references under `docs/diagnostics/parmenides/v093-gpu-atlas-2026-10-14/`.
