# TODO

## SCRIPTING ENGINES

- [ ] zForth dictionary size — append-only dict grows with every unique script word + all INDEXOF_* constants; fixed at `ZF_DICT_SIZE` (32 KB in `zfconf.h`); monitor if level script count grows; remediation is either bumping `ZF_DICT_SIZE` or reinitialising `g_ctx` at level unload and replaying bootstrap + constants — [investigation](docs/investigations/2026-04-29-forth-compile-run-audit.md)
- [investigated] Forth compile vs. run separation — correctly handled: RunScript splits at last `;`, compiles defs once into persistent `g_ctx`, wraps call body in `_wfsN`. Constants use inline literals not `constant` (correct). Pre-compile pass at level load is feasible (low effort, defer until hitching observed) — [investigation](docs/investigations/2026-04-29-forth-compile-run-audit.md)


## LUA ENGINE

- [ ] Lua remote step debugger — MobDebug / LuaLS-DAP wired into lua_engine for in-game step debugging


## SCRIPTING INFRASTRUCTURE

- [ ] Review actor variable space w.r.t. scripting languages — each actor has a fixed-size mailbox array; audit whether per-actor _ENV tables (Lua), JS object state, wasm linear memory, and Fennel locals all play well with that constraint; document any per-language limits
- [investigated] Mailbox constants cross-language audit — consistent by design: `scripting_stub.cc` builds one `mailboxIndexArray[]` from `mailbox.inc` and `ScriptRouter` broadcasts it to every engine at init. Lua/JS/WASM use `read_mailbox` (underscore); Forth uses `read-mailbox` (hyphen, idiomatic). WASM imports constants from the `"consts"` module by name rather than as plain globals, but names are identical. No action needed.


## CONCURRENCY / ASYNC

The 1994 cooperative tasker (`hal/tasker.cc`) was never completed for Linux (context-switch
asm was never written) and is being deleted.  If a use case arises (background loading,
timer callbacks, concurrent AI), explore these alternatives instead:

- [ ] `std::thread` + work queue — simplest; good for background asset loading
- [ ] C++20 coroutines — stackless; fits scripted AI / state-machine actors well
- [ ] Fiber library (e.g. Boost.Context or `libco`) — stackful cooperative tasks, closest to the original tasker model; worth revisiting if multiple concurrent game tasks are needed


## LEVEL / GAMEPLAY

- [ ] Marble-madness: script-based input remapping — `Script Controls Input = True`; script reads mailbox 1008 (`EMAILBOX_HARDWARE_JOYSTICK1`, physical joystick, read-only) to get raw buttons, remaps them (e.g. LEFT/RIGHT → strafe bits), then writes to mailbox 3024 (`EMAILBOX_INPUT`, write-only) so the movement handler sees the remapped state. Current implementation handles LEFT/RIGHT strafe in `movement.cc` (TurnRate==0 branch) instead; the script approach is a viable future refactor. See `player.cc:192` for the 1-line passthrough pattern.


## ENGINE ROBUSTNESS

- [x] Jolt defensive null in `JoltBodyCreateStaticMesh` — `IsInvalid()` guard already landed in all three `CreateAndAddBody` wrappers (7af255b, 2026-05-10).
- [x] LMalloc DEBUG canary — `0xDEADBEEF` sentinel + pre-write assertion audit + ASan `task build-asan`; three-layer overrun defence. Done 2026-05-17 — [plan](docs/plans/2026-05-17-engine-caps.md)
- [ ] Per-level `MAX_ACTIVE_ROOMS` — currently compile-time constant; deferred until after first level ships — [plan](docs/plans/per-level-max-active-rooms.md)


## PHYSICS

