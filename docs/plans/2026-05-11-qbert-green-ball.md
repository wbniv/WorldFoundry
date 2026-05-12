# Plan — Q*bert Green Ball (enemy-freeze pickup)

**Date:** 2026-05-11
**Status:** Done (2026-05-11, commit `2ad0459`)

> **Retroactive plan.** Written after the code shipped, at user request, to fill in the missing design doc for an enemy that was implemented without one. Going forward, plans precede implementation — see [[feedback_plans_before_implementation]].

## Context

After Red Ball ([red-ball-enemy](2026-05-11-qbert-red-ball-enemy.md)) and Coily ([coily-and-discs](2026-05-11-qbert-coily-and-discs.md)) shipped, the next arcade-faithful enemy was the **Green Ball** — visually a red-ball look-alike that on player contact does *not* kill Q*bert but freezes every enemy on the pyramid for ~5 seconds. It's a defensive pickup rather than a threat, and gameplay-wise it gates the difficulty curve in later rounds.

## Reference (arcade Q*bert)

- Spawns at the same apex-adjacent cubes as the Red Ball.
- Bounces straight down with the same gravity / hop cadence as a Red Ball — it is *indistinguishable* from a Red Ball in motion, only by colour.
- On Q*bert contact: all enemies on the board freeze for ~5 s, ball is consumed, no death.
- Spawn rate ~25 s in the arcade attract loop; appears less often than Red Balls.

See: [Wikipedia — Q*bert](https://en.wikipedia.org/wiki/Q*bert) "green balls slow the action".

## Design

Re-use the entire Red Ball state machine and hop arc; the only behavioural deltas are at the *contact* edge and a global freeze gate that every enemy reads.

| Piece | Choice |
|---|---|
| Mesh & motion | Identical to Red Ball — same `redball_script` generator with `variant='green'` switch |
| Director slot count | Single ball alive at a time (vs. red ball's 3-slot pool) |
| Freeze mechanism | Single global `GB_MB_FREEZE_TIMER` counter; every enemy script bails out at top of tick if `> 0`, decrements once per director tick |
| Spawn cadence | `GB_FIRST_DELAY = 600` ticks (10 s) intro grace, then `GB_SPAWN_INTERVAL = 1500` (25 s) |
| Contact semantics | Skip `FALL_DEATH` write; latch `GB_FREEZE_TIMER = GB_FREEZE_TICKS` (300, = 5 s) and self-clear |

## Mailbox layout

| mb | Name | Owner | Purpose |
|---|---|---|---|
| 486–493 | `GB_MB_BASE`..+7 | green ball | Same 8-slot ROW/COL/COOLDOWN/PHASE/START_Z/END_Z/FROM_ROW/FROM_COL layout as a red ball |
| 546 | `GB_MB_FREEZE_TIMER` | global | Counts down each director tick; non-zero ⇒ all enemies skip movement |
| 547 | `GB_MB_SPAWN_TIMER` | director | Countdown until next green spawn |
| 548 | `GB_MB_ACTIVE` | director | 1 = a green ball is currently in flight |

## Script change for existing enemies

Every variant of `redball_script` (red, slick, sam, ugg, wrongway, green itself) gains the same first line:

```
GB_MB_FREEZE_TIMER read-mailbox 0 <> if exit then
```

The green ball's own script branches at the contact check — instead of writing `FALL_DEATH = 1` it writes `GB_MB_FREEZE_TIMER = GB_FREEZE_TICKS` and sets its own `RB_PHASE = 0` (despawn).

## Out of scope

- Score popups ("+100" for picking up a green).
- Audio sting on freeze.
- Visible freeze indicator (e.g., enemy desaturation / blue tint while frozen). Currently freeze is silent — enemies just stop moving.

## Verification

Smoke-tested in `qbert_practice` with multiple red balls in flight: spawning a green ball and walking into it visibly halts all reds for 5 s, then they resume.

## Files touched

- `wflevels/qbert_practice/blender_create_qbert.py` — `redball_script(variant='green')` branch, director spawn logic
- `wflevels/qbert_practice/qbert_practice.lev` — regenerated
