# Plan — Debug bridge gap features (mailbox write, input inject, script hot-swap, shader hot-reload, breakpoints)

**Date:** 2026-05-03

**Parent plan:** [2026-04-29-live-editor-bridge.md](2026-04-29-live-editor-bridge.md) — Phases 1–3 + parts of Phase 4 are landed. This plan covers the five remaining capabilities.

**Status:**
- Phase A — **landed** 2026-05-03 (commits 63f01d7, 1e0098e); pytest harness in [tests/test_phase_a.py](../../tests/test_phase_a.py) covers `set_mailbox` + `inject_input` end-to-end against qbert_practice.
- Phase B1 (`set_shader`) — **landed** 2026-05-03 (905a75a). Spike found there is no shader cache; ~80 LOC instead of 1–2 days. Tests in [tests/test_phase_b.py](../../tests/test_phase_b.py).
- Phase B2 (`reload_script`) — design agreed 2026-05-03: append-leak, dev/debug-only feature; per-actor override map keyed by `actor_idx` (not src pointer); ~100 reload budget per session before engine restart.
- Phase C — deferred per plan; see Phase C section.

## Goal

Round out the WF live debug bridge (TCP/JSON on port 7777) so it can verify and iterate on level scripts without rebuilds. Five features split into three buckets:

| # | Feature | Status today | Bucket |
|---|---|---|---|
| 1 | `set_mailbox` (write any global / actor-local mailbox over the wire) | never planned | **Phase A — quick wins** |
| 2 | `inject_input` (override `EMAILBOX_HARDWARE_JOYSTICK1_RAW` / button slots) | never planned | **Phase A — quick wins** |
| 3 | `set_shader` (recompile + swap a named GL shader on the next frame) | Phase 4 pending | **Phase B — main-thread asset hot-reload** |
| 4 | `reload_script` (re-parse zForth source, swap the per-actor script body) | never planned | **Phase B — main-thread asset hot-reload** |
| 5 | `set_breakpoint` / `break` / `step` at script labels (DAP-compatible) | Phase 4 pending | **Phase C — debugger** |

Phase A is ~half a day of work, Phase B is ~1–2 days, Phase C is the multi-week DAP integration. **Order is significant:** Phase A unblocks faster Forth-level iteration *today* without committing to the larger asset-pipeline or DAP designs.

**Hard constraint (carried from the parent plan and the ports memory):** all five features are debug-tool additions to the engine — **they do not change runtime game semantics**. They are not subject to the "no runtime changes for ports" rule because nothing a level script can observe is changed by their existence; turning the bridge off must leave the game identical. This makes them safe to land at any time without coordinating with port work.

## Phase A — quick wins (mailbox write + input inject)

These two are the smallest plumbing changes against the existing `PendingUpdate` queue in `engine/stubs/debug_server.cc:205`. Both follow the same shape as `WATCH` / `SET_PROP`: parse op, push a `PendingUpdate`, drain on the game thread, apply via an existing engine API.

### A1. `set_mailbox`

**Op:**
```json
{"op":"set_mailbox", "idx": <actor_idx>, "mailbox": <mbx_idx>, "value": <int>}
```

For `idx == 0` (or omitted) and a global mailbox index (≥ `MAILBOX_USER_BASE` per the existing convention), the write goes through `LevelMailboxes::WriteMailbox(mailbox, value)` (`wfsource/source/game/mailbox.cc:54`) — the same function the engine itself calls. For per-actor local mailboxes, route through `actor->GetMailboxes().WriteMailbox(...)`, mirroring how the `watch` op already resolves the actor for context.

**Engine-side changes** (~30 LOC, single file):
- `engine/stubs/debug_server.cc`:
  - Extend `PendingUpdate::Kind` enum with `SET_MAILBOX`.
  - Add fields: reuse `mailbox_idx` for the slot; reuse `value` (double) for the new value (truncate to `Scalar` on write).
  - Parse handler (alongside `watch`/`unwatch` at line 335):
    ```cc
    } else if (op == "set_mailbox") {
        PendingUpdate u;
        u.kind        = PendingUpdate::SET_MAILBOX;
        u.actor_idx   = parse_jint(line, "idx", 0);
        u.mailbox_idx = parse_jint(line, "mailbox", -1);
        u.value       = parse_jnum(line, "value", 0.0);
        gQueue.push(u);
    }
    ```
  - Drain handler (alongside the existing `WATCH` branch):
    ```cc
    } else if (u.kind == PendingUpdate::SET_MAILBOX) {
        Actor* actor = (u.actor_idx > 0) ? lookup_actor(u.actor_idx) : nullptr;
        if (actor) {
            actor->GetMailboxes().WriteMailbox(u.mailbox_idx, (Scalar)u.value);
        } else {
            // Global mailbox path — same dispatch ReadMailbox uses for global
            // indices in the level mailbox space.
            level._levelMailboxes.WriteMailbox(u.mailbox_idx, (Scalar)u.value);
        }
    }
    ```
