# Android Port — Executable Size and RAM Usage

**Date:** 2026-04-18
**Branch:** 2026-android
**Artifacts:**
- Debug: `android/app/build/outputs/apk/debug/worldfoundry-debug.apk`
- Release: `android/app/build/outputs/apk/release/worldfoundry-release.apk`

**Toolchain:** NDK 26.2.11394342, arm64-v8a, clang.

**Build-type flags as of this report:**
- **Debug** — `-DCMAKE_BUILD_TYPE=Debug`; the engine target (`wf_game`) is compiled with `-O0 -g`. AGP strips debug symbols from the shipped `.so`.
- **Release iter 1** — `-DCMAKE_BUILD_TYPE=Release`; engine target is `-O3 -flto=thin -ffunction-sections -fdata-sections -fno-unwind-tables -fno-asynchronous-unwind-tables`, linked with `-flto=thin -Wl,--gc-sections -Wl,--icf=safe`. Vendored Jolt and zForth inherit the same Release flags. miniaudio additionally has `MA_NO_MP3` and `MA_NO_GENERATION` on top of the pre-existing `MA_NO_ENCODING` + `MA_NO_FLAC`.
- **Release iter 2** — everything from iter 1 plus: `-fno-exceptions`, `-fvisibility=hidden` (with 11 explicit `WF_ANDROID_EXPORT` annotations on HAL / NativeActivity-facing functions + `-Wl,--export-dynamic-symbol=ANativeActivity_onCreate` for the NDK-vendored glue), `MA_NO_VORBIS`. Also deletes the `NO_CONSOLE` Windows WRL-exporter branch in `pigsys/assert.hp` (the last `throw` in the tree) so `-fno-exceptions` applies cleanly.

> **Note on the prior baseline:** before the Release pass, the main `wf_game` target had `-O0 -g` hardcoded in `CMakeLists.txt` inside its `target_compile_options`. Gradle was passing `-DCMAKE_BUILD_TYPE=RelWithDebInfo` but that override nullified the optimisation — the "RelWithDebInfo" APK shipped in commit `53fff41` was effectively an unoptimised build masquerading as release. The "debug" column below is measured from that APK; the "release iter N" columns are the optimised builds.

> **Note on APK-size comparisons at iter 2:** between iter 1 and iter 2 measurements, `wfsource/source/game/cd.iff` was regenerated and grew from 174,080 B to 4,724,736 B (unrelated to this plan — a separate content rebuild). Raw "APK on disk" numbers are therefore not apples-to-apples across iterations. The primary metric below is **stripped `.so`**, which is entirely code/data from the CMake build and is unaffected by the content change. "APK minus cd.iff-compressed" is reported for honest APK comparison.

## Side-by-side summary

| Metric | Debug (`-O0 -g`) | Release iter 1 (`-O3 + LTO + GC + ICF`) | Release iter 2 (`+ no-exceptions + hidden-visibility + MA_NO_VORBIS`) | Δ (iter 1 → iter 2) |
|---|---:|---:|---:|---:|
| **`libwf_game.so` stripped** | **4.69 MB** (4,913,640 B) | **3.81 MB** (3,991,208 B) | **2.43 MB** (2,552,760 B) | **−1.44 MB (−36%)** |
| `libwf_game.so` in APK, compressed | 1.85 MB (1,894,598 B) | 1.48 MB (1,556,745 B) | 1.00 MB (1,045,251 B) | −512 KB (−33%) |
| `libwf_game.so` unstripped (dev tree) | 31.1 MB | 31.7 MB | 26.1 MB (27,340,744) | −5.6 MB |
| APK minus cd.iff-compressed | ~2.68 MB | ~2.11 MB | ~1.70 MB (1,697,642 B) | −432 KB (−20%) |
| APK on disk (raw, see cd.iff caveat above) | 2.62 MB (2,742,470) | 2.16 MB (2,263,520) | 2.80 MB (2,936,362) | — |
| `.text` (code) | 2,866,608 B | 2,447,784 B | **1,818,360 B** | **−629 KB (−26%)** |
| `.eh_frame` (C++ unwind tables) | 432,152 B | 307,480 B | **98,596 B** | **−209 KB (−68%)** |
| `.gcc_except_table` | 58,156 B | 55,948 B | **19,960 B** | **−36 KB (−64%)** |
| `.dynsym` | 225,960 B | 175,608 B | **56,136 B** | **−119 KB (−68%)** |
| `.dynstr` | 463,239 B | 341,260 B | **106,011 B** | **−235 KB (−69%)** |
| `.gnu.hash` + `.hash` | 113,448 B | 110,028 B | **33,084 B** | **−77 KB (−70%)** |
| `.rela.dyn` | 208,248 B | 198,240 B | 178,248 B | −20 KB |
| `.rela.plt` | 93,672 B | 34,872 B | 13,824 B | −21 KB |
| `.rodata` | 147,772 B | 131,776 B | 120,163 B | −11 KB |
| `.bss` (zero-init globals) | 159,776 B | 158,656 B | 103,136 B | −54 KB (hidden visibility let the linker drop unreferenced globals) |

