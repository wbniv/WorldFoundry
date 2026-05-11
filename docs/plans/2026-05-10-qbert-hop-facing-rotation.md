---
plan: qbert-hop-facing-rotation
date: 2026-05-10
status: Done 2026-05-11
scope: ~30 LOC of zForth in [wflevels/qbert_practice/blender_create_qbert.py](../../wflevels/qbert_practice/blender_create_qbert.py)
---

# Q*bert hop-direction facing rotation (Phase 1: smooth yaw)

**Status:** Done 2026-05-11 — `HOP_FACING` (mb 433) + DELTA_YAW lerp block landed in [blender_create_qbert.py](../../wflevels/qbert_practice/blender_create_qbert.py); resets wired into restart + apex-respawn paths.

## Context

In the original arcade Q*bert, the character snaps to face the diagonal he's about to hop toward — there's a dedicated sprite facing for each of NE / SE / SW / NW. Our 3D player mesh currently teleports to the next cube without ever rotating, which reads as "sliding," not "hopping."

User direction: since we're in real 3D rather than 2D sprite cels, **smoothly interpolate** the yaw across the hop's 12-frame cooldown ("keyframed" rather than snap). Stretch-and-squash deformation is a Phase 2 follow-up — out of scope here.

## Existing facts to reuse

- **Hop state machine** lives in the Q*bert player wf_Script at [blender_create_qbert.py:366–572](../../wflevels/qbert_practice/blender_create_qbert.py). The hop is currently *instant* — `do-hop` ([line 463](../../wflevels/qbert_practice/blender_create_qbert.py)) writes the new XYZ in one tick, then sets `mb 402 HOP_COOLDOWN = 12` to gate further input.
- **Hop-direction deltas** already exist as `(dr, dc)` pairs passed into `do-hop`:
  - `(-1, 0)` UP → NE diagonal
  - `( 1, 1)` RIGHT → SE diagonal
  - `( 1, 0)` DOWN → SW diagonal
  - `(-1,-1)` LEFT → NW diagonal
- **`DELTA_YAW` mailbox (3034)** is the right primitive — handler at [actor.cc:1377-1383](../../wfsource/source/game/actor.cc) does `RotateAboutAxis(lookUp, Angle::Revolution(value))`, applying an *incremental* world-Z rotation each write. This means the script doesn't have to track or compute absolute yaw — only the per-frame Δ.
- **Tick-cooldown pattern** for short timed actions: see fall-animation at [blender_create_qbert.py:521-535](../../wflevels/qbert_practice/blender_create_qbert.py) — a counter that decrements each frame and runs side effects until it hits zero. We'll mirror it.
- **Free local mailboxes**: 400..436 are this actor's user-range. Currently used: 400, 401, 402, 411–420, 422, 425, 426, 430, 431, 432. **Slots 433 and 434 are free** for our two new state cells.
- **Constraints already on file**: angles in revolutions (0 ≤ rev < 1) per memory; no nested `:` defs in script body; zForth `/` is float division (fine here — `0.25 / 12` returns the per-frame fractional revolution); mailboxes are fixed-point on real target so 0.25/12 ≈ 0.0208 rev/frame is well within precision.

## Approach

Two new local mailboxes + edits to `do-hop` + a new per-tick block before the existing `tick-cd`. All in the player script body in [blender_create_qbert.py](../../wflevels/qbert_practice/blender_create_qbert.py).

### State

| mb  | Name           | Type                          | Purpose                                                                                       |
|-----|----------------|-------------------------------|-----------------------------------------------------------------------------------------------|
| 433 | `HOP_FACING`   | int 0..3                      | Current facing index. Encoding: `0=NE, 1=SE, 2=SW, 3=NW` (clockwise from NE).                 |
| 434 | `HOP_YAW_INC` | float (revolutions, signed)   | Per-frame DELTA_YAW to apply while `HOP_COOLDOWN > 0`. Set by `do-hop`, untouched once cd=0. |

### `do-hop` — at hop start, compute facing turn (~12 LOC added)

Right before the existing `12 402 write-mailbox` cooldown set:

1. Compute `target-facing` from `(dr, dc)`. Inline `if/then` chain — same style as `step-move` already uses.
2. Read `HOP_FACING` (mb 433) → `current-facing`.
3. Compute **signed shortest turn** in quarter-revolutions: `delta = ((target - current + 2) mod 4) - 2` ∈ `{-2, -1, 0, 1}`. (`-2` and `+2` both mean U-turn — pick negative for consistent CCW direction.) zForth `mod` is the integer `%`, no float-cast needed.
4. Compute per-frame increment `delta * 0.25 / 12` revolutions and store in mb 434.
5. Update `HOP_FACING := target-facing` (mb 433).

For a U-turn (`delta = -2`), Q*bert rotates 180° over 12 frames — slightly faster angular speed, but acceptable because U-turns are rare. Phase 2 can revisit easing.

