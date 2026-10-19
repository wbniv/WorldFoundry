# Plan — Android size trim, iteration 2

**Date:** 2026-04-18
**Status:** IMPLEMENTED (2026‑10‑01), verification step 5 (the user's snowgoons sideload) PENDING. Items 1, 2, 3 (`MA_NO_VORBIS`) and 5 shipped on 2026‑04‑18 in `934583ee`. The 2026‑10‑01 pass landed the rest of item 3 (`b40acc9c`, the WAV-only decoder init) and the missing half of item 2 (`f619a5eb`, hiding the static C++ runtime's exports), and re-measured everything.
**Follow-up to:** [Android port size/RAM report](../investigations/2026-04-18-android-port-size-and-ram.md)
**Results:** [Android size trim, iteration 2 — results](../investigations/2026-10-01-android-size-trim-iter-2-results.md)

## Checklist

- [x] ~~1. `-fno-exceptions`~~: `934583ee`
- [x] ~~2. `-fvisibility=hidden` + `WF_ANDROID_EXPORT`~~: `934583ee`; ~~hide the static C++ runtime, builtins and zForth with `--exclude-libs`~~: `f619a5eb` (an addition to the plan; see Deviations)
- [x] ~~3. `MA_NO_VORBIS`~~: `934583ee` (saves 0 B, see Measurements); ~~WAV-only decoder init~~: `b40acc9c`
- [x] ~~4. Skip the libGLESv3 strip~~ (skipped by design)
- [x] ~~5. Delete the `NO_CONSOLE` Windows branch~~: `934583ee`
- [x] ~~Regression test~~: `tests/test_android_size_trim.py` (`b40acc9c`, `f619a5eb`)
- [x] ~~Measurements, both ABIs, all three flavors~~: see below
- [x] ~~Device smoke test~~: condo release on the Chromecast HD, PASS
- [ ] Verification step 5: the user sideloads snowgoons

## Deviations (2026‑10‑01)

- **`--exclude-libs` added (item 2).** The plan expected "our exports + the C++ runtime symbols the linker couldn't hide". The linker can hide them: `-Wl,--exclude-libs,<archive>` for libc++_static, libc++abi, libunwind, the two clang builtins archives and libzforth. The archives are named one by one, never `ALL`, because libwfengine.a holds `WF_ANDROID_EXPORT` functions. It is Android Clang Release only. Without it, item 2's predicted `.dynsym` / `.dynstr` saving did not appear (2,061 exports as found).
- **The decoder init spelling (item 3).** miniaudio 0.11.25 has no public `ma_decoder_init_wav_from_memory`. The code sets `encodingFormat = ma_encoding_format_wav` instead (details under item 3).
- **`buffer.cc` applies to every platform, as the plan has it.** It is not Android-only, and its behaviour is unchanged: the harness decodes WAV to identical frames, and the stock decoder set is identical on all platforms.
- **The export list is the plan's, not the minimum.** Only `ANativeActivity_onCreate` is looked up by name. `android_main` is called directly by the glue. The other 18 `WF_ANDROID_EXPORT` functions stay exported, as the plan specifies: about 0.5 KB in all.
- **Measured with Gradle directly, not `task build-apk`,** which needs sudo for its SDK install step on this machine. There is no `release/worldfoundry-release.apk` any more; the APKs are per flavor.

## State as found (2026‑10‑01)

The old status line said none of the build changes were applied; `TODO.md` said the `-fno-exceptions` / `-fvisibility=hidden` halves had shipped. The code says most of the plan had shipped, all in one commit, `934583ee` "feat(android): release build with aggressive size trim" (2026‑04‑18), found with `git log -S`:

| Item | State as found | Evidence |
|---|---|---|
| 1. `-fno-exceptions` | **Shipped** in `934583ee` (with `-fno-unwind-tables -fno-asynchronous-unwind-tables`); carried into the `wfengine` target by `d865c405` (the engine library split) | `CMakeLists.txt`: the Clang Release options of `wfengine`, `wf_game` and `Jolt` |
| 2. `-fvisibility=hidden` + exports | **Shipped** in `934583ee`: `wf_android_export.hp`, `-Wl,--export-dynamic-symbol=ANativeActivity_onCreate`. Annotated functions have since grown from 11 to 18 (lifecycle and phone-overlay HAL calls) | 20 defined dynamic symbols of ours, but **2,061** in all: the static C++ runtime (≈2,020) and zForth (11) still exported |
| 3. `MA_NO_VORBIS` | **Shipped** in `934583ee` | `miniaudio_impl.cc` |
| 3. format-specific decoder init | **Not done**: `buffer.cc` still used the generic `ma_decoder_init_memory` with a default config at both sites | `buffer.cc:75`, `:105` |
| 5. delete `NO_CONSOLE` Windows branch | **Shipped** in `934583ee` | no `NO_CONSOLE` / `WRLExporter` / `windows.h` left in `wfsource/source` |

