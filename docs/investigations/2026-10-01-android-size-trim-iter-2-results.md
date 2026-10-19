# Android Size Trim, Iteration 2 — Results

**Date:** 2026-10-01\
**Branch:** 2026-new-level\
**Plan:** [Android size trim, iteration 2](../plans/2026-04-18-android-size-trim-iter-2.md)\
**Follow-up to:** [Android port — executable size and RAM usage](2026-04-18-android-port-size-and-ram.md) (2026‑04‑18)\
**Toolchain:** NDK 26.2.11394342 (clang 17), Gradle release build, both ABIs (arm64-v8a, armeabi-v7a), three app flavors (condo, aquarium, snowgoons).

## Summary

Most of iteration 2 had already shipped in April, in one commit (`934583ee`); the TODO line was right and the plan header was stale. This pass finished the plan and found the one place it had fallen short:

- **The static C++ runtime was still exported.** `-fvisibility=hidden` only covers code compiled with it, so the release `libwf_game.so` still exported **2,061** dynamic symbols, about 2,020 of them from the statically linked libc++. Hiding the runtime, compiler-builtin and zForth archives at link time (`-Wl,--exclude-libs,…`, Android release only) leaves **exactly 20** exports. Unexported runtime code also stops being a garbage-collection root, so the linker drops the parts we never call.
- **The headline:** the stripped `libwf_game.so` shrinks by **481 KiB** on arm64-v8a (2.73 → 2.23 MB, −18%) and **335 KiB** on armeabi-v7a, the Chromecast HD's ABI (2.23 → 1.89 MB, −15%). **Every release APK is 243 KB smaller.** Counting from a same-source iteration‑1 rebuild, iteration 2 as a whole now takes **46%** off the arm64 library and **40%** off the armeabi-v7a one.
- **The WAV-only decoder init** (the last unshipped line of the plan) landed, but it saves **0 bytes**. The other decoders were already compiled out.
- **One April claim was wrong.** `MA_NO_VORBIS` saves **0 bytes**: miniaudio 0.11 compiles Vorbis only when `stb_vorbis` is included first, and nothing includes it. The 153 KB of miniaudio `.text` that the April report credited to it came from the visibility and exceptions flags.
- **Risk and cost:** no feature was given up. Nothing outside the `.so` links against the hidden symbols, because the APK ships no other native library, and the only symbol looked up by name, `ANativeActivity_onCreate`, stays exported. The condo release ran on the Chromecast HD at 59.9 fps with the phone-controller panel up. All 188 tests in the area pass (179 existing, 9 new).

## 1. State as found

The TODO said the `-fno-exceptions` / `-fvisibility=hidden` halves had shipped. The plan said nothing had. `git log -S` on each change settled it:

| Plan item | State as found | Commit |
|---|---|---|
| 1. `-fno-exceptions` | Shipped | `934583ee`, `d865c405` |
| 2. `-fvisibility=hidden` + exports | Shipped | `934583ee` |
| 3. `MA_NO_VORBIS` | Shipped (a no-op; see §2) | `934583ee` |
| 3. WAV-only decoder init | **Not done** | — |
| 4. Strip libGLESv3 calls | Skipped by design | — |
| 5. Delete the Windows branch | Shipped | `934583ee` |

- **1.** `-fno-exceptions` and `-fno-unwind-tables` went onto the `wf_game` and Jolt Release builds on 2026‑04‑18. They were copied onto `wfengine` when the engine became a library (`d865c405`).
- **2.** The `WF_ANDROID_EXPORT` macro and `--export-dynamic-symbol=ANativeActivity_onCreate` shipped with the flag. The marked functions have grown from 11 to 18 (lifecycle and phone-overlay calls).
- **3.** Both decoder inits in `buffer.cc` still used the generic `ma_decoder_init_memory`.
- **5.** The `NO_CONSOLE` branch of `pigsys/assert.hp` is gone.

The April [size report](2026-04-18-android-port-size-and-ram.md) already had an iteration‑2 column. Only the plan header was out of date.

**This pass:**

| Commit | Change |
|---|---|
| `b40acc9c` | WAV-only decoder init, plus tests |
| `f619a5eb` | Hide the static archives' exports, plus a test |
| `4714308a` | Plan: measurements and verification |

- **`b40acc9c`.** Both `SoundBuffer::play()` decoder inits in `buffer.cc` name `ma_encoding_format_wav`. It adds `tests/test_android_size_trim.py` and an equivalence harness that compiles the game's own miniaudio build.
- **`f619a5eb`.** `CMakeLists.txt` passes `-Wl,--exclude-libs` for libc++_static, libc++abi, libunwind, both clang builtins archives and libzforth, on Android Clang Release only. A test pins the export set.