- `engine/stubs/debug_server.hp`: no public-API change (the queue is internal).
- No `kPropMap` change. No new memory.

**Undo / revert:** Phase 3 already records pre-change state for `SET_PROP` and `SET_TRANSFORM` into `gChangeStack` and `gOriginals`. Extend with a `MAILBOX` `ChangeRecord::Kind` so `undo_step` can pop a mailbox write and restore the prior value. ~5 extra LOC.

**Verification:**
- `qbert_practice` is the canonical bench. Launch `task run-debug -- wflevels/qbert_practice-standalone.iff`, then send `{"op":"set_mailbox","mailbox":200,"value":2}`. Expect cube 0 to flip from teal to yellow within one frame, and the per-child visibility scripts (which read 200) to drive the visibility mailboxes 300/301/302.
- Test `undo_step` brings cube 0 back to teal.
- Test write to a per-actor local slot (`Number Of Local Mailboxes` > 0).

**Estimated effort:** half a day, including verification harness.

### A2. `inject_input`

**Op:**
```json
{"op":"inject_input", "slot":"joystick1_raw", "value": <int>, "duration_frames": <N|0>}
```

`slot` selects which input-mailbox is overridden. Initial set: `joystick1_raw`, `joystick1_raw_justpressed`, `joystick1` (post-deadzone), `joystick2_raw`, etc. — whatever the existing `EMAILBOX_HARDWARE_JOYSTICK*` enum covers (`wfsource/source/game/level.cc:1405`).

`duration_frames`:
- `0` (default) — one-frame override; the next HID poll wins again.
- `N > 0` — sticky for N frames.
- `-1` — sticky until cleared by a follow-up `inject_input` with `value: 0`.

**Engine-side changes** (~40 LOC):
- The HID layer writes into the joystick mailboxes once per frame (search target: wherever `EMAILBOX_HARDWARE_JOYSTICK1_RAW` is set; line 1409 of `level.cc` dispatches reads, the writer is in the input subsystem). Add an "override" layer in front of that writer: a small static struct in `debug_server.cc` holding `{ slot_id, value, frames_remaining }` per slot, drained at the same point HID is normally polled.
- `PendingUpdate::Kind` gains `INJECT_INPUT`.
- The HID writer checks the override table after writing the real value; if active, replaces the mailbox value with the override and decrements `frames_remaining`.

**Why an override layer instead of just calling `set_mailbox` on `EMAILBOX_HARDWARE_JOYSTICK1_RAW`:** the HID poll runs every frame and would clobber a one-shot `set_mailbox` write before any script could read it. The override layer is what makes injection actually testable; otherwise it races the HID.

**Verification:**
- Launch qbert_practice on the bridge, send `{"op":"inject_input","slot":"joystick1_raw","value":2048,"duration_frames":1}` (2048 = `EJ_BUTTONF_UP`). Expect Q\*bert to start a hop arc on the next frame.
- Watch `INDEXOF_HOP_PHASE` (402) transition 0 → 1 → ... → 0 over ~24 frames.
- Verify that injecting nonsense (e.g. value `-1`) doesn't crash anything.

**Estimated effort:** half a day, mostly figuring out the right HID-write callsite.

### Phase A out-of-scope

- **Multi-actor batched writes.** A `set_mailboxes` op taking a `[{idx, mailbox, value}, ...]` array would be useful for "set all 28 cube states to 2" tests, but `set_mailbox` × 28 in a tight loop is fine for now (the queue handles it).
- **Mailbox-as-watchpoint** (engine pauses when mailbox value crosses a threshold). Useful for catching "who set this" bugs, but Phase C breakpoints subsume it.

---

## Phase B — main-thread asset hot-reload (shader + script)