The [size report](../investigations/2026-04-18-android-port-size-and-ram.md) had already been updated with an iteration‑2 column at the time; only this plan's header was stale.

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

  **As landed (2026‑10‑01):** miniaudio 0.11.25 has no public `ma_decoder_init_wav_from_memory` (only a `static …__internal` one), so both sites keep `ma_decoder_init_memory` with a config whose `encodingFormat = ma_encoding_format_wav` (`make_wav_decoder_config()` in `buffer.cc`). That is the 0.11 spelling of the same thing: dr_wav first, no trial-and-error. `tests/wav_decoder_init_test.cc` proves it decodes PCM and IMA ADPCM WAV to the same frames as the generic init and refuses Ogg Vorbis and junk either way.

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

## Measurements (2026‑10‑01)

These were measured on today's source, with both ABIs and all three flavors, through the Gradle release build. The "iteration 1" column is a same-source counterfactual: the iteration‑2 flags and `MA_NO_VORBIS` are stripped by a CMake compiler/linker launcher. A pass-through build with the same launcher matched Gradle byte for byte. The method, the charts and the full discussion are in the [results report](../investigations/2026-10-01-android-size-trim-iter-2-results.md).

| | Iteration 1 | As found (`934583ee` flags) | Now (`f619a5eb`) | Δ now vs as found |
|---|---:|---:|---:|---:|
| condo APK (B) | 3,742,904 | 2,824,830 | 2,581,660 | −243,170 |
| aquarium APK (B) | 3,724,513 | 2,806,439 | 2,563,780 | −242,659 (its `cd.iff` was rebuilt in between, +514) |
| snowgoons APK (B) | 10,861,243 | 9,943,169 | 9,699,996 | −243,173 |
| arm64-v8a `libwf_game.so` stripped (B) | 4,171,512 | 2,726,312 | 2,233,704 | −492,608 |
| armeabi-v7a `libwf_game.so` stripped (B) | 3,156,020 | 2,230,976 | 1,887,912 | −343,064 |
| arm64 `.eh_frame` / `.gcc_except_table` (B) | 355,948 / 58,696 | 98,692 / 20,000 | 50,784 / 13,160 | −47,908 / −6,840 |
| armeabi-v7a `.ARM.exidx` / `.ARM.extab` (B) | 48,096 / 77,500 | 12,000 / 31,272 | 6,376 / 14,352 | −5,624 / −16,920 |
| arm64 `.dynsym` / `.dynstr` (B) | 166,248 / 327,434 | 57,168 / 106,615 | 7,104 / 3,958 | −50,064 / −102,657 |
| armeabi-v7a `.dynsym` / `.dynstr` (B) | 110,880 / 327,467 | 38,112 / 106,598 | 4,736 / 3,923 | −33,376 / −102,675 |
| defined dynamic symbols (arm64 / v7a) | 6,599 / 6,604 | 2,061 / 2,063 | 20 / 20 | −2,041 / −2,043 |

**Predictions that did not hold:**

- **Item 1 predicted that `.eh_frame` and `.gcc_except_table` would go "entirely".** They did not: 51 KB + 13 KB remain on arm64. That data belongs to the NDK's prebuilt libc++_static / libc++abi, which are compiled with exceptions and are out of reach of our flags. Hiding their exports let `--gc-sections` drop the unused part (−55 KB).
- **Item 2's `.dynsym` (~10 KB) / `.dynstr` (~20 KB) prediction failed in April** (57 KB / 107 KB, 2,061 exports). It holds only now, with `--exclude-libs` (7 KB / 4 KB, 20 exports).
- **Item 3's −100 to 150 KB for `MA_NO_VORBIS` is wrong: it saves 0 B.** A build with only that define removed is byte-identical. miniaudio 0.11.25 defines `MA_HAS_VORBIS` only `#ifdef STB_VORBIS_INCLUDE_STB_VORBIS_H`, and nothing includes stb_vorbis. The WAV-only init saves 0 B on arm64 (+16 B on armeabi-v7a) for the same reason.

