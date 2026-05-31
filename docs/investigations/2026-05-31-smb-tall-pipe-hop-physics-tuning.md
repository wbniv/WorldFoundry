# Investigation: tuning Mario's physics so the W1-1 tall-pipe hop is reachable

**Date:** 2026-05-31
**Question:** The canonical W1-1 sequence — stage on the shorter `entry_pipe`, jump onto
`brick_1up`, then jump from the brick over/onto the 4-tile `pipe_64` (the tallest pipe) —
was not doable: Mario fell several metres short of the brick. How do we make it *achievable*
(somewhat difficult, never impossible) **without touching the canonical level geometry**?

This documents the *method* — how the answer was found — not just the answer.

---

## 1. Frame the constraint first

The level is faithful SMB W1-1. Pipe heights and the brick/pipe positions are canonical and
**off-limits**. The only thing we may change is Mario's *character physics* — and that is itself
faithful, because real-SMB Mario clears a 4-tile pipe with a running jump. So the search space is
the player's movement-block fields, not the level.

Geometry (from `wflevels/smb_w1_1/blender_create_smb.py`, T = 1.5 m):

| Object | X span (m) | top Z (m) | role |
|---|---|---|---|
| `entry_pipe` (3T) | 69.0–72.0 | 4.5 | shorter pipe — stage here |
| `brick_1up` | 84.75–86.25 | 7.5 | stepping stone (bottom 6.0) |
| `pipe_64` (4T) | 94.5–97.5 | 6.0 | tallest pipe |

## 2. Measure before theorising

Rather than guess at parameters, the first move was to *measure the actual physics* with the
debug bridge (`tests/measure_mario_physics.py`): drive Mario and read back X/Z/velocity mailboxes.

- **Max jump height: ~5.1 m from the ground, ~9.5 m from the pipe top.** Height is *not* the
  problem — from the pipe Mario easily reaches the brick's 7.5 m.
- **Run speed: ~2.8 m/s.** This is the bottleneck. A full jump only carried him ~9 m forward,
  but the pipe→brick gap is ~13 m. He landed 4–6 m short, on the ground (`tests/test_pipe_hop.py`).

Conclusion from measurement: the blocker is **horizontal reach**, governed by run speed — not
jump height. This redirected the whole effort away from the jump and onto ground speed.

## 3. Read the handler; derive the speed model

`wfsource/source/movement/movement.cc` (MarbleHandler / doom-stick path) accumulates
`wheelVelocity += RunningAccel·dt` per held-direction frame (line ~318) and decays it by
`drag = 1 − RunningDecel·dt·30` (line ~233). Solving for steady state:

```
steady ground speed = RunningAcceleration / (RunningDeceleration × 30)
                     = 60 / (0.85 × 30) ≈ 2.35 m/s          (matches the measured ~2.8)
```

Two consequences fell out of this, both load-bearing:

1. **`Max Ground Speed` is inert.** It only clips *above* the steady value. With steady ≈ 2.35
   and `Max Ground Speed` = 32, the cap never binds. The prior SMB retunes
   ([2026-05-17](../plans/2026-05-17-smb-mario-speed-jump-tuning.md),
   [2026-05-18](../plans/2026-05-18-smb-mario-movement-retune.md)) bumped `Max Ground Speed`
   6→12→24→32 to "speed Mario up" — **every one of those was a no-op.** The real knob is
   `Running Deceleration`. (Lesson: derive the model from the handler before turning dials.)

2. **The air "sustain" branch carries ground speed into the jump.** With `Air Acceleration = 0`,
   holding the move direction while moving that way sets horizontal air-drag = 1 (movement.cc
   ~872–895), so takeoff momentum persists for the whole jump. Therefore raising ground speed
   raises horizontal jump reach **1:1** — exactly the lever needed. (`Horiz Air Drag` only bites
   on released frames; the old comment claiming it damps the launch was stale.)

## 4. The bug is an *arc-shape* problem, not just "more speed"

Raising speed isn't enough — the descending arc has to cross the brick-top height (7.5 m)
*within* the brick's 1.5 m-wide X-span. Too slow → the arc has already dropped below the brick
when it arrives (passes underneath, bottom 6.0 m). Too fast / too floaty → it's still above 7.5 m
at the brick's X and sails over. So there is a **landing window**, found with clean trajectory
traces (`tests/trace_hop_arc.py` — launch Mario airborne off the pipe edge and print the raw
(t, X, Z) arc):