## 2. Before and after

Three builds of today's source, measured the same way:

- **Iteration 1** is a counterfactual: today's tree built with the iteration‑2 flags removed (no `-fvisibility=hidden`, `-fno-exceptions`, `-fno-unwind-tables`, `--exclude-libs` or `MA_NO_VORBIS`), through a CMake compiler and linker launcher (see §4). It answers "what did iteration 2 buy on this code base", which April's iteration‑1 numbers (an older, smaller engine) cannot.
- **As found** is the Gradle release build of `ace2e0be` + `b40acc9c` (the WAV-init change, which is byte-identical on arm64).
- **Now** is the Gradle release build of `f619a5eb`.

As a check on the method, a launcher pass-through build of `f619a5eb` came out byte-for-byte the same size as Gradle's, section by section.

### Per app: release APK (both ABIs inside)

| App | Iteration 1 (B) | As found (B) | Now (B) | Δ now vs as found | Δ now vs iteration 1 |
|---|---:|---:|---:|---:|---:|
| condo | 3,742,904 | 2,824,830 | 2,581,660 | **−243,170 (−8.6%)** | −1,161,244 (−31%) |
| aquarium | 3,724,513 | 2,806,439 | 2,563,780 | **−242,659 (−8.6%)** | −1,160,733 (−31%) |
| snowgoons | 10,861,243 | 9,943,169 | 9,699,996 | **−243,173 (−2.4%)** | −1,161,247 (−11%) |

The three apps carry the same native library, so they move by the same amount, 243,178 B of compressed library. The aquarium figure is 514 B smaller because its `cd.iff` was rebuilt between the two builds, by `ace2e0be`, a content commit from another session. The iteration‑1 APK sizes are derived: the as-found APK, with each library entry's deflate size swapped for the iteration‑1 library's deflate size at level 6. Level 6 reproduces AGP's compressed sizes for the as-found and now libraries to the byte.

### Per ABI: stripped `libwf_game.so` and the sections the plan predicted

**arm64-v8a**

| Section | Iteration 1 | As found | Now | Δ now vs as found | Plan prediction |
|---|---:|---:|---:|---:|---|
| **file (stripped)** | 4,171,512 | 2,726,312 | **2,233,704** | **−492,608** | — |
| `.text` | 2,619,188 | 1,999,524 | 1,821,308 | −178,216 | Vorbis: −100 to 150 KB |
| `.eh_frame` | 355,948 | 98,692 | 50,784 | −47,908 | dropped entirely |
| `.eh_frame_hdr` | 58,452 | 16,148 | 8,340 | −7,808 | — |
| `.gcc_except_table` | 58,696 | 20,000 | 13,160 | −6,840 | dropped entirely |
| `.dynsym` | 166,248 | 57,168 | **7,104** | −50,064 | ~10 KB |
| `.dynstr` | 327,434 | 106,615 | **3,958** | −102,657 | ~20 KB |
| `.gnu.hash` + `.hash` | 104,816 | 33,480 | 2,524 | −30,956 | smaller |
| `.rela.dyn` | 175,704 | 158,280 | 128,088 | −30,192 | smaller |
| defined dynamic symbols | 6,599 | 2,061 | **20** | −2,041 | "12 + runtime" |

**armeabi-v7a** (ARM EHABI: unwind data lives in `.ARM.exidx` / `.ARM.extab`, and there is no `.eh_frame` or `.gcc_except_table`)

| Section | Iteration 1 | As found | Now | Δ now vs as found | Plan prediction |
|---|---:|---:|---:|---:|---|
| **file (stripped)** | 3,156,020 | 2,230,976 | **1,887,912** | **−343,064** | — |
| `.text` | 2,199,304 | 1,775,296 | 1,656,752 | −118,544 | — |
| `.ARM.exidx` | 48,096 | 12,000 | 6,376 | −5,624 | — |
| `.ARM.extab` | 77,500 | 31,272 | 14,352 | −16,920 | — |
| `.dynsym` | 110,880 | 38,112 | **4,736** | −33,376 | — |
| `.dynstr` | 327,467 | 106,598 | **3,923** | −102,675 | — |
| `.gnu.hash` + `.hash` | 104,868 | 33,488 | 2,524 | −30,964 | — |
| `.rel.dyn` | 59,344 | 53,256 | 43,192 | −10,064 | — |
| defined dynamic symbols | 6,604 | 2,063 | **20** | −2,043 | — |

(The plan wrote its predictions for arm64 only.)

### Predictions against measurements

