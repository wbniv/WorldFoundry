# Plan: moon lander launch sequence (Starship HLS ascent)

**Status:** In progress
**Date:** 2026-06-02
**Estimate:** ~2 h

## Context

V2 of the lander plan ([2026-05-31-moon-artemis-lander.md](2026-05-31-moon-artemis-lander.md)) called for a "launch sequence: countdown timer, Raptor exhaust effect at base, vertical ascent via scripted position." Now that the AmbientLight fix lets curved-geometry actors render properly, the visual side is unblocked.

The cinematic: player spawns, has ~10 sec to look around. HUD shows "LAUNCH IN: T-5" countdown centered. At T-0, Raptor exhaust cones appear under the lander base (bright orange, emissive) and the whole vehicle starts accelerating upward. After ~15 sec of ascent the lander is offscreen above the top of frame. Cinematic event the player just watches.

## Mockups

### Phase 0 — Idle (player spawn, before countdown starts)

```
+--------------------------------------------------------------------------+
| SCORE 0                  TIME 0                  LIVES 0    [minimap]    |
| SITE 01 -- CONNECTING RIDGE                                              |
| LAT 89.4632 S  LON 227.0382 E                                            |
| ELEV +1945 m   (delta +0.0 m)                                            |
| POS X+0   Y+0   (m from spawn)                                           |
|                                                                          |
|                                                                          |
|                                                                          |
|                  .              ___                                      |
|              (astronaut)        |##|  <- Starship lander tower           |
|                                 |##|     standing on regolith            |
|        ~~~~~~~~~~~~~~~~~~~~~~~~|##|~~~~~~~~~~~~~~~~~~~~~~~~~~~          |
|                                 |__|                                      |
+--------------------------------------------------------------------------+
   No countdown text. Standard vista. Same as current screenshot.
```

### Phase 1 — Countdown (T-5 ... T-1)

```
+--------------------------------------------------------------------------+
| SCORE 0                  TIME 0                  LIVES 0    [minimap]    |
| SITE 01 -- CONNECTING RIDGE                                              |
| LAT 89.4632 S  LON 227.0382 E                                            |
| ELEV +1945 m   (delta +0.0 m)                                            |
| POS X+0   Y+0   (m from spawn)                                           |
|                                                                          |
|                  *** LAUNCH IN: T-3 ***   <- 3x scale, bright orange     |
|                                                                          |
|                                                                          |
|                  .              ___                                      |
|              (astronaut)        |##|                                     |
|                                 |##|                                     |
|        ~~~~~~~~~~~~~~~~~~~~~~~~|##|~~~~~~~~~~~~~~~~~~~~~~~~~~~          |
|                                 |__|                                      |
+--------------------------------------------------------------------------+
   Countdown text centered, ~y=110 (below 4-line text block, above lander
   top). Bright orange (1.0, 0.6, 0.1) to match Raptor exhaust color.
   Number counts 5 -> 4 -> 3 -> 2 -> 1, one number per second.
```

### Phase 2 — Ignition (~1 sec)

```
+--------------------------------------------------------------------------+
| SCORE 0                  TIME 0                  LIVES 0    [minimap]    |
| SITE 01 -- CONNECTING RIDGE                                              |
| ...                                                                      |
|                                                                          |
|                  *** IGNITION ***   <- big, bright, brief flash          |
|                                                                          |
|                                                                          |
|                  .              ___                                      |
|                                 |##|                                     |
|                                 |##|                                     |
|                                 |XX|  <- 3 Raptor exhaust cones          |
|        ~~~~~~~~~~~~~~~~~~~~~~~~|XX|~~~~~~~~~~~~~~~~~~~~~~~~~~~          |
|                                 (vv)  <- bright orange flame poking out  |
+--------------------------------------------------------------------------+
   Lander still on ground (Z = 0). Raptor cones at the engine-mount base
   now poking visibly below the lander silhouette (they're at mesh-local
   z = -1 to -3 so they're buried until the lander rises, but the "tips"
   reach z = -1 which is at or just below the terrain surface). At T=0+
   the lander begins moving so the cones become more visible.
```

### Phase 3 — Ascent (steady climb, lander rising)

```
+--------------------------------------------------------------------------+
| SCORE 0                  TIME 0                  LIVES 0    [minimap]    |
| SITE 01 -- CONNECTING RIDGE                                              |
| ...                                                                      |
|                                 ___                                      |
|                                 |##|  <- Lander 15-30 m up               |
|                                 |##|                                     |
|                                 |##|                                     |
|              T+3                |XX|     T+N counter, small, top-right   |
|                                 |XX|     of the lander, dim orange       |
|                                 (vv)  <- bright orange exhaust trailing  |
|                                                                          |
|                  .                                                       |
|              (astronaut, now looking up at the lander)                   |
|        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~          |
+--------------------------------------------------------------------------+
   Lander Z grows quadratically (a ≈ 0.5 m/s² per tick²). By T+10 sec it's
   at ~25 m altitude. By T+15 it's off the top of the camera frustum.
   Exhaust cones travel with the lander (they're part of its mesh), so the
   bright orange visible glow follows the rising vehicle.
```