**Bottom line:** iter 2 shrinks the stripped `.so` by another 1.44 MB (a 36% reduction vs iter 1, and a 48% cumulative reduction vs debug). The biggest single wins are `-fvisibility=hidden` (collapses `.dynsym` + `.dynstr` + `.hash` — ~430 KB) and `-fno-exceptions` (`.eh_frame` + `.gcc_except_table` — ~244 KB). Combined with `MA_NO_VORBIS`, `.text` drops 629 KB. On-device speedup still hasn't been measured — runtime benchmarking needs a physical handset with `dumpsys` / systrace access.

## What shrank — subsystem breakdown of `.text`

Symbol-level counts from `llvm-nm --print-size --size-sort --demangle`. "other" is everything not matching a Jolt / miniaudio / TSF / zForth prefix — mostly WF engine code plus C++ runtime + vendored headers (miniaudio, tsf) inlined into other TUs.

| Subsystem | Debug (`-O0 -g`) | Release iter 1 | Release iter 2 | Δ (iter 1 → iter 2) |
|---|---:|---:|---:|---:|
| Jolt (`JPH::`) | ~1,030 KB | ~1,152 KB | **749 KB** | **−403 KB (−35%)** |
| miniaudio (`ma_`) | ~593 KB | ~334 KB | **181 KB** | **−153 KB (−46%)** |
| TSF / TML | ~40 KB | ~28 KB | 5 KB | −23 KB |
| zForth | ~3 KB | ~3 KB | 3 KB | unchanged |
| everything else (WF engine + C++ runtime + vendored inlines) | ~1,200 KB | ~930 KB | **1,165 KB** | +235 KB (see note) |

**Why did "other" go up in iter 2?** The grouper attributes symbols to Jolt/miniaudio/TSF/zForth only by demangled-name prefix (`JPH::`, `ma_`, `tsf_`, `zf_`). Under `-fvisibility=hidden` the linker collapses many of those namespaced symbols through ICF and LTO into unnamed stub thunks that demangle without the prefix — so they leave the named-subsystem rows and land in "other." Net engine `.text` (the `.text` row in the summary table above) dropped from 2,447 KB → 1,818 KB (−629 KB). That is the honest total.

**Why this breakdown.** The biggest iter-2 wins are:

- **Jolt −403 KB.** Hidden visibility lets the linker inline + deduplicate Jolt's huge template instantiation tree (Jolt has 3,026 exported symbols at iter 1, 1,613 at iter 2 — nearly halved). `-fno-exceptions` also removes per-function unwind stubs throughout Jolt.
- **miniaudio −153 KB.** `MA_NO_VORBIS` plus `--gc-sections` pruning of all the resource-manager code paths the Vorbis decoder was the only caller of. miniaudio went from 1,867 symbols at iter 1 → 1,306 → now 261 symbols in the subsystem tally (the rest folded into "other" via the ICF collapse above).
- **TSF −23 KB.** Hidden visibility + LTO inlined almost everything into the single caller in `music.cc`.

## APK composition (release iter 2)