These two need the same architectural piece — a **main-thread deferred-work queue** — because GL calls and the zForth dictionary both have thread-affinity that the bridge listener thread doesn't have. The existing `DrainQueue` runs on the game thread but **before** rendering; shader and script reloads should run at a known-safe point.

### B1. `set_shader` (Phase 4 of parent plan)

**Spike findings (2026-05-03):** there is no shader cache. [`backend_modern.cc`](../../wfsource/source/gfx/glpipeline/backend_modern.cc) holds a single program (`_prog`) compiled once in `LazyInit()` from two embedded `const char*` strings (`kVS`, `kFS`). The legacy fixed-function path was retired post-Phase 0 4c(f) per the file header — there's only one backend. No name-keyed map, no material system above. Threading is also free: the renderer runs on the same thread as `Level::update()` ([game.cc:319](../../wfsource/source/game/game.cc)), so the existing `DrainQueue` is the right place to invoke a reload — no second queue needed.

**Op:**
```json
{"op":"set_shader", "vert":"...", "frag":"..."}
```
`name` is omitted because there's only one program. Forward-compat: a future per-pass shader system can add `name` and treat the absence as "main".

**Engine-side changes (~80 LOC):**
- [`renderer_backend.hp`](../../wfsource/source/gfx/renderer_backend.hp): add a virtual `bool ReloadProgram(const char* vert, const char* frag, std::string& log_out)` to `RendererBackend`, with a default no-op base impl so non-modern backends (none today) don't have to implement it.
- [`backend_modern.cc`](../../wfsource/source/gfx/glpipeline/backend_modern.cc):
  1. Refactor `CompileShader` and `LinkProgram` to non-aborting variants — return `0` on failure, write the log into a `std::string&` out-param. The old aborting behavior is kept inside `LazyInit()` (a compile failure at startup is still fatal).
  2. Implement `ReloadProgram`: `Flush()` first, compile new vs+fs, link new program, on success swap `_prog` and re-fetch all 12 uniform locations, delete the old program; on failure leave `_prog` untouched and write the log to `log_out`.
- [`debug_server.cc`](../../engine/stubs/debug_server.cc):
  - `PendingUpdate::Kind::SET_SHADER`, two `std::string` fields for vert/frag source.
  - Parse handler alongside `set_mailbox`.
  - Drain handler calls `RendererBackendGet().ReloadProgram(...)` and replies `{"op":"shader_reloaded"}` or `{"op":"error","what":"shader_compile","log":"..."}`.

**Verification:**
- Push GLSL that multiplies output by `vec3(1, 0, 0)`, expect everything to turn red on the next frame. Push the original back, scene returns to normal.
- Push deliberately broken GLSL, expect an error reply with the log and an unchanged scene.
- Pytest case in [tests/test_phase_b.py](../../tests/test_phase_b.py) covers both happy + sad paths.

**Estimated effort (revised):** ~3 hours including pytest. The original 1–2 day estimate assumed a shader cache that doesn't exist.

### B2. `reload_script` (zForth hot-swap)

**Op:**
```json
{"op":"reload_script", "idx": <actor_idx>, "source": "<zforth source>"}
```

**The hard part — zForth's dictionary model.** The vendored `engine/vendor/zforth-41db72d1` keeps a single shared dictionary; per-actor "scripts" are entry points into that dictionary that share state. Hot-swapping one actor's script body without disturbing other actors' entry points needs one of:

- **Approach 1 — append-only dictionary (simplest, leaks).** Each `reload_script` compiles the new source as fresh dictionary entries with mangled names; the actor's script handle is updated to point at the new entry. Old entries are orphaned but not freed. Acceptable for debug iteration where you'll restart the engine after a session.
- **Approach 2 — per-actor dictionaries (correct, big change).** Each actor gets its own zForth interpreter instance with its own dict. Memory cost = `ZF_DICT_SIZE` × actors; ~10 KB × hundreds of actors = MB-scale. Probably too expensive for the engine's mobile targets but fine on Linux desktop.
- **Approach 3 — dictionary checkpoints (pragmatic).** Snapshot the dict pointer before compiling each actor's initial script at level load. On `reload_script`, rewind the dict pointer to that actor's checkpoint, recompile. Safe **only** if scripts don't define globally-visible words after their checkpoint — which the zForth scripts in `mm_practice` and `qbert_practice` happen not to do.

