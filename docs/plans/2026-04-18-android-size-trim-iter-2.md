# Plan — Android size trim, iteration 2

**Date:** 2026-04-18
**Status:** In progress
**Follow-up to:** [Android port size/RAM report](../investigations/2026-04-18-android-port-size-and-ram.md)

## Context

The port-closure report lists five "further size wins not taken" at the end. Iteration 1 (Release build: `-O3 -flto=thin -ffunction-sections -fdata-sections`, linked with `--gc-sections --icf=safe`, plus `MA_NO_MP3` + `MA_NO_GENERATION`) dropped the APK from 2.62 MB → 2.16 MB and `libwf_game.so` stripped from 4.69 MB → 3.81 MB.

Iteration 2 lands: exceptions off, hidden visibility by default, tighter miniaudio, and deletion of the only remaining Windows-specific code path in the runtime.

## Design decisions locked in

- **SFX format is WAV with IMA ADPCM inside** (WAVE_FORMAT_DVI_ADPCM, codec 0x0011). ~4× smaller than linear PCM at negligible decode cost; matches the console pedigree (every console generation ships with an ADPCM hardware audio DMA path, and IMA ADPCM transcodes trivially to DSP-ADPCM / VAG / XMA at pack time on each console target). miniaudio's `dr_wav` decodes IMA ADPCM natively — **no miniaudio code change needed beyond the Vorbis trim**; the runtime path is identical to linear-PCM WAV.
- **Vorbis stays disabled.** Music goes through MIDI + SF2 (not miniaudio decoding); SFX is ADPCM WAV. Nothing wants Vorbis.
- **Instrument patches stay SF2** via TinySoundFont — and this same SF2/TSF path is a candidate to host **most SFX** in a follow-up. SF2 isn't just for music: its velocity layers + envelopes + filters + pitch-as-parameter let one sample fabricate dozens of effects (footsteps, impacts, UI clicks, weapon fire). SFX becomes a `(preset, note, vel, duration)` tuple triggered via `tml_message` through the existing music path. This would drop most `ma_decoder_init_wav_from_memory` callers and potentially let us retire `dr_wav` entirely, keeping WAV/ADPCM only for voice lines and complex pre-rendered ambients. **Out of scope for this plan** (size-win trim only) — called out so the decoder-init choice below doesn't foreclose it.
- **`-fno-rtti` is out of scope**, confirmed by compile failure: 50+ `dynamic_cast` sites in `game/level.cc`, `game/actor.cc`, `movement/`, `physics/`, `room/` etc. Converting these to an integer type-tag is a separate refactor.

## Changes

### 1. `-fno-exceptions` project-wide

**Files:**
- `CMakeLists.txt:386–405` — add `-fno-exceptions` to the `wf_game` and `Jolt` target Release compile options. (`zforth` is C, no flag needed.)

**Why safe:** grep for `try|throw|catch` across `wfsource/source` and `engine/vendor/jolt-physics-5.5.0/Jolt/` found exactly one live throw site — `pigsys/assert.hp:134,144` — inside a `#ifdef` guarded to `NO_CONSOLE` (Windows WRL exporter, uses `MessageBox` from `windows.h`). The Android `#else` branch uses `std::cerr` + `Fail()` and doesn't throw. Jolt core has zero `throw`. After the Windows-path deletion below (item 5), there's no live throw anywhere.

**Expected delta:** drops `.eh_frame` (~307 KB in current release) and `.gcc_except_table` (~56 KB) entirely. ~360 KB saved.

### 2. `-fvisibility=hidden` + explicit exports

**Files:**
- `CMakeLists.txt` — add `-fvisibility=hidden` to `wf_game` and `Jolt` target Release compile options.
- New: `wfsource/source/hal/android/wf_android_export.hp` — single-line header defining `#define WF_ANDROID_EXPORT __attribute__((visibility("default")))`.
- Annotate 11 existing `extern "C"` functions with `WF_ANDROID_EXPORT`:
  - `android_main` — `hal/android/native_app_entry.cc:357`
  - `WFAndroidPumpEvents` — `hal/android/native_app_entry.cc:340`
  - `WFAndroidGetAssetManager` — `hal/android/native_app_entry.cc:332`
  - `WFAndroidEglInit` — `gfx/gl/android_window.cc:61`
  - `WFAndroidEglTerm` — `gfx/gl/android_window.cc:171`
  - `WFAndroidSetHudEnabled` — `gfx/gl/android_window.cc:312`
  - `HALCreateAAssetAccessor` — `hal/android/asset_accessor_aasset.cc:93`
  - `HALNotifySuspend`, `HALNotifyResume`, `HALIsSuspended`, `HALPumpSuspendedEvents` — `hal/android/lifecycle.cc:21,27,33,42`

**`ANativeActivity_onCreate` special case:** lives in the NDK-vendored `android_native_app_glue.c` which we don't modify. The `-u ANativeActivity_onCreate` linker flag already at `CMakeLists.txt:376` prevents GC. With `-fvisibility=hidden`, we'd also need to export it — add `-Wl,--export-dynamic-symbol=ANativeActivity_onCreate` to the link options rather than patching vendor code.

**Expected delta:** per the report estimate and NDK examples, substantially smaller `.dynsym` (~226 KB → ~10 KB range) / `.dynstr` (~341 KB → ~20 KB) / `.rela.dyn` / `.gnu.hash`. 200–400 KB off the stripped `.so`, a smaller APK compressed delta.

**Risk:** if any symbol we missed is actually called across the `.so` boundary, it becomes a runtime lookup failure (not a link failure). Mitigation: exhaustive list above is from agent audit of the Android HAL + vendored glue. Smoke-test on device before claiming done.