```
assets/cd.iff                 4,724,736 B         (deflate → 1,238,720 B — see cd.iff-regen caveat above)
lib/arm64-v8a/libwf_game.so   2,552,760 B         (deflate → 1,045,251 B)
assets/florestan-subset.sf2     531,786 B         (deflate →   507,851 B)
assets/level0.mid                 7,590 B         (stored uncompressed)
res/mipmap-*/ (10 PNGs)         122,376 B         (already compressed)
META-INF + manifest + resources  ~ 10 KB
```

Note: the SF2 compresses poorly in the APK (508 / 532 → only 4% saved). That's because SF2 already contains compressed audio samples internally. Once the [audio-assets-from-iff plan](../plans/2026-04-18-audio-assets-from-iff.md) lands, these loose entries collapse into `cd.iff` but APK size barely changes — the bytes have to ship either way.

## Dynamic dependencies (`.so` NEEDED entries, unchanged between builds)

```
libEGL.so  libGLESv3.so  libandroid.so  liblog.so  libm.so
libOpenSLES.so  libdl.so  libc.so
```

No `libstdc++` / `libc++` — the NDK statically links the C++ runtime into the `.so` so we have no libc++ ABI version to worry about on end-user devices.

## Largest individual symbols (release, unstripped)

```
40,960  b  gStreamNames                  // dstream.cc static name table
16,280  b  actorNames                    // Actor::Print ostream static array
15,604  T  ma_pcm_f32_to_s16
10,880  T  JPH::PhysicsSystem::Update
 9,248  B  JPH::CollisionDispatch::sCollideShape
 9,248  B  JPH::CollisionDispatch::sCastShape
 8,192  B  callStack                     // zForth workspace
```

