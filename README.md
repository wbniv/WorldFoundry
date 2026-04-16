# WorldFoundry Project Status

**As of:** 2026-04-16  
**Branch:** `2026-first-working-gap`

---

## Summary

The past several days have produced a large amount of work across two fronts: **scripting system** and **dead-code removal**.

The scripting system is comprehensively implemented — Lua, Fennel, QuickJS, JerryScript, wasm3, WAMR, Wren, and Forth (zForth) are all compiled and wired into the `ScriptRouter` dispatch table. Lua/Fennel/QuickJS/wasm3 have been smoke-tested end-to-end (snowgoons player moves, director cuts cameras). JerryScript, WAMR, Wren, and Forth are landed but not yet smoke-tested; those tests are blocked on HAL cleanup currently happening on this branch.

Dead-code removal is largely done: Batches 1–7 are complete, reducing `wfsource/source/` from 64,252 to 36,199 code lines (−43.7%). One batch (Batch 8 — physics replacement) is in progress.

Jolt Physics integration is actively in progress: Phases 1–3 are committed (`b17a7ca`); further work is in the current uncommitted changes (`jolt_backend.cc`, `jolt_backend.hp`, `level.cc`, `halbase.h`, `haltest.cc`).

Multiple larger investigations (audio, mobile port, multiplayer, constraint-based props) are written up and deferred pending prerequisite work.

---

## Plans