- [ ] Level pipeline Phase D — decompile the 4 source-less levels (`cube`, `basic`, `cyber`, `main_game`) — [plan](docs/plans/2026-04-17-level-pipeline-proof.md)
- [ ] Level pipeline Phase E — produce multi-level `cd.iff`, confirm all 7 levels load in `wf_game`; gates `common.inc` breaking rearrangement — [plan](docs/plans/2026-04-17-level-pipeline-proof.md)
- [x] levcomp-rs common-block — `snowgoons.lvl` flip committed in `3c40a2a`; levcomp-rs output byte-identical to oracle modulo 3 uninitialized heap-pad bytes — [plan](docs/plans/2026-04-19-levcomp-common-block-two-phase.md)
- [ ] textile-rs Phase 2 — diagnose 2 non-square texture mismatches (`G_HedgeWsnowSide`, `G_shakesWsnowRM`); package texture outputs into pipeline — [plan](docs/plans/2026-04-19-textile-rs-validation.md)


## PLATFORMS

- [ ] iOS Phase 2C — wire MetalView `CADisplayLink` tick → `SetCurrentEncoder` → engine frame loop → `EndFrame`; first boot of engine main loop on iOS — [plan](docs/plans/2026-04-21-ios-port-codemagic.md)
- [ ] Android launcher polish — adaptive icon XML, foreground/background drawables — [plan](docs/plans/2026-04-18-android-launcher-polish.md)
- [ ] Android size trim iter 2 — `-fno-exceptions`, `-fvisibility=hidden`, miniaudio Vorbis trim, Windows-path deletion — [plan](docs/plans/2026-04-18-android-size-trim-iter-2.md)
- [ ] Audio assets from IFF — bundle MIDI/SF2/WAV inside `cd.iff`; retire loose-file audio loaders — [plan](docs/plans/2026-04-18-audio-assets-from-iff.md)
- [ ] Steam Phases 3+4 — SteamPipe depot + build script; store page on Steamworks — [plan](docs/plans/2026-04-17-steam.md)
- [ ] Chromecast/Google TV Phase 2 — on-device verification on physical hardware; banner image; CI — [plan](docs/plans/2026-04-23-chromecast-googletv-port.md)


## TOOLS

- [ ] Game ideas dependency graph — extract dependencies from `docs/game-ideas/` docs; build synthesis tooling — [plan](docs/plans/2026-04-28-game-ideas-dependency-graph-and-tooling.md)
- [ ] WF asset provider pure-Python rewrite — no C extensions; pure-Python `providers.py` and `wf-asset.py` CLI — [plan](docs/plans/2026-04-28-wf-asset-provider-pure-python.md)
- [ ] Blender run operator — export + build + launch chain from Blender UI (one click: `.blend` → `.iff` → `wf_game`) — [plan](docs/plans/2026-04-29-blender-run-operator.md)
- [ ] Live editor bridge Phase 2 — bidirectional TCP/JSON protocol; Blender → engine property/transform push without restart — [plan](docs/plans/2026-04-29-live-editor-bridge.md)
- [x] Debug bridge: clear watches on client disconnect — `CLIENT_DISCONNECT` sentinel posted to queue on disconnect; `DrainQueue` clears `gWatches` and `gMailboxPrev` (67ae680).
- [ ] Move OAD schema fixtures out of test path — production code (e.g. `wflevels/qbert_practice/blender_create_qbert.py:46-47`) loads `STATPLAT_OAD` and `ENEMY_OAD` from `wftools/wf_oad/tests/fixtures/*.oad`. Schemas are first-class production artefacts, not test fixtures; relocate to e.g. `wftools/wf_oad/schemas/` and update consumers.
- [x] Surface "actor outside room bbox" as a visible build warning. levcomp-rs `rooms.rs` now emits a per-actor `eprintln!` warning (name + world-center in Blender units) when a non-room actor's center falls outside every room bbox. Companion section added to `docs/level-design-troubleshooting.md`.


## BUILD / TOOLCHAIN

