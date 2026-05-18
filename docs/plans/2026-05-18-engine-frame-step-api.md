# Engine frame-step API — split `WFGame::RunLevel` into per-frame `StepFrame`

**Status:** Parked (TODO). Plan agreed 2026-05-18; not yet implemented. Sub-task #1 of Phase 0b in the [collaborative editor design doc](../investigations/2026-05-18-collaborative-level-editor-design.md). Trigger to start: editor prototype gets past file-watch and needs direct frame-stepping from a host process. ~1–2 weeks estimated. Independent of [sub-task #2 (external GL context)](2026-05-18-engine-external-gl-context.md) — either can land first.

## Context

[`WFGame::RunLevel`](../../wfsource/source/game/game.cc) at line 256 owns the per-frame loop:

```cpp
while ( !_curLevel->done() && _bContinue && !HALWindowCloseRequested() ) {
    if (HALIsSuspended()) { HALPumpSuspendedEvents(); usleep(16000); continue; }
    RestApi_DrainQueue();
    DebugServer_DrainQueue(*_curLevel);
    if (PIGSUserAborted()) { _bContinue = false; ... }
    _curLevel->Validate();
    if (!DebugServer_IsPaused()) _curLevel->update(deltaTime);
    if (camera valid) { _display->RenderBegin(); _curLevel->RenderScene(); _display->RenderEnd(); }
    DebugServer_Broadcast{State,Perf,Mailboxes}(*_curLevel);
    // designer-cheats HUD/initials block
    deltaTime = _display->PageFlip();
}
```

For an editor that embeds the engine into its own widget, the editor needs to own the outer loop. The engine should expose "step one frame" rather than "run forever" — caller drives cadence, caller decides when to swap buffers, caller queries lifecycle state instead of relying on `while` predicates inside the engine.

## Architectural approach

1. **Split body and loop.** New method `WFGame::StepFrame(bool do_swap, Scalar* out_dt)` does one tick — suspend-check + cheats + `Level::update` + render + DebugServer broadcasts + designer-cheats HUD + optional `PageFlip`. Returns `FrameResult` enum: `Rendered`, `Suspended`, `Done`.