### New tick block — interpolate yaw across cooldown (~2 LOC added)

Insert **between the existing autopilot/joystick block and `tick-cd`** (around [line 564](../../wflevels/qbert_practice/blender_create_qbert.py)):

```
\\ smooth yaw across remaining cooldown frames
402 read-mailbox 0 > if 434 read-mailbox EMAILBOX_DELTA_YAW write-mailbox then
```

`HOP_COOLDOWN > 0` ⇒ we're mid-hop ⇒ write the stored per-frame increment into `DELTA_YAW`. Total turn over 12 frames = `delta * 0.25 rev` = exactly the requested quarter / half / U-turn. When the last cooldown tick lands, `tick-cd` decrements to 0 and the rotation block stops firing — actor is at the target heading.

### Initialisation

`HOP_FACING` defaults to whatever the player's authored rest yaw is in the `.blend`. Two approaches:

- **Cheap**: start mb 433 = 2 (SW). If the rest pose doesn't match, the *first* hop will appear to rotate from SW to wherever; one frame of cosmetic glitch on first input. Acceptable for Phase 1.
- **Tidy** (preferred): also write mb 433's reset value alongside the existing per-game restart block at [blender_create_qbert.py:489-505](../../wflevels/qbert_practice/blender_create_qbert.py) (the `0 400 write-mailbox` family), and the round-clear apex-respawn block at [line 514](../../wflevels/qbert_practice/blender_create_qbert.py). Pick whichever facing index matches the authored rest pose; verify by inspection in the running game.

Plan goes with the tidy approach — same 5 lines also reset mb 434 = 0 so a stale half-completed turn from before respawn doesn't leak through.

## Critical files

| File | Change |
|---|---|
| [wflevels/qbert_practice/blender_create_qbert.py](../../wflevels/qbert_practice/blender_create_qbert.py) | Player script body only: ~12 LOC added inside `do-hop`, ~2 LOC of new tick block, ~3 LOC of mb-433/434 resets in restart + apex-respawn blocks |

No engine changes. No `mailbox.inc` changes (using actor-local mailboxes 433/434). No `.lev` / `.iff` text changes. No new OAS fields.

## Verification

Per memory: after editing the .blend's Forth, run steps 2–3 of the qbert build pipeline (`build_level_binary.sh` then iffcomp standalone) and print + run the step-4 `wf_game -L<...>` command.

1. **Engine builds clean** (no engine changes — should be a no-op rebuild; only level binaries regenerate).
2. **Boot qbert_practice standalone**. With keyboard input, hop in each of the four diagonals from the apex:
   - DOWN (SW): mesh rotates to face SW over the hop.
   - LEFT (NW): rotates to face NW over the hop.
   - UP (NE): rotates to face NE.
   - RIGHT (SE): rotates to face SE.
3. **Reverse direction test**: hop SW, then immediately hop NE on landing → 180° turn animates over 12 frames in one consistent direction (script picks CCW).
4. **Adjacent direction test**: hop SW → hop SE → hop NE → hop NW. Each is a 90° turn; all should look symmetrical (no visible 270° "long way" rotation — that's what the signed-shortest math guards against).
5. **Death + respawn test**: drive Q*bert off the edge (ball falls), wait for FALL_PHASE to snap to apex. Apex Q*bert should be back at the canonical rest yaw, not whatever heading he had when he fell (mb 433/434 reset confirms).
6. **Autopilot mode**: enable the walker autopilot (`mb 430 != 0`) — autopilot calls `do-hop` directly so rotations should animate the same way during the screenshot capture sweep. No test artefacts expected (CAPTURE_TRIGGER fires at frame 0 and frame post-hop, both at rest between hops).

## Follow-up plans

- [Q*bert physics-based player hops](2026-05-10-qbert-physics-hops.md) — replaces today's teleport `do-hop` with velocity-driven parabolic arcs. At integration time, swap the rotation block's trigger from `HOP_COOLDOWN > 0` to the physics-hops "mid-hop" signal (~1 LOC). Yaw interpolation logic is reusable as-is.

## Out of scope (Phase 2+)

- **Stretch-and-squash** (traditional animation principle): mesh deformation during the hop arc — vertical stretch on take-off, horizontal squash on landing.
- **Hop-arc Z-motion**: covered by the [physics-hops follow-up](2026-05-10-qbert-physics-hops.md). Could alternatively land as a Phase 1.5 teleport-based parabola over the 12-frame cooldown if the user wants it sooner.
- **Easing curve**: linear interpolation now; ease-out on landing (or ease-in-out) is more lifelike. Trivial follow-up once we add a frame-counter-aware lerp helper.
- **Idle facing memory across game-over**: currently rest yaw resets to canonical on respawn; could persist last facing instead.