- [x] Foundry Linux Phase 0 — per-metapackage install scripts; `install-worldfoundry-retro-tools.sh` answers 6502-emulator question; `foundry-linux` GitHub org; WF workspace setup moved to its own plan (caed61ca)
- [ ] WF workspace setup — `setup-wf-workspace.sh`: clone `wbniv/{WorldFoundry,wf-games}`, install Rust, build wftools, register Blender addon — [plan](docs/plans/2026-05-17-wf-workspace-setup.md)
- [ ] Eliminate RTTI — replace all 51 `dynamic_cast` calls with `kind()`-guarded `static_cast`; `camera.cc:98` handled by pushing `GetWatchObject()` up into `MovementHandler`; enables `-fno-rtti` on Android; ~3–4 h — [plan](docs/plans/deferred/2026-04-29-eliminate-rtti.md) [investigation](docs/investigations/2026-04-29-rtti-audit.md)
- [investigated] RTTI claim — `kind()` / `EActorKind` at `baseobject.hp:71` is enum-dispatch, not C++ RTTI. However, the engine has **51 `dynamic_cast` calls** across `level.cc`, `movecam.cc`, `actor.cc`, `room/`, `movement/`, etc. `-fno-rtti` is not viable without replacing all of them. The "no RTTI" claim was aspirational. `kind()` has only 2 live call sites; `dynamic_cast` is the de-facto pattern. Jolt's `RTTI.cpp` is its own custom type system, unrelated to C++ RTTI.


## NAMING

- [ ] Rename `room` — "room" is a misnomer; the concept is a designer-drawn zone that controls CD asset streaming (load/unload assets as the player moves through the graph). Candidates: **Zone** (most self-explanatory), **Cell** (Elder Scrolls precedent — same mechanism), **Sector** (Doom/Quake lineage, implies spatial partition), **Region** (geographic, no shape implication)


## QBERT ARCADE FIDELITY

Remaining gaps for a faithful arcade reproduction. Player + 28 cubes + intro
camera + all 8 enemies (red ball, Coily egg+snake, green ball, Slick, Sam, Ugg,
Wrong-Way) + 2 spinning discs are in place; cube state machine handles L1R1
single-step cycles. Items below are what still separates `qbert_practice` from
a one-to-one arcade copy.

### Core gameplay

- [x] Per-round difficulty scaling — Phase A visibility gating (56c8ee2) + Phase B spawn-interval scaling; single shared spawn-timer sequencer (16 rounds × ROM-decoded sequences) done 2026-05-16 — [plan](docs/qbert/plans/2026-05-16-qbert-spawn-sequencer.md); second Coily egg in L4 done 8e55799.
- [x] Score & lives HUD — SCORE increments +25/+50/cube, +1000/round-clear, enemy-kill +100/+300, all wired. TIMER counts elapsed ticks; LIVES display was already wired (2026-05-14).
- [x] High-score persistence — 23-entry binary file seeded with arcade defaults, AAA initials picker on game-over, two-column overlay table (2026-05-15).
- [x] Bonus-points popups — floating +25/+50/+100/+300/+500 labels all done 0a39ce8.
- [x] Coily-falls-off-disc — snake chases Q✱bert onto disc coords; retires with +500 score + popup. Done b9639f9, 0a39ce8.
- [x] +50 popup (2nd cube hop, L2+) and +500 popup (Coily-off-disc) — done 0a39ce8 — [plan](docs/plans/2026-05-16-qbert-popup-50-500.md)
- [cancelled] Bonus letter "S" — not in original Gottlieb arcade; cancelled 2026-05-16.
- [x] Enemy coexistence rules — Rule 1: no climber while Coily active; Rule 2: no simultaneous climbers (Ugg blocks Wrong-Way and vice versa); freeze timer guards all spawns. Done 2026-05-15 — [plan](docs/qbert/plans/2026-05-15-qbert-enemy-coexistence.md)
- [x] Second Coily egg in L4 — arcade spawns two simultaneous Coily eggs from round 12 onward; deferred from difficulty-scaling plan — done 8e55799 — [plan](docs/qbert/plans/2026-05-16-qbert-second-coily-egg.md)

### Audio