**Decision (2026-05-03):** Approach 1 (append + leak). User-confirmed dev/debug-only feature; restart after ~100 reloads is acceptable. `ZF_DICT_SIZE = 65536` and a typical qbert script is ~500 bytes → ~200–400 dict bytes per reload.

**Implementation choice — override map, not pointer overwrite.** The plan originally said to overwrite `actor->GetCommonBlockPtr()->Script`. Implementation goes the other way: keep the OAD pointer untouched, maintain `actor_idx → wordName` override map inside `scripting_zforth.cc`, and have `RunScript` consult it before falling through to the existing src-pointer cache. Localises every reload-related change to one file and one map; `revert_all` just clears the map. No new lifetime story, no chance of corrupting `_pScript`.

**Engine-side changes:**
- [`scripting_forth.hp`](../../engine/stubs/scripting_forth.hp): add `bool ReloadActorScript(int actor_idx, const char* src, std::string& log_out)`, `void ClearActorScriptOverrides()`, `void ClearActorScriptOverride(int)`.
- [`scripting_zforth.cc`](../../engine/stubs/scripting_zforth.cc): `g_actorOverride` map; `RunScript` consults it first. Reload compiles a fresh `_wfsRldN` wrapper word with N from a session-monotonic counter; on success registers the override, on `zf_eval` failure returns the `zf_result` name in `log_out` and leaves the prior override intact.
- [`debug_server.cc`](../../engine/stubs/debug_server.cc): `RELOAD_SCRIPT` op. Tracks `gLastReloadSource[idx]` so `undo_step` can recompile the prior source (also leaks dict bytes — acceptable for debug). New `ChangeRecord::SCRIPT` records the prior source; undo restores it (or clears the override if there was no prior). `revert_all` calls `ClearActorScriptOverrides()`.
- [`debug_server.cc`](../../engine/stubs/debug_server.cc): **`common.Script` guard** — `SET_PROP` rejects `common.Script` with an explanatory error pointing the caller at `reload_script` instead.

**Helper-word collision is correct.** zForth allows redefinition (new word wins). When actor 5's reload defines `: stick ...`, the new `stick` shadows the old. **But** wrapper words for OTHER actors (e.g. `_wfs7`) were *compiled* against the old `stick`'s dict address, so they keep using the old definition. Result: actor 5 gets the new helpers, every other actor undisturbed. Falls out of zForth's append-only model for free.

**Critical constraint inherited from the parent plan:** `scene:set_prop` on `common.Script` was previously routable through `kPropMap` and corrupted the Script handle field. Landed alongside B2: `SET_PROP` drain handler hard-errors on `common.Script` with an explanatory "use reload_script instead" message. The `kPropMap` entry stays (so the lookup still finds it and we can produce a specific error rather than a generic "unknown property") but never reaches the writer.

**Verification:**
- Edit the qbert director script's win-counter loop to count differently (e.g. count cubes where state == 0 instead of != 2), push via `reload_script` mid-game, watch mailbox 412 change.
- Push a script with a syntax error, expect `{"op":"error","what":"script_compile","idx":N,"log":"..."}` and the old script still running.
- Push 50 reloads in a session, confirm no crash (Approach 1 leak budget).

**Estimated effort:** 2 days (most of which is choosing the dict-management approach and handling errors).

---

## Phase C — script breakpoints (DAP)

The parent plan recommends adopting **DAP** (Debug Adapter Protocol) for this rather than rolling a custom `set_breakpoint` op. Reasoning re-confirmed from `2026-04-29-live-editor-bridge.md:213` — VS Code, JetBrains, Neovim, and Emacs all speak DAP, so a DAP server in the engine gives every editor for free.

This phase is large enough that it warrants **its own plan document** rather than a section here. Sketch only:

