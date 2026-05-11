# Plan — Mailbox `X/Y/Z_POS` writes bypass Jolt character body

**Date:** 2026-05-11
**Status:** Done 2026-05-11. The naive fix from the original plan now lands cleanly because the underlying Validate strict-equality false-positive was fixed independently in commit [`a56cd51`](../../) ([physical-validate-float-tolerance plan](2026-05-11-physical-validate-float-tolerance.md)). Re-applied the `JoltCharacterSetPosition` call in all three `EMAILBOX_X/Y/Z_POS` handlers at [actor.cc:1343-1395](../../wfsource/source/game/actor.cc); engine boots the qbert standalone through gameplay with no Validate assert and no observable position-write loss.

## Symptom

Qbert practice autopilot dies within ~10 s every run. Q*bert visibly sits at Z≈7 even though the player script writes `15 INDEXOF_Z_POS write-mailbox` on every apex respawn / round-clear / FALL_PHASE end.

Verified via debug bridge: `mb[3011]` (`INDEXOF_Z_POS`) reads back 7.0 immediately after the script writes 15.

## Root cause

[`wfsource/source/game/actor.cc:1343-1369`](../../wfsource/source/game/actor.cc) handles `EMAILBOX_X_POS / Y_POS / Z_POS` by calling `_physicalAttributes.SetPosition(...) + SetPredictedPosition(...)`. Those just update the C++ `_position` field.

For actors with a Jolt character body (Q*bert is one — `JoltMakeCharacter` at [actor.cc:707](../../wfsource/source/game/actor.cc)), the per-tick movement code at [`movement.cc:441-448`](../../wfsource/source/movement/movement.cc) calls `JoltSyncFromCharacter(JoltCharacterGetPosition(charID))` — which writes Jolt's authoritative position back into `_position`. So any write made through the mailbox is silently overwritten on the next physics tick.

`JoltCharacterSetPosition` exists at [`jolt/jolt_backend.cc:593`](../../wfsource/source/physics/jolt/jolt_backend.cc) but is currently unused by the mailbox write path.

## Fix

In the three `EMAILBOX_X/Y/Z_POS` cases, after `_physicalAttributes.SetPosition`, also push to Jolt when the actor has a character handle:

```cpp
#ifdef PHYSICS_ENGINE_JOLT
uint32_t charID = _physicalAttributes.JoltCharacterID();
if (charID != kJoltInvalidBodyID)
    JoltCharacterSetPosition(charID, tVect);
#endif
```

Same shape for X, Y, Z.

## Why this matters beyond autopilot

Every place in the Forth script that teleports a player (apex respawn after death, round-clear reset, game-over restart) is currently broken — the script writes target position, the engine ignores it, Q*bert keeps wherever Jolt last placed him. Fixing this restores all the existing position-write paths the script already has.

## Verification

1. Rebuild `wf_game` (`engine/build_game.sh`).
2. Launch standalone; via debug bridge, set `mb[3011]=15` on the player actor.
3. Probe `mb[3011]` 100 ms later — expect 15 (or whatever physics resolves to after one step with gravity), not 7.
4. Re-run the autopilot walker. Expect Q*bert to visibly hop across cubes.

## Risks

- Other (non-character) Jolt actors using rigid bodies still go through the old `_position`-only path; if they later need mailbox teleport they will hit the same bug. Out of scope here — fix only the character path.
- Snapping Jolt position mid-physics-step is the standard way to teleport a CharacterVirtual; should not destabilise the sim.

## 2026-05-11 attempt — reverted

Added the `JoltCharacterSetPosition` calls under `#ifdef PHYSICS_ENGINE_JOLT` in all three mailbox cases. Engine crashed on intro with:

```
FATAL ERROR: PhysicalAttributes::Validate() failed.
predictedMotionVector = 22.78765297, -30.6890564, 7.993789673
      expansionVector = 22.78765297, -30.6890564, 7.99379015
```

The Validate at [physical.hpi:67](../../wfsource/source/physics/physical.hpi) does strict-equality `Vector3` comparison. The two vectors match to 5 decimal places but differ in the 6th — looks like a Scalar→Vector3 conversion precision issue *or* an accumulated-colSpace-expansion vs. recomputed-motion mismatch. Reverted the actor.cc edit (`display.hp` BG init kept).

Open question: is the precision mismatch:

(a) **A pre-existing precision bug** in `_colSpace.Expand()` accumulation that my change just happened to exercise via the camshot intro pan — fix this independently of the mailbox path, or

(b) **A side effect** of the order-of-operations: my mailbox write fires *after* the camshot has already expanded the colSpace for its own motion, and `SetPosition` + `SetPredictedPosition` (= 0 delta) doesn't undo the prior expansion.

To investigate (b): the mailbox path should probably call `_colSpace.ShrinkToUnExp()` or similar before the SetPredictedPosition expand, so the colSpace tracks JUST the teleport-induced delta. Need to find/add an "unexpand" method on `ColSpace`.

The trigger position (8.93, -34.24, 26.21) matches mid-camshot-intro-pan, not Q*bert. So `(a)` is more likely — the cam intro itself, not my fix, exposes the bug. My fix probably triggered it because the additional Jolt-character teleports change tick timing enough to shift which physics step it lands on.