- [x] Sound effects — hop, land, fall, death (Votrax swear), round-clear jingle. MAME-extracted PCM WAVs. Done 46d4c16 + d85d424 + d85d424 + 7557a5e.
- [x] Q✱bert curse bubble ("@!#?*") on death — visual implemented (e3a50b4, 2229963, 2026-05-12); audio cue deferred to SFX pass.
- [x] Curse bubble "@!#?*" text — texture map on bubble mesh done 2026-05-16 — [plan](docs/plans/2026-05-16-curse-bubble-texture.md)

### Visual polish

- [x] Distinct enemy meshes — Slick/Sam (green body + orange spiky hair), Ugg/Wrong-Way (magenta climber + snout + antennae), Coily (2.5-turn bezier spiral + head/tongue). Done 2026-05-11 — [plan](docs/qbert/plans/2026-05-11-qbert-distinct-enemy-meshes.md)
- [x] Player death animation — tumble + splat + curse bubble implemented (e3a50b4, 2229963, 2026-05-12). Full-sprite explosion deferred.
- [x] Disc spin VFX — yellow rim flash ring for 8 frames on Q✱bert boarding. Done e04fb99 — [plan](docs/qbert/plans/2026-05-15-qbert-disc-flash-vfx.md)
- [x] Game-over screen + name entry — 8f2b6a1: GO_BLOCK (mb 590) prevents Forth restart during C++ initials entry; GO_HOLD_TIMER (mb 591) enforces 3 s minimum hold on game-over screen; 3 s post-confirm hold shows updated table.

### Verification / breadth

- [x] End-to-end test of all 16 rounds (L1R1..L4R4) — director mailbox test (`tests/test_director_mailbox.py`) verifies cube-state cycle, score, palette, and enemy-mix gating for all 16 rounds. Done ef7ad1c.
- [x] L2-L4 per-level behaviour confirmation — covered by director mailbox test and prior spot-checks. Done ef7ad1c.


## QBERT 3D ENHANCEMENTS

Polish ideas that go beyond a faithful arcade reproduction. Hold these until the
arcade copy is complete; revisit as a second pass. Add new entries here as we
encounter them while implementing the arcade port.

- [ ] Up-hop vs down-hop arc asymmetry — climbing leaps heavier (higher/slower), falling leaps snappier (lower/faster); arcade uses one fixed sprite parabola for all four directions, so this is a 3D-only embellishment


## DEFERRED UNTIL LEVEL

