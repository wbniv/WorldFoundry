# WorldFoundry Project Status

**As of:** 2026-04-17  
**Branch:** `2026-first-working-gap`

---

## Summary

Five days of work (2026-04-12 – 2026-04-17) across six major areas:

**Scripting system** — Seven engines smoke-tested end-to-end in snowgoons: Lua 5.4, Fennel, QuickJS, JerryScript, WAMR (classic interp), Wren, and Forth (zForth). Five additional Forth backends (ficl, atlast, embed, libforth, pforth) build and link but are not yet end-to-end tested. All wired into a `ScriptRouter` dispatch table with per-engine sigils. wasm3 retired 2026-04-16 (WAMR reached parity). Lua made optional via `WF_LUA_ENGINE=lua54|none` (2026-04-16); `scripting_lua.cc/hp` extracted as a peer TU matching all other engine plugs. WAMR AOT deferred.

**Blender ↔ level round-trip** — `levcomp-rs` (Rust) compiles `.lev` source → binary `.lvl`; snowgoons loads end-to-end from `levcomp-rs` output. Blender plugin imports/exports 152/152 OAD fields, all light/slope/animation-channel types, Tcl→Lua script migration. Coordinate system fixed (WF is Z-up). Phase 2c complete (2026-04-17): `mesh_bbox.rs` extracts per-mesh bounding boxes from MODL/VRTX chunks; `asset_registry.rs` assigns packed `[TYPE|ROOM|INDEX]` asset IDs and emits `asset.inc`; `ButtonType::Filename` handled alongside `MeshName`; 37 objects placed, all Jolt bodies valid. Remaining: real path/channel keyframes.

**Jolt Physics** — Integrated and default (`WF_PHYSICS_ENGINE=jolt`). Five-step plan complete: SIGABRT fixed, zombie kinematic bodies eliminated, WF↔Jolt authority model locked, 3 m vertical pop fixed (feet vs centre offset), 60 s soak passed. Legacy `physics/wf/` retained pending a second level.

**Dead-code removal** — Batches 1–7 complete: `wfsource/source/` reduced from 64,252 → 36,199 lines (−43.7%). Batch 8 (Jolt replaces WF physics) in progress.

**Steam (Phases 1–2)** — Steamworks SDK lifecycle wired into HAL (`SteamAPI_Init/Shutdown` in `HALStart`) and display (`SteamAPI_RunCallbacks` after `XEventLoop` in `PageFlip`). Steam Input polls all connected controllers each frame and ORs results into `_JoystickButtonsF`; keyboard path unchanged. `WF_ENABLE_STEAM=1` build flag; SDK not committed (see `engine/vendor/steamworks/README.md`). `steam/game_actions_480.vdf` defines the `InGame` action set. `steam_appid.txt=480` for dev. Phases 3 (SteamPipe depot) and 4 (store page) deferred.

**Audio (Phases 1–2 + in-progress 3–4)** — Phase 1 (2026-04-17): miniaudio v0.11.25 vendored; `SoundDevice`/`SoundBuffer` reimplemented on `ma_engine`; `_InitAudio`/`_TermAudio` in HAL; fire-and-forget `play()` via heap `PlayInstance` freed by end-callback. Phase 2 (2026-04-17): TinySoundFont (`tsf.h`/`tml.h`) vendored; `MusicPlayer` renders MIDI → stereo float PCM as a miniaudio custom data source on the audio thread; C-major scale (`test_scale.mid`) audible via PulseAudio. Phase 3 in progress: per-level music (`level<N>.mid`) loads on `RunLevel`, stops on exit; `level0.mid` added. Phase 4 in progress: `play_music`/`stop_music`/`set_music_volume` Lua C closures registered in `scripting_lua.cc`.

**Tooling and plans** — `engine/` reorganised to top-level. REST API box PoC landed. Android + iOS port plans written (blocked on GL immediate-mode rewrite + CMake migration). CLI level override (`-L<path>`) confirmed done. Audio investigation updated: `AudioBackend` pimpl seam documented; MIDI sources (OpenScore CC0, Mutopia, piano-midi.de) researched and catalogued; IFF format lineage (EA IFF 85 → AIFF, RIFF, WF IFF) documented.

---

## Plans

### Active