| launch Vx | result |
|---|---|
| ~7 m/s | at the brick's X the arc is already at Z≈4.2 → **passes under**, lands on the ground |
| ~9.3–9.6 m/s | descending arc hits **X≈85.8, Z≈7.5 → lands ON the brick** |
| ≳10.5 m/s | still above 7.5 m at the brick's X → **flies over**, lands past it |

So the target is a launch of **~9–10 m/s** — not "as fast as possible."

## 5. Debug-bridge pitfalls (and how each was worked around)

Most of the time went here. The bridge is not a clean instrument for a millisecond-precise
platforming move; several artifacts produced confidently-wrong readings until isolated:

| Artifact | Symptom | Fix |
|---|---|---|
| **Jump-button frame roulette** | Firing the JUMP bit near the pipe edge sometimes registered (peak ~9.5 m), sometimes not (peak ~4.5 m = a fall-off, no jump) — Mario had already stepped off the edge before the bit landed. | Fire the jump a hair *earlier* (still on the pipe), or for measurement bypass the button and inject the jump's `ZSPEED` directly. |
| **On-ground velocity injection eaten** | Setting `ZSPEED`/`XSPEED` while Jolt reports on-ground → the ground handler overwrites it that frame; peak came out at ~+2.6 m instead of +5 m. | Launch from *airborne* (teleport just above the pipe top) so the air handler runs and sustains the injected velocity. |
| **Apex caught as a "landing"** | The settle-detector ("Z stable for N samples") fired at the arc's apex (Z momentarily flat) → reported a bogus mid-air "landing". | Track the *full* trajectory for a fixed duration and read where Z actually settles; never early-break on stability. |
| **Lagged, change-only broadcasts** | Velocity/position readbacks lag and only update on change, so a single `Vx` sample under-reads true flight speed. | Compute speed from a position delta over a window; treat single mailbox samples as approximate. |

The decisive instrument turned out to be the **raw trajectory print** (§4) — immune to all four
once launches were airborne and tracking ran full-length.

## 6. Iterate the one knob; tune for *difficulty*, not just possibility

`Running Deceleration` was the only field changed. The progression:

| value | top speed | outcome |
|---|---|---|
| 0.85 (orig) | 2.8 m/s | 4–6 m short of the brick — impossible |
| 0.22 | 9.0 m/s | reaches the brick's distance, but **overshoots** on a full jump |
| 0.20 | 9.0 m/s* | a real run-up jump lands the brick — but only at *near-max* speed (knife-edge, leaning impossible) |
| **0.18** | **11.1 m/s** | headroom: a well-timed jump lands the brick; too-early → short, too-late → overshoot |

\* re-measured 8.99 m/s at decel 0.22, confirming the §3 model is accurate.

The final choice was driven by the **design intent** (per the request): the hop should take a
player *a number of tries*, not work first time, and never be impossible. 0.20 made it possible
only at Mario's exact speed ceiling — too punishing. 0.18 lifts the ceiling to 11.1 m/s so the
~9–10 m/s landing window is comfortably *reachable* from the 3 m pipe-top runway, while the
narrow brick and the jump timing keep it a skill move with failure on both sides.

## 7. Result

- **`Running Deceleration` 0.85 → 0.18** in `blender_create_smb.py`; nothing else touched.
- The hop is two discrete jumps: run off `entry_pipe` and land **on** `brick_1up`, then a second
  jump **from** the brick over/onto `pipe_64`. Both verified in-engine.
- Geometry untouched; the change is purely Mario's run speed, which also makes the level feel
  closer to real-SMB pace.

Commits: `6690a91a` (0.20), `2947a153` (0.18). Plan:
[docs/plans/2026-05-31-smb-tall-pipe-hop-physics.md](../plans/2026-05-31-smb-tall-pipe-hop-physics.md).

## 8. How to re-tune later

Want it easier? Lower `Running Deceleration` (more top speed → wider reachable window). Harder?
Raise it toward 0.20 (back to the knife-edge). The map: `top speed = 60 / (decel × 30)`; the
brick lands at a launch of ~9–10 m/s. There is a competing pressure on the *second* jump —
faster Mario slides off the narrow brick sooner, shortening the window to launch the brick→pipe
jump — so the sweet spot balances "reach the brick" against "stay on it long enough to jump again."
That trade is best judged by a human play-test.