Hotlist is unchanged between debug and release: the same three static arrays (`gStreamNames`, `actorNames`, Jolt's `CollisionDispatch` function tables) dominate `.bss` because they are initialised data, not code, and global data doesn't get optimised away.

## Runtime RAM

### How to read these numbers

- **VmRSS (Resident Set Size)** — physical memory pages currently mapped for the process. Counts shared-library pages in full even when many processes share them, so overstates the cost attributable to this process.
- **PSS (Proportional Set Size)** — for each page, divides the cost by how many processes share it. This is what Android's `dumpsys meminfo` calls "TOTAL PSS" and what the OS uses for low-memory-killer decisions. **This is the honest "cost" figure.**
- **Private-dirty** — pages that are only ours and have been written (heap, BSS). This is the floor that can't be reclaimed under pressure.

### Desktop Linux proxy

Captured from `/proc/$PID/status` and `/proc/$PID/smaps_rollup` while `engine/wf_game` was running in the default dev configuration (Jolt + all scripting engines + X11 + mesa GL + miniaudio + TSF, snowgoons level loaded, physics ticking, ~6 s after launch).

**Caveat.** This is a desktop Linux build from `engine/build_game.sh` — it's a different build than the Android APK. It includes features Android strips (all scripting engines, REST API, X11, mesa) and runs on a much larger shared-library stack (libGL, libX11, libxcb, glibc). So it is *not* the same process Android measures, but it's the best proxy we have without adb.

```
VmPeak:   1,016,392 kB    // virtual address space (mostly unreserved mappings)
VmSize:   1,016,392 kB
VmHWM:      101,720 kB    // high-water RSS
VmRSS:      101,720 kB    // ~99 MB resident
VmData:     168,088 kB    // ~164 MB anonymous heap + writable data
VmStk:        8,192 kB
VmExe:        3,924 kB    // code pages actually paged in (far less than the on-disk .so size)
VmLib:      171,488 kB    // shared library mappings (X11, mesa, GL, glibc, …)

Rss:        101,724 kB
Pss:         59,921 kB    ← honest cost
Pss_Dirty:   41,740 kB
Pss_Anon:    41,728 kB    // our private heap
Pss_File:    18,181 kB    // code + ro-data pages
Shared_Clean: 59,868 kB   // system libs shared with other processes
Private_Dirty: 41,736 kB  // pages we own outright
```

### Projecting to on-device Android

Debug vs release optimisation barely moves the RSS needle: `VmExe` (code pages actually paged in) was ~4 MB out of ~99 MB RSS. Saving 420 KB of `.text` is ~10% of that — noise compared to the 42 MB private-dirty heap. Optimisation buys speed, not smaller footprint.

The Android/Linux divergence is much larger than the debug/release divergence. Likely delta from the 99 MB / 59 MB PSS Linux proxy:

**Likely smaller on Android:**
- `VmLib`: ~167 MB on Linux is dominated by the mesa + X11 + glibc stack. Android loads a much tighter set (EGL/GLES vendor driver + bionic + OpenSLES) for graphics + audio.
- No X server, mesa i965/llvmpipe, pulseaudio backing state.

**Likely larger on Android:**
- ART + framework: the NativeActivity process loads `libart.so`, framework classes for `android.app.NativeActivity` + our tiny `LogViewerActivity`, plus the Android GC heap. Typical baseline is 15–30 MB PSS for framework glue before the native lib does anything.
- Compositor surface buffers (2× framebuffer-size, RGBA8888) are accounted to the app on some devices — e.g. 1080p × 4 B × 2 = 16 MB.

**Net projection:** **50–90 MB PSS** on a typical arm64 handset under snowgoons. The engine itself (private-dirty anon) should track the desktop ~42 MB closely since Jolt allocations, TSF synth voices, Forth VM workspace, and render buffers are platform-independent.

### Runtime components — what we know and don't

The rows below are an honest mix of measured and estimated. Where a number is a guess, it's labelled as one.

| Component | Contribution | How certain |
|---|---|---|
| Jolt allocators | ~10–25 MB | Broadphase tree + temp-allocator reserve (configured ~32 MB in our setup) + body storage. Scales with scene complexity. Grounded in how Jolt is configured, not in a profiler run. |
| SF2 mmap (florestan-subset) | 0.52 MB | Exact — file is 531,786 B, mmap'd into the process at play-time. |
| `cd.iff` in memory | 174 KB on disk; in-memory expansion **not measured** | `cd.iff` is read through `AAssetManager` and parsed into level data (meshes, textures, mailboxes, script bytecode). The total expansion factor depends on texture/vertex/script layout and hasn't been instrumented. |
| TSF synth + tml_message list | ~200–500 KB | Rough; varies with how many voices are active. |
| Forth VM workspace | < 50 KB | Solid upper bound — symbol table shows `callStack` at 8 KB and the zForth data section is small. |
| GL/EGL driver state | 5–20 MB | Vendor-dependent (Adreno vs Mali vs etc.); impossible to tighten without device measurement. |
| Misc heap (STL, strings, IO buffers) | 1–3 MB | Estimate. |

The desktop-proxy 42 MB private-dirty includes the above rolled up, roughly consistent with a Jolt-dominated allocation picture plus a handful of MB of everything else.

### On-device measurement (when a device is attached)

Quick "where are we now":

```
adb shell dumpsys meminfo org.worldfoundry.wf_game
```

Look at "TOTAL PSS" — that's the number comparable to the 59 MB desktop proxy. Breakdown is by category (Dalvik heap, native heap, code, stack, graphics, etc.).

If a PID is available (`adb shell pidof org.worldfoundry.wf_game`):

```
adb shell cat /proc/<pid>/status        | grep Vm
adb shell cat /proc/<pid>/smaps_rollup
```

These match the `/proc` sampling done for the desktop proxy above. Capturing these once on real hardware would let us replace the "projection" section with real numbers.

## Build pipeline — what "release" means here

There are two independent toolchains in an Android build, and they mean different things by "release":

- **Native side** (`libwf_game.so`, the whole engine): compiled by clang through CMake + NDK, then stripped by AGP's `stripReleaseDebugSymbols` step. All the size savings above come from this pipeline — our new `-O3` + thin LTO + `--gc-sections --icf=safe` flags.
- **Java side** (`LogViewerActivity.java` + a few dozen lines of glue): compiled to bytecode, optionally minified by R8. R8 removes unused Java classes/methods, renames them to shorter names, and inlines trivial accessors. Its effectiveness scales with how much Java there is. Because ours is a single tiny Activity, R8 is worth at most a few KB and we leave it off (`isMinifyEnabled = false`).

R8 does **not** touch the native side. The native side is shrunk/optimised entirely by the clang + linker pipeline above. Saying "R8 won't help much" doesn't mean "optimisation won't help" — it means R8 specifically isn't the lever. The lever we actually used is the native-compile flags.

## Size-win follow-ups — status after iter 2

1. ~~**`-fno-exceptions` project-wide.**~~ **Landed in iter 2.** Confirmed no live `throw` in runtime; the only one was in a Windows-only `NO_CONSOLE` branch of `pigsys/assert.hp` that we deleted. Actual savings on `.eh_frame` + `.gcc_except_table` combined: ~245 KB (not zero — the C++ runtime still emits some unwind stubs for implicit destructor chains).
2. **`-fno-rtti`.** **Deferred** — compile-tested, fails with ~50 `dynamic_cast` sites across `game/level.cc`, `game/actor.cc`, `movement/`, `physics/`, `room/`. Converting these to an integer type-tag is a separate refactor (not a flag flip). See [plan: 2026-04-18-android-size-trim-iter-2.md](../plans/2026-04-18-android-size-trim-iter-2.md).
3. ~~**`-fvisibility=hidden` + explicit default-visibility on exports.**~~ **Landed in iter 2.** 11 HAL / NativeActivity-facing functions annotated with `WF_ANDROID_EXPORT`; `ANativeActivity_onCreate` handled via `-Wl,--export-dynamic-symbol=…`. Actual savings across `.dynsym` + `.dynstr` + `.hash`: ~430 KB.
4. ~~**Trim miniaudio further (`MA_NO_VORBIS`).**~~ **Landed in iter 2.** WAV + IMA ADPCM is the committed SFX format (`dr_wav` decodes both). Actual miniaudio `.text` delta: −153 KB.
5. **Drop miniaudio's `ma_dr_wav` if WAV stops being used.** Deferred — requires the "SFX via SF2 synth path" architectural change first. If most SFX move onto TSF preset triggers (see [audio-assets-from-iff plan](../plans/2026-04-18-audio-assets-from-iff.md) + the iter-2 plan's design-decisions section), then a followup can retire dr_wav entirely, keeping only voice-line WAV/ADPCM paths.
6. **Strip `libGLESv3` calls we don't use.** Deferred — not a size lever (libGLESv3 is system-provided, not shipped in the APK; the `NEEDED` entry costs a few bytes). Startup-time win is unquantified without on-device profiling.