| Plan item | Predicted (arm64) | Measured (arm64) | Verdict |
|---|---|---|---|
| 1. No exceptions | Unwind tables gone, ~360 KB | −338 KB; 64 KB remain | **Partly met** |
| 2. Hidden visibility | `.dynsym` ~10 KB, `.dynstr` ~20 KB | As found 57 + 107 KB; now 7 + 4 KB | **Met only now** |
| 3. `MA_NO_VORBIS` | −100 to 150 KB `.text` | 0 B | **Wrong** |
| 3. WAV-only init | (part of the Vorbis saving) | 0 B (armeabi-v7a +16 B) | **No saving** |
| 5. Windows branch | Negligible | 0 B | **Met** |

- **1. No exceptions.** From iteration 1 to as found: `.eh_frame` −257 KB, `.eh_frame_hdr` −42 KB, `.gcc_except_table` −39 KB. The 51 KB + 13 KB that remain belong to the NDK's prebuilt `libc++_static.a` and `libc++abi.a`, which are compiled with exceptions, so our flags cannot reach them. Hiding their exports let the linker drop the unused part (−55 KB). The rest needs a C++ runtime rebuilt with `-fno-exceptions`.
- **2. Hidden visibility.** The flag hides only code compiled with it, so the static C++ runtime still exported 2,061 symbols until `--exclude-libs`. Now there are 20. The dynamic-linking sections are 585 KB smaller than iteration 1, and the whole `.so` 1.94 MB smaller.
- **3. `MA_NO_VORBIS`.** A build with only that define removed is byte-identical to now (2,233,704 B). In miniaudio 0.11.25, `MA_HAS_VORBIS` is defined only when `STB_VORBIS_INCLUDE_STB_VORBIS_H` is, so Vorbis was never compiled in. The define stays as a statement of intent.
- **3. WAV-only init.** With Vorbis, MP3 and FLAC all absent, WAV was already the only stock decoder left to probe.
- **5. Windows branch.** It was compiled out already.

### Charts

<svg viewBox="0 0 760 260" width="760" role="img" aria-label="Stripped libwf_game.so, per ABI" style="max-width:100%;height:auto;font-family:system-ui,sans-serif;font-size:13px">
<text x="0" y="18" font-weight="600" font-size="15" fill="currentColor">Stripped libwf_game.so, per ABI</text>
<rect x="0" y="30" width="12" height="12" fill="#9aa0a6"/><text x="17" y="40" fill="currentColor">Iteration 1 (rebuilt today)</text>
<rect x="228" y="30" width="12" height="12" fill="#5b8def"/><text x="245" y="40" fill="currentColor">As found (934583ee, April)</text>
<rect x="449" y="30" width="12" height="12" fill="#1b9e77"/><text x="466" y="40" fill="currentColor">Now (+ hidden runtime exports)</text>
<line x1="150.0" y1="52" x2="150.0" y2="216" stroke="currentColor" stroke-opacity="0.15"/>
<text x="150.0" y="232" text-anchor="middle" fill="currentColor" fill-opacity="0.75">0</text>
<line x1="265.6" y1="52" x2="265.6" y2="216" stroke="currentColor" stroke-opacity="0.15"/>
<text x="265.6" y="232" text-anchor="middle" fill="currentColor" fill-opacity="0.75">1</text>
<line x1="381.1" y1="52" x2="381.1" y2="216" stroke="currentColor" stroke-opacity="0.15"/>
<text x="381.1" y="232" text-anchor="middle" fill="currentColor" fill-opacity="0.75">2</text>
<line x1="496.7" y1="52" x2="496.7" y2="216" stroke="currentColor" stroke-opacity="0.15"/>
<text x="496.7" y="232" text-anchor="middle" fill="currentColor" fill-opacity="0.75">3</text>
<line x1="612.2" y1="52" x2="612.2" y2="216" stroke="currentColor" stroke-opacity="0.15"/>
<text x="612.2" y="232" text-anchor="middle" fill="currentColor" fill-opacity="0.75">4</text>
<text x="410.0" y="252" text-anchor="middle" fill="currentColor">Size (MB, 10⁶ bytes)</text>
<text x="140" y="91.0" text-anchor="end" font-weight="600" fill="currentColor">arm64-v8a</text>
<rect x="150" y="56" width="482.0" height="18" rx="2" fill="#9aa0a6"/>
<text x="638.0" y="69" fill="currentColor">4.17</text>
<rect x="150" y="78" width="315.0" height="18" rx="2" fill="#5b8def"/>
<text x="471.0" y="91" fill="currentColor">2.73</text>
<rect x="150" y="100" width="258.1" height="18" rx="2" fill="#1b9e77"/>
<text x="414.1" y="113" fill="currentColor">2.23</text>
<text x="140" y="173.0" text-anchor="end" font-weight="600" fill="currentColor">armeabi-v7a</text>
<rect x="150" y="138" width="364.7" height="18" rx="2" fill="#9aa0a6"/>
<text x="520.7" y="151" fill="currentColor">3.16</text>
<rect x="150" y="160" width="257.8" height="18" rx="2" fill="#5b8def"/>
<text x="413.8" y="173" fill="currentColor">2.23</text>
<rect x="150" y="182" width="218.2" height="18" rx="2" fill="#1b9e77"/>
<text x="374.2" y="195" fill="currentColor">1.89</text>
<line x1="150" y1="52" x2="150" y2="216" stroke="currentColor" stroke-opacity="0.6"/>
</svg>

