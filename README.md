# WorldFoundry Project Status

**As of:** 2026-04-19  
**Branch:** `2026-android`

---

## Summary

Eight days of work (2026-04-12 – 2026-04-19). Newest first:

**Blender round-trip reaches gameplay (2026-04-19)** — Four exporter fixes (unrotated BOX3, gated Mesh Name, preserved authored BOX3, enum-label import) take `snowgoons-blender.iff` through load, physics, scripts, audio, REST API, and into per-frame enemy-AI execution before a `statplat` assertion at ~5 s that still likely stems from levcomp-rs's Phase-2c dummy-channel stub (real path keyframes not yet serialized, pathCount=1 + chanCount=1 vs the original's 1 + 6) — see plan [blender-level-roundtrip](docs/plans/2026-04-16-blender-level-roundtrip.md).

**Android port closure (2026-04-18)** — Branch hits its close criterion (polished sideloadable APK) with only launcher icons + one stale `build.gradle.kts` comment left and Play Store / keystore / R8 / splash explicitly out of scope — see [closure audit](docs/investigations/2026-04-18-android-port-closure.md).

**Android audio — Für Elise on snowgoons (2026-04-18)** — Desktop miniaudio + TinySoundFont ports to Android as-is via an `HALGetAssetAccessor()` memory loader (`audio_stub.cc` retired, `music.cc` reworked); follow-up plan [audio-assets-from-iff](docs/plans/2026-04-18-audio-assets-from-iff.md) routes audio through `cd.iff` like every other asset class.

**Android post-boot polish (2026-04-18)** — Snowgoons is a fully playable APK on stock arm64: viewport/projection aspect from real EGL surface (`aebbb15`), pause/resume preserving EGL context + events-during-suspend (`0b19119`), zForth `here` bootstrap fix for `if/else/then` (`62451a1`), and an on-screen d-pad + A/B HUD (`c20e56e`, TV-mode suppressed).

**Snowgoons rendering on Android phone (2026-04-18)** — Phase 3 step 7 ✅: sideloaded debug APK boots snowgoons on physical arm64 via `NativeActivity` + EGL 3.0 + `AAssetManager`-backed `cd.iff`, unblocked by four pre-flight fixes (Forth shell bootstrap, graceful missing-engine no-op, 4096² framebuffer cap, GLSL ES `int` precision) and on-device `wf.log` since `adb logcat` wasn't reachable.

**Snowgoons joystick control restored (2026-04-17)** — On-disk `snowgoons.iff`/`cd.iff` still had the pre-`671de1e` `?cam`-helper director that zForth's minimal bootstrap couldn't compile; byte-preserving re-patch (`a7ef46e`) landed the inlined three-block form the current `patch_snowgoons_forth.py` produces.

**Window-close shutdown stability (2026-04-17)** — `mesa.cc` now handles `WM_DELETE_WINDOW` and `rest_api.cc` registers `RestApi_Stop` via `sys_atexit`; X11 close button exits cleanly instead of aborting.

**Graphics — retire immediate-mode GL / Android Phase 0 (2026-04-18, complete)** — Modern VBO + GLSL 330 / GLES 300 es shader backend is the sole GL path on Linux and Android (legacy fixed-function retired at `ff589c8`, **−541 LOC** net across 16 files; tag `pre-legacy-gl-retire` at `807d1ea` preserves the last `backend_legacy.cc` commit).

**Audio (Phases 1–5 complete) (2026-04-17)** — miniaudio + TinySoundFont vendored with per-level `level<N>.mid` music, fire-and-forget SFX, and 3D positional playback audible in snowgoons, but only via `scripting_lua.cc` closures — mailbox-wired audio API for the other seven engines is deferred.

**Android port (Phases 0+1+2 complete; Phase 3 steps 1–6 done) (2026-04-18)** — Phase 0 retired legacy GL, Phases 1+2 landed CMake+NDK build / HAL lifecycle seam / AssetAccessor, and Phase 3 added `NativeActivity` + EGL 3.0, a Gradle project (AGP 8.5.2, leanback manifest, arm64-v8a, min 21 / target 34), gamepad + touch with TV-mode detection, and `AAssetManager`-backed `cd.iff` — only step 7 (device smoke test) remained at the time, since closed.

