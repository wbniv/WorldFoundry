# TODO

## SCRIPTING ENGINES

- [verify] Forth plug wiring — `scripting_forth.hp`, `scripting_zforth.cc`, `zfconf.h`, `\` sigil in ScriptRouter; snowgoons IFF patched via `scripts/patch_snowgoons_forth.py`; needs smoke test once build is unblocked — [plan](docs/plans/2026-04-14-forth-scripting-engine.md)
- [verify] Wren plug — `scripting_wren.{hp,cc}`, `wren-0.4.0` vendor, `//wren\n` sigil, snowgoons IFF patched via `scripts/patch_snowgoons_wren.py`; needs smoke test once build is unblocked — [plan](docs/plans/2026-04-14-wren-scripting-engine.md)
- [verify] WAMR interp — `wamr_engine` namespace, wasm-C-API, global-import constants; vendor at `engine/vendor/wamr-2.2.0`; WAT sources in `wamr-2.2.0-wf/`; needs smoke test + global-import WAT compiled (requires wabt/wat2wasm) — [plan](docs/plans/2026-04-14-wamr-dev-aot-ship.md)
- [verify] JerryScript smoke test — JerryScript compiled (7 GCC 14 bugs fixed); snowgoons patched with JS; run `wf_game -Lwflevels/snowgoons.iff` to confirm player+director — [plan](docs/plans/2026-04-15-scripting-plans-align-scriptrouter.md#d2-jerryscript-smoke-test) [investigation](docs/investigations/2026-04-15-jerryscript-gcc14-build-fixes.md)
- [ ] Review Forth compile vs. run separation — Forth conflates compile-time (`:` definitions, immediate words) with run-time (interpret loop); audit how `scripting_zforth.cc` handles this for per-actor scripts and whether a pre-compile pass into a saved dictionary makes sense


## LUA ENGINE

- [verify] Fix #6 smoke test — coroutine continuations implemented; needs snowgoons regression run — [plan](docs/plans/2026-04-15-lua-engine-fixes.md)
- [ ] Lua remote step debugger — MobDebug / LuaLS-DAP wired into lua_engine for in-game step debugging


## SCRIPTING INFRASTRUCTURE

- [ ] Review actor variable space w.r.t. scripting languages — each actor has a fixed-size mailbox array; audit whether per-actor _ENV tables (Lua), JS object state, wasm linear memory, and Fennel locals all play well with that constraint; document any per-language limits

- [ ] `WF_DEFAULT_ENGINE` knob — sigil-less script fallback engine selection — [plan](docs/plans/2026-04-14-pluggable-scripting-engine.md)
- [investigated] Mailbox constants cross-language audit — consistent by design: `scripting_stub.cc` builds one `mailboxIndexArray[]` from `mailbox.inc` and `ScriptRouter` broadcasts it to every engine at init. Lua/JS/WASM use `read_mailbox` (underscore); Forth uses `read-mailbox` (hyphen, idiomatic). WASM imports constants from the `"consts"` module by name rather than as plain globals, but names are identical. No action needed.
- [ ] `scripts/check_iff_no_js.py` — JS footprint checker; blocked on JS scripts being authored into assets — [plan](docs/plans/2026-04-14-pluggable-scripting-engine.md)
- [verify] `WF_JS_ENGINE=jerryscript-nano` — deferred until footprint pressure — [plan](docs/plans/2026-04-14-pluggable-scripting-engine.md)
- [ ] Collapse wasm sigil `#b64\n` → bare `#` — workaround for cd.iff `##` TCL lines; revert once cd.iff cleaned up


## CONCURRENCY / ASYNC

The 1994 cooperative tasker (`hal/tasker.cc`) was never completed for Linux (context-switch
asm was never written) and is being deleted.  If a use case arises (background loading,
timer callbacks, concurrent AI), explore these alternatives instead:

- [ ] `std::thread` + work queue — simplest; good for background asset loading
- [ ] C++20 coroutines — stackless; fits scripted AI / state-machine actors well
- [ ] Fiber library (e.g. Boost.Context or `libco`) — stackful cooperative tasks, closest to the original tasker model; worth revisiting if multiple concurrent game tasks are needed


## PHYSICS


## BUILD / TOOLCHAIN

- [investigated] RTTI claim — `kind()` / `EActorKind` at `baseobject.hp:71` is enum-dispatch, not C++ RTTI. However, the engine has **51 `dynamic_cast` calls** across `level.cc`, `movecam.cc`, `actor.cc`, `room/`, `movement/`, etc. `-fno-rtti` is not viable without replacing all of them. The "no RTTI" claim was aspirational. `kind()` has only 2 live call sites; `dynamic_cast` is the de-facto pattern. Jolt's `RTTI.cpp` is its own custom type system, unrelated to C++ RTTI.


## NAMING

- [ ] Rename `room` — "room" is a misnomer; the concept is a designer-drawn zone that controls CD asset streaming (load/unload assets as the player moves through the graph). Candidates: **Zone** (most self-explanatory), **Cell** (Elder Scrolls precedent — same mechanism), **Sector** (Doom/Quake lineage, implies spatial partition), **Region** (geographic, no shape implication)


## TBD?

- [ ] `WF_JS_ENGINE=jerryscript-nano` footprint build
- [ ] Alternate wasm sigil `#!wat` — deferred pending wabt vendor — [plan](docs/plans/2026-04-14-wasm3-scripting-engine.md)


## DONE

- [x] Lua 5.4 interpreter spike — NullInterpreter replaced, snowgoons player + director ported — [plan](docs/plans/2026-04-13-lua-interpreter-spike.md)
- [x] Fennel on Lua — `;` sigil, embedded fennel.lua, sub-dispatch inside lua_engine — [plan](docs/plans/2026-04-14-fennel-on-lua.md)
- [x] Vendor Lua 5.4 — statically linked into wf_game — [plan](docs/plans/2026-04-14-vendor-lua.md)
- [x] Pluggable scripting engine — ScriptRouter neutral dispatcher, all engines as peers — [plan](docs/plans/2026-04-14-pluggable-scripting-engine.md)
- [x] wasm3 scripting spike — `#b64\n` sigil, wasm3 engine plug — [plan](docs/plans/2026-04-14-wasm3-scripting-engine.md)
- [x] lua_engine fixes #1–#5 — compile cache, per-actor _ENV, Fennel pre-compilation, sandbox, debug prints — [plan](docs/plans/2026-04-15-lua-engine-fixes.md)
- [x] REST API PoC — cpp-httplib, 5 routes, GL wireframe box renderer, Postman collection playback
- [x] `wf_game -L<level.iff>` CLI flag — bypass cd.iff for dev iteration
- [x] movecam crash stabilised — invalid (Actor*)&msgData cast at movecam.cc:964 guarded; physics replacement planned
- [x] Rust tool ports (`iffcomp`, `iffdump`, `oaddump`, `lvldump`) — all build and pass tests; crates at `wftools/{iffcomp-rs,iffdump-rs,oaddump-rs,lvldump-rs}`; `wf_iff` + `wf_oad` as library foundations