<details><summary>Raw numbers (<code>llvm-size -A</code>, <code>llvm-nm -D</code>, <code>stat</code>, <code>unzip -v</code>)</summary>

```
tag      abi                 so     .text .eh_frame  .eh_hdr  .gcc_ex  .dynsym   .dynstr .rela.dyn   nexp
iter1    arm64-v8a      4171512   2619188   355948    58452    58696   166248    327434    175704   6599
iter1    armeabi-v7a    3156020   2199304                              110880    327467             6604
before   arm64-v8a      2726312   1999524    98692    16148    20000    57168    106615    158280   2061
before   armeabi-v7a    2230976   1775296                               38112    106598             2063
decoder  arm64-v8a      2726312   1999524    98692    16148    20000    57168    106615    158280   2061
decoder  armeabi-v7a    2230992   1775312                               38112    106598             2063
after    arm64-v8a      2233704   1821308    50784     8340    13160     7104      3958    128088     20
after    armeabi-v7a    1887912   1656752                                4736      3923               20
vorbis   arm64-v8a      2233704   1821308    50784     8340    13160     7104      3958    128088     20
(armeabi-v7a: .ARM.exidx 48096 / 12000 / 12000 / 6376, .ARM.extab 77500 / 31272 / 31272 / 14352, .rel.dyn 59344 / 53256 / 53256 / 43192 for iter1 / before / decoder / after)

APK (B)         before     after      lib deflated arm64 / v7a (before -> after)
condo          2824830   2581660     1154414 / 1191678 -> 1025989 / 1076925
aquarium       2806439   2563780     (same libraries)
snowgoons      9943169   9699996     (same libraries)
iter1 APK = before + (1658086 - 1154414) + (1606080 - 1191678) = before + 918074   (deflate level 6, which reproduces AGP's sizes exactly)
```

</details>

## Report updates

Update [`docs/investigations/2026-04-18-android-port-size-and-ram.md`](../investigations/2026-04-18-android-port-size-and-ram.md):

1. Rename column headers: "Debug (`-O0 -g`)" / "Release iter 1 (`-O3 + LTO + GC`)" / **new** "Release iter 2 (`+ no-exceptions + hidden-visibility + MA_NO_VORBIS`)".
2. Add numbers to summary table, delta column.
3. Add the change-log entry to the "Further size wins not taken" section — mark items 1/2/3/4 done, item 5 deferred with rationale.
4. Subsystem breakdown table gets a new release iter-2 column.
5. Don't retouch the runtime-RAM section — these changes don't move RSS meaningfully (code pages are <5% of RSS).

**2026‑10‑01:** items 1 to 4 were done in April. This pass adds a follow-up note at the top of that report, linking to the [results report](../investigations/2026-10-01-android-size-trim-iter-2-results.md), and a correction on the `MA_NO_VORBIS` attribution.

## Verification

Run 2026‑10‑01 against `f619a5eb` (release, both ABIs, all three flavors; the Gradle invocation is under Deviations).

1. APK builds clean, no new warnings beyond baseline.

    ```
    $ grep -cE "warning:|error:" before.log excl.log after.log
    before.log:0
    excl.log:0
    after.log:0
    BUILD SUCCESSFUL in 1m 22s      (excl.log: the build that relinked libwf_game.so for both ABIs)
    GRADLE_RC=0
    ```
    PASS

