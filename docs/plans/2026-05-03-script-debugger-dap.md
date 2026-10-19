# Plan — Script debugger via DAP (zForth step / breakpoints / variable inspection)

**Date:** 2026-05-03

**Status:** Not started — deferred. Trigger to begin: Phase A and Phase B of the [debug-bridge gap-features plan](2026-05-03-debug-bridge-gap-features.md) have been used in anger for ≈ 1 week and a concrete "I keep needing this" pain point has surfaced (e.g. a script bug whose diagnosis cost > 1 hour without step debugging).

**Parent plans:**
- [2026-04-29-live-editor-bridge.md](2026-04-29-live-editor-bridge.md) — original Phase 4 sketch; the relevant analysis of DAP vs. CDP vs. GDB-RSP vs. Godot's protocol is at lines 200–248.
- [2026-05-03-debug-bridge-gap-features.md](2026-05-03-debug-bridge-gap-features.md) — Phase C section explicitly defers to this document.

## Goal

Give level-script authors a real source-level debugger for zForth: set breakpoints, step, pause, inspect mailbox values as locals, and resume — from VS Code, Neovim, JetBrains, or Emacs without WF shipping any editor plugin. The bridge on port 7777 stays the game-state channel; debugging gets its own socket on port **8888** speaking [Debug Adapter Protocol](https://microsoft.github.io/debug-adapter-protocol/) over TCP.

**Non-goal:** debugging the C++ engine — that is what `gdb`/`lldb` are for. This plan covers script-level breakpoints only.

**Why DAP and not a custom op:** every modern editor already speaks DAP. Rolling a `set_breakpoint` / `step` / `continue` op set in our bridge would force users to write a separate editor extension per editor. With DAP, one server in `wf_game` lights up four editors at once. Decision originally made in the parent plan ([line 213](2026-04-29-live-editor-bridge.md)); re-confirmed here because nothing has changed.

## Hard preconditions (must land before any DAP code)

These two are the real cost. The DAP protocol layer itself is mechanical — what is hard is making zForth observable.

### P1 — zForth source-line map

zForth (`engine/vendor/zforth-41db72d1/src/zforth/zforth.c`) does **not** track source line numbers when compiling. Words live in the dictionary as bytecode with no back-link to source. For source-line breakpoints we need a side table built during compilation: `(actor_handle, dictionary_addr) → (script_id, line_number)`.

Two ways to build it:

- **Wrapper-side mapping** (preferred): instrument `engine/stubs/scripting_zforth.cc`. Before each call to `zf_eval`, feed source one line at a time, snapshot the dictionary `here` pointer before/after each line. Any code compiled in that window belongs to that line. Cheap, no upstream zForth changes.
- **Vendor patch**: add `zf_addr` line-number side-array inside `zforth.c`'s `do_word`. More invasive; harder to keep in sync if we ever bump zForth.

Pick the wrapper-side approach. The map lives in our stub, not in vendored code.

### P2 — pre-execute callback in zForth

Step / breakpoint requires a hook fired *before* each Forth word executes, with current dictionary address and access to the data stack. zForth has `ZF_ENABLE_TRACE` + `zf_host_trace` (see `zforth.h:91, 107`) — that's a *post-hoc printf* hook, not an interception point. We need either:

- A new compile-time `ZF_ENABLE_STEP` macro inside `zforth.c`'s inner interpreter loop that calls a host callback `zf_host_step(zf_ctx*, zf_addr ip)` with the option to suspend (return value asks for: continue / pause / abort).
- Or: rewrite each compiled word's first opcode to a `BREAK` primitive when a breakpoint lands on it, and restore on continue. Avoids the per-word callback overhead but is fiddly with multi-cell primitives.

Recommend the macro path. The cost of one indirect call per inner-loop iteration is fine for a debug build; the production-build engine compiles `ZF_ENABLE_STEP=0` and the hook compiles to nothing.

**Vendor patch:** this is the one place a small patch to `engine/vendor/zforth-41db72d1/src/zforth/zforth.c` is unavoidable. Keep it minimal (≤ 30 LOC) and document it in `engine/vendor/README.md` so a future zForth bump knows what to re-apply.

### P3 — pause-the-world primitive

When a breakpoint hits, the game thread needs to stop running scripts but keep rendering and keep handling DAP requests. The bridge's existing pause op (Phase 2) stops *everything* — including input — which is the wrong shape: a debugger pause should freeze game logic but the editor's introspection requests still need to execute. Add `Level::PauseScripts()` distinct from the existing `Level::Pause()`.

## Architecture

```
   ┌──────────────┐   port 7777 (bridge)    ┌────────────────────┐
   │  editor /    │  ─────────────────────▶ │  debug_server.cc   │
   │  CLI tool    │  ◀───────────────────── │  (game-state ops)  │
   └──────────────┘                         └────────────────────┘
                                                     │
   ┌──────────────┐   port 8888 (DAP)               │ shared
   │  VS Code /   │  ─────────────────────▶ ┌────────────────────┐
   │  nvim-dap /  │                         │  dap_server.cc     │
   │  ...         │  ◀───────────────────── │  (cppdap)          │
   └──────────────┘                         └────────────────────┘
                                                     │
                                                     ▼
                                            ┌────────────────────┐
                                            │ scripting_zforth.cc│
                                            │  + step hook       │
                                            │  + line map        │
                                            └────────────────────┘
```

**Two sockets, one engine.** They share access to the same `Level*` and the same pause flag, but the protocols are independent. Conceptually the bridge handles "the editor wants to nudge game state" and DAP handles "the editor is stepping through a script".

## Library choice — cppdap

Use [`cppdap`](https://github.com/google/cppdap) (Google, Apache-2.0). It is a header-light C++ library that implements DAP request/response/event marshalling. We provide:

- A `dap::net::Server` listening on TCP 8888.
- Implementations for the request handlers we care about (table below).
- Event emitters for `stopped`, `output`, `terminated`.

Vendor it under `engine/vendor/cppdap-<sha>/`, mirror the existing pattern (jolt, miniaudio, quickjs, etc.). Build statically. Estimated size: low single-digit MB; well under the 40 MB ceiling per the no-giant-vendor feedback.

Explicitly **not** writing our own DAP marshaller. We have already done one bespoke JSON protocol (the bridge) — duplicating that effort for DAP is exactly the trap this plan exists to avoid.

## DAP capability scope

Initial cut, sized to ship in one workable increment:

| DAP request | Phase C scope | Notes |
|---|---|---|
| `initialize` | ✓ | Advertise capabilities below. |
| `launch` / `attach` | ✓ attach only | We do not launch wf_game from the editor; user runs the game, then attaches. |
| `setBreakpoints` | ✓ by `(script_id, label)` first; by `(source_path, line)` once P1 lands | Two stages — see below. |
| `configurationDone` | ✓ | |
| `threads` | ✓ | One synthetic thread (the game thread). |
| `stackTrace` | ✓ shallow | Top frame = current Forth word; we do not unwind the Forth call stack initially. |
| `scopes` / `variables` | ✓ | Mailboxes-as-locals: each scope is the current actor's mailbox table. |
| `continue` / `pause` / `next` / `stepIn` / `stepOut` | ✓ except `stepIn`/`stepOut` initially (no Forth-word call-stack walking yet) | |
| `evaluate` | ✓ | Pipe expression to `zf_eval` with output captured; reply with stack-top. |
| `disconnect` | ✓ | Clears all breakpoints, resumes. |

**Two-stage breakpoints:**

- **Stage 1** — labels only: `setBreakpoints` with `source.name == "<script_id>"` and `breakpoints[].name == "<word>"`. Trips when the Forth word with that name is about to execute. Easy — does not need P1 (the line map). Editors don't natively offer "pick a word"; users will invoke this through a "WF: break on Forth word…" command in a small VS Code companion (one optional `package.json` extension that wraps the standard DAP debug type).
- **Stage 2** — by source line: standard "click in the gutter" UX. Requires the line map from P1.

Ship Stage 1 first. Stage 2 lights up the moment P1 is implemented, with no wire-protocol changes.

## Variable inspection — mailboxes as locals

A debugger that stops on a breakpoint without showing variable values is half-useless. Forth has no named locals, but WF actors have **mailboxes** — both global and per-actor — and those *are* the script's state. The mapping:

| DAP scope | WF data |
|---|---|
| `Locals` | Current actor's mailbox table (`actor->GetMailboxes()`); names from the actor's mailbox-name array |
| `Arguments` | Top of the data stack (last 4 cells), shown as `tos`, `tos-1`, `tos-2`, `tos-3` |
| `Globals` | `LevelMailboxes` — mailboxes ≥ `MAILBOX_USER_BASE`; names from the level's name table |

Variables are read-only in Phase C v1. To write, the editor user already has `set_mailbox` on the bridge from Phase A — point them at that instead of widening the DAP write path.

## Threading & lifecycle

- DAP server starts in `LazyInit()` of `wf_game` if env `WF_DAP_PORT` is set (default unset → no DAP listener; matches how `WF_DEBUG_BRIDGE_PORT` already gates the bridge).
- Listener accepts on port 8888 in its own thread. cppdap takes care of request dispatch.
- Step / breakpoint hits run on the **game thread** (inside `zf_host_step`); they signal a condition variable that the DAP thread reads to emit a `stopped` event to the editor. The game thread blocks on the same condvar until `continue` / `next`.
- Pausing freezes scripts (via P3) but rendering continues — so the game window stays live while the editor inspects. No frozen-window UX.

This is the same pattern Lua's `MobDebug` and Python's `debugpy` use; nothing novel.

## Effort & file touch list

| Component | New / modified | LOC | Effort |
|---|---|---|---|
| **P1** — line map in `scripting_zforth.cc` | modify | ~80 | 2–3 days |
| **P2** — `ZF_ENABLE_STEP` patch in vendored `zforth.c` + `zforth.h` | vendor patch | ~30 | 1 day |
| **P3** — `Level::PauseScripts()` | modify `wfsource/source/game/level.cc` | ~40 | 0.5 day |
| **cppdap** vendor + CMake wiring | new `engine/vendor/cppdap-<sha>/` + `engine/CMakeLists.txt` | (drop-in) | 0.5 day |
| `dap_server.cc` / `.hp` | new in `engine/stubs/` | ~600 | 5–7 days |
| Stage 1 breakpoints (label match) | within `dap_server.cc` | (in above) | (in above) |
| Stage 2 breakpoints (line match) | within `dap_server.cc` once P1 lands | (in above) | (in above) |
| Optional VS Code companion (`wf-debugger/`) | new top-level dir | ~150 | 1 day |
| Pytest harness — boot qbert_practice, attach via cppdap client, set breakpoint on `qbert-tick`, expect `stopped` | new `tests/test_dap.py` | ~120 | 1 day |
| Docs — [docs/script-debugger.md](../script-debugger.md) (attach instructions for VS Code / nvim-dap) | new | ~80 | 0.5 day |

**Total: 2–4 weeks**, consistent with the parent plan's estimate. Wide range because P2 (vendor patch) carries unknown risk if zForth's inner loop is more entangled than a quick read suggests.

## Acceptance criteria

Phase C is done when:

1. With `WF_DAP_PORT=8888`, qbert_practice launches and accepts a VS Code DAP attach on port 8888.
2. A breakpoint on the `qbert-tick` word in qbert's director script trips on every game tick; `continue` advances by one tick.
3. The Locals / Globals scopes show the current actor's and level's mailbox tables, with values updating after each `continue`.
4. `evaluate` against `INDEXOF_HOP_PHASE @ .` prints the current hop phase.
5. Detaching the editor leaves the game running with no breakpoints set and no stalls.
6. Pytest harness covers attach → breakpoint → continue against qbert_practice headless.
7. The vendor patch to zForth is documented in `engine/vendor/README.md` with the exact diff and reapplication notes.

## Risks & open questions

- **zForth inner-loop overhead.** A per-word callback adds an indirect call to the hottest path in scripting. If profiling shows this hurts even the production build (it shouldn't — `ZF_ENABLE_STEP=0` should compile it out), revisit Approach 2 (rewrite first opcode to `BREAK`) for a zero-overhead opt-out.
- **Multiple actors, one breakpoint.** A breakpoint on a shared word fires every time *any* actor hits it. Filtering by actor is not in v1 — users get noisy stops. Add a `condition` (DAP supports conditional breakpoints) that compares the current actor index against a captured value once it becomes annoying.
- **Hot-reloaded scripts and stale breakpoints.** Once Phase B2 (`reload_script`) lands, a recompile invalidates dictionary addresses; breakpoints set against the old dictionary entries will silently stop firing. Solution: on `reload_script`, re-resolve all active breakpoints against the new dictionary by name. Cross-cuts with [Phase B2](2026-05-03-debug-bridge-gap-features.md#b2-reload_script-zforth-hot-swap) — the order matters: Phase B2 should land first so we know the recompile shape we're integrating against.
- **Forth call-stack visibility.** zForth's return stack holds dictionary addresses, not source frames. Mapping those back to user-recognisable names needs the line map (P1) plus a reverse lookup `dictionary_addr → word_name`. Doable; deferred from v1.
- **Variable write through DAP.** Users will eventually want to right-click → set value. Maps cleanly onto the bridge's existing `set_mailbox` op, but exposing it through DAP requires plumbing. Defer.
- **Other scripting engines.** This plan is zForth-only. Lua already has MobDebug, QuickJS already has CDP — neither needs WF code. Wren / WAMR / pforth / atlast / ficl / nanoforth would each need their own equivalents and probably never get them. Not a v1 concern.

## What this plan deliberately does **not** cover

- Debugger UI for non-DAP editors (Sublime, Vim without nvim-dap, Helix, Zed). Users on those editors fall back to the bridge's `watch` / `set_mailbox` ops.
- Time-travel / reverse-step. Out of scope; would require deterministic replay (which WF does not have today).
- Profiling / flamegraphs. Different problem; mention here only to say "not this plan".
- C++ engine debugging — `gdb` exists.
- A WF-specific protocol layered on DAP. We use DAP as-is; any extensions go through DAP's `customRequest` mechanism, not via a parallel schema.
