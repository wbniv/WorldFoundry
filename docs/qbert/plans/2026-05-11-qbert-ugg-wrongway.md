# Plan — Q✱bert Ugg &amp; Wrong-Way (side-of-pyramid climbers)

**Date:** 2026-05-11
**Status:** Done (2026-05-11, commits `4799990` initial implementation + `9116d4e` Escher orientation fix)

> **Retroactive plan.** Written after the code shipped, at user request — see [[feedback_plans_before_implementation]].

## Context

Ugg and Wrong-Way are the two **side-of-pyramid climbers** in arcade Q✱bert. Unlike the descenders (Red, Green, Slick, Sam) that bounce down the *top* of the cubes, Ugg and Wrong-Way climb up the *side faces* of the pyramid in an [Escher-style](https://en.wikipedia.org/wiki/M._C._Escher) gravity flip — body rotated 90° so their "feet" rest on the vertical face of a cube, "up" pointing outward from the pyramid.

They're killed if Q✱bert lands on their cube (same FALL_DEATH path as Red Ball — i.e., Q✱bert dies on contact). Spawn at the bottom row and hop upward toward the apex.

## Reference (arcade Q✱bert)

- **Ugg** (purple) climbs the **right** side face (cubes at column == row, the right edge of each row).
- **Wrong-Way** (green) climbs the **left** side face (cubes at column 0, the left edge).
- Both bodies are rendered as if gravity has rotated 90° — they appear to walk *up* the slope of the pyramid side, feet on the vertical face. Wikipedia describes it as ["along the sides of the cubes in an Escheresque manner"](https://en.wikipedia.org/wiki/Q*bert).
- Q✱bert dies on contact (not the climber — these are real threats).
- Despawn when they reach the apex or fall off.

## Design

### Motion (commit 4799990)

Re-use `redball_script` with `variant='ugg'` and `variant='wrongway'`. Two deltas:

1. **Hop direction inverted** — instead of (row+1, col) / (row+1, col+1) descenders, climbers do (row-1, col) for Wrong-Way and (row-1, col-1) for Ugg (staying on their respective edge).
2. **World-space position offset** — body sits at the cube's *side face* not the top: world-X offset by `±(CUBE_SIZE/2 + body_half_x)`, world-Z at cube *centre* (not above the cube top as descenders are).

Z formula switches based on variant: descenders use `_RB_Z_BASE` (cube-top), climbers use `_CLIMBER_Z_BASE` (cube-centre).

### Body orientation: Escher flip (commits 4799990 + 9116d4e)

A two-rotation composition tips the body sideways and then swings it to face up the slope. WF actor axes are +X forward, +Y left, +Z up (see [[project_wf_axis_convention]]).

| Step | Ugg | Wrong-Way |
|---|---|---|
| `DELTA_PITCH` (rev) about local +Y | +0.25 (tips body so local +Z → world +X, outward to right) | −0.25 (tips body so local +Z → world −X, outward to left) |
| `DELTA_YAW` (rev) about new local +Z | +0.5 (swings forward from world −Z to world +Z, i.e. up the slope) | 0.0 (already facing +Z after pitch) |

The yaw step was the **9116d4e fixup**: before that commit, the climbers were on the right side face geometrically but oriented "head-down" — local +X (forward) pointed down the slope instead of up. The `DELTA_YAW = 0.5` for Ugg flips this; Wrong-Way's mirrored pitch already left +X facing up the slope so it gets 0.

### Killing the climber

Q✱bert lands on a cube; the player's hop-completion logic writes `FALL_DEATH = 1` if the cube is occupied by an Ugg/WW. Same death pipeline as Red Ball — no special-case for the climbers.

## Mailbox layout

| mb | Name | Owner | Purpose |
|---|---|---|---|
| 553–560 | `UGG_MB_BASE`..+7 | ugg | 8-slot state block |
| 569 | `UGG_MB_ACTIVE` | director | 1 = Ugg alive |
| 570 | `UGG_MB_SPAWN_TIMER` | director | Countdown to next Ugg spawn |
| 561–568 | `WW_MB_BASE`..+7 | wrongway | 8-slot state block |
| 571 | `WW_MB_ACTIVE` | director | 1 = Wrong-Way alive |
| 572 | `WW_MB_SPAWN_TIMER` | director | Countdown to next WW spawn |

## Spawn cadence

| | Ugg | Wrong-Way |
|---|---|---|
| First delay | `UGG_FIRST_DELAY = 1200` (20 s) | `WW_FIRST_DELAY = 1800` (30 s) |
| Interval | `UGG_SPAWN_INTERVAL = 1200` (20 s) | `WW_SPAWN_INTERVAL = 1500` (25 s) |

## Out of scope

- Climber-specific death animation (currently just despawn).
- Audio sting on climber spawn.
- Visual distinction between Ugg and Wrong-Way meshes — currently both share the red-ball mesh tinted differently (Ugg purple, WW green).

## Verification

Smoke-tested in `qbert_practice`:
1. Spawn Ugg → body is upright on the right side face, "forward" points up the slope, hops climb toward apex.
2. Same for Wrong-Way on the left.
3. Land Q✱bert on a cube currently occupied by Ugg → player dies, lives counter decrements, respawn at apex.
4. Captured to `qbert-all-enemies.mp4` showing all 7 arcade enemies in flight together.

## Files touched

- `wflevels/qbert_practice/blender_create_qbert.py` — `UGG_*`/`WW_*` constants, `redball_script(variant='ugg'|'wrongway')` branch, side-face X/Z offsets, two-step pitch+yaw rotation composition
- `wflevels/qbert_practice/qbert_practice.lev` — regenerated
