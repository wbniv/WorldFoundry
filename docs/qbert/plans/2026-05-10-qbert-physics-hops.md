# Plan — Q✱bert physics-based player hops

**Date:** 2026-05-10
**Status:** Parked — lerp-based hop-arc + `FALL_PHASE` machine is sufficient; Jolt-driven hops add complexity with no visible payoff for Q✱bert.

## Relationship to the rotation plan

The [hop-facing-rotation plan](2026-05-10-qbert-hop-facing-rotation.md) lands first and adds a smooth yaw interpolation across the existing 12-frame `HOP_COOLDOWN`. When this plan replaces the cooldown-based hop with a physics arc, swap the rotation block's trigger from `HOP_COOLDOWN > 0` to whatever this plan's mid-hop signal is (~1 LOC) and the yaw interpolation continues to work unchanged. The two plans are otherwise independent.

## Context

Today's `do-hop` (in [wflevels/qbert_practice/blender_create_qbert.py:334-348](../../wflevels/qbert_practice/blender_create_qbert.py)) writes `INDEXOF_X_POS / Y_POS / Z_POS` directly. Per [wfsource/source/game/actor.cc:1313-1338](../../wfsource/source/game/actor.cc), those calls go through `_physicalAttributes.SetPosition()` + `SetPredictedPosition()` — i.e. they teleport Q✱bert's Jolt character body. The existing `JoltMakeCharacter()` rig at [actor.cc:707](../../wfsource/source/game/actor.cc), gravity, and cube collision are all functional but bypassed.

Result: gameplay is 2.5D arithmetic. Hops are integer (row, col) deltas → world XYZ via `1.4142136 *` math; Z is `(6-row)*2 + 1 + 2`. The fall animation is a manual `FALL_PHASE` state machine at [blender_create_qbert.py:392-403](../../wflevels/qbert_practice/blender_create_qbert.py) that decrements `INDEXOF_Z_POS` one unit per tick. None of this uses physics.

## Goal

Replace teleport-based hops with physics-driven hops. A hop becomes a one-shot velocity impulse; gravity + Jolt collision against the cube static meshes does the rest. Q✱bert flies in a parabolic arc, lands on the destination cube top, and the director observes the landing event to advance cube state.

The (row, col) bookkeeping stays — it's how we identify which cube was just landed on, and is the right granularity for the Q✱bert game logic. What changes is that the *position* of Q✱bert is owned by physics, not by the Forth director.

## Decisions

- **Velocity mailboxes**, not impulses. `INDEXOF_XSPEED / YSPEED / ZSPEED` already exist ([actor.cc:1405-1428](../../wfsource/source/game/actor.cc)) and call `JoltCharacterSetLinVelocity` on the Jolt CharacterVirtual. Single mailbox write per axis per hop.
- **Keep current gravity.** Jolt `selftest ok (sphere fell to z=5.098)` log line says gravity ≈ -9.8. We tune *hop velocity* to match arcade pacing (≈0.4-0.5s per hop), not the world.
- **Snap-to-cube on landing** to prevent drift accumulation. After Q✱bert's vertical velocity crosses zero (apex of arc) and Z stabilises near a cube top, snap (X, Y) to the exact center of the inferred (row, col) cube. Drift would compound across rounds.
- **Drop the manual FALL_PHASE state machine.** Off-edge falls become free behaviour: no cube under Q✱bert → gravity ramps him down. Death detection is `INDEXOF_Z_POS < threshold` (e.g. -5).
- **Drop the safety-net Z<-2 teleport.** Same reason — physics handles it.

## Approach

### Phase 1 — Tuning harness

A small dev hook in the player script that on a debug key (or on `mb[450]` poke) launches Q✱bert with configurable `(vx, vy, vz)`, then prints landed XYZ to the log via a one-shot print after Z stabilises. Used by hand to find the impulse magnitudes that produce a 1-cube DR / DL / UR / UL hop given current gravity.

Expected ballpark: with cube spacing ≈ 2.828 in horizontal (SQRT2 × CUBE_SIZE) and ΔZ = ±2 between adjacent cube tops, and gravity = 9.8, a 0.5s hop needs `vz ≈ 4.45 m/s` going up (apex 0.225 cubes above start) and `vh ≈ 5.66 m/s` horizontal. These are starting numbers; tune empirically.