2. **Caller-owned loop predicates.** The terminating conditions (`_curLevel->done()`, `_bContinue`, `HALWindowCloseRequested()`) become queryable state: `WFGame::LevelDone() const`, `WFGame::ContinueRequested() const`. `HALWindowCloseRequested()` stays a free function callers can poll separately (and the editor will replace with its own window-close handling in [sub-task #2](2026-05-18-engine-external-gl-context.md)).

3. **`_curLevel` and `_bContinue` promoted to `WFGame` members.** Today they're locals in `RunLevel`; the editor needs to construct a level and then step it across many `StepFrame` calls. Pair with new `WFGame::LoadLevel(_DiskFile*)` / `WFGame::UnloadLevel()` methods that wrap the per-level setup (music, SFX, RestApi, DebugServer) and teardown.

4. **Suspend handling stays inside `StepFrame`.** Android's `HALIsSuspended` + `HALPumpSuspendedEvents` is platform glue that runs regardless of host — embed inside `StepFrame`, return `FrameResult::Suspended` so the host can decide what to do (sleep, render its own UI, whatever). Standalone `wf_game`'s loop ignores the result and falls through to the next iteration.

5. **`PageFlip` becomes a parameter.** `StepFrame(do_swap=true)` defaults to swapping — standalone behaviour preserved. Editor passes `do_swap=false` and drives `_display->PageFlip()` itself when it wants to swap after compositing its own widgets on top. `out_dt` returns the measured deltaTime either way; when `do_swap=false`, expose a separate `Display::MeasureDelta()` (renamed from the timing block currently inside `PageFlip`) so the host can recover the same number.

6. **deltaTime clamp inside `StepFrame`.** Editor-paused-on-a-modal would otherwise hand the simulation a multi-second `deltaTime` on the next step. Clamp to ≤100 ms inside `StepFrame` per the variable-tick-rate constraint ([project_variable_tick_rate_loadbearing](../../../.claude/projects/-home-will-WorldFoundry/memory/project_variable_tick_rate_loadbearing.md)). Matches existing [Jolt](https://github.com/jrouwe/JoltPhysics) substep tolerance.

7. **`RunLevel` becomes a thin loop.** Setup (music, SFX, RestApi, DebugServer) stays at the top; loop becomes `while (!LevelDone() && ContinueRequested() && !HALWindowCloseRequested()) StepFrame(true);`; teardown stays at the bottom. Standalone behaviour bit-identical.

8. **`RunGameScript` is untouched.** The per-level outer loop in `WFGame::RunGameScript` (level-by-level cycling) stays as-is. Editor v1 pins to one level via the existing `gLevelOverridePath` / `-L` flag — no need to expose level-cycling control yet.

## Files modified

| File | Change |
|---|---|
| [wfsource/source/game/game.hp](../../wfsource/source/game/game.hp) | Add `enum class FrameResult { Rendered, Suspended, Done };`. Add `FrameResult StepFrame(bool do_swap = true, Scalar* out_dt = nullptr);`. Add `bool LevelDone() const;`, `bool ContinueRequested() const;`. Add `void LoadLevel(_DiskFile*); void UnloadLevel();`. Promote `_curLevel`, `_bContinue` to private members. |
| [wfsource/source/game/game.cc](../../wfsource/source/game/game.cc) | Implement `LoadLevel` (music + SFX + `RestApi_Start` + `DebugServer_Start` + `new Level(...)`). Implement `StepFrame` (body lifted from `RunLevel`'s `while` interior, plus the deltaTime clamp). Implement `UnloadLevel` (`RestApi_Stop` + `DebugServer_Stop` + music stop + SFX clear + `MEMORY_DELETE _curLevel` + final two `PageFlip` calls). Rewrite `RunLevel` as `LoadLevel(...); while (...) StepFrame(true); UnloadLevel();`. |
| [wfsource/source/gfx/display.hp](../../wfsource/source/gfx/display.hp), [wfsource/source/gfx/gl/display.cc](../../wfsource/source/gfx/gl/display.cc) | Add `Scalar MeasureDelta()` that returns the same deltaTime `PageFlip` currently computes, without doing the actual buffer swap. Used by host-driven `do_swap=false` callers. |
| [wfsource/source/hal/lifecycle.h](../../wfsource/source/hal/lifecycle.h) | No change. `HALWindowCloseRequested`, `HALIsSuspended`, `HALPumpSuspendedEvents` stay free functions. |

No file deletions; no header break (`StepFrame` etc. are additions).

## Verification

1. **Bit-identical standalone behaviour.** Run snowgoons + qbert_practice + smb_w1_1 in `wf_game` after the refactor. Frame timing, music sync, joystick, debug-bridge, HUD all unchanged. Screenshots at known frame markers diffed against pre-refactor — pixel-equal not required; visual parity is enough (per [feedback_screenshots_for_proof](../../../.claude/projects/-home-will-WorldFoundry/memory/feedback_screenshots_for_proof.md)).

2. **Headless `StepFrame` smoke test.** New `tests/test_frame_step_api.cc`: `WFGame g(-1); g.LoadLevel(...); for (int i=0; i<60; ++i) auto r = g.StepFrame(false); g.UnloadLevel();` — exercises the API surface without a window. Asserts `r != FrameResult::Done` for the first 30 frames on a level that runs ≥60.

3. **No-swap mode visual parity.** Drive snowgoons via a tiny harness that does `g.StepFrame(false); g.Display()->PageFlip();` instead of `g.StepFrame(true);`. Same on-screen result.

4. **Suspend path on Android.** Run on Android device; background the app; verify `StepFrame` returns `FrameResult::Suspended` and the standalone `wf_game` loop's `usleep(16000)` cadence matches pre-refactor (one frame ≈ 16 ms).

5. **SMB walkthrough harness.** [tests/.smb_walkthrough.log](../../tests/) passes — the deterministic state-injection harness is the strongest end-to-end check.

## Risks / things to watch

- **`_curLevel` lifetime change.** Today destroyed when `RunLevel` returns; promoting to member shifts to `WFGame` destruction unless `UnloadLevel` is called. Standalone `RunLevel` MUST call `UnloadLevel` before returning so the deletion timing is preserved. Add an assert in `~WFGame` that `_curLevel` is null to catch host-side leaks.

- **`_bContinue` reset semantics.** Today reset to `true` at the top of each `RunLevel`. Member promotion means it persists across `LoadLevel` calls; `LoadLevel` must explicitly reset to `true`. `PIGSUserAborted` block inside `StepFrame` still sets it to `false` to short-circuit.

- **`RestApi_Start` / `DebugServer_Start` lifecycle.** Today called once per level. With editor-side `LoadLevel` / `UnloadLevel` they fire at the same boundaries — but the editor might `LoadLevel` + `UnloadLevel` many times per process. Confirm these are re-startable; current implementation looks idle-when-stopped but verify on a tight load/unload loop.

- **deltaTime when host stalls.** Editor pauses on a modal for 5 s → next `StepFrame` would see deltaTime ≈ 5 s without the clamp. Clamp to 100 ms inside `StepFrame` and document in the header comment. Jolt and movement code already tolerate variable dt per [project_variable_tick_rate_loadbearing](../../../.claude/projects/-home-will-WorldFoundry/memory/project_variable_tick_rate_loadbearing.md).

- **`HALWindowCloseRequested` in editor mode.** Engine still polls it inside `StepFrame`? No — the predicate moves to the caller's loop. Engine doesn't read it. Document in the header that callers own the close check.

- **Order-table flush across `LoadLevel` / `UnloadLevel`.** The two final `_display->PageFlip()` calls in `RunLevel`'s exit ("insure no pending ordertable renderings") move into `UnloadLevel` so the timing is preserved. Verify in step 1 that visual playback ends cleanly.

- **Order of work.** Independent of Phase 0b sub-task #2 (external GL context). Either can land first; combine into the editor when both are done.

## Implementation sequence

Each numbered step is its own commit per [feedback_commit_after_each_phase](../../../.claude/projects/-home-will-WorldFoundry/memory/feedback_commit_after_each_phase.md).

1. **Extract `WFGame::LoadLevel` and `WFGame::UnloadLevel`.** Move per-level setup and teardown from `RunLevel` into the new methods. `RunLevel` calls them around the existing `while` loop. No behaviour change. Verify snowgoons + smb_w1_1 walkthrough.
2. **Promote `_curLevel` and `_bContinue` to `WFGame` members.** Update all uses inside `RunLevel` to read members. Add `Level* CurrentLevel() const` accessor. Verify identical to step 1.
3. **Add `Display::MeasureDelta()`.** Factor the deltaTime computation out of `PageFlip` into a callable that doesn't swap. `PageFlip` calls it internally so existing behaviour is identical. Verify standalone unchanged.
4. **Add `WFGame::StepFrame(bool do_swap, Scalar* out_dt)`.** Body lifted from the `while` interior. Returns `FrameResult`. Calls `MeasureDelta` if `do_swap=false`, `PageFlip` if `do_swap=true`. `RunLevel` becomes the thin loop calling it. Verify identical playback.
5. **Add `LevelDone()` / `ContinueRequested()` accessors.** Make `RunLevel`'s loop predicate use them. Verify identical.
6. **Add the deltaTime clamp (≤100 ms) inside `StepFrame`.** Verify standalone unchanged (clamp rarely fires); verify headless smoke test (step 7) survives an artificial 1 s pause between `StepFrame` calls.
7. **Headless smoke test in `tests/`.** Tiny driver constructs `WFGame`, calls `LoadLevel` / `StepFrame` / `UnloadLevel`. Confirms the API works from outside.
8. **Update editor design doc.** Mark Phase 0b sub-task #1 done with commit hashes in the [Tier 1 entry](../investigations/2026-05-18-collaborative-level-editor-design.md). Move corresponding [TODO.md](../../TODO.md) entry to done.
