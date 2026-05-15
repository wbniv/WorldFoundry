# Plan — Q✱bert Slick &amp; Sam (cube-flippers)

**Date:** 2026-05-11
**Status:** Done (2026-05-11, commit `5c93811`)

> **Retroactive plan.** Written after the code shipped, at user request — see [[feedback_plans_before_implementation]].

## Context

Slick and Sam are the **purple cube-flipper** enemies in arcade Q✱bert. They bounce down the pyramid like a Red Ball, but on landing they *revert* the cube they touch (state 2 → state 0), undoing Q✱bert's progress. They don't kill the player on contact — Q✱bert kills *them* by landing on the same cube.

Gameplay-wise they're the first enemy that interacts with the cube-state grid, which is the substantive new system here.

## Reference (arcade Q✱bert)

- Both Slick and Sam are visually identical purple humanoids; only their spawn cadence and round-appearance differ.
- Bounce down the pyramid using the same hop cadence and (row+1, col) / (row+1, col+1) alternation as Red Ball.
- On landing on a cube that's been flipped (state 2 or state 3), reset it to state 0 ("undoing" the player's progress).
- Vanish off the bottom of the pyramid (same as Red Ball).
- Killed if Q✱bert lands on their cube (no death animation needed — they just disappear).

See: [Wikipedia — Q✱bert](https://en.wikipedia.org/wiki/Q*bert) and arcade attract-mode reference.

## Design

Re-use the Red Ball hop state machine (`redball_script` generator) with two new variants `slick` and `sam`. The behavioural delta is **at the landing edge**: on hop completion, instead of just decrementing the cooldown, walk the cube-state mailbox for the landed cube and force it back to 0 if it was 2.

| Piece | Choice |
|---|---|
| Mesh & motion | Same red-ball icosphere mesh, purple material; same hop arc and cadence |
| Variants | `slick` and `sam` share the script template but have independent mailbox slots and spawn timers |
| Director slot count | One Slick alive at a time; one Sam alive at a time (separate active flags) |
| Cube-flip mechanism | On landing, compute cube-state mailbox index from (row, col), read it, if `>= 2` write `0` |
| Player contact | Kill self (clear ACTIVE, RB_PHASE = 0); do NOT write `FALL_DEATH` |

## Spawn cadence

| | Slick | Sam |
|---|---|---|
| First delay | `SLICK_FIRST_DELAY = 600` (10 s) | `SAM_FIRST_DELAY = 900` (15 s) |
| Interval | `SLICK_SPAWN_INTERVAL = 480` (8 s) | `SAM_SPAWN_INTERVAL = 1500` (25 s) |

Slick spawns aggressively; Sam is rarer. Matches the arcade tension where the purples appear suddenly and the player has to interrupt their downward path.

## Mailbox layout

| mb | Name | Owner | Purpose |
|---|---|---|---|
| 494–501 | `SLICK_MB_BASE`..+7 | slick | 8-slot red-ball-shape state block |
| 549 | `SLICK_MB_ACTIVE` | director | 1 = Slick alive |
| 550 | `SLICK_MB_SPAWN_TIMER` | director | Countdown to next Slick spawn |
| 502–509 | `SAM_MB_BASE`..+7 | sam | 8-slot red-ball-shape state block |
| 551 | `SAM_MB_ACTIVE` | director | 1 = Sam alive |
| 552 | `SAM_MB_SPAWN_TIMER` | director | Countdown to next Sam spawn |

## Cube-flip implementation note

Cube-state mailboxes live in the existing per-cube grid established by the [16-rounds palette plan](2026-05-09-qbert-cube-palettes-16-rounds.md). The Slick/Sam landing branch in `redball_script` computes `INDEXOF_CUBE_STATE_BASE + row * NUM_ROWS + col` and writes 0. Because cubes are individually addressable, this is a single mailbox poke per hop — no list iteration.

## Out of scope

- Visual distinction between Slick and Sam — currently both are the same purple mesh.
- Score popup on killing a cube-flipper.
- Slick-only vs. Sam-only round gating (arcade tier rules); both spawn from round 1.

## Verification

Smoke-tested in `qbert_practice`: spawn Slick on a flipped cube, observe state reverting to 0; land Q✱bert on Slick's current cube mid-hop, observe Slick vanishing without triggering player death.

## Files touched

- `wflevels/qbert_practice/blender_create_qbert.py` — `redball_script(variant='slick'|'sam')` branches, two new director actors + spawn timers
- `wflevels/qbert_practice/qbert_practice.lev` — regenerated
