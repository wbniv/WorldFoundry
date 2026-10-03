# Phase 1 validation — 2026-10-03

Worktree: `/tmp/WorldFoundry-framerate`.
Implementation commit: [`402d0f2f`](https://github.com/wbniv/WorldFoundry/commit/402d0f2f),
created on `feature/engine-framerate-mailbox` from `10310efe`, then fast-forward
merged and pushed to `2026-new-level` on 2026-10-03.
The original checkout's unrelated edits were left in place.

## Linux

The initial run used GCC 15.2, Debug, Jolt, zForth, Lua, and the debug bridge,
with sanitizers and the other optional interpreters disabled. The follow-up
run below enables all default scripting backends and adds the unswapped host check.

```sh
cmake -S . -B build-framerate -G Ninja -DCMAKE_BUILD_TYPE=Debug -DWF_ASAN=OFF \
  -DWF_ENABLE_FENNEL=OFF -DWF_JS_ENGINE=none -DWF_WASM_ENGINE=none -DWF_ENABLE_WREN=OFF
cmake --build build-framerate --target wf_game wf_host_gl_e2e_test frame_rate_test -j 4
ctest --test-dir build-framerate \
  -R '^(frame_rate_sampler|frame_rate_mailbox|frame_rate_mailbox_fixed_sim|wf_game_smoke_cycle[12]|wf_host_gl_e2e_cycle[12])$' \
  --output-on-failure
python3 -m pytest tests/test_mailbox_hot_path.py -q
```

The display/socket tests require X11 and local network access. The sampler
test requires neither. The integration fixture launches its own game process,
uses a private debug port, injects a temporary zForth script, and intentionally
ends that process with a rejected write to the read-only mailbox.

Observed integration output:

```text
PASS: named zForth reads match the C++ mailbox read; repeated reads agree
PASS: active 550 ms hitch surfaced as 1.753 FPS
PASS: next completed frames recover without smoothing
PASS: FPS remains available during simulation pause
PASS: writes to FRAMERATE follow the existing system mailbox rejection policy
```

The initial CTest run passes all 7 selected tests (sampler, two mailbox configurations,
and four standalone/host-context smoke runs). The same mailbox checks pass with `-rate10`. Controlled timestamps also verify exact
500 ms → 2 FPS and 2 s → 0.5 FPS intervals. The mailbox hot-path checks pass
(2 tests). Existing Q*bert smoke runs emit Forth compile-error messages for
some authored enemy scripts; these were not changed by this feature, and the
small injected diagnostic script compiles and runs successfully.

## Android

Both `arm64-v8a` and `armeabi-v7a` full engine targets build successfully with
NDK r26c (26.2.11394342), Debug, Android API 26. Run once per ABI:

```sh
cmake -S . -B build-framerate-android -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE=/home/will/android-sdk-local/ndk/26.2.11394342/build/cmake/android.toolchain.cmake \
  -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-26 -DCMAKE_BUILD_TYPE=Debug -DWF_ASAN=OFF
cmake --build build-framerate-android --target wf_game -j 2
```

Use `build-framerate-android32` and `-DANDROID_ABI=armeabi-v7a` for the 32-bit build.

The connected device supports `armeabi-v7a`, so the standalone sampler test was
built and run for that architecture. The test links the real Android lifecycle
HAL, with window/event dependencies stubbed in the test source. It also samples
the live monotonic clock, rather than only checking injected timestamps.

```sh
/home/will/android-sdk-local/ndk/26.2.11394342/toolchains/llvm/prebuilt/linux-x86_64/bin/armv7a-linux-androideabi26-clang++ \
  -std=c++17 -Wall -Wextra -Werror -static-libstdc++ -I wfsource/source \
  tests/frame_rate_test.cc wfsource/source/hal/android/lifecycle.cc \
  -o /tmp/frame-rate-test-android32
/home/will/android-sdk-local/platform-tools/adb push /tmp/frame-rate-test-android32 /data/local/tmp/wf-frame-rate-test
/home/will/android-sdk-local/platform-tools/adb shell /data/local/tmp/wf-frame-rate-test
```

```text
PASS: raw cadence, stalls, host gaps, invalid samples, lifecycle resets
```

The initial standalone test did not exercise NativeActivity. The follow-up
game check did: an isolated `org.worldfoundry.wf_game.fpscheck` APK packaged
the rebuilt 32-bit engine, existing snowgoons assets, and `--frame-rate-checks`.
Will was notified before installation/testing. The same process (PID 32518)
survived Home/background and reopening. Named zForth reads matched raw FPS,
the lifecycle generation advanced from 1 to 3, the first resumed read was zero,
and positive samples recovered. `check_frame_rate_log.py --resume` passed
over 3207 samples. The temporary app was stopped and uninstalled; existing
game applications were untouched. No additional Chromecast testing is running.

## Follow-up Linux and scripting checks

```sh
cmake -S . -B build-framerate -DWF_ENABLE_FENNEL=ON -DWF_JS_ENGINE=quickjs \
  -DWF_WASM_ENGINE=wamr -DWF_ENABLE_WREN=ON
cmake --build build-framerate --target wf_game wf_host_gl_e2e_test frame_rate_test -j4
ctest --test-dir build-framerate \
  -R 'frame_rate_|wf_game_smoke_cycle[12]|wf_host_gl_e2e_cycle[12]' --output-on-failure
```

- [x] All 8 selected tests pass. The added `frame_rate_host_no_swap` uses
  `StepFrame(false)`, two level load/unload cycles, and a 20 ms host gap.
- [x] Runtime probes pass for Lua, Fennel, Wren, zForth, QuickJS, WAMR, and PILOT.
- [x] The two mailbox hot-path pytest checks still pass.

`--frame-rate-checks` (or `WF_FRAME_RATE_CHECKS=1`) reads the named mailbox
through each compiled interpreter, compares it with the engine's cached value,
and aborts on disagreement. It temporarily uses global user mailbox 1899 and
restores its prior value. Logging includes the first positive sample after
each zero baseline, plus periodic samples. This mode is for validation only.

The checks exposed WAMR 2.2 import-name vectors containing a trailing NUL and
uninitialized element counts in borrowed C-API vectors. Both were corrected;
the named imported global `INDEXOF_FRAMERATE` now passes the real WAMR runtime probe.

Alternate Forth bridges use a standalone sampler-backed mailbox fixture and
the actual interpreter, isolating them from unrelated authored level scripts:

```sh
cmake -S . -B build-framerate-backends -G Ninja -DCMAKE_BUILD_TYPE=Debug \
  -DWF_ASAN=OFF -DWF_FORTH_ENGINE=ficl -DWF_NEURAL_FORTH=OFF \
  -DWF_ENABLE_FENNEL=OFF -DWF_JS_ENGINE=none -DWF_WASM_ENGINE=none -DWF_ENABLE_WREN=OFF
cmake --build build-framerate-backends --target frame_rate_forth_probe -j4
ctest --test-dir build-framerate-backends -R frame_rate_optional_forth --output-on-failure
```

Repeat configuration with `WF_FORTH_ENGINE=atlast`, `embed`, `libforth`, and `pforth`.

| Optional backend | Observed result |
| --- | --- |
| Ficl | Passes after building its generated softcore and disabling upstream Unity tests. Existing integer bridge maps raw 62.5 → 62, 2 → 2, and 0.5 → 0. This is a precision limitation. |
| Atlast | Builds; interpreter probe crashes with SIGSEGV. |
| embed | Builds; probe leaves the scratch sentinel unchanged instead of writing the read value. |
| libforth | Builds; bridge execution fails its bounds check and leaves the sentinel unchanged. |
| pForth | Builds; runtime aborts after dictionary initialization. |
| JerryScript | Build blocked by GCC 15 `-Werror=pedantic`. A temporary diagnostic override exposed missing Date/RegExp prototype identifiers under the existing minimal profile. The override was removed. |

These failures are recorded follow-up defects; none is counted as a passing
raw fractional FPS interpreter. The default QuickJS build was restored and
all 8 native checks passed again.

## Apple builds and runtimes

- [x] [macOS workflow](https://codemagic.io/app/6aafa6886ab3f21cf431a6cb/build/6ac0b1e614c34c56a5bfae38)
  passes on arm64 Apple hardware, including the full existing workflow and
  the new mailbox probe with 60 unswapped steps over two load/unload cycles.
  Raw samples around 30–40 FPS remain independent of the fixed `-rate20` simulation.
- [x] [iOS workflow](https://codemagic.io/app/6aafa6886ab3f21cf431a6cb/build/6ac0b93f012d4459df20e02a)
  builds and passes on iPhone and iPad simulators. Real UIKit background/resume
  is driven by launching Settings then returning to the same game process.
  Each device log passes `check_frame_rate_log.py --resume` (17 and 16 samples).

These runs use Xcode 26.6. Initial linking exposed missing Apple implementations
of `Display::GetSurfaceSize` used by the level menu; those were added using
the existing platform surface dimensions. Physical iOS hardware was not tested.

## Browser and hosted editor

Emscripten 6.0.0 Release builds pass for `wf_game` and `wf_edit_web`. The editor
uses the existing Yrs Emscripten patch and a native `levtree` build to preload
the real level document; this run used Rust 1.97.1. Missing browser definitions
for the shared media interface's `TakePliRequests`/`SendPli` were added as
empty hooks, matching the existing browser-owned media pipeline.

```sh
DISPLAY=:0 python3 tests/frame_rate_browser.py build-framerate-web \
  --output /tmp/framerate-browser-final
DISPLAY=:0 python3 tests/frame_rate_browser.py build-framerate-web-editor --editor \
  --output /tmp/framerate-browser-editor-final
```

The manual browser fixture requires Chrome and Python Playwright. It launches
a separate profile, attaches with emulation defaults disabled, and uses real
window minimization/restoration. It verifies frames stop while hidden,
the resumed mailbox first reports zero, and a subsequent positive script read
matches the engine. It closes its browser and local HTTP server afterward.

- [x] Standalone browser runtime passes.
- [x] Hosted editor runtime passes, exercising its real `StepFrame(false)` loop
  and adopted host WebGL context.

Concise retained results are in [runtime-checks.txt](runtime-checks.txt).