<svg viewBox="0 0 760 342" width="760" role="img" aria-label="Release APK, per app" style="max-width:100%;height:auto;font-family:system-ui,sans-serif;font-size:13px">
<text x="0" y="18" font-weight="600" font-size="15" fill="currentColor">Release APK, per app</text>
<rect x="0" y="30" width="12" height="12" fill="#9aa0a6"/><text x="17" y="40" fill="currentColor">Iteration 1 (rebuilt today)</text>
<rect x="228" y="30" width="12" height="12" fill="#5b8def"/><text x="245" y="40" fill="currentColor">As found (934583ee, April)</text>
<rect x="449" y="30" width="12" height="12" fill="#1b9e77"/><text x="466" y="40" fill="currentColor">Now (+ hidden runtime exports)</text>
<line x1="150.0" y1="52" x2="150.0" y2="298" stroke="currentColor" stroke-opacity="0.15"/>
<text x="150.0" y="314" text-anchor="middle" fill="currentColor" fill-opacity="0.75">0</text>
<line x1="240.4" y1="52" x2="240.4" y2="298" stroke="currentColor" stroke-opacity="0.15"/>
<text x="240.4" y="314" text-anchor="middle" fill="currentColor" fill-opacity="0.75">2</text>
<line x1="330.9" y1="52" x2="330.9" y2="298" stroke="currentColor" stroke-opacity="0.15"/>
<text x="330.9" y="314" text-anchor="middle" fill="currentColor" fill-opacity="0.75">4</text>
<line x1="421.3" y1="52" x2="421.3" y2="298" stroke="currentColor" stroke-opacity="0.15"/>
<text x="421.3" y="314" text-anchor="middle" fill="currentColor" fill-opacity="0.75">6</text>
<line x1="511.7" y1="52" x2="511.7" y2="298" stroke="currentColor" stroke-opacity="0.15"/>
<text x="511.7" y="314" text-anchor="middle" fill="currentColor" fill-opacity="0.75">8</text>
<line x1="602.2" y1="52" x2="602.2" y2="298" stroke="currentColor" stroke-opacity="0.15"/>
<text x="602.2" y="314" text-anchor="middle" fill="currentColor" fill-opacity="0.75">10</text>
<text x="410.0" y="334" text-anchor="middle" fill="currentColor">Size (MB, 10⁶ bytes); both ABIs in every APK</text>
<text x="140" y="91.0" text-anchor="end" font-weight="600" fill="currentColor">condo</text>
<rect x="150" y="56" width="169.2" height="18" rx="2" fill="#9aa0a6"/>
<text x="325.2" y="69" fill="currentColor">3.74</text>
<rect x="150" y="78" width="127.7" height="18" rx="2" fill="#5b8def"/>
<text x="283.7" y="91" fill="currentColor">2.82</text>
<rect x="150" y="100" width="116.7" height="18" rx="2" fill="#1b9e77"/>
<text x="272.7" y="113" fill="currentColor">2.58</text>
<text x="140" y="173.0" text-anchor="end" font-weight="600" fill="currentColor">aquarium</text>
<rect x="150" y="138" width="168.4" height="18" rx="2" fill="#9aa0a6"/>
<text x="324.4" y="151" fill="currentColor">3.72</text>
<rect x="150" y="160" width="126.9" height="18" rx="2" fill="#5b8def"/>
<text x="282.9" y="173" fill="currentColor">2.81</text>
<rect x="150" y="182" width="115.9" height="18" rx="2" fill="#1b9e77"/>
<text x="271.9" y="195" fill="currentColor">2.56</text>
<text x="140" y="255.0" text-anchor="end" font-weight="600" fill="currentColor">snowgoons</text>
<rect x="150" y="220" width="491.1" height="18" rx="2" fill="#9aa0a6"/>
<text x="647.1" y="233" fill="currentColor">10.86</text>
<rect x="150" y="242" width="449.6" height="18" rx="2" fill="#5b8def"/>
<text x="605.6" y="255" fill="currentColor">9.94</text>
<rect x="150" y="264" width="438.6" height="18" rx="2" fill="#1b9e77"/>
<text x="594.6" y="277" fill="currentColor">9.70</text>
<line x1="150" y1="52" x2="150" y2="298" stroke="currentColor" stroke-opacity="0.6"/>
</svg>

