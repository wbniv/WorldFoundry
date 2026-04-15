# TODO




## SCRIPTING ENGINES

- [ ] Forth plug wiring — `scripting_forth.{hp,cc}`, per-backend impls, `\` sigil in ScriptRouter — [plan](docs/plans/2026-04-14-forth-scripting-engine.md)
- [ ] Wren plug — `wren_engine` namespace, `//wren\n` sigil, snowgoons port — [plan](docs/plans/2026-04-14-wren-scripting-engine.md)
- [ ] WAMR dev/ship — `wamr_engine` namespace, AOT-only ship target, replaces wasm3 for prod — [plan](docs/plans/2026-04-14-wamr-dev-aot-ship.md)
- [ ] JerryScript smoke test — not yet run; JS engine compiled but untested against snowgoons — [plan](docs/plans/2026-04-15-phase-d-scripting-engines.md)


## LUA ENGINE

- [ ] Fix #6 — coroutine continuations for multi-tick scripts (AI, cutscenes, dialogue) — [plan](docs/plans/2026-04-15-lua-engine-fixes.md)
- [ ] Lua remote step debugger — MobDebug / LuaLS-DAP wired into lua_engine for in-game step debugging


## SCRIPTING INFRASTRUCTURE

- [ ] `WF_DEFAULT_ENGINE` knob — sigil-less script fallback engine selection — [plan](docs/plans/2026-04-14-pluggable-scripting-engine.md)
- [ ] Mailbox constants cross-language audit — verify INDEXOF_* names are consistent across Lua/JS/wasm — [plan](docs/plans/2026-04-14-pluggable-scripting-engine.md)
- [ ] `scripts/check_iff_no_js.py` — JS footprint checker; blocked on JS scripts being authored into assets — [plan](docs/plans/2026-04-14-pluggable-scripting-engine.md)
- [ ] `WF_JS_ENGINE=jerryscript-nano` — deferred until footprint pressure — [plan](docs/plans/2026-04-14-pluggable-scripting-engine.md)
- [ ] Collapse wasm sigil `#b64\n` → bare `#` — workaround for cd.iff `##` TCL lines; revert once cd.iff cleaned up


## PHYSICS

- [ ] Replace physics engine — Jolt integration; pre-existing bad cast in movecam.cc:964 is the trigger — [investigation](docs/investigations/2026-04-14-jolt-physics-integration.md)


## TBD?

- [ ] `WF_JS_ENGINE=jerryscript-nano` footprint build
- [ ] Alternate wasm sigil `#!wat` — deferred pending wabt vendor — [plan](docs/plans/2026-04-14-wasm3-scripting-engine.md)
- [ ] Rust OAD layer — deferred indefinitely — [investigation](docs/investigations/2026-04-11-wftools-rewrite-analysis.md)


## DONE

- [x] Lua 5.4 interpreter spike — NullInterpreter replaced, snowgoons player + director ported — [plan](docs/plans/2026-04-13-lua-interpreter-spike.md)
- [x] Fennel on Lua — `;` sigil, embedded fennel.lua, sub-dispatch inside lua_engine — [plan](docs/plans/2026-04-14-fennel-on-lua.md)
- [x] Vendor Lua 5.4 — statically linked into wf_game — [plan](docs/plans/2026-04-14-vendor-lua.md)
- [x] Pluggable scripting engine — ScriptRouter neutral dispatcher, all engines as peers — [plan](docs/plans/2026-04-14-pluggable-scripting-engine.md)
- [x] wasm3 scripting spike — `#b64\n` sigil, wasm3 engine plug — [plan](docs/plans/2026-04-14-wasm3-scripting-engine.md)
- [x] lua_engine fixes #1–#5 — compile cache, per-actor _ENV, Fennel pre-compilation, sandbox, debug prints — [plan](docs/plans/2026-04-15-lua-engine-fixes.md)
- [x] REST API PoC — cpp-httplib, 5 routes, GL wireframe box renderer, Postman collection playback — [plan](docs/plans/2026-04-15-phase-d-scripting-engines.md)
- [x] `wf_game -L<level.iff>` CLI flag — bypass cd.iff for dev iteration
- [x] movecam crash stabilised — invalid (Actor*)&msgData cast at movecam.cc:964 guarded; physics replacement planned