### Phase 2 — Replace `do-hop` with velocity-launch

`do-hop` currently:
1. Updates (row, col) state.
2. Writes XYZ position.
3. Sets `HOP_COOLDOWN = 12`.
4. Sets `QBERT_LANDED = 1`.

After:
1. Updates (row, col) state.
2. Computes target (X_dst, Y_dst, Z_dst) but doesn't write it; uses it to derive the velocity vector.
3. Writes XSPEED/YSPEED/ZSPEED.
4. Sets a new `HOP_IN_FLIGHT = 1` flag and clears `QBERT_LANDED`.

A new per-tick player block watches for landing (vertical velocity transitions from negative to ≥0 *and* horizontal velocity is small *and* Z near a cube top). On landing:
1. Snap (X, Y) to expected cube centre.
2. Zero velocity.
3. Set `QBERT_LANDED = 1`.
4. Clear `HOP_IN_FLIGHT`.
5. Begin `HOP_COOLDOWN` (frames during which input is locked).

### Phase 3 — Off-edge fall via physics

Remove `FALL_PHASE` machine ([blender_create_qbert.py:392-403](../../wflevels/qbert_practice/blender_create_qbert.py)) and the off-edge branch in `do-hop` ([:340-348](../../wflevels/qbert_practice/blender_create_qbert.py)). Replace with:

- During `HOP_IN_FLIGHT`, if Z < `FALL_DEATH_Z` (e.g. -5), trigger death: clear flight flag, decrement lives, set `FALL_DEATH = 1`.
- The existing apex respawn handler (`mb[426]` flag) already snaps to apex on respawn — keep it, but it now sets velocity to zero too.

### Phase 4 — Joystick verification

Boot, play with the keyboard/joystick, confirm Q✱bert hops with arcs, lands cleanly, falls off the edge correctly. This is the user-visible "yes, physics works" moment.

### Phase 5 — Autopilot revisit

The autopilot's 32-step Warnsdorff coverage path ([blender_create_qbert.py:407-433](../../wflevels/qbert_practice/blender_create_qbert.py)) currently hops one per tick using the cooldown. After Phase 2, autopilot must wait for `QBERT_LANDED` between steps instead of fixed cooldown. Trivial change.

The walker harness and pixel-diff become orthogonal — once Q✱bert flies in arcs, a screenshot won't pixel-match an arcade frame. Walker can be archived; arcade-palette regression can be re-tooled later as a static cube-color check (no player in frame) if useful.

## Critical files

| File | Action |
|---|---|
| [wflevels/qbert_practice/blender_create_qbert.py](../../wflevels/qbert_practice/blender_create_qbert.py) | rewrite `do-hop`, add landing watcher, remove `FALL_PHASE` machine |
| (none in engine) | velocity mailbox path already exists |
| `docs/plans/2026-05-10-qbert-physics-hops.md` | this doc |

No engine C++ changes anticipated.

## Verification

1. Boot `wf_game -Lwflevels/qbert_practice-standalone.iff`.
2. Joystick: Q✱bert visibly arcs between cube tops, no teleport snap.
3. Autopilot: 28-cube clear of L1R1 still works, with arc visuals.
4. Off-edge: walking off the bottom row visibly falls and triggers death.
5. Screen recording shows arcs (subjective but the win criterion).

## Risks

- **Hop tuning is annoying.** Phase 1 mitigates by giving a fast loop. May need 5-10 iterations to find good values.
- **CharacterVirtual + horizontal launch** may behave oddly — characters in Jolt are usually walking, not ballistic. May need to detach from "character" mode mid-flight (set zero ground move, allow gravity), then re-attach on landing. Investigate during Phase 1 if arcs look wrong.
- **Cube collision precision.** If Q✱bert lands between two cubes (on an edge), what does Jolt do? Snap-to-cube on landing should mask it but watch for edge cases.
- **Autopilot timing.** Replacing fixed cooldown with landed-event introduces an idle gap if landing detection is slow. Tune the landing predicate in Phase 2.

## Out of scope

- Mesh fan-out cleanup (1344 actors → 28 with dynamic colour). User confirmed this comes after physics.
- Camera movement / orbit / follow. Stays fixed iso for now.
- Walker/pixel-diff harness. Archive after Phase 4 ships.
- Multi-player or enemy AI (Coily, Slick, Sam). Out of scope for this plan.