| Date | Plan | Status | Summary |
|------|------|--------|---------|
| 2026-04-16 | [Test plan for hook](docs/plans/2026-04-16-hook-test.md) | **Planned** | This is a test plan created to verify that update_wf_status.py correctly inserts a new row into the Plans table of wf-status.md. |
| 2026-04-16 | [ScriptLanguage OAD field](docs/plans/2026-04-16-script-language-oad-field.md) | **Planned** | Move language selection from runtime sigil detection into an explicit `int32 ScriptLanguage` OAD field (dropmenu in Blender). Dispatch via function pointer table. Migration scriptable from Blender headless. |
| 2026-04-15 | [Dead-code removal](docs/plans/2026-04-15-dead-code-removal.md) | **Partial** | Batches 1–7 complete (−43.7% LOC). Batch 6 (`#if 0` sweep) done. Batch 7 (PSX/Win artifacts, OpusMake, platform guards) done. Batch 8 (Jolt physics replacement) in progress. |
| 2026-04-15 | [Lua engine fixes (#1–#6)](docs/plans/2026-04-15-lua-engine-fixes.md) | **Landed** | All 6 fixes implemented: script cache, per-actor envs, Fennel precompile, debug gating, stdlib sandbox, coroutine continuations. Smoke test pending HAL cleanup. |
| 2026-04-15 | [Align scripting plans to ScriptRouter](docs/plans/2026-04-15-scripting-plans-align-scriptrouter.md) | **Landed** | Phases A–E complete: all plan docs updated, JS/wasm3 renamed to `js_engine`/`wasm3_engine` namespaces, WAMR/Wren/Forth landed. Smoke tests blocked on HAL cleanup. |
| 2026-04-14 | [WAMR (dev interp + AOT ship)](docs/plans/2026-04-14-wamr-dev-aot-ship.md) | **Partial** | Phase 1 (classic interpreter) landed 2026-04-15. WAT sources compiled. Smoke test blocked on HAL cleanup. Phase 2 (AOT) deferred. |
| 2026-04-14 | [Wren scripting engine](docs/plans/2026-04-14-wren-scripting-engine.md) | **Landed** | All phases complete: vendor, plug, dispatch, build, docs, patcher. Smoke test blocked on HAL cleanup. |
| 2026-04-14 | [Forth scripting engine](docs/plans/2026-04-14-forth-scripting-engine.md) | **Partial** | Phase 1 (all 6 vendors) done. zForth default backend landed with `scripting_forth.hp`/`scripting_zforth.cc`, dispatch arm, build flag, patcher, docs. Smoke test blocked on HAL cleanup. Alternate backends (ficl, atlast, embed, libforth, pforth) deferred until zForth smoke test passes. |
| 2026-04-14 | [Pluggable JS engines (QuickJS / JerryScript)](docs/plans/2026-04-14-pluggable-scripting-engine.md) | **Partial** | Both engines landed 2026-04-14 with `js_engine` namespace. QuickJS smoke-tested (snowgoons passes). JerryScript build path landed but **never run** — needs smoke test. |
| 2026-04-14 | [WebAssembly (wasm3)](docs/plans/2026-04-14-wasm3-scripting-engine.md) | **Complete** | Landed 2026-04-14. Sigil `#b64\n`, dispatch in `ScriptRouter`, snowgoons AssemblyScript scripts. Renamed to `wasm3_engine` namespace 2026-04-15. |
| 2026-04-14 | [Fennel on Lua](docs/plans/2026-04-14-fennel-on-lua.md) | **Complete** | Landed 2026-04-14. `;` sigil, sub-dispatch inside `lua_engine`, vendored Fennel 1.6.1, minifier, codegen, snowgoons Fennel scripts. |
| 2026-04-14 | [Vendor Lua 5.4](docs/plans/2026-04-14-vendor-lua.md) | **Complete** | Landed 2026-04-14. Lua 5.4.8 in `wftools/vendor/lua-5.4.8/`, compiled directly from source, no system `liblua5.4` dependency. |
| 2026-04-13 | [Lua interpreter spike](docs/plans/2026-04-13-lua-interpreter-spike.md) | **Complete** | Landed 2026-04-13; refactored 2026-04-15 to `lua_engine` namespace in `ScriptRouter`. Snowgoons player + director ported to Lua; player moves, cameras cut. |

---

## Investigations

| Date | Investigation | Status | Summary |
|------|---------------|--------|---------|
| 2026-04-16 | [Coding-conventions remediation](docs/investigations/2026-04-16-coding-conventions-remediation.md) | **In progress** | Audit of 2026-authored code in `wfsource/source/` against `docs/coding-conventions.md`. Honest accounting of where recent additions don't yet follow the rules they propose. |
| 2026-04-15 | [JerryScript GCC 14 build fixes](docs/investigations/2026-04-15-jerryscript-gcc14-build-fixes.md) | **Reference** | Documents 7 GCC 14 build failures in JerryScript v3.0.0 with `wf-minimal` profile and how they were fixed. Applied as part of the JS engine landing. |
| 2026-04-15 | [LOC tracking](docs/investigations/2026-04-15-loc-tracking.md) | **Ongoing** | Tracks code line count over time. Current HEAD: ~36,199 lines (−43.7% from baseline 64,252 at `74d1a47`). Tool: `scripts/loc_report.py`. |
| 2026-04-14 | [Scripting language replacement](docs/investigations/2026-04-14-scripting-language-replacement.md) | **Complete** | Comprehensive survey that recommended Lua 5.4 as the primary engine. Spawned all scripting plans. Decision: Lua won. |
| 2026-04-14 | [Physics engine survey](docs/investigations/2026-04-14-physics-engine-survey.md) | **Complete** | Surveyed Bullet, PhysX, Rapier, Jolt, and others. Recommended **Jolt Physics** (MIT, ~300 KB, `CharacterVirtual`, active upstream). Spawned Jolt integration plan. |
| 2026-04-14 | [Jolt Physics integration](docs/investigations/2026-04-14-jolt-physics-integration.md) | **In progress** | Phases 1–3 committed (`b17a7ca`). Phase 4+ in current uncommitted changes (`jolt_backend.cc/hp`, `level.cc`). HAL changes (`halbase.h`, `haltest.cc`) also in flight. |
| 2026-04-14 | [Remove audio subsystem](docs/investigations/2026-04-14-remove-audio.md) | **Complete** | Implemented 2026-04-15. `wfsource/source/audio/` and `wfsource/source/audiofmt/` deleted. Stub audio stubs were non-functional on Linux. To be replaced by miniaudio (see audio investigation). |
| 2026-04-14 | [Compile-time switches](docs/investigations/2026-04-14-compile-time-switches.md) | **Reference** | Generated catalogue of 929 unique `#ifdef` switches across the codebase. Informational. See also `docs/compile-time-switches.md` (live version). |
| 2026-04-14 | [Audio: sound effects, music, positional sound](docs/investigations/2026-04-14-audio-sound-music.md) | **Deferred** | Full miniaudio-based audio plan: SFX one-shots, music streaming, 3D panning, script-triggerable via mailboxes. Statically linked. Not yet scheduled. |
| 2026-04-14 | [Constraint-based props](docs/investigations/2026-04-14-constraint-based-props.md) | **Deferred** | Doors, chains, pulleys, elevators via Jolt constraints. **Hard prerequisite:** Jolt integration must land first; also requires IFF binary chunk support. Not yet scheduled. |
| 2026-04-14 | [Mobile port (Android / iOS)](docs/investigations/2026-04-14-mobile-port-android-ios.md) | **Deferred** | Full plan for arm64 Android and iOS builds. Key blocker: immediate-mode GL must be replaced before any mobile API can work. CMake migration required. Not yet scheduled. |
| 2026-04-14 | [Multiplayer, voice chat, mobile input](docs/investigations/2026-04-14-multiplayer-voice-mobile-input.md) | **Deferred** | Surveyed multiplayer sync models, voice (LKWS/Agora/LiveKit), mobile input (touch/gyro/haptics). Depends on mobile port landing first. Not yet scheduled. |
| 2026-04-14 | [REST API box PoC](docs/investigations/2026-04-14-rest-api-box-poc.md) | **Deferred** | Proof-of-concept for an HTTP API embedded in `wf_game` for creating/moving/deleting boxes at runtime. Not yet implemented. |
| 2026-04-14 | [Party game — reaction timer + image recognition](docs/investigations/2026-04-14-party-game.md) | **Reference** | Chromecast party game concept (phone as controller, TV as display). Not a WF engine task — explores a standalone project idea. |
| 2026-04-14 | [Party game — card games (fill-in-the-blank / comic strip)](docs/investigations/2026-04-14-party-game-cards.md) | **Reference** | Two Chromecast card game designs. Same platform stack as above. Not a WF engine task. |
| 2026-04-13 | [Blender → cd.iff pipeline](docs/investigations/2026-04-13-blender-to-cd-iff-pipeline.md) | **Reference** | Maps the existing pipeline and proposes the Blender-native replacement for the 3DS Max content path. Key follow-up: no automated `.lev` → `.iff` path from Blender yet. |
| 2026-04-13 | [OAS / OAD format](docs/investigations/2026-04-13-oas-oad-format.md) | **Reference** | Documents the OAS (object attribute source) and OAD (compiled descriptor) binary format. Used by `wf_blender` and `oas2oad-rs`. |
| 2026-04-13 | [ButtonType × showAs coverage audit](docs/investigations/2026-04-13-showas-coverage.md) | **Complete** | Audited all OAD field type × showAs combinations against the Blender plugin. Gaps identified and fixed. |
| 2026-04-12 | [Steam shipping plan](docs/investigations/2026-04-12-steam-shipping-plan.md) | **Reference** | Comprehensive plan for shipping a WF-based game on Steam. Enumerates runtime blockers (build system, C++ dialect, HAL, graphics, scripting). Most blockers are now resolved or being resolved; Steam packaging itself not yet started. |
| 2026-04-11 | [iffcomp — Rust rewrite](docs/investigations/2026-04-11-iffcomp-rs-rewrite.md) | **Complete** | Rust port in `wftools/iffcomp-rs/`. Byte-exact against C++ oracle. Includes comprehensive `all_features.iff.txt` torture test shared with Go port. |
| 2026-04-11 | [iffcomp — Go rewrite](docs/investigations/2026-04-11-iffcomp-go-rewrite.md) | **Complete** | Go port in `wftools/iffcomp-go/`. Byte-exact against C++ oracle (both binary and text output). Passes shared torture fixture. Go is primary; C++ kept as oracle. |
| 2026-04-11 | [iffcomp — C++ modernization](docs/investigations/2026-04-11-iffcomp-modernization.md) | **Complete** | Modernized the 1996 flex/bison C++ `iffcomp` to build on GCC 15 / Clang under C++17. Now serves as byte-exact oracle for Go and Rust ports. |
| 2026-04-11 | [wftools rewrite analysis](docs/investigations/2026-04-11-wftools-rewrite-analysis.md) | **Reference** | Analyzes all ~23 `wftools/` directories; recommends which to drop, rewrite (Go/Rust), or replace with off-the-shelf tools. |
| (early) | [WF viewer design notes](docs/investigations/wf-viewer.md) | **Reference** | Describes the standalone `wftools/wf_viewer/` approach for rendering level geometry without the full engine stack. Superseded by `wf_game` running end-to-end. |
| (early) | [Production pathway diagram](docs/investigations/production-pathway.md) | **Reference** | Mermaid diagram of the original pipeline from `.oas` / 3D editor → `cd.iff`. Useful map of where each tool fits. |

---

## Current blockers

**Jolt character position fix (in progress, this branch):** JerryScript, WAMR, Wren, Forth/zForth, and Lua coroutines need snowgoons smoke tests, but those were deferred until this branch's in-flight changes are committed cleanly.

The uncommitted work is two things:

- **HAL cleanup** (`halbase.h`, `haltest.cc`) — trivial. Removes dangling `TEST_TASKER` / `TEST_TIMER` guards and `TaskerTest()`/`TimerTest()` call sites left over from the Batch 5 tasker deletion. No logic change; not blocking the build on its own.

- **Jolt character controller position fix** (`jolt_backend.cc`, `level.cc`) — the real work. WF stores actor position at the **feet**; Jolt's `CharacterVirtual` expects position at the **centre** of the bounding box. Fix stores `ctr = minPt + half` and applies it on every `SetPosition`; subtracts on every `GetPosition`. Also adds `JoltOptimizeBroadPhase()` call in `level.cc` after all static bodies are registered (required before `CharacterVirtual` queries can find them). 120-frame stderr trace is in place to verify ground contact.

**To unblock:** build with `WF_PHYSICS_ENGINE=jolt`, confirm the character lands on the floor (stderr shows `GROUND`), commit all four files, then run the scripting smoke tests in sequence: JerryScript → WAMR → Wren → Forth/zForth.

---

## Open follow-up work

### Scripting
- **JerryScript smoke test** — build path landed; never run (`WF_JS_ENGINE=jerryscript`). Half-day effort.
- **WAMR smoke test** — Phase 1 interp landed; needs snowgoons player + director verification.
- **Wren smoke test** — fully landed; needs snowgoons verification.
- **Forth/zForth smoke test** — fully landed; needs snowgoons verification.
- **Forth alternate backends** — ficl, atlast, embed, libforth, pforth deferred until zForth smoke test passes.
- **WAMR Phase 2 (AOT)** — deferred; `wamrc` + `#aot\n` sigil; ~10 KB runtime vs. 519 KB interp.
- **wasm3 retirement** — planned after WAMR interp is proven at parity (remove vendor tree + `scripting_wasm3.cc`).
- **Lua remote step debugger** — explicit user request for "later": MobDebug/DBG.lua/LuaLS-DAP into LuaInterpreter for in-game step debugging.
- **Fennel macros / `require`** — `fennel.searcher` / `package.searchers`; `.fnl` build step.
- **Coroutine smoke test** — fix #6 landed but untested end-to-end with a real yielding script.
- **wasm module cache** — hash source pointer + size, reuse compiled modules across `RunScript` calls (needed before wasm in hot-loop scripts).
- **Binary IFF chunk types** — `WSM `/`AOT ` tags with explicit length; drop base64 for ~33% asset shrink.
- **WASM `#` sigil vs `#!wasm\n`** — open question noted in wasm3 plan; tentatively keep `#` as discriminator, treat rest of first line as subtype.
- **Collapse `#b64\n` wasm sigil back to bare `#`** — `#b64\n` is a workaround for `cd.iff`'s `##` TCL shell lines; revert once `cd.iff` is cleaned up.
- **Cross-language API parity audit** — `read_actor`/`read_fixed`/`read_color`/`read_flags` typed accessors need to be consistent across all engines when added. No canonical IDL yet.
- **`WF_DEFAULT_ENGINE` knob** — for Lua-off builds, needs a way to select the sigil-less fallthrough engine. Currently undefined behavior.
- **Lua → JS / Lua → Wren script converters** — mirroring `tcl_to_lua_in_dump.py`.
- **Load level by filename from CLI** — `wf_game <level.iff>` flag to bypass `cd.iff` for dev iteration (after Lua spike + iffdump round-trip).

### Physics
- **Jolt Phases 4+** — in progress (`jolt_backend.cc/hp`, `level.cc` uncommitted). Phase 3 was `CharacterVirtual`; check plan for Phase 4+ scope.
- **Remove `physics/wf/`** — kept until Jolt passes snowgoons parity on at least one other level; removal is a separate reviewable commit.
- **Constraint-based props** — doors/chains/pulleys via Jolt; blocked on Jolt parity + IFF binary chunks.

### Dead code
- **Batch 8** — Jolt replaces WF physics (in progress).
- **`hal/_list` + `hal/_mempool` migration** — refactor `MsgPort` to use `cpplib/minlist.hp` + `memory/mempool.hp`, then delete the HAL remnants.
- **`eval/` (120 LOC)** — tool-side callers (`wftools/prep`, `wftools/iff2lvl`) need porting to Blender plugin first.

### Content pipeline
- **Blender → `cd.iff` automation** — no automated `.lev` → `.iff` path from Blender yet; currently requires manual `iffcomp` invocation.
- **iffcomp: Rust is primary** — Decision: tools in Rust. Three implementations exist (C++ modernized oracle, Go, Rust); all pass `all_features.iff.txt`. Rust port (`iffcomp-rs/`) is the going-forward implementation. C++ kept as byte-exact oracle; Go port (`iffcomp-go/`) is superseded.

### Larger / deferred work
- **Audio (miniaudio)** — SFX one-shots, music streaming, 3D panning, all statically linked. No start date.
- **Mobile port** — Android arm64 / iOS arm64; blocked on GL immediate-mode replacement + CMake migration.
- **Multiplayer / voice / mobile input** — blocked on mobile port.
- **Steam packaging** — most runtime blockers resolved; packaging pipeline itself not yet started.

## Last Change

**2026-04-16 03:30** — [`docs/plans/2026-04-16-hook-test.md`](docs/plans/2026-04-16-hook-test.md): Test plan for hook