Every bar is labelled with its value, in decimal MB. Grey is iteration 1, rebuilt from today's source. Blue is the state found today (iteration 2 as shipped in April). Green is now.

## 3. What stays exported, and why

`llvm-nm -D --defined-only` on the release library, for both ABIs, lists exactly these 20 symbols. `tests/test_android_size_trim.py` fails if the list changes.

| Symbol | Looked up by name? | Why it is visible |
|---|---|---|
| `ANativeActivity_onCreate` | **Yes** | NativeActivity finds it with `dlsym()` |
| `android_main` | No | Kept by convention |
| 7 `WFAndroid*` functions | No | The plan's HAL exports |
| 11 lifecycle and asset functions | No | The plan's HAL exports |

- **`ANativeActivity_onCreate`.** `android.app.NativeActivity` loads `libwf_game.so` (manifest `android.app.lib_name` = `wf_game`) and looks this name up with `dlsym()`. It lives in the NDK's `android_native_app_glue.c`, which we don't modify, so `-Wl,--export-dynamic-symbol=ANativeActivity_onCreate` exports it and `-u` keeps `--gc-sections` from dropping it.
- **`android_main`.** The glue calls it directly (`android_native_app_glue.c:226`), not by name. It stays exported as the plan and the NDK convention have it.
- **`WFAndroid*`.** `WFAndroidEglInit`, `WFAndroidEglTerm`, `WFAndroidSetHudEnabled`, `WFAndroidGetAssetManager`, `WFAndroidHasWindow`, `WFAndroidPumpEvents` and `WFAndroidPhoneOverlayRects`: window, EGL, assets, the event pump and the phone-overlay rectangles.
- **`HAL*` / `*HostGLContext`.** `HALCreateAAssetAccessor`, `HALNotifySuspend`, `HALNotifyResume`, `HALIsSuspended`, `HALPumpSuspendedEvents`, `HALWindowCloseRequested`, `HALCloseWindow`, `HALRequestClose`, `SetHostGLContext`, `GetHostGLContext` and `ClearHostGLContext`: lifecycle and asset-accessor calls.

No code in the tree calls `dlsym()` or `RegisterNatives`. There are no JNI `Java_*` functions, and the only Java class (`LogViewerActivity`) declares no `native` methods. So `ANativeActivity_onCreate` is the only symbol another component needs to find by name. The other 19 are kept only because the plan specifies them. They cost about 0.5 KB, and hiding them is a decision for later, not a size lever.

**The phone controller** (`hal/phonepad/`: the POSIX socket server, the controller page, the QR overlay and the vendored `qrcodegen`) is linked into `wf_game` directly. It has no `try`, `throw` or `catch`, and nothing in it is looked up by name. It compiled, linked for both ABIs and served its page on the device.

**Left untouched:**

- **`-fno-rtti`**: out of scope. It fails to compile against the engine's `dynamic_cast` sites (the plan counted 50+), and replacing them with a type tag is a separate refactor.
- **Audio formats**: SFX stay WAV, linear PCM or IMA ADPCM, decoded by dr_wav. Vorbis stays off. Music stays MIDI + SF2 through TinySoundFont.
- **Non-Android builds**: the link flags sit inside `if(ANDROID)` and apply only to Clang Release. The `buffer.cc` change applies everywhere, but it decodes every WAV to identical frames (the harness proves this) and rejects every non-WAV as before. The Linux `task build` compiled it cleanly.

## 4. How it was measured (copy-paste)

Release APKs. `task build-apk` needs sudo for its SDK step on this machine, so call Gradle directly:

```bash
cd ~/WorldFoundry-wbniv/android
ANDROID_HOME=$HOME/android-sdk-local ./gradlew :app:assembleCondoRelease :app:assembleAquariumRelease \
  :app:assembleSnowgoonsRelease \
  -x lintVitalAnalyzeSnowgoonsRelease -x lintVitalReportSnowgoonsRelease -x lintVitalSnowgoonsRelease
# (the snowgoons lint tasks are skipped because a gitignored soundfont is absent on this machine)
```

Sizes and sections:

```bash
NDK=$HOME/android-sdk-local/ndk/26.2.11394342/toolchains/llvm/prebuilt/linux-x86_64/bin
APK=app/build/outputs/apk/condo/release/worldfoundry-condo-release.apk
stat -c%s "$APK"
unzip -v "$APK" | grep libwf_game.so                     # per-ABI length and compressed size
for abi in arm64-v8a armeabi-v7a; do
  SO=$(ls app/build/intermediates/stripped_native_libs/condoRelease/*/out/lib/$abi/libwf_game.so)
  stat -c%s "$SO"
  $NDK/llvm-size -A "$SO"                                # .text .eh_frame .gcc_except_table .dynsym ...
  $NDK/llvm-nm -D --defined-only "$SO" | wc -l           # exported symbols
  $NDK/llvm-readelf -d "$SO" | grep NEEDED
done
```