- [ ] `WF_DEFAULT_ENGINE` knob — sigil-less script fallback engine selection — [plan](docs/plans/2026-04-14-pluggable-scripting-engine.md)
- [ ] Collapse wasm sigil `#b64\n` → bare `#` — workaround for cd.iff `##` TCL lines; revert once cd.iff cleaned up
- [ ] Alternate wasm sigil `#!wat` — deferred pending wabt vendor — [plan](docs/plans/2026-04-14-wasm3-scripting-engine.md) (won't be needed)
- [ ] ScriptLanguage OAD field — re-add to `common.inc`; blocked on level-pipeline-proof Phase E; revert `language = 3;` stopgap in `engine/stubs/scripting_stub.cc` — [plan](docs/plans/2026-04-16-script-language-oad-field.md)
- [ ] Strip spurious BOX3 chunks from non-geometry actors in `wflevels/snowgoons/snowgoons.lev` — [plan](docs/plans/2026-04-19-strip-nongeom-box3.md)
- [ ] Orthographic projection — add `Mat4Ortho` to `backend_modern.cc`, `SetProjectionOrtho()` to `RendererBackend`, `orthographic: Bool` flag to `camshot.oas`; ~½ day; needed by Marble Madness, Crystal Castles, Miner 2049er (isometric framing has visible perspective distortion without it); single shared implementation — whichever of those three ships first pays the cost; blocked on level-pipeline-proof Phase E (OAD schema change) — [investigation](docs/investigations/2026-04-29-camera-system.md)

- [ ] `scripts/check_iff_no_js.py` — JS footprint checker; blocked on JS scripts being authored into assets — [plan](docs/plans/2026-04-14-pluggable-scripting-engine.md)
- [ ] `WF_JS_ENGINE=jerryscript-nano` footprint build — deferred until footprint pressure — [plan](docs/plans/2026-04-14-pluggable-scripting-engine.md)
- [ ] WAMR Phase 2 — AOT compilation ship path; deferred until ship target is concrete — [plan](docs/plans/2026-04-14-wamr-dev-aot-ship.md)
- [ ] WAMR Phase 3 — w2c2 AOT backend; deferred until Phase 2 lands — [plan](docs/plans/2026-04-14-wamr-dev-aot-ship.md)


## DONE

- [x] Multi-step cube cycles — L1/L3 single-hop (0→2 +25); L2 two-hop (0→1→2 +25+50, done→revert 0); L4 two-hop (done→revert 1) — [plan](docs/plans/2026-05-14-qbert-multi-step-cube-cycles.md)
- [x] Lua 5.4 interpreter spike — NullInterpreter replaced, snowgoons player + director ported — [plan](docs/plans/2026-04-13-lua-interpreter-spike.md)
- [x] Fennel on Lua — `;` sigil, embedded fennel.lua, sub-dispatch inside lua_engine — [plan](docs/plans/2026-04-14-fennel-on-lua.md)
- [x] Vendor Lua 5.4 — statically linked into wf_game — [plan](docs/plans/2026-04-14-vendor-lua.md)
- [x] Pluggable scripting engine — ScriptRouter neutral dispatcher, all engines as peers — [plan](docs/plans/2026-04-14-pluggable-scripting-engine.md)
- [x] wasm3 scripting spike — `#b64\n` sigil, wasm3 engine plug — [plan](docs/plans/2026-04-14-wasm3-scripting-engine.md)
- [x] lua_engine fixes #1–#6 — compile cache, per-actor _ENV, Fennel pre-compilation, sandbox, debug prints, coroutine continuations — smoke-tested 2026-04-16 — [plan](docs/plans/2026-04-15-lua-engine-fixes.md)
- [x] Forth plug — `scripting_zforth.cc`, `\` sigil, snowgoons smoke test passed 2026-04-16 — [plan](docs/plans/2026-04-14-forth-scripting-engine.md)
- [x] Wren plug — `scripting_wren.{hp,cc}`, `//wren\n` sigil, snowgoons smoke test passed 2026-04-16 — [plan](docs/plans/2026-04-14-wren-scripting-engine.md)
- [x] WAMR interp — wasm-C-API, global-import constants, snowgoons smoke test passed 2026-04-16 — [plan](docs/plans/2026-04-14-wamr-dev-aot-ship.md)
- [x] JerryScript — 7 GCC 14 bugs fixed, snowgoons smoke test passed 2026-04-16 — [plan](docs/plans/2026-04-15-scripting-plans-align-scriptrouter.md)
- [x] REST API PoC — cpp-httplib, 5 routes, GL wireframe box renderer, Postman collection playback
- [x] `wf_game -L<level.iff>` CLI flag — bypass cd.iff for dev iteration
- [x] movecam crash stabilised — invalid (Actor*)&msgData cast at movecam.cc:964 guarded
- [x] Jolt physics integration — snowgoons player walks on floor, 60 s soak passed — [plan](docs/plans/2026-04-16-jolt-physics-finish.md)
- [x] Rust tool ports (`iffcomp`, `iffdump`, `oaddump`, `lvldump`) — all build and pass tests; crates at `wftools/{iffcomp-rs,iffdump-rs,oaddump-rs,lvldump-rs}`; `wf_iff` + `wf_oad` as library foundations
- [x] Blender addon packaging — `blender_manifest.toml` in both addons; `blender-build/install/validate/package` Taskfile tasks; manual rewritten provenance-first; install.sh gap resolved via addon split — [plan](docs/plans/2026-04-28-blender-addon-packaging.md)
