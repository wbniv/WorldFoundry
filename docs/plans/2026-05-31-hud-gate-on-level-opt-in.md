# Plan: gate the arcade HUD on whether the level wrote any HUD mailbox

**Status:** In progress
**Date:** 2026-05-31
**Estimate:** 15 min

## Context

`gfx/gl/display.cc:766-767` unconditionally calls `DrawHud(wfWindowWidth, wfWindowHeight)` for any `DESIGNER_CHEATS && __LINUX__` build — which is every dev/edit build. `DrawHud` reads `wf_hud_score / wf_hud_timer / wf_hud_lives / wf_hud_game_over` (globals defined in `game/main.cc:76-79`, refreshed each frame from mailboxes 70/71/72/420 by `game.cc:558-561`) and draws `SCORE / TIME / LIVES` in yellow at the top of the window plus a `GAME OVER` overlay.

This is arcade chrome for qbert and SMB — they actively set those mailboxes from their Forth scripts. Levels that don't (snowgoons, mm_practice, moon_site01, future Mars/Tier-1 work) still get the HUD rendered, showing a stale `SCORE 0 / TIME 0 / LIVES 0` strip that doesn't belong in a walking-around-the-moon level.

The existing design is already mailbox-driven (per-level data via mb 70/71/72/420). What's missing is the *gate* — the engine treats "mailbox unwritten" the same as "mailbox = 0," so the HUD shows for everyone.

## Approach

Gate `DrawHud` on whether the level has written *any* of the HUD mailboxes since boot. Simplest sufficient test: skip the draw when all four HUD globals are zero (and no high-score-initials entry is active). qbert and SMB both write `lives = 3` from their Forth startup scripts on the first tick, so they pass the gate immediately and indefinitely; snowgoons / mm_practice / moon_site01 stay silent.

This is one `if` in `display.cc` — no OAS field, no new mailbox, no per-level config. The "opt-in by writing the existing mailbox" is the level-side contract and it's already how qbert/SMB work.

## Files

`wfsource/source/gfx/gl/display.cc` — wrap the existing `DrawHud(...)` call:

```cpp
#if DESIGNER_CHEATS && defined(__LINUX__)
    if (wf_hud_score | wf_hud_timer | wf_hud_lives | wf_hud_game_over
        | wf_hud_entering_initials)
    {
        DrawHud(wfWindowWidth, wfWindowHeight);
    }
#endif
```

`int | int` (bitwise OR) is fine here — these are all small non-negative integers; the result is non-zero iff any operand is non-zero, and it's cheaper than four `||` short-circuits since we want to check all four every frame anyway.

## Verification

1. `task build` clean.
2. `task run-moon` — vista cam screenshot via `WF_GAME_SCREENSHOT_PPM`. No yellow `SCORE/TIME/LIVES` strip.
3. `task run-qbert` — HUD shows immediately (qbert's Director writes `LIVES = 3` on first tick).
4. `task run-smb` — HUD shows immediately (SMB's startup script writes `LIVES = 3`).
5. Snowgoons and MM smoke — no HUD (no mailbox writes), no regressions in geometry.
6. Game-over flow in qbert: kill all lives → `mb 420` → 1 → HUD stays visible (the `game_over` term in the OR).

## Risks

- **qbert / SMB at frame 0 before the startup script runs**: the HUD might flicker off for one frame at level boot. Acceptable — invisible at 60 Hz, and the existing startup-script tick is responsible for writing the lives mailbox before any user-visible frame.
- **High-score initials entry**: the existing `wf_hud_entering_initials` global is already covered by including it in the OR — initials entry stays visible even if score = timer = lives = 0 = game_over = 0 (improbable but covered).
- **No effect on production builds** — the whole HUD path is `DESIGNER_CHEATS`-gated already; release builds (e.g. Android APK) never see it.

## Related

- `gfx/gl/display.cc:79-203` — `DrawHud` body (qbert/SMB-specific layout; arcade chrome).
- `game/game.cc:552-580` — per-frame mailbox→HUD-global refresh.
- [snowgoons inheritance trap](2026-05-31-uninitialised-fog-defaults.md) — sibling "level scaffolded off arcade level inherits arcade chrome" lesson; the fog version was OAS-driven, this is mailbox-driven.