**Blender ↔ level round-trip (2026-04-17)** — `levcomp-rs` compiles `.lev` → `.lvl` end-to-end and the Blender plugin round-trips 152/152 OAD fields with Phase 2c mesh bboxes / packed asset IDs / `asset.inc` landed — real path/channel keyframes are the last remaining piece.

**Level pipeline proof (2026-04-17, in progress)** — Phases A+B+C done (`primitives.lev`/`whitestar.lev` compile through the pipeline; `wf_oad` has a `common.oad` fixture test; `levcomp decompile` round-trips snowgoons' 36 objects with an 8-byte common-block delta), with D–E (decompile 4 source-less levels, multi-level `cd.iff`) gating the `common.inc` rearrangement the deferred ScriptLanguage OAD plan needs.

**Tooling and plans (2026-04-17)** — `engine/` reorganised to top-level; REST API box PoC landed; iOS plan written (blocked on Android); CLI level override (`-L<path>`) confirmed; IFF lineage + MIDI-source investigations filed.

**Scripting system (2026-04-16)** — Seven engines smoke-tested end-to-end in snowgoons (Lua 5.4, Fennel, QuickJS, JerryScript, WAMR, Wren, zForth) with Lua optional (`WF_LUA_ENGINE=lua54|none`) and wasm3 retired in favour of WAMR — five alternate Forth backends build+link but aren't end-to-end tested, WAMR AOT deferred.

**Dead-code removal (2026-04-15, closed 2026-04-18)** — Batches 1–7 complete (`wfsource/source/` 64,252 → 36,199 lines, −43.7%) with Batch 8 (`physics/wf/`, ~1,700 LOC) deferred until Jolt parity on a second level and `hal/_list` / `_mempool` migration left as future opt-in.

**Jolt Physics (2026-04-14)** — Integrated as default (`WF_PHYSICS_ENGINE=jolt`) with the five-step plan complete (SIGABRT, zombie bodies, authority model, vertical pop, 60 s soak); legacy `physics/wf/` retained until parity on a second level.

**Steam (Phases 1+2) (2026-04-12)** — Steamworks SDK lifecycle wired into HAL + `PageFlip` with Steam Input ORing into `_JoystickButtonsF` each frame (`WF_ENABLE_STEAM=1`; SDK not committed); Phases 3 (depot) and 4 (store page) deferred.

---

## Plans

### Active

| Date | Plan | Status | Summary |
|------|------|--------|---------|
| 2026-04-16 | [Plan: git-branch-browser — curses TUI for browsing branch diffs](docs/plans/2026-04-16-git-branch-browser.md) | **In testing** | **Goal:** A Python curses program at `scripts/git-branch-browser.py` that lets you browse all git branches, see per-branch changed files as a collapsible directory tree with status annotations, and view file diffs inline. Implementation landed (~784 LOC); currently in user testing. |
| 2026-04-16 | [Plan: Blender ↔ Level Round-Trip](docs/plans/2026-04-16-blender-level-roundtrip.md) | **In progress — step 6 🟡** | Steps 1–5 complete (levcomp-rs pipeline, 152/152 OAD fields, Z-up coordinate fix).  2026-04-19: four exporter fixes (unrotated BOX3, gated Mesh Name, preserved authored BOX3, enum-label import) take `snowgoons-blender.iff` through full init + into per-frame enemy-AI execution; asserts on `Cannot generate or move a statplat at runtime` at ~5 s.  Likely root cause is levcomp-rs's Phase-2c dummy-channel stub — Blender emits real PATH/CHAN text but levcomp-rs drops it (LVL pathCount=1 + chanCount=1 vs original 1 + 6), so snowman01's runtime position drifts ~0.15 m and it collides with the player on the first tick.  Unblocks the deferred `ScriptLanguage` OAD plan once stable. |
| 2026-04-17 | [Plan: Prove all 7 level pipelines before breaking common.inc](docs/plans/2026-04-17-level-pipeline-proof.md) | **In progress — Phases A+B done** | Phase A (`534ead7`): `primitives.lev` + `whitestar.lev` compile through `iffcomp-rs` → `levcomp-rs` (skips OBJ chunks with no Class Name — Max aim-point helpers). Phase B: `wf_oad/tests/fixtures/common.oad` committed; `parse_common_oad` test asserts 14 entries + `Script` field; 6 tests pass. Phases C (decompile subcommand), D (4 source-less levels), E (multi-level `cd.iff`) remaining before the gated common.inc rearrangement that unblocks the ScriptLanguage OAD plan. |

### Backlog

| Date | Plan | Status | Summary |
|------|------|--------|---------|
| 2026-04-18 | [Plan: Android launcher polish — adaptive-icon XML](docs/plans/2026-04-18-android-launcher-polish.md) | **Not started** | **Goal:** Layer `res/mipmap-anydpi-v26/ic_launcher.xml` adaptive-icon XML on top of the legacy mipmap PNGs that just landed, so Android 8+ renders rounded / themed / dynamic-shape forms via foreground + background drawables. Carry-over from the Android port closure audit. |
| 2026-04-18 | [Plan: audio assets from iff](docs/plans/2026-04-18-audio-assets-from-iff.md) | **Not started** | **Goal:** retire every filesystem / loose-file audio loader — MIDI, soundfont, SFX all come through `cd.iff` / `level<N>.iff` chunks like meshes and textures already do. Current `loadAssetBytes(path)` path stays behind a `-DWF_AUDIO_DEV_LOOSE_FILES=1` opt-in for iteration. Requires new IFF chunk tags (MIDI/SFNT/SFX) + `iffcomp-rs` + `levcomp-rs` + Blender plugin updates. Unblocks the iOS port from needing its own asset-bundling pipeline. |
| 2026-04-17 | [Plan: Steam release](docs/plans/2026-04-17-steam.md) | **In progress — Phases 1+2 done** | Steamworks SDK lifecycle wired into HAL + PageFlip. Steam Input → `EJ_BUTTONF_*` merged in `_JoystickButtonsF`. `WF_ENABLE_STEAM=1` build flag; SDK not committed (see vendor README). Phases 3 (depot) and 4 (store page) deferred. |
| 2026-04-17 | [Plan: Mailbox-wired audio API](docs/plans/deferred/2026-04-17-audio-mailbox-api.md) | **Not started** | **Goal:** Every scripting engine can trigger music + SFX via mailbox writes. `EMAILBOX_SOUND=3017` enum and OAD `sfx0..sfx127` asset slots still exist; handler + slot loader were deleted in the `460a3fd` dead-code sweep (pre-cleanup impl was Linux-stubbed). Phase A: restore `_sfx[128]` loader + `EMAILBOX_SOUND` handler that plays at the actor's position. Phase B: `MUSIC_PLAY`/`MUSIC_STOP`/`MUSIC_VOLUME` mailboxes; Lua closures become forwarders. Phase C (opt): named `SFX_*` constants. |
| 2026-04-16 | [ScriptLanguage OAD field](docs/plans/2026-04-16-script-language-oad-field.md) | **Deferred — blocked on Blender+levcomp-rs level round-trip** | Field added then reverted from `common.oad` to restore binary layout compat with existing compiled levels. Dispatch table + language param threading remain in engine (passing 0=Lua). Will re-introduce once all levels compile through Blender+levcomp-rs. |
| 2026-04-16 | [Plan: iOS port](docs/plans/2026-04-16-ios-port.md) | **Backlog — blocked on lack of a Mac** | **Goal:** An IPA that runs snowgoons on a tethered iPhone, installed via Xcode with a developer profile. Proof-of-viability, not a shipping product. Xcode + signing + device provisioning all require macOS; Android prerequisite already satisfied. |

### Complete

| Date | Plan | Status | Summary |
|------|------|--------|---------|
| 2026-04-16 | [Plan: Android port](docs/plans/2026-04-16-android-port.md) | **Closed 2026-04-18** | Phases 0+1+2 + Phase 3 steps 1–7 all landed: legacy GL retired (`ff589c8`, `pre-legacy-gl-retire` tag at `807d1ea`), CMake+NDK build, HAL lifecycle seam, AssetAccessor, `NativeActivity` + EGL 3.0, Gradle project (AGP 8.5.2, leanback, arm64-v8a, min 21 / target 34), gamepad + touch with TV-mode detection, `AAssetManager`-backed `cd.iff`, on-device smoke test on arm64 phone. Post-boot polish shipped (viewport aspect, pause/resume EGL preservation, zForth `here` director fix, on-screen touch HUD). Remaining polish tracked as separate plans: [android-launcher-polish](docs/plans/2026-04-18-android-launcher-polish.md) and [audio-assets-from-iff](docs/plans/2026-04-18-audio-assets-from-iff.md). |
| 2026-04-15 | [Dead-code removal](docs/plans/2026-04-15-dead-code-removal.md) | **Closed 2026-04-18** | Batches 1–7 landed (64,252 → 36,199 LOC, −43.7%). LOC claims verified against git history — Batch 5 `03211f9` shows −20,967 across 208 files; `e2dcc98` milestone records the 36,199 total. Batch 8 (`physics/wf/` deletion, ~1,700 LOC) + `hal/_list`/`_mempool` migration (stretch) accepted at their estimates, deferred to future opportunistic commits. |
| 2026-04-16 | [Plan: Lua engine is not special — make it optional](docs/plans/2026-04-16-lua-not-special.md) | **Done** | `scripting_lua.cc/hp` extracted; `WF_LUA_ENGINE=lua54\|none` added to `build_game.sh`; all `lua_engine::` calls guarded; Fennel+none warns and forces lua54; stale `scripting_wasm3.hp` include removed. |
| 2026-04-16 | [Engine directory reorganization](docs/plans/2026-04-16-engine-directory-reorganization.md) | **Complete** | `engine/` is now a top-level directory. `wftools/wf_engine/` → `engine/`, `wftools/vendor/` → `engine/vendor/`, `wf_viewer/stubs/` → `engine/stubs/`, `wf_viewer/include/` → `engine/include/`. `wftools/` is now strictly dev tooling. |
| 2026-04-16 | [Finish Jolt physics integration](docs/plans/2026-04-16-jolt-physics-finish.md) | **Complete** | Five-step plan: fix SIGABRT (`JoltSyncFromCharacter`), eliminate zombie kinematic bodies, lock WF↔Jolt authority model, fix 3 m vertical pop (feet vs centre offset), 60 s soak. Player walks on snowgoons floor. |
| 2026-04-15 | [Lua engine fixes (#1–#6)](docs/plans/2026-04-15-lua-engine-fixes.md) | **Complete** | All 6 fixes: script cache, per-actor envs, Fennel precompile, debug gating, stdlib sandbox, coroutine continuations. Smoke-tested 2026-04-16. |
| 2026-04-15 | [Align scripting plans to ScriptRouter](docs/plans/2026-04-15-scripting-plans-align-scriptrouter.md) | **Complete** | Phases A–E complete: all plan docs updated, JS/wasm3 renamed to `js_engine`/`wasm3_engine` namespaces, WAMR/Wren/Forth landed. All engine smoke tests passed 2026-04-16. |
| 2026-04-14 | [WAMR (dev interp + AOT ship)](docs/plans/2026-04-14-wamr-dev-aot-ship.md) | **Complete** | Phase 1 (classic interpreter) landed 2026-04-15; smoke-tested 2026-04-16 (GROUND, no crashes). Phase 2 (AOT) and Phase 3 (w2c2) deferred until ship targets are concrete. |
| 2026-04-14 | [Forth scripting engine](docs/plans/2026-04-14-forth-scripting-engine.md) | **Complete** | All seven phases landed 2026-04-16. All six backends build and link; snowgoons.iff + cd.iff carry Forth scripts (`\ wf` sigil) via byte-preserving patcher. zForth is the default and smoke-tested; the five alternates (ficl, atlast, embed, libforth, pforth) are build-verified but not yet end-to-end smoke-tested. |
| 2026-04-14 | [Pluggable JS engines (QuickJS / JerryScript)](docs/plans/2026-04-14-pluggable-scripting-engine.md) | **Complete** | Both engines landed 2026-04-14 with `js_engine` namespace. QuickJS and JerryScript both smoke-tested 2026-04-16 (snowgoons passes). |
| 2026-04-14 | [Wren scripting engine](docs/plans/2026-04-14-wren-scripting-engine.md) | **Complete** | All phases complete: vendor, plug, dispatch, build, docs, patcher. Smoke-tested 2026-04-16 (GROUND, no crashes). |
| 2026-04-14 | [WebAssembly (wasm3)](docs/plans/2026-04-14-wasm3-scripting-engine.md) | **Retired 2026-04-16** | Initial wasm spike. WAMR reached parity; `engine/vendor/wasm3-v0.5.0/` + `scripting_wasm3.{hp,cc}` deleted. `WF_WASM_ENGINE=wamr` is now the only wasm option. |
| 2026-04-14 | [Fennel on Lua](docs/plans/2026-04-14-fennel-on-lua.md) | **Complete** | Landed 2026-04-14. `;` sigil, sub-dispatch inside `lua_engine`, vendored Fennel 1.6.1, minifier, codegen, snowgoons Fennel scripts. |
| 2026-04-14 | [Vendor Lua 5.4](docs/plans/2026-04-14-vendor-lua.md) | **Complete** | Landed 2026-04-14. Lua 5.4.8 in `engine/vendor/lua-5.4.8/`, compiled directly from source, no system `liblua5.4` dependency. |
| 2026-04-13 | [Lua interpreter spike](docs/plans/2026-04-13-lua-interpreter-spike.md) | **Complete** | Landed 2026-04-13; refactored 2026-04-15 to `lua_engine` namespace in `ScriptRouter`. Snowgoons player + director ported to Lua; player moves, cameras cut. |

---

## Investigations

| Date | Investigation | Status | Summary |
|------|---------------|--------|---------|
| 2026-04-18 | [Android Port — Executable Size and RAM Usage](docs/investigations/2026-04-18-android-port-size-and-ram.md) | **In progress** | **Branch:** 2026-android **Artifact:** `android/app/build/outputs/apk/debug/worldfoundry-debug.apk` **NDK:** 26.2.11394342, arm64-v8a, `-DCMAKE_BUILD_TYPE=RelWithDebInfo`, then stripped by AGP … |
| 2026-04-18 | [Closing the Android Port — Remaining Work](docs/investigations/2026-04-18-android-port-closure.md) | **Playable APK shipped; this doc lists what's left to call it "done."** | **Branch:** 2026-android |
| 2026-04-17 | [IFF format lineage — EA IFF 85, AIFF, RIFF, WorldFoundry IFF](docs/investigations/2026-04-17-iff-format-lineage.md) | **Complete** | Traces all four formats from the common 1985 ancestor. Key findings: AIFF and WF IFF independently arrived at the same solution (bake navigational offsets at write time for slow-media random access); WF uniquely separates interchange (text source) from execution (platform binary); `.align(2048)` maps CD-ROM sectors. Side-by-side comparison table included. |
| 2026-04-16 | [Reverse-engineering the WF binary level format for `levcomp-rs`](docs/investigations/2026-04-16-levcomp-rs-reverse-engineering.md) | **Phase 2c complete** | Binary format fully mapped; Phase 2c (2026-04-17): mesh bbox from MODL/VRTX, packed asset IDs, `asset.inc` output, 37 objects validated. Remaining: real path/channel keyframes. |
| 2026-04-16 | [Coding-conventions remediation](docs/investigations/2026-04-16-coding-conventions-remediation.md) | **In progress** | Audit of 2026-authored code in `wfsource/source/` against `docs/coding-conventions.md`. Honest accounting of where recent additions don't yet follow the rules they propose. |
| 2026-04-15 | [LOC tracking](docs/investigations/2026-04-15-loc-tracking.md) | **Ongoing** | Tracks code line count over time. Dead-code removal took the tree from 64,252 (baseline `74d1a47`) to 36,199 (−43.7%, `e2dcc98` after Batch 7); retiring the legacy `physics/wf/` backend is projected to land the reduction at ~35,113 (−45.3%). Tool: `scripts/loc_report.py`. |
| 2026-04-14 | [Scripting language replacement](docs/investigations/2026-04-14-scripting-language-replacement.md) | **Complete** | Comprehensive survey that recommended Lua 5.4 as the primary engine. Spawned all scripting plans. Decision: Lua won. |
| 2026-04-14 | [Physics engine survey](docs/investigations/2026-04-14-physics-engine-survey.md) | **Complete** | Surveyed Bullet, PhysX, Rapier, Jolt, and others. Recommended **Jolt Physics** (MIT, ~300 KB, `CharacterVirtual`, active upstream). Spawned Jolt integration plan. |
| 2026-04-14 | [Jolt Physics integration](docs/investigations/2026-04-14-jolt-physics-integration.md) | **Functional** | Jolt is the default (`WF_PHYSICS_ENGINE=jolt`); snowgoons is playable. Runtime init/shutdown moved to `WFGame` (`b5dc7fe`). Legacy `physics/wf/` retained pending parity on a second level. |
| 2026-04-14 | [Remove audio subsystem](docs/investigations/2026-04-14-remove-audio.md) | **Complete** | Implemented 2026-04-15. `wfsource/source/audio/` and `wfsource/source/audiofmt/` deleted. Stub audio stubs were non-functional on Linux. To be replaced by miniaudio (see audio investigation). |
| 2026-04-13 | [ButtonType × showAs coverage audit](docs/investigations/2026-04-13-showas-coverage.md) | **Complete** | Audited all OAD field type × showAs combinations against the Blender plugin. Gaps identified and fixed. |
| 2026-04-11 | [iffcomp — Rust rewrite](docs/investigations/2026-04-11-iffcomp-rs-rewrite.md) | **Complete** | Rust port in `wftools/iffcomp-rs/`. Byte-exact against C++ oracle. Includes comprehensive `all_features.iff.txt` torture test shared with Go port. |
| 2026-04-11 | [iffcomp — Go rewrite](docs/investigations/2026-04-11-iffcomp-go-rewrite.md) | **Complete** | Go port in `wftools/iffcomp-go/`. Byte-exact against C++ oracle (both binary and text output). Passes shared torture fixture. Go is primary; C++ kept as oracle. |
| 2026-04-11 | [iffcomp — C++ modernization](docs/investigations/2026-04-11-iffcomp-modernization.md) | **Complete** | Modernized the 1996 flex/bison C++ `iffcomp` to build on GCC 15 / Clang under C++17. Now serves as byte-exact oracle for Go and Rust ports. |
| 2026-04-14 | [Audio: sound effects, music, positional sound](docs/investigations/2026-04-14-audio-sound-music.md) | **Active — Phases 1–5 complete** | Phase 1: miniaudio SFX one-shots. Phase 2: TinySoundFont MIDI player audible. Phase 3: per-level `level<N>.mid` + load/stop hooks. Phase 4: `play_music`/`stop_music`/`set_music_volume` Lua closures (Lua-only, not mailbox). Phase 5: 3D positional SFX + listener tracking from camera (three miniaudio gotchas surfaced and fixed). Phases 6 (mobile) and 7 (docs) deferred; mailbox-wired audio API for non-Lua engines deferred. |
| 2026-04-14 | [Constraint-based props](docs/investigations/2026-04-14-constraint-based-props.md) | **Deferred** | Doors, chains, pulleys, elevators via Jolt constraints. **Hard prerequisite:** Jolt integration must land first; also requires IFF binary chunk support. Not yet scheduled. |
| 2026-04-14 | [Multiplayer, voice chat, mobile input](docs/investigations/2026-04-14-multiplayer-voice-mobile-input.md) | **Deferred** | Surveyed multiplayer sync models, voice (LKWS/Agora/LiveKit), mobile input (touch/gyro/haptics). Depends on mobile port landing first. Not yet scheduled. |
| 2026-04-14 | [REST API box PoC](docs/investigations/2026-04-14-rest-api-box-poc.md) | **Complete** | cpp-httplib embedded server in `wf_game`; create/recolor/resize/delete GL wireframe boxes via HTTP at runtime. Landed `7e690e1`. |

---
## Reference

| Date | Document | Summary |
|------|----------|---------|
| 2026-04-16 | [Scripting languages in WF](docs/scripting-languages.md) | Survey of all supported engines (Lua, Fennel, JS, wasm, Wren, Forth). Covers integration surface, binary cost (`.text`, `-O2`), RAM footprint, compile-time switches, and reference scripts for each language. |
| 2026-04-16 | [Coding conventions](docs/coding-conventions.md) | Authoritative C++ style guide for WF runtime code. Subsumes `wfsource/source/codingstandards.txt`. Covers target envelope, naming, Validate() discipline, assert family, no-fallback policy, lookup tables, OAS/OAD decision tree, mailboxes, streams, and foreign-library interop. |
| 2026-04-15 | [JerryScript GCC 14 build fixes](docs/reference/2026-04-15-jerryscript-gcc14-build-fixes.md) | Documents 7 GCC 14 build failures in JerryScript v3.0.0 with `wf-minimal` profile and how they were fixed. Applied as part of the JS engine landing. |
| 2026-04-14 | [Compile-time switches](docs/reference/2026-04-14-compile-time-switches.md) | Generated catalogue of 929 unique `#ifdef` switches across the codebase. Informational. See also `docs/compile-time-switches.md` (live version). |
| 2026-04-13 | [Blender → cd.iff pipeline](docs/reference/2026-04-13-blender-to-cd-iff-pipeline.md) | Maps the existing pipeline and proposes the Blender-native replacement for the 3DS Max content path. Key follow-up: no automated `.lev` → `.iff` path from Blender yet. |
| 2026-04-13 | [OAS / OAD format](docs/reference/2026-04-13-oas-oad-format.md) | Documents the OAS (object attribute source) and OAD (compiled descriptor) binary format. Used by `wf_blender` and `oas2oad-rs`. |
| 2026-04-12 | [Steam shipping plan](docs/reference/2026-04-12-steam-shipping-plan.md) | Comprehensive plan for shipping a WF-based game on Steam. Enumerates runtime blockers (build system, C++ dialect, HAL, graphics, scripting). Most blockers are now resolved or being resolved; Steam packaging itself not yet started. |
| 2026-04-11 | [wftools rewrite analysis](docs/reference/2026-04-11-wftools-rewrite-analysis.md) | Analyzes all ~23 `wftools/` directories; recommends which to drop, rewrite (Go/Rust), or replace with off-the-shelf tools. |
| (early) | [WF viewer design notes](docs/reference/wf-viewer.md) | Describes the standalone `wftools/wf_viewer/` approach for rendering level geometry without the full engine stack. Superseded by `wf_game` running end-to-end. |
| (early) | [Production pathway diagram](docs/reference/production-pathway.md) | Mermaid diagram of the original pipeline from `.oas` / 3D editor → `cd.iff`. Useful map of where each tool fits. |


## Current blockers

No hard blockers. Jolt is functional and all scripting engines are smoke-tested. Active areas of ongoing work are listed in Open follow-up work below.

---

## Open follow-up work

### Scripting
- **WAMR Phase 2 (AOT)** — deferred; `wamrc` compiles `.wasm` → native machine code offline; output is ISA-specific (x86_64, arm32, arm64 each need a separate `.aot` blob); ~10 KB AOT loader vs. ~107 KB classic interp. Revisit when ship targets are concrete.
- **wasm3 retired** — done 2026-04-16; `engine/vendor/wasm3-v0.5.0/` + `scripting_wasm3.{hp,cc}` removed; `WF_WASM_ENGINE=wamr` is the only wasm option.
- **Lua remote step debugger** — explicit user request for "later": MobDebug/DBG.lua/LuaLS-DAP into LuaInterpreter for in-game step debugging.
- **Fennel macros / `require`** — `fennel.searcher` / `package.searchers`; `.fnl` build step.
- **Coroutine smoke test** — fix #6 landed but untested end-to-end with a real yielding script.
- **wasm module cache** — hash source pointer + size, reuse compiled modules across `RunScript` calls (needed before wasm in hot-loop scripts).
- **Binary IFF chunk types** — `WSM `/`AOT ` tags with explicit length; drop base64 for ~33% asset shrink.
- **Cross-language API parity audit** — `read_actor`/`read_fixed`/`read_color`/`read_flags` typed accessors need to be consistent across all engines when added. No canonical IDL yet.
- **`WF_DEFAULT_ENGINE` knob** — for Lua-off builds, needs a way to select the sigil-less fallthrough engine. Currently undefined behavior.
- **Lua → JS / Lua → Wren script converters** — mirroring `tcl_to_lua_in_dump.py`.
- **Load level by filename from CLI** — **done**: `-L<path>` flag in `main.cc:167`; `gLevelOverridePath` in `game.cc:140`. `wf_game -L<level.iff>` bypasses `cd.iff`.

### Physics
- **Remove `physics/wf/`** — kept until Jolt passes snowgoons parity on at least one other level; removal is a separate reviewable commit.
- **Constraint-based props** — doors/chains/pulleys via Jolt; blocked on Jolt parity + IFF binary chunks.

### Dead code
- **Batch 8** — Jolt replaces WF physics (in progress).
- **`hal/_list` + `hal/_mempool` migration** — refactor `MsgPort` to use `cpplib/minlist.hp` + `memory/mempool.hp`, then delete the HAL remnants.
- **`eval/` (120 LOC)** — tool-side callers (`wftools/prep`, `wftools/iff2lvl`) need porting to Blender plugin first.

### Content pipeline
- **Blender → `cd.iff` pipeline** — Phases 2a + 2b + 2c landed; snowgoons loads 37 objects end-to-end, all Jolt bodies valid. Remaining: real path/channel keyframes.
- **iffcomp: Rust is primary** — Decision: tools in Rust. Four implementations exist (C++ modernized oracle, Go, Node.js, Rust); all pass `all_features.iff.txt`. Rust port (`iffcomp-rs/`) is the going-forward implementation. C++ kept as byte-exact oracle; Go and Node.js ports are superseded.

### Larger / deferred work
- **Audio (miniaudio)** — Phases 1–5 complete (SFX one-shots, MIDI MusicPlayer, per-level music, Lua scripting surface, 3D positional SFX + listener tracking). Phases 6 (mobile backends) and 7 (docs) deferred. **Gap:** audio API is Lua-only (C closures in `scripting_lua.cc`), not mailbox-wired; the other seven scripting engines currently can't trigger music or SFX.
- **Mobile port** — Android arm64 / iOS arm64; plans written ([Android](docs/plans/2026-04-16-android-port.md), [iOS](docs/plans/2026-04-16-ios-port.md)). Android Phases 1+2 done; Phase 0 (immediate-mode GL retirement) in progress — steps 1/2/4a/4b landed 2026-04-17, step 4c remaining is **proper shader ports of directional lighting + linear fog + matte triangles, not Android-only stubs**. iOS still blocked on Android.
- **Multiplayer / voice / mobile input** — blocked on mobile port.
- **Steam packaging** — Phases 1+2 done: Steamworks SDK lifecycle and Steam Input are wired in. Phases 3 (SteamPipe depot build + upload) and 4 (store page assets) deferred; blocked on Steamworks partner account and store capsule art.

---

## Last Change

**2026-04-19 05:20** — [`docs/plans/2026-04-16-git-branch-browser.md`](docs/plans/2026-04-16-git-branch-browser.md): Plan: git-branch-browser — curses TUI for browsing a branch pipeline
