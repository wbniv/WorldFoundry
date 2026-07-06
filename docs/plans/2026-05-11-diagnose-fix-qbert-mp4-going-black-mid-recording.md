# Plan — diagnose & fix qbert mp4 going black mid-recording

**Status:** PARTIAL — blackout reproduced & root-caused (X11 backbuffer occlusion); diagnostic probes + matte-background fix not landed. See [record-video-fbo-capture](2026-05-11-record-video-fbo-capture.md).

## Context

The autopilot-via-joystick-injection landed (commit `9c6695f`), and Q*bert clears 2 rounds cleanly. But the resulting mp4 (`qbert-2-rounds.mp4`) renders normally for the first ~11 s (≈7–8 hops) then cuts to solid black for the remainder, even though the walker keeps reporting clean hops and the game logically completes both rounds.

Verified by extracting frames at 1 s intervals:
- `t=1, 5, 10, 11`: pyramid + Q*bert visible, several cubes flipped yellow.
- `t=12` onward: pure black 673-byte PNGs.

The user noted "there should be a Matte object in the level" — pointing at the matte object as the likely culprit (it's currently `Model Type='None'`, so it draws nothing).

## What the matte currently does (nothing useful)

`wflevels/qbert_practice/blender_create_qbert.py:234-244` configures a matte actor with `wf_Matte Type='Color'` and `wf_Background Color=0x101830`, then sets `wf_Model Type='None'` to suppress a debug-box render.

In the engine:
- `wfsource/source/game/actor.cc:455-462` only instantiates `RenderActorMatte` when `MODEL_TYPE_MATTE` is set, *not* `MODEL_TYPE_NONE`. So the matte actor exists, but no render actor is created for it.
- `wfsource/source/renderassets/rendacto.cc:316-360` (`RenderActorMatte::Render`) only does anything when `MatteType == 2` (Image). For `MatteType == 1` (Color), the function returns without drawing.
- Nothing in the engine reads `_Matte::BackgroundColor` and pushes it to `display.SetBackgroundColor`. The OAS field is dead.

So today the BG is whatever `glClearColor` is set to. The earlier `display.hp` fix (default-init `_backgroundColor*` to `0.0f`) makes that black. Before the fix, it was uninitialised-stack-junk orange.

## Likely root cause of the blackout (hypotheses, ranked)

1. **Window occlusion / X11 backbuffer**: the wf_game window gets occluded by something (focus-stealing, screensaver, etc.) and `glReadPixels` on an unmapped backbuffer returns zero. The visible window during play would also be black at that moment. Consistent with "cuts to black and stays black."
2. **Camshot index corruption**: `INDEXOF_CAMSHOT` (mb 1921) is rewritten at `blender_create_qbert.py:941` with `100 read-mailbox`, which is a scratch mailbox. If mb 100 holds a stale or invalid camshot index after the intro phase, the camera teleports to a no-actor camshot, framing nothing. Would explain black BG (no matte = clearColor=0) AND no cubes (camera looking into void).
3. **A render-pipeline assertion that's swallowed**: less likely; engine logs would show it.
4. **Frame-skip from "delta too large"**: the engine prints `delta too large` and clamps; visible as low fps but should not cause permanent black.

(1) and (2) feel most likely; (2) is the one we can diagnose without OS poking.

## Plan

### Step 1 — Diagnose live

Launch wf_game with the existing standalone iff and debug bridge. Probe these mailboxes once per 250 ms from the moment the walker starts:

- `1921` (CAMSHOT)
- `100` (the scratch mailbox the camshot routing reads from)
- `3009/3010/3011` (player X/Y/Z — confirm Q*bert hasn't drifted out of view)
- `416/417/418` (intro phase / timer / done)
- camera's own position via watching the camera actor (`Y_POS`/`Z_POS` on camera idx)

Goal: catch the *exact* tick on which the blackout starts and see which mailbox transitioned.

Tooling: extend `/tmp/probe_hop.py` or write a sibling script `/tmp/probe_camshot.py`. The walker doesn't need to change.

### Step 2 — If camshot corruption (hypothesis 2)

The offending line is at `blender_create_qbert.py:941`:
```
"else drop 100 read-mailbox dup 0 <> if INDEXOF_CAMSHOT write-mailbox else drop then "
```

It re-writes the active camshot from mb 100 every tick when `415` (cs_death hold timer) hits zero. If mb 100 ever lands non-zero with a bogus camshot id, camera locks to that.

Fix options (pick after live trace shows which case fires):

- Guard the write so it only fires when mb 100 holds a *valid* camshot index (e.g., `dup 8 = | 13 = | ... ` style sanity check), OR
- Stop using mb 100 as the camshot scratch and read from a different, deliberately-written mailbox, OR
- Latch the desired post-intro camshot once (write `CS_PYRAMID_IDX` to mb 1921 on intro-done) and remove the per-tick rewrite entirely.

### Step 3 — If window occlusion (hypothesis 1)

If diagnosis points at the window not the engine, the user is launching wf_game with their own window manager — the harness can keep the existing inject_input approach, but we should make the recording resilient by either:

- Setting `WLR_RENDERER_ALLOW_SOFTWARE=1` / `__GL_YIELD=NOTHING` env hints, OR
- Forcing the wf_game window to "always on top" before the walker starts, OR
- Switching the capture path from window-backed `glReadPixels` to an off-screen FBO that's always rendered regardless of visibility (engine-side fix; bigger).

### Step 4 — Wire the matte to actually paint the BG (user's hint)

Independent of (2)/(3), the user wants the matte to be the source of truth for the BG colour, not a stack-junk default. Fix:

1. At level load (in `Level::Level` or wherever actors are constructed), iterate the actors, find the one whose `MovementClass == Actor::Matte_KIND` with `MatteType == 1`, and call `display.SetBackgroundColor(Color(matte_oad->BackgroundColor))`. The `Color` ctor can decode a packed RGB int.
2. Remove the dead `Model Type='None'` workaround in `blender_create_qbert.py:244` and let the matte be `Model Type='Matte'` (5) with `Matte Type='Color'`. With nothing rendered (RenderActorMatte::Render is a no-op for Color), this is safe — the only effect now is the level-load wiring above.
3. Revert (or keep) the `display.hp` default-init. Keeping it is fine as a defence-in-depth; the matte-driven path supersedes it.

## Critical files

| File | Role |
|---|---|
| `wflevels/qbert_practice/blender_create_qbert.py:241,244,941` | Matte object setup; camshot rewrite |
| `wfsource/source/game/level.cc` (or `wfgame.cc` — find the actor-construct loop) | Wire matte BackgroundColor → display.SetBackgroundColor |
| `wfsource/source/game/actor.cc:455-462` | MODEL_TYPE_MATTE branch (no change; just reference) |
| `wfsource/source/renderassets/rendacto.cc:316-360` | RenderActorMatte::Render (no change) |
| `scripts/research/wf/qbert_wf_walker.py` | Walker — unchanged, just used to drive the repro |

## Verification

1. Re-run the same 2-round walker recording. Frames at `t=15, 20, 30, 40` must all show the pyramid (not black).
2. Set `wf_Background Color=0xFF0000` (bright red) on the matte in the Blender script, rebuild the level, re-record — frames should show a red BG, confirming the level-load wiring works end-to-end.
3. The autopilot still clears 2 rounds at 3 lives in roughly the same wall-clock time.

## What I am NOT doing

- No changes to the joystick-injection walker — that's working.
- No physics / Jolt changes. The `2026-05-11-mailbox-pos-write-bypasses-jolt.md` bug stays out of scope.
- No new in-level autopilot Forth code.