2. APK is self-contained: `unzip -l` shows `libwf_game.so` + assets + icons as before.

    ```
    $ unzip -l worldfoundry-condo-release.apk | grep -E 'lib/|assets/'
      2233704  1981-01-01 01:01   lib/arm64-v8a/libwf_game.so
      1887912  1981-01-01 01:01   lib/armeabi-v7a/libwf_game.so
      2422784  1981-01-01 01:01   assets/cd.iff
        17826  1981-01-01 01:01   assets/controller.html
          648  1981-01-01 01:01   assets/layout.json
          131  1981-01-01 01:01   assets/wf_args.txt
      res/ PNGs: 31
    $ unzip -l worldfoundry-aquarium-release.apk | grep -E 'lib/|assets/'
      2233704  1981-01-01 01:01   lib/arm64-v8a/libwf_game.so
      1887912  1981-01-01 01:01   lib/armeabi-v7a/libwf_game.so
       188416  1981-01-01 01:01   assets/cd.iff
        17826  1981-01-01 01:01   assets/controller.html
          376  1981-01-01 01:01   assets/layout.json
      res/ PNGs: 31
    $ unzip -l worldfoundry-snowgoons-release.apk | grep -E 'lib/|assets/'
      2233704  1981-01-01 01:01   lib/arm64-v8a/libwf_game.so
      1887912  1981-01-01 01:01   lib/armeabi-v7a/libwf_game.so
      1384448  1981-01-01 01:01   assets/cd.iff
      7842132  1981-01-01 01:01   assets/florestan-subset.sf2
         7590  1981-01-01 01:01   assets/level0.mid
      res/ PNGs: 31
    $ diff <(unzip -Z1 before/…apk | sort) <(unzip -Z1 after/…apk | sort)
    condo: same 50 entries; aquarium: same 49 entries; snowgoons: same 49 entries
    ```
    PASS

3. `llvm-readelf -d` shows the same `NEEDED` entries (no lib drops).

    ```
    $ llvm-readelf -d arm64-v8a/libwf_game.so | grep NEEDED
      0x0000000000000001 (NEEDED)       Shared library: [libEGL.so]
      0x0000000000000001 (NEEDED)       Shared library: [libGLESv3.so]
      0x0000000000000001 (NEEDED)       Shared library: [libandroid.so]
      0x0000000000000001 (NEEDED)       Shared library: [liblog.so]
      0x0000000000000001 (NEEDED)       Shared library: [libm.so]
      0x0000000000000001 (NEEDED)       Shared library: [libOpenSLES.so]
      0x0000000000000001 (NEEDED)       Shared library: [libdl.so]
      0x0000000000000001 (NEEDED)       Shared library: [libc.so]
    $ llvm-readelf -d armeabi-v7a/libwf_game.so | grep NEEDED
      0x00000001 (NEEDED)       Shared library: [libEGL.so]
      0x00000001 (NEEDED)       Shared library: [libGLESv3.so]
      0x00000001 (NEEDED)       Shared library: [libandroid.so]
      0x00000001 (NEEDED)       Shared library: [liblog.so]
      0x00000001 (NEEDED)       Shared library: [libm.so]
      0x00000001 (NEEDED)       Shared library: [libOpenSLES.so]
      0x00000001 (NEEDED)       Shared library: [libdl.so]
      0x00000001 (NEEDED)       Shared library: [libc.so]
    (identical for the as-found build, both ABIs)
    ```
    PASS

4. `llvm-nm -D` on the stripped `.so` shows a much smaller export set — with our 12 exports + the C++ runtime symbols the linker couldn't hide.

    ```
    $ llvm-nm -D --defined-only arm64-v8a/libwf_game.so
    00000000000a6578 T ANativeActivity_onCreate;00000000000aaadc T ClearHostGLContext;00000000000aaad0 T GetHostGLContext;00000000000aaac8 T HALCloseWindow;00000000000ac2f8 T HALCreateAAssetAccessor;00000000000aaa94 T HALIsSuspended;00000000000aaa84 T HALNotifyResume;00000000000aaa70 T HALNotifySuspend;00000000000aaabc T HALPumpSuspendedEvents;00000000000aaae0 T HALRequestClose;00000000000aaac0 T HALWindowCloseRequested;00000000000aaacc T SetHostGLContext;00000000000ac344 T WFAndroidEglInit;00000000000ac6f8 T WFAndroidEglTerm;000000000009a444 T WFAndroidGetAssetManager;000000000009a450 T WFAndroidHasWindow;000000000009a650 T WFAndroidPhoneOverlayRects;000000000009a45c T WFAndroidPumpEvents;00000000000ac750 T WFAndroidSetHudEnabled;000000000009a730 T android_main;
    $ llvm-nm -D --defined-only armeabi-v7a/libwf_game.so
    000673a0 T ANativeActivity_onCreate;0006a948 T ClearHostGLContext;0006a938 T GetHostGLContext;0006a934 T HALCloseWindow;0006bcd8 T HALCreateAAssetAccessor;0006a904 T HALIsSuspended;0006a8f0 T HALNotifyResume;0006a8dc T HALNotifySuspend;0006a92c T HALPumpSuspendedEvents;0006a94a T HALRequestClose;0006a930 T HALWindowCloseRequested;0006a936 T SetHostGLContext;0006bd08 T WFAndroidEglInit;0006bfb4 T WFAndroidEglTerm;0005e1d0 T WFAndroidGetAssetManager;0005e1dc T WFAndroidHasWindow;0005e388 T WFAndroidPhoneOverlayRects;0005e1e8 T WFAndroidPumpEvents;0006bfec T WFAndroidSetHudEnabled;0005e430 T android_main;
    (as found: 2,061 / 2,063; iteration 1: 6,599 / 6,604)
    ```
    PASS. There are 20 exports: 18 `WF_ANDROID_EXPORT` + `android_main` + `ANativeActivity_onCreate`, and no C++ runtime symbols at all, since `--exclude-libs` hides them. `tests/test_android_size_trim.py` pins this set.