| Date | Plan | Status | Summary |
|------|------|--------|---------|
| 2026-04-16 | [Plan: git-branch-browser — curses TUI for browsing branch diffs](docs/plans/2026-04-16-git-branch-browser.md) | **Not started** | **Goal:** A Python curses program at `scripts/git-branch-browser.py` that lets you browse all git branches, see per-branch changed files as a collapsible directory tree with status annotations, and … |
| 2026-04-17 | [Plan: Steam release](docs/plans/2026-04-17-steam.md) | **In progress — Phases 1+2 done** | Steamworks SDK lifecycle wired into HAL + PageFlip. Steam Input → `EJ_BUTTONF_*` merged in `_JoystickButtonsF`. `WF_ENABLE_STEAM=1` build flag; SDK not committed (see vendor README). Phases 3 (depot) and 4 (store page) deferred. |
| 2026-04-16 | [Plan: Android port](docs/plans/2026-04-16-android-port.md) | **Not started** | **Goal:** An APK that runs snowgoons on arm64 Android and Google TV (Chromecast with Google TV). TV: leanback manifest + runtime `UI_MODE_TYPE_TELEVISION` detection → gamepad-only, no on-screen d-pad. Same APK for both targets. Forth-only scripting in v1. |
| 2026-04-15 | [Dead-code removal](docs/plans/2026-04-15-dead-code-removal.md) | **Partial** | Batches 1–7 complete (−43.7% LOC). Batch 6 (`#if 0` sweep) done. Batch 7 (PSX/Win artifacts, OpusMake, platform guards) done. Batch 8 (Jolt physics replacement) in progress. |

### Deferred

| Date | Plan | Status | Summary |
|------|------|--------|---------|
| 2026-04-16 | [ScriptLanguage OAD field](docs/plans/2026-04-16-script-language-oad-field.md) | **Deferred — blocked on Blender+levcomp-rs level round-trip** | Field added then reverted from `common.oad` to restore binary layout compat with existing compiled levels. Dispatch table + language param threading remain in engine (passing 0=Lua). Will re-introduce once all levels compile through Blender+levcomp-rs. |
| 2026-04-16 | [Plan: iOS port](docs/plans/2026-04-16-ios-port.md) | **Deferred — blocked on Android port** | **Goal:** An IPA that runs snowgoons on a tethered iPhone, installed via Xcode with a developer profile. Proof-of-viability, not a shipping product. |

### Complete