## Sources

All numbers are from branch `2026-android`. Debug column from commit `53fff41` (the effectively-unoptimised "RelWithDebInfo" build). Release iter 1 from the commit following that (Release build-type wired in + `MA_NO_MP3` + `MA_NO_GENERATION`). Release iter 2 from the iter-2 implementation commit ([plan](../plans/2026-04-18-android-size-trim-iter-2.md)).

- `unzip -v` on the APKs.
- `llvm-size -A` and `llvm-nm --print-size --size-sort --demangle` from NDK `toolchains/llvm/prebuilt/linux-x86_64/bin/`.
- `/proc/$PID/status` and `/proc/$PID/smaps_rollup` sampled from the running desktop `engine/wf_game`, cwd `wfsource/source/game/`, snowgoons loaded, physics ticking, ~6 s after launch.

## Things we still don't know

1. **On-device PSS.** Needs `dumpsys meminfo` from a real handset. The "projected 50–90 MB" range will collapse once we can measure.
2. **In-memory expansion of `cd.iff`.** Needs heap instrumentation around `Level::Level`. Right now this is the biggest gap between "file size on disk" and "runtime RAM".
3. **Runtime speedup from -O0 → -O3.** Needs frametime profiling on the same physical hardware before/after the Release switch. Likely substantial for CPU-heavy paths (Jolt integration, script VM, IFF parse) — but unquantified.