The iteration‑1 counterfactual is a CMake configure identical to Gradle's, from `android/app/.cxx/Release/*/<abi>/metadata_generation_command.txt`, plus a launcher on every compile and link. The launcher drops `-fvisibility=hidden -fno-exceptions -fno-unwind-tables -fno-asynchronous-unwind-tables -Wl,--exclude-libs,*` and compiles a copy of `miniaudio_impl.cc` without `#define MA_NO_VORBIS`. A second mode drops only `MA_NO_VORBIS`; a third passes everything through, as the method check. The scripts were session scratch and are not committed, so here is the core:

```bash
# launcher.sh — CMAKE_{C,CXX}_COMPILER_LAUNCHER and CMAKE_{C,CXX}_LINKER_LAUNCHER
out=(); for a in "$@"; do case "$a" in
  -fvisibility=hidden|-fno-exceptions|-fno-unwind-tables|-fno-asynchronous-unwind-tables|-Wl,--exclude-libs,*) ;;
  */audio/linux/miniaudio_impl.cc) sed '/#define MA_NO_VORBIS/d' "$a" > /tmp/mi.cc; out+=(/tmp/mi.cc) ;;
  *) out+=("$a") ;; esac; done; exec "${out[@]}"

SDK=$HOME/android-sdk-local; NDKR=$SDK/ndk/26.2.11394342
$SDK/cmake/3.22.1/bin/cmake -H. -Bbuild-iter1-arm64 -GNinja -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_SYSTEM_NAME=Android -DCMAKE_SYSTEM_VERSION=21 -DANDROID_PLATFORM=android-21 \
  -DANDROID_ABI=arm64-v8a -DCMAKE_ANDROID_ARCH_ABI=arm64-v8a -DANDROID_NDK=$NDKR -DCMAKE_ANDROID_NDK=$NDKR \
  -DCMAKE_TOOLCHAIN_FILE=$NDKR/build/cmake/android.toolchain.cmake -DCMAKE_MAKE_PROGRAM=$SDK/cmake/3.22.1/bin/ninja \
  -DCMAKE_CXX_COMPILER_LAUNCHER=$PWD/launcher.sh -DCMAKE_C_COMPILER_LAUNCHER=$PWD/launcher.sh \
  -DCMAKE_CXX_LINKER_LAUNCHER=$PWD/launcher.sh -DCMAKE_C_LINKER_LAUNCHER=$PWD/launcher.sh
$SDK/cmake/3.22.1/bin/ninja -C build-iter1-arm64 wf_game
$NDKR/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip --strip-unneeded \
  -o libwf_game.iter1.so "$(find build-iter1-arm64 -name libwf_game.so)"   # what AGP's strip step does
```

## 5. Risks and what was verified

| Check | Result | Evidence |
|---|---|---|
| Release build, both ABIs, three apps | **PASS** | `BUILD SUCCESSFUL`; no warnings or errors in the Gradle logs |
| APK contents | **PASS** | Same entry lists before and after (50, 49 and 49 entries) |
| `NEEDED` libraries | **PASS** | Same 8 system libraries, both ABIs |
| Export set | **PASS** | Exactly the 20 in §3, both ABIs |
| Size-trim tests | **PASS** | 9 passed |
| Phone-controller and app tests | **PASS** | 179 passed (see the note below) |
| Clean rerun of both sets | **PASS** | 188 passed |
| Linux build | **PASS** | Changed `buffer.cc` compiles; `wf_game` links |
| Condo release on the Chromecast HD | **PASS** | Details below the commands |
| Snowgoons sideload (plan step 5) | **PENDING** | The user's own check |

The commands:

