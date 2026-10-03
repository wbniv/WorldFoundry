# Phase 1 validation — 2026-10-03

Worktree: `/tmp/WorldFoundry-framerate`.
Implementation commit: [`402d0f2f`](https://github.com/wbniv/WorldFoundry/commit/402d0f2f),
created on `feature/engine-framerate-mailbox` from `10310efe`, then fast-forward
merged and pushed to `2026-new-level` on 2026-10-03.
The original checkout's unrelated edits were left in place.

## Linux

Configuration uses GCC 15.2, Debug, Jolt, zForth, Lua, and the debug bridge.
Sanitizers are disabled for this build. Optional Fennel, JS, WAMR, and Wren
backends are disabled; no runtime validation is claimed for those backends.

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

The final CTest run passes all 7 selected tests (sampler, two mailbox configurations,
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

This device test does not validate NativeActivity callbacks or an in-game FPS
overlay. Android game lifecycle integration, Apple builds/runs, and WASM
visibility handling remain pending as recorded in the parent plan.