### 3. `MA_NO_VORBIS` + format-specific decoder init

**Files:**
- `wfsource/source/audio/linux/miniaudio_impl.cc` — add `#define MA_NO_VORBIS` alongside existing `MA_NO_FLAC`, `MA_NO_MP3`, `MA_NO_GENERATION`, `MA_NO_ENCODING`. Update the comment block to reflect the WAV-only commitment.
- `wfsource/source/audio/linux/buffer.cc:70–75` and `:100–105` — replace:
  ```cpp
  ma_decoder_config dcfg = ma_decoder_config_init_default();
  if (ma_decoder_init_memory(data, len, &dcfg, &dec) != MA_SUCCESS) { ... }
  ```
  with:
  ```cpp
  if (ma_decoder_init_wav_from_memory(data, len, nullptr, &dec) != MA_SUCCESS) { ... }
  ```
  (The config arg goes away; WAV init doesn't take one.)

**Expected delta:** ~100–150 KB `.text` (Vorbis decoder is one of the larger ma_* families remaining).

### 4. Skip: "strip libGLESv3 calls we don't use"

**Not doing.** Re-reading the report, this was labelled "not really a size lever, more of a startup-time lever" — libGLESv3 is a system library, not shipped in the APK, and the `NEEDED` ELF entry costs a handful of bytes. Stripping unused `glFoo` calls wouldn't move the APK size needle measurably, and the startup-time win is unquantified without device profiling. Leaving as a follow-up gated on real device profiling data.

### 5. Delete unused Windows code (`pigsys/assert.hp`)

**Scope audit:** `grep -rln "WF_TARGET_WIN|_WIN32|windows\.h|MessageBox|WRLExporter" wfsource/source` returns exactly one file — `pigsys/assert.hp`. There's no other Windows-specific code in the runtime tree. This deletion is tightly scoped.

**Files:**
- `wfsource/source/pigsys/assert.hp:115–192` — remove the `#if defined(NO_CONSOLE)` branch in its entirety: the `#include <windows.h>` / `<winuser.h>`, the `WRLExporterException` class, the two `MessageBox`-based `AssertMsg` / `AssertMsgFileLine` macros, and the matching `#else` / `#endif` / `EXPORTER_EXCEPTION_DEFINED` bookends. The Linux path (what was the `#else` branch) becomes unconditional.

**Why safe:** `NO_CONSOLE` is never defined in any Android or Linux build (only the WRL exporter tool-build defines it). The branch is unreachable in the runtime. Deleting it is pure bit-rot removal.

**Expected delta:** negligible bytes in the binary (the branch was compiled out anyway) — **but** it removes the last live `throw` site so `-fno-exceptions` gets cleanly applied with no `#ifdef` dance.

## Measurement protocol

1. Clean the CMake cache: `rm -rf android/app/.cxx android/app/build/intermediates/cxx`
2. `task build-apk` (release).
3. Capture (all comparable to earlier iterations):
   - `stat -c%s` on `android/app/build/outputs/apk/release/worldfoundry-release.apk`
   - `ls -la` on the stripped `.so` in `app/build/intermediates/stripped_native_libs/release/…/lib/arm64-v8a/libwf_game.so`
   - `llvm-size -A` on the stripped `.so` — full section breakdown
   - `unzip -v` on the APK — composition check
   - `llvm-nm --print-size --size-sort --demangle` on the unstripped `.so`, piped through the Python grouper used earlier — subsystem contribution (Jolt / miniaudio / TSF / zForth / other)

## Report updates

Update [`docs/investigations/2026-04-18-android-port-size-and-ram.md`](../investigations/2026-04-18-android-port-size-and-ram.md):

1. Rename column headers: "Debug (`-O0 -g`)" / "Release iter 1 (`-O3 + LTO + GC`)" / **new** "Release iter 2 (`+ no-exceptions + hidden-visibility + MA_NO_VORBIS`)".
2. Add numbers to summary table, delta column.
3. Add the change-log entry to the "Further size wins not taken" section — mark items 1/2/3/4 done, item 5 deferred with rationale.
4. Subsystem breakdown table gets a new release iter-2 column.
5. Don't retouch the runtime-RAM section — these changes don't move RSS meaningfully (code pages are <5% of RSS).

## Verification

1. APK builds clean, no new warnings beyond baseline.
2. APK is self-contained: `unzip -l` shows `libwf_game.so` + assets + icons as before.
3. `llvm-readelf -d` shows the same `NEEDED` entries (no lib drops).
4. `llvm-nm -D` on the stripped `.so` shows a much smaller export set — with our 12 exports + the C++ runtime symbols the linker couldn't hide.
5. User sideloads via Drive → snowgoons boots, icon shows, music plays, physics runs, touch HUD responds (same smoke test as iter 1).

## Critical files

- `CMakeLists.txt` (Release compile + link options for `wf_game` and `Jolt`)
- `wfsource/source/audio/linux/miniaudio_impl.cc` (MA_NO_VORBIS)
- `wfsource/source/audio/linux/buffer.cc` (format-specific decoder init, 2 sites)
- `wfsource/source/pigsys/assert.hp` (delete NO_CONSOLE branch)
- `wfsource/source/hal/android/wf_android_export.hp` (new — export macro)
- `wfsource/source/hal/android/native_app_entry.cc` (annotate 3 exports)
- `wfsource/source/hal/android/asset_accessor_aasset.cc` (annotate 1)
- `wfsource/source/hal/android/lifecycle.cc` (annotate 4)
- `wfsource/source/gfx/gl/android_window.cc` (annotate 3)
- `docs/investigations/2026-04-18-android-port-size-and-ram.md` (new column + text updates)