- New listener thread on a separate port (8888?) speaking DAP-over-TCP — keep the bridge on 7777 for game-state ops, DAP on its own socket for script debugging.
- Hook points in zForth: pre-execute callback on each Forth word, with line-number map (zForth doesn't currently track source line numbers — this is a precondition).
- Capabilities: breakpoints by `(script_id, label)` initially, then by source line once the line-number map lands. Step / continue / pause / variable inspection (mailboxes-as-locals).
- Use `cppdap` (Google, Apache-2.0) as the protocol implementation, link statically.

**Effort estimate:** 2–4 weeks. **Recommendation:** do not start until Phase A and B are landed and there is a concrete "I keep needing this" pain point — DAP is high effort and the simpler ops above cover ~80% of debug needs.

**This plan defers Phase C** to a follow-up plan: [2026-05-03-script-debugger-dap.md](2026-05-03-script-debugger-dap.md). That doc is written but **not started** — trigger to begin work is "Phase A and B have been used in anger for ~1 week and a concrete pain point has surfaced".

---

## File touch list

| Phase | File | Action |
|---|---|---|
| A1, A2 | `engine/stubs/debug_server.cc` | extend `PendingUpdate`, add op parsers + drain handlers |
| A1 | `wfsource/source/game/mailbox.cc` | (no change — `WriteMailbox` already exists) |
| A2 | input subsystem (TBD — `wfsource/source/game/level.cc` area or HID layer) | add override hook ahead of HID write |
| B1 | `wfsource/source/gfx/glpipeline/backend_modern.cc` | add `Reload(name, vert, frag)` entry point + cache lookup |
| B1 | `engine/stubs/debug_server.cc` | enqueue → render-thread drain |
| B2 | `engine/stubs/scripting_zforth.cc` | add `RecompileScript`, choose dict-management approach |
| B2 | `engine/stubs/debug_server.cc` | guard `kPropMap`'s `common.Script` (reject set_prop), add `reload_script` op |
| Phase C | (separate plan doc) | DAP server, line-number map, port 8888, cppdap dep |

## Verification matrix (cross-cutting)

After each phase, the bridge should still behave correctly for everything below it:

| Capability | Phase 1 | Phase 2 | Phase 3 | Phase A | Phase B | Phase C |
|---|---|---|---|---|---|---|
| Connect / log stream | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Transform / property write | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Pause / step / pick | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| Undo / revert (incl. mailbox & script) | — | — | ✓ | + mailbox | + script | + script |
| `watch` / `mailbox` push | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `set_mailbox` | — | — | — | ✓ | ✓ | ✓ |
| `inject_input` | — | — | — | ✓ | ✓ | ✓ |
| `set_shader` | — | — | — | — | ✓ | ✓ |
| `reload_script` | — | — | — | — | ✓ | ✓ |
| DAP breakpoints | — | — | — | — | — | ✓ |

A regression test in `wftools/wf_blender/debug_bridge.py` (or a new `tests/` directory) should exercise the row marked ✓ for the current phase. Existing Phase 1–3 ops have ad-hoc verification only — Phase A is a good time to add a small pytest harness that boots qbert_practice headless and exercises each op.

## Risks & open questions

- **HID-write callsite for `inject_input`.** Confirmed `EMAILBOX_HARDWARE_JOYSTICK1_RAW` slot exists, but the writer location is not yet identified in the source tree. Half-day spike at the start of Phase A2 to find it.
- **Shader cache structure.** Same: half-day spike at start of B1 to read `backend_modern.cc` end-to-end and document the cache key.
- **zForth dictionary management.** Approach 1 (leak on reload) is the recommended path, but it requires explicit operator buy-in — calling out here so it isn't quietly chosen at implementation time.
- **`common.Script` guard.** Removing `common.Script` from `kPropMap` is a behavior change for any existing tool that pushes property writes. Today no such tool exists (the property is corrupted by the write, so nothing relies on it), but worth a `git grep set_prop.*Script` before landing.
- **Phase C deferral.** If a port project (e.g. Q\*bert beyond MVP, or a heavier-Forth game like Bomberman) hits a script bug that takes > 1 hour to diagnose without a debugger, that's the signal to start the DAP plan early.

## Acceptance criteria

Phase A done when:
1. `set_mailbox` works against global and per-actor mailboxes, with undo.
2. `inject_input` lets a Python script make Q\*bert hop in all four diagonals from the bridge with no joystick connected.
3. Both ops covered by automated tests against qbert_practice.

Phase B done when:
1. `set_shader` swaps a live program with no flicker; broken GLSL leaves the prior shader running and reports the compile log.
2. `reload_script` swaps a live actor's Forth without disturbing other actors; mailboxes survive the swap; broken Forth leaves the prior script running and reports the compile log.
3. Documentation updated in `docs/scripting-languages.md` ("hot-reload caveats: dictionary leaks per session, restart engine after ~100 reloads").

Phase C done when: covered by its own plan document.