| Date | Plan | Status | Summary |
|------|------|--------|---------|
| 2026-04-16 | [Plan: Lua engine is not special — make it optional](docs/plans/2026-04-16-lua-not-special.md) | **Done** | `scripting_lua.cc/hp` extracted; `WF_LUA_ENGINE=lua54\|none` added to `build_game.sh`; all `lua_engine::` calls guarded; Fennel+none warns and forces lua54; stale `scripting_wasm3.hp` include removed. |
| 2026-04-16 | [Engine directory reorganization](docs/plans/2026-04-16-engine-directory-reorganization.md) | **Complete** | `engine/` is now a top-level directory. `wftools/wf_engine/` → `engine/`, `wftools/vendor/` → `engine/vendor/`, `wf_viewer/stubs/` → `engine/stubs/`, `wf_viewer/include/` → `engine/include/`. `wftools/` is now strictly dev tooling. |
| 2026-04-16 | [Plan: Blender ↔ Level Round-Trip](docs/plans/2026-04-16-blender-level-roundtrip.md) | **Complete** | `levcomp-rs` compiles `.lev` → `.lvl`; snowgoons loads in `wf_game`. Blender import/export round-trips 152/152 OAD fields. Lights, slopes, animation channels, scripts all emit. Coordinate system fixed (WF is Z-up, not Y-up). Tcl scripts ported to Lua. Investigation: [reverse-engineering doc](docs/investigations/2026-04-16-levcomp-rs-reverse-engineering.md). |
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
| 2026-04-17 | [IFF format lineage — EA IFF 85, AIFF, RIFF, WorldFoundry IFF](docs/investigations/2026-04-17-iff-format-lineage.md) | **Complete** | Traces all four formats from the common 1985 ancestor. Key findings: AIFF and WF IFF independently arrived at the same solution (bake navigational offsets at write time for slow-media random access); WF uniquely separates interchange (text source) from execution (platform binary); `.align(2048)` maps CD-ROM sectors. Side-by-side comparison table included. |
| 2026-04-16 | [Reverse-engineering the WF binary level format for `levcomp-rs`](docs/investigations/2026-04-16-levcomp-rs-reverse-engineering.md) | **Phase 2c complete** | Binary format fully mapped; Phase 2c (2026-04-17): mesh bbox from MODL/VRTX, packed asset IDs, `asset.inc` output, 37 objects validated. Remaining: real path/channel keyframes. |
| 2026-04-16 | [Coding-conventions remediation](docs/investigations/2026-04-16-coding-conventions-remediation.md) | **In progress** | Audit of 2026-authored code in `wfsource/source/` against `docs/coding-conventions.md`. Honest accounting of where recent additions don't yet follow the rules they propose. |
| 2026-04-15 | [LOC tracking](docs/investigations/2026-04-15-loc-tracking.md) | **Ongoing** | Tracks code line count over time. Current HEAD: ~36,199 lines (−43.7% from baseline 64,252 at `74d1a47`). Tool: `scripts/loc_report.py`. |
| 2026-04-14 | [Scripting language replacement](docs/investigations/2026-04-14-scripting-language-replacement.md) | **Complete** | Comprehensive survey that recommended Lua 5.4 as the primary engine. Spawned all scripting plans. Decision: Lua won. |
| 2026-04-14 | [Physics engine survey](docs/investigations/2026-04-14-physics-engine-survey.md) | **Complete** | Surveyed Bullet, PhysX, Rapier, Jolt, and others. Recommended **Jolt Physics** (MIT, ~300 KB, `CharacterVirtual`, active upstream). Spawned Jolt integration plan. |
| 2026-04-14 | [Jolt Physics integration](docs/investigations/2026-04-14-jolt-physics-integration.md) | **Functional** | Jolt is the default (`WF_PHYSICS_ENGINE=jolt`); snowgoons is playable. Runtime init/shutdown moved to `WFGame` (`b5dc7fe`). Legacy `physics/wf/` retained pending parity on a second level. |
| 2026-04-14 | [Remove audio subsystem](docs/investigations/2026-04-14-remove-audio.md) | **Complete** | Implemented 2026-04-15. `wfsource/source/audio/` and `wfsource/source/audiofmt/` deleted. Stub audio stubs were non-functional on Linux. To be replaced by miniaudio (see audio investigation). |
| 2026-04-13 | [ButtonType × showAs coverage audit](docs/investigations/2026-04-13-showas-coverage.md) | **Complete** | Audited all OAD field type × showAs combinations against the Blender plugin. Gaps identified and fixed. |
| 2026-04-11 | [iffcomp — Rust rewrite](docs/investigations/2026-04-11-iffcomp-rs-rewrite.md) | **Complete** | Rust port in `wftools/iffcomp-rs/`. Byte-exact against C++ oracle. Includes comprehensive `all_features.iff.txt` torture test shared with Go port. |
| 2026-04-11 | [iffcomp — Go rewrite](docs/investigations/2026-04-11-iffcomp-go-rewrite.md) | **Complete** | Go port in `wftools/iffcomp-go/`. Byte-exact against C++ oracle (both binary and text output). Passes shared torture fixture. Go is primary; C++ kept as oracle. |
| 2026-04-11 | [iffcomp — C++ modernization](docs/investigations/2026-04-11-iffcomp-modernization.md) | **Complete** | Modernized the 1996 flex/bison C++ `iffcomp` to build on GCC 15 / Clang under C++17. Now serves as byte-exact oracle for Go and Rust ports. |
| 2026-04-14 | [Audio: sound effects, music, positional sound](docs/investigations/2026-04-14-audio-sound-music.md) | **Active — Phases 1+2 complete; Phase 3+4 in progress** | Phase 1: miniaudio v0.11.25 SFX one-shots working. Phase 2: TinySoundFont MIDI player, C-major scale audible. Phase 3 (in progress): per-level `level<N>.mid` + load/stop hooks. Phase 4 (in progress): `play_music`/`stop_music`/`set_music_volume` Lua closures. Phase 5 (3D SFX) deferred. |
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
- **Audio (miniaudio)** — Phases 1+2 landed (SFX one-shots + MIDI MusicPlayer audible). Phases 3+4 in progress (per-level music + Lua scripting surface). Phases 5–7 (3D SFX, mobile backends, docs) deferred.
- **Mobile port** — Android arm64 / iOS arm64; plans written ([Android](docs/plans/2026-04-16-android-port.md), [iOS](docs/plans/2026-04-16-ios-port.md)); blocked on GL immediate-mode replacement + CMake migration.
- **Multiplayer / voice / mobile input** — blocked on mobile port.
- **Steam packaging** — Phases 1+2 done: Steamworks SDK lifecycle and Steam Input are wired in. Phases 3 (SteamPipe depot build + upload) and 4 (store page assets) deferred; blocked on Steamworks partner account and store capsule art.

---

## Last Change

**2026-04-17 03:25** — [`docs/investigations/2026-04-14-audio-sound-music.md`](docs/investigations/2026-04-14-audio-sound-music.md): Investigation: Audio — sound effects, music, positional sound
