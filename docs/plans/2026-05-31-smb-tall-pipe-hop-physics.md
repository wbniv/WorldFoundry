# SMB W1-1 — make the tall-pipe hop reachable (Mario horizontal-speed tuning)

**Status:** Done — 2026-05-31 (~1 h: investigation + arc-trace tuning over several rebuilds). `Running Deceleration` 0.85 → 0.20; top speed 2.8 → 9.0 m/s; verified a real run-up jump lands ON the brick and clears `pipe_64`. Recording: [tests/recordings/smb_tall_pipe_hop.mp4](../../tests/recordings/smb_tall_pipe_hop.mp4). Needs an interactive feel-test to confirm the difficulty is right.

## The challenge (canonical, do NOT change geometry)

`pipe_64` (cols 64-65, **4T = 6.0 m tall**) is the tallest pipe in W1-1. Mario
cannot clear it from the ground. The intended traversal, per the user:

> Jump from the (shorter) pipe → onto the brick → onto/over the very tall pipe.
> If you land on the ground, return to the shorter pipe, jump on top of it, and try again.

The three objects (verified from [`blender_create_smb.py`](../../wflevels/smb_w1_1/blender_create_smb.py)):

| Object | X span (m) | Top Z (m) | Role |
|---|---|---|---|
| `entry_pipe` (3T) | 69.0 – 72.0 | 4.5 | the "shorter pipe" — stage from here |
| `brick_1up` (row 4) | 84.75 – 86.25 | 7.5 | the "brick" stepping stone |
| `pipe_64` (4T) | 94.5 – 97.5 | 6.0 | the "very very tall pipe" |

**Constraint:** the level layout is the canonical, faithful SMB W1-1. Geometry
(pipe heights, brick/pipe positions) is **not** to be touched. Only Mario's
*character physics* may be tuned — and that is faithful, since real SMB Mario
clears a 4-tile pipe with a running jump.

## Root cause — horizontal air reach, not jump height

Measured (`tests/measure_mario_physics.py`, `tests/test_pipe_hop.py`):

- Max jump height **5.14 m from ground**, **~9.5 m from the pipe top** — height is *not* the problem.
- Walking/running speed **~2.8 m/s** — far too slow.
- From `entry_pipe` top, Mario lands back on the **ground at X ≈ 75–80.5** — he reaches
  9.5 m of height but only ~9 m of horizontal distance, **falling 4–6 m short of the brick** (X 84.75).

The ground handler ([`movement.cc:300-408`](../../wfsource/source/movement/movement.cc)) accumulates
`wheelVelocity += runningAccel·dt` per frame, decayed by `drag = 1 − RunningDecel·dt·30`. Steady state:

```
ground speed = RunningAccel / (RunningDeceleration × 30)
             = 60 / (0.85 × 30) ≈ 2.35 m/s          (matches measured ~2.8)
```

This is **independent of `Max Ground Speed`** once that exceeds the steady value — so the
prior retunes ([2026-05-17](2026-05-17-smb-mario-speed-jump-tuning.md),
[2026-05-18](2026-05-18-smb-mario-movement-retune.md)) that pushed `Max Ground Speed` 6→12→24→32
**did nothing**; `Running Deceleration = 0.85` is the dominant throttle.

The air handler ([`movement.cc:872-895`](../../wfsource/source/movement/movement.cc)) has a "sustain"
branch: with `Air Acceleration = 0`, holding RIGHT while moving +X sets `hDrag = 1` (no decay) — so
**takeoff momentum persists for the whole jump while RIGHT is held**. Therefore raising ground speed
directly raises horizontal jump reach. `Horiz Air Drag` is dead under Jolt anyway (see `movement.cc`
note at the powerup template, line 698) — the 1108-1110 comment claiming it damps the launch is stale.

## Arc math → target speed

Jump from pipe top: `Z0 = 4.5`, `Vz0 ≈ 10.95 m/s`, `g ≈ 12` (FallingAcceleration). Mario descends
through the brick-top height (7.5 m) at **t ≈ 1.49 s** after launch. To land on the 1.5 m-wide brick
top (X 84.75–86.25) from launch X ≈ 72:

```
launch speed ∈ [12.75 / 1.49, 14.25 / 1.49] = [8.6, 9.6] m/s
```

A ~1 m/s-wide window → an inherently precise, skill-based hop (exactly the "retry from the shorter
pipe" feel). Target **~9 m/s**:

```
RunningDeceleration = 60 / (9 × 30) ≈ 0.222    (start at 0.22, verify, fine-tune ±0.02)
```

## Empirical landing window (trajectory traces, `tests/trace_hop_arc.py`)

Launching off the pipe edge (Z≈4.65) with the measured jump `Vz=10.95`:

| Actual launch Vx | Outcome |
|---|---|
| ~7 m/s | at the brick's X (84.75) the arc has already dropped to Z≈4.2 — **passes under** (brick bottom 6.0), lands on ground X≈88 |
| **~9.3–9.6 m/s** | descending arc reaches **X≈85.8, Z≈7.5 → lands ON the brick** ✓ |
| ≳10.5 m/s | overshoots — at brick X he is still above 7.5, flies over, lands past X≈90 |

So the brick is solid and reachable; the landing window is ~**9.0–10.0 m/s** launch — a fast, well-timed jump. The brick is NOT tunneled or non-solid; the earlier "always overshoots/short" readings were test artifacts (apex caught as a landing; on-ground `ZSPEED` injection eaten).

## Change (one knob)

In [`blender_create_smb.py`](../../wflevels/smb_w1_1/blender_create_smb.py) player block (~line 1101):

- `wf_Running Deceleration`: **0.85 → 0.18** (raises steady ground/air speed ~2.35 → **11.1 m/s**; measured 8.99 m/s at 0.22, so model is accurate). At 0.20 (top 9.0) the brick needed *near-max* speed — a knife-edge leaning toward impossible. 0.18 gives headroom so a well-timed jump lands it while too-early (short) / too-late (overshoot) miss — **achievable with practice, not first-try** (design intent per user: somewhat difficult, never impossible).
- Fix the stale `Horiz Air Drag` comment (the sustain branch keeps held-RIGHT momentum; the knob only bites on released frames).
- Leave geometry, jump accel, gravity, `Max Ground Speed` untouched.

## Build + verify

1. `blender --background --python wflevels/smb_w1_1/blender_create_smb.py` (regenerate `.lev`)
2. `task build-level -- smb_w1_1` (→ `smb_w1_1-standalone.iff`)
3. `python3 tests/test_pipe_hop.py` — confirm Mario lands **on the brick** (Z ≈ 7.5) from the pipe,
   then **clears `pipe_64`** (lands at X > 97.5) from the brick. Fine-tune `Running Deceleration` if
   he undershoots (lower it) or overshoots the brick (raise it).
4. Screenshot proof of Mario on/over the tall pipe; update the `run_smb_w1_1_playthrough.py`
   triggers for the new speed and re-record.

## Watch-items

- Faster Mario slides further before stopping (lower decel) — pipe-warp "stop on `entry_pipe` + press
  Down" may need a more deliberate approach. Flag for the interactive feel test; do not pre-compensate.
- Re-tune `run_smb_w1_1_playthrough.py` JUMP_TRIGGERS (they assume ~3 m/s).