```bash
# Release build, both ABIs, three apps (in android/)
ANDROID_HOME=$HOME/android-sdk-local ./gradlew \
  :app:assembleCondoRelease :app:assembleAquariumRelease :app:assembleSnowgoonsRelease \
  -x lintVitalAnalyzeSnowgoonsRelease -x lintVitalReportSnowgoonsRelease -x lintVitalSnowgoonsRelease
# APK contents
diff <(unzip -Z1 before/worldfoundry-condo-release.apk | sort) \
     <(unzip -Z1 after/worldfoundry-condo-release.apk | sort)
# NEEDED libraries, export set
llvm-readelf -d libwf_game.so | grep NEEDED; llvm-nm -D --defined-only libwf_game.so
# Size-trim tests (decoder-equivalence harness for PCM / IMA ADPCM / Ogg / junk; built-.so exports and NEEDED)
python3 -m pytest tests/test_android_size_trim.py -q
# Phone-controller and app tests
python3 -m pytest tests/test_phone_controller.py tests/test_phone_controller_page.py \
  tests/test_phone_controller_android.py tests/test_phone_overlay.py tests/test_phone_qr.py \
  tests/test_aquarium_android.py tests/test_condo_android.py -q
# Clean rerun of both sets
python3 -m pytest tests/test_phone_controller.py tests/test_phone_controller_page.py \
  tests/test_phone_controller_android.py tests/test_phone_overlay.py tests/test_phone_qr.py \
  tests/test_aquarium_android.py tests/test_condo_android.py tests/test_android_size_trim.py -q
# Linux build
task build
# Condo release on the Chromecast HD (armeabi-v7a)
ADB=$HOME/android-sdk-local/platform-tools/adb bash scripts/android-device-run.sh \
  --app condo --release --seconds 8 192.168.4.38:41447
```

The device run:

- installed and launched in 487 ms
- process alive after 8 s, with no crash lines in logcat
- `EGL ready`
- `phonepad: listening on 192.168.4.38:8765`
- the "Use your phone as the controller" panel on screen, with its QR code and logo
- median frame 16.7 ms (59.9 fps)
- PSS 49,152 KB
- the controller page answered `200` (17,826 B) to an HTTP fetch from this PC
- no key events sent

Note on the 179: the first run failed one test, `test_built_aquarium_apk_contents`. It compares the **debug** aquarium APK's `cd.iff` with `wflevels/aquarium-cd.iff`, and another session had rebuilt that bundle (content commit `ace2e0be`) after the debug APK was built. Rebuilding the debug APK (`:app:assembleAquariumDebug`) fixed it, and nothing in this change was involved.

**Residual risk:** a component that resolved one of the now-hidden C++ runtime symbols by name would fail at run time, not at link time. No such component exists: the APK has one native library, and the device run exercised start-up, EGL, assets, the event pump and the phone-pad server. Snowgoons and aquarium were not launched on the device this time, but they run the same library.

## 6. What is left