5. User sideloads via Drive → snowgoons boots, icon shows, music plays, physics runs, touch HUD responds (same smoke test as iter 1).

    PENDING: this is the user's own sideload check. As a stand-in on the same library, the condo release ran on the Chromecast HD (armeabi-v7a) via adb, with no key events sent:

    ```
    $ ADB=…/platform-tools/adb bash scripts/android-device-run.sh --app condo --release --seconds 8 192.168.4.38:41447
    2026-10-01T13:10:29Z installing …/worldfoundry-condo-release.apk (2581660 bytes)
    2026-10-01T13:10:33Z PASS  installed org.worldfoundry.wf_game.condo
    2026-10-01T13:10:35Z PASS  launched (TotalTime: 487 ms)
    2026-10-01T13:10:43Z PASS  process alive after 8 s (pid 19170)
    2026-10-01T13:10:44Z INFO  memory: TOTAL PSS 49152 KB (meminfo.txt)
    2026-10-01T13:10:52Z PASS  screenshot …/condo-20261001T131028Z/screen.png (1784 1920x1080 distinct colours at 160x90) — open it and look
    2026-10-01T13:10:52Z PASS  no crash lines in logcat
    2026-10-01T13:10:52Z PASS  EGL context up (android_main: EGL ready)
    2026-10-01T13:10:52Z INFO  frame pacing (…): 127 frames: min 16.7 ms, median 16.7 ms (59.9 fps), p90 33.4 ms, worst 50.1 ms; display refresh 16.68 ms
    2026-10-01T13:10:52Z RESULT: PASS
    $ grep phonepad logcat-wf.txt
    10-01 20:10:35.270 19170 19192 I wf_game : phonepad: listening on 192.168.4.38:8765
    $ curl -s -o /dev/null -w "%{http_code} %{size_download}\n" "http://192.168.4.38:8765/?k=359433"
    200 17826
    ```
    The screenshot shows the "Use your phone as the controller" panel with the QR code and its logo, over the condo.

Tests:

```
$ python3 -m pytest tests/test_android_size_trim.py -q
9 passed in 17.70s
$ python3 -m pytest tests/test_phone_controller.py tests/test_phone_controller_page.py tests/test_phone_controller_android.py tests/test_phone_overlay.py tests/test_phone_qr.py tests/test_aquarium_android.py tests/test_condo_android.py -q
FAILED tests/test_aquarium_android.py::test_built_aquarium_apk_contents   (the debug aquarium APK's cd.iff predated ace2e0be's rebuild of wflevels/aquarium-cd.iff)
1 failed, 178 passed in 166.18s (0:02:46)
$ ./gradlew :app:assembleAquariumDebug && python3 -m pytest tests/test_aquarium_android.py -q -k built
2 passed, 12 deselected in 0.15s
$ python3 -m pytest <the seven files above> tests/test_android_size_trim.py -q      # clean rerun
188 passed in 119.62s (0:01:59)
$ task build        # Linux; compiles the changed audio/linux/buffer.cc
  CC …/wfsource/source/audio/linux/buffer.cc
Built: /home/will/WorldFoundry-wbniv/engine/wf_game
```

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
- [docs/investigations/2026-04-18-android-port-size-and-ram.md](../investigations/2026-04-18-android-port-size-and-ram.md) (new column + text updates)