## State machine

Phase is derived each frame from the `TIME` mailbox (1906, level-clock seconds since level load) — **not** from a per-frame tick counter, because WF's dt is variable and the engine runs anywhere from 3 fps (when wrapped in ffmpeg record) to 60+ fps. Seconds are the only stable unit ([[feedback_timing_in_seconds_not_ticks]]).

| Phase | Wall-clock window | What's happening |
|---|---|---|
| Idle | 0 — 10 s | Player explores. Lander stationary. No HUD countdown. |
| Countdown | 10 — 15 s | HUD shows "LAUNCH IN: T-5..." down to T-1. Lander stationary. |
| Ignition | 15 — 16 s | HUD shows "IGNITION". Raptor exhaust appears. Lander still on ground. |
| Ascent | 16 s onward | Lander Z position increases (quadratic: `dz = 0.5 × a × t²` with a = 0.5 m/s²). After ~10 s ascent (t = 26 s) the lander is 25 m up; by ~22 s it's at ~80 m and well off-frame. |

The `MOON_LAUNCH_TIMER` (mailbox 1880) entry was originally a per-frame tick counter; it is now repurposed as a one-shot baseline (captured TIME at first script tick) if we later want to delay the launch relative to player spawn vs level load. For the moon level there's no respawn, so we read TIME directly and TIMER stays unused.

## Files modified

### Mailbox

- `wfsource/source/mailbox/mailbox.inc` — three new entries:
  - `MOON_LAUNCH_TIMER` (1880): tick counter, written by player script each tick
  - `MOON_LAUNCH_PHASE` (1881): 0=idle, 1=countdown, 2=ignition, 3=ascent — derived value, read by HUD + lander
  - `MOON_LAUNCH_T_MINUS` (1882): seconds-until-launch (or seconds-since-ignition for phase ≥ 2), for HUD display

### Blender script

`wflevels/moon_site01/blender_create_moon.py`:

1. **Lander mesh** — extend `_build_artemis_lander()` with three Raptor exhaust cones below the engine-mount base. Mesh-local positions: same X-Y as Raptor nozzles, but `z = -3` to `z = -1` (below ground level so they're buried initially; the visible exhaust appears when the lander has risen ~3+ m off the surface). Material: solid bright orange `(1.0, 0.6, 0.1)` with emission so they read bright against the dark underside.
2. **Lander script** — add `wf_Script` to the lander actor. Reads `MOON_LAUNCH_PHASE`; in phase 3 (ascent), reads `MOON_LAUNCH_T_MINUS` and computes new `Z_POS` from quadratic ascent curve, writes back.
3. **Player script** — extend the existing player `wf_Script` to drive the timer:
   - Increment `MOON_LAUNCH_TIMER` each tick
   - Derive `MOON_LAUNCH_PHASE` from timer value
   - Compute and write `MOON_LAUNCH_T_MINUS` (countdown seconds for phase 1, ascent seconds for phase 3)

### HUD

`wfsource/source/game/game.cc` + `wfsource/source/game/main.cc`:

- Add `int wf_moon_launch_phase` + `float wf_moon_launch_t_minus` to the moon-overlay extern block. Read from mailboxes 1881 / 1882 each frame.

`wfsource/source/gfx/gl/display.cc`:

- In the moon-overlay block, conditional on `wf_moon_launch_phase`:
  - Phase 1: centered text "LAUNCH IN: T-{seconds remaining}" — large kScale (3×), bright orange, near top-center of frame just below SCORE/TIME row
  - Phase 2: centered "IGNITION", same style, briefly (~1 sec)
  - Phase 3: centered "T+{seconds since ignition}", smaller, fades or stays subtle

## Verification

1. `task build-level -- moon_site01` clean (mailbox.inc dep propagates via the compile_stub depfile fix).
2. `task build` (engine rebuild for the HUD additions).
3. `task run-moon` boot; capture via `WF_GAME_SCREENSHOT_PPM` at t = 0, 5, 10, 12, 15, 20 sec (use `-record_video` + `ffmpeg -ss` to extract at known timestamps). Expect:
   - t=0: spawn shot, no countdown
   - t=12: countdown visible, T-3 or so
   - t=15: ignition or just-after-ignition, exhaust cones visible under the lander
   - t=20: lander mid-ascent, raised position visible, exhaust trailing
4. Bridge-confirm via `--debug-print-actors` that the lander actor's `Z_POS` mailbox is increasing.
5. Eye-test the exhaust cones — should be unmistakably bright orange/yellow against the lander's white body and the dark sky.

## Out of scope (v3+)

- Audio cue (no audio infrastructure for the moon yet)
- Particle flame effect (exhaust cones are static-geometry stand-ins for actual particles)
- Cone *animation* (flickering, scale pulse) — could come later
- The lander going to a destination (it just goes up; no rendezvous with anything offscreen)
- Multiple launches (it's a one-shot event)

## Estimate

~2 h: 30 min mailbox + Blender script (Raptor cones + scripts), 30 min lander script tuning, 45 min HUD code in display.cc, 15 min verification + screenshot.