- **Plan verification step 5** (sideload snowgoons through Drive: icon, music, physics, touch HUD) is the user's own check and is **still pending**. The condo device run above covers the same library on the Chromecast HD.
- **Remaining unwind data (about 64 KB on arm64)** comes from the prebuilt NDK C++ runtime. Removing it would need a libc++ built with `-fno-exceptions`: a toolchain project, not a flag.
- **The 19 extra exports** could be hidden, leaving only `ANativeActivity_onCreate` (and `android_main`). That would save under 1 KB, so it is not worth the risk without a reason.
- **`-fno-rtti`**: a type-tag refactor first (see the plan).
- **Retiring dr_wav** once SFX move onto the SF2/TinySoundFont path: an architecture change, out of scope (see the plan's design decisions).
- **The April report's subsystem table** credits `MA_NO_VORBIS` with −153 KB of miniaudio `.text`. That figure is the visibility and exceptions flags at work; a correction note now sits there.

## Appendix: raw measurements

`llvm-size -A` and `llvm-nm -D` per build. Tags: `iter1` = counterfactual, `before` = as found, `decoder` = as found + `b40acc9c`, `after` = `f619a5eb`, `vorbis` = after with only `MA_NO_VORBIS` removed (arm64 only).

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

== iter1 arm64-v8a: llvm-size -A (selected)
.dynsym                  166248       760
.gnu.hash                 49392    180960
.hash                     55424    230352
.dynstr                  327434    285776
.rela.dyn                175704    613216
.gcc_except_table         58696    826216
.rodata                  138392    884912
.eh_frame_hdr             58452   1023304
.eh_frame                355948   1081760
.text                   2619188   1437712
.data.rel.ro              60016   4085904
.bss                     362800   4177520
Total                   4531723
== iter1 armeabi-v7a: llvm-size -A (selected)
.dynsym                  110880       528
.gnu.hash                 49420    125364
.hash                     55448    174784
.dynstr                  327467    230232
.rel.dyn                  59344    557700
.ARM.exidx                48096    617044
.ARM.extab                77500    677956
.rodata                  127404    755456
.text                   2199304    882864
.data.rel.ro              30560   3111936
.bss                     323968   3162624
Total                   3478298
== before arm64-v8a: llvm-size -A (selected)
.dynsym                   57168       760
.gnu.hash                 14416     62792
.hash                     19064     77208
.dynstr                  106615     96272
.rela.dyn                158280    202888
.gcc_except_table         20000    376048
.rodata                  131065    396048
.eh_frame_hdr             16148    527116
.eh_frame                 98692    543264
.text                   1999524    641968
.data.rel.ro              56736   2655552
.bss                     315536   2732320
Total                   3039251
== before armeabi-v7a: llvm-size -A (selected)
.dynsym                   38112       528
.gnu.hash                 14424     43500
.hash                     19064     57924
.dynstr                  106598     76988
.rel.dyn                  53256    183588
.ARM.exidx                12000    236844
.ARM.extab                31272    253804
.rodata                  120352    285080
.text                   1775296    405440
.data.rel.ro              28776   2194784
.bss                     277792   2237568
Total                   2507077
== after arm64-v8a: llvm-size -A (selected)
.dynsym                    7104       760
.gnu.hash                   148      8552
.hash                      2376      8700
.dynstr                    3958     11076
.rela.dyn                128088     15040
.gcc_except_table         13160    149776
.rodata                  125401    162944
.eh_frame_hdr              8340    288348
.eh_frame                 50784    296688
.text                   1821308    347472
.data.rel.ro              45768   2177344
.bss                     314192   2239712
Total                   2545310
== after armeabi-v7a: llvm-size -A (selected)
.dynsym                    4736       528
.gnu.hash                   148      5952
.hash                      2376      6100
.dynstr                    3923      8476
.rel.dyn                  43192     12400
.ARM.exidx                 6376     55592
.ARM.extab                14352     64176
.rodata                  115112     78528
.text                   1656752    193648
.data.rel.ro              23272   1858944
.bss                     277632   1894512
Total                   2163858
== after arm64-v8a: llvm-nm -D --defined-only
00000000000a6578 T ANativeActivity_onCreate
00000000000aaadc T ClearHostGLContext
00000000000aaad0 T GetHostGLContext
00000000000aaac8 T HALCloseWindow
00000000000ac2f8 T HALCreateAAssetAccessor
00000000000aaa94 T HALIsSuspended
00000000000aaa84 T HALNotifyResume
00000000000aaa70 T HALNotifySuspend
00000000000aaabc T HALPumpSuspendedEvents
00000000000aaae0 T HALRequestClose
00000000000aaac0 T HALWindowCloseRequested
00000000000aaacc T SetHostGLContext
00000000000ac344 T WFAndroidEglInit
00000000000ac6f8 T WFAndroidEglTerm
000000000009a444 T WFAndroidGetAssetManager
000000000009a450 T WFAndroidHasWindow
000000000009a650 T WFAndroidPhoneOverlayRects
000000000009a45c T WFAndroidPumpEvents
00000000000ac750 T WFAndroidSetHudEnabled
000000000009a730 T android_main
```

APK sizes and per-ABI library entries (`unzip -v`: length / deflated):

```
before condo 2824830 B
    2726312 1154414 lib/arm64-v8a/libwf_game.so
    2230976 1191678 lib/armeabi-v7a/libwf_game.so
    2422784 138595 assets/cd.iff
    17826 6984 assets/controller.html
    648 295 assets/layout.json
    131 62 assets/wf_args.txt
before aquarium 2806439 B
    2726312 1154414 lib/arm64-v8a/libwf_game.so
    2230976 1191678 lib/armeabi-v7a/libwf_game.so
    186368 42139 assets/cd.iff
    17826 6984 assets/controller.html
    376 226 assets/layout.json
before snowgoons 9943169 B
    2726312 1154414 lib/arm64-v8a/libwf_game.so
    2230976 1191678 lib/armeabi-v7a/libwf_game.so
    1384448 249692 assets/cd.iff
    7842132 6678164 assets/florestan-subset.sf2
    7590 7590 assets/level0.mid
after condo 2581660 B
    2233704 1025989 lib/arm64-v8a/libwf_game.so
    1887912 1076925 lib/armeabi-v7a/libwf_game.so
    2422784 138595 assets/cd.iff
    17826 6984 assets/controller.html
    648 295 assets/layout.json
    131 62 assets/wf_args.txt
after aquarium 2563780 B
    2233704 1025989 lib/arm64-v8a/libwf_game.so
    1887912 1076925 lib/armeabi-v7a/libwf_game.so
    188416 42655 assets/cd.iff
    17826 6984 assets/controller.html
    376 226 assets/layout.json
after snowgoons 9699996 B
    2233704 1025989 lib/arm64-v8a/libwf_game.so
    1887912 1076925 lib/armeabi-v7a/libwf_game.so
    1384448 249692 assets/cd.iff
    7842132 6678164 assets/florestan-subset.sf2
    7590 7590 assets/level0.mid
iter1 (derived): before + (deflate6(iter1 arm64) 1658086 - 1154414) + (deflate6(iter1 v7a) 1606080 - 1191678) = before + 918074
```
