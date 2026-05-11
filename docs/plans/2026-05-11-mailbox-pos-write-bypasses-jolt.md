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

The investigation surfaced that the Validate was triggering on the **cam intro pan**, not on Q*bert's teleport — the additional `JoltCharacterSetPosition` calls just changed tick timing enough to expose a pre-existing float-precision false-positive that's been in `ColSpace::Expand()` round-trip arithmetic all along. That bug was then fixed independently in commit `a56cd51` ([physical-validate-float-tolerance plan](2026-05-11-physical-validate-float-tolerance.md)) — `PhysicalAttributes::Validate()` now uses a per-axis `Scalar::FromDouble(1e-3)` abs-diff threshold instead of bitwise `Vector3::operator==`. With that landed, the naive fix re-applies cleanly.

## How Jolt handles teleporting (added 2026-05-11)

The fix delegates to [`JoltCharacterSetPosition(handle, pos)`](../../wfsource/source/physics/jolt/jolt_backend.cc) at [jolt_backend.cc:593-599](../../wfsource/source/physics/jolt/jolt_backend.cc):

```cpp
void JoltCharacterSetPosition(uint32_t handle, const Vector3& pos)
{
    if (handle >= (uint32_t)gCharacters.size() || !gCharacters[handle].occupied) return;
    CharEntry& e = gCharacters[handle];
    e.posCache = pos;
    e.character->SetPosition(ToJph(pos + e.ctr));
}
```

Two layers of "teleport" happen here, and each has a story worth knowing:

### Layer 1 — WF↔Jolt position offset

A WF actor's reported `_position` is the **feet** position (per existing WF convention). The Jolt `CharacterVirtual`'s position is the **centre of the collision shape**. The two differ by a fixed offset `ctr = minPt + half`, computed once at [`JoltCharacterCreate`](../../wfsource/source/physics/jolt/jolt_backend.cc) ([jolt_backend.cc:485-522](../../wfsource/source/physics/jolt/jolt_backend.cc)) from the colSpace bbox passed in by `JoltMakeCharacter`. So every WF↔Jolt position transfer routes through `pos + e.ctr` (outbound) or `p - e.ctr` (inbound, see `JoltCharacterUpdate` at line 632). The new mailbox-write path uses that exact pattern — we pass the actor-feet pos and the function applies the offset.

The cached `posCache` is the value that `JoltCharacterGetPosition()` returns to `movement.cc::JoltSyncFromCharacter`. It's updated *before* the Jolt SetPosition call here, then **rewritten** from `character->GetPosition() - ctr` on the next `JoltCharacterUpdate` ([jolt_backend.cc:631-632](../../wfsource/source/physics/jolt/jolt_backend.cc)). So if Jolt resolves the teleport into a slightly different pose (penetration push-out, see Layer 2), the next physics tick reflects that adjustment back into WF.

### Layer 2 — Jolt's `CharacterVirtual::SetPosition` semantics

Internally `e.character->SetPosition(...)` is Jolt's [public API](https://jrouwe.github.io/JoltPhysics/class_character_base.html) on `CharacterVirtual`. Per Jolt's design:

- **No collision resolution at the moment of set.** The character is instantly moved to the new position, even if that puts the shape inside static geometry. There is no contact solver, no penetration check, no swept-test from the old position to the new — it's a literal pose write.
- **Velocity is unaffected.** Any linear velocity set via `SetLinearVelocity` (we use this for gravity-driven WF motion in `JoltCharacterSetLinVelocity`, [jolt_backend.cc:585-591](../../wfsource/source/physics/jolt/jolt_backend.cc)) is preserved. The character will continue moving from the new pose on the next `ExtendedUpdate`.
- **Penetration is resolved on the next `ExtendedUpdate`.** When `JoltCharacterUpdate` runs (called from `movement.cc` each frame), the character's standard contact-collection + contact-solving path runs from the new starting pose. Any overlap with static geometry gets resolved by Jolt's normal character-controller logic — typically the character is pushed out along the contact normal, the resolved pose is read back via `GetPosition()`, and `posCache` updates. This is why we cache `posCache = pos` *before* `SetPosition` but trust the post-update value as authoritative.
- **No body activation, no constraint-solver wakeup.** Unlike Jolt rigid bodies (where `BodyInterface::SetPosition` requires an `Activate` argument and can sleep otherwise), `CharacterVirtual` has no sleeping behaviour — it runs every tick regardless. Teleporting is "free" in that sense; you don't need to wake anything.

### Comparison: Jolt rigid-body teleport (not used here, but worth knowing)

For non-character Jolt actors (the rigid-body path used by `STATIC` and `KINEMATIC` bodies in WF), teleport would go through `BodyInterface::SetPosition(bodyID, pos, EActivation::Activate)` or `MoveKinematic(bodyID, pos, rot, dt)` instead. `MoveKinematic` interpolates the body's velocity over `dt` so it sweeps to the target — useful for moving platforms (it pushes other bodies it intersects). `SetPosition` is the equivalent of `CharacterVirtual::SetPosition` — instant relocation, no sweep, penetration unresolved until the next step. Today only the character path is wired into the mailbox-pos handlers (the explicit "Risks" call-out in this plan); rigid-body actors that need mailbox teleport later will need a parallel `JoltBodySetPosition` call.

### Why this is the right pattern for Q*bert's use case

Q*bert's script writes target positions in three situations: apex respawn (after a death fall), round-clear reset (back to apex when a round is won), and game-over restart (reset to apex with full lives). All three are **discontinuous** teleports — there's no semantically meaningful velocity carrying from the old pose to the new one, no "sweep through everything between" semantics needed, and the target is always free space (the apex cube, above the pyramid). `CharacterVirtual::SetPosition` is the exact match: instant relocation, the next `ExtendedUpdate` settles the character onto the apex cube via the standard ground-detection path, gravity continues from there. Q*bert's `linVelocity` was probably zero already at the moment the script writes the teleport (or will be in the next tick once the script also writes `Z_SPEED = 0`); either way, preserving velocity through the teleport is correct.

## Implementation details (added 2026-05-11)

Final code at [actor.cc:1343-1395](../../wfsource/source/game/actor.cc) — three identical blocks for X/Y/Z:

```cpp
case EMAILBOX_X_POS:
{
    Vector3 tVect = _physicalAttributes.Position();
    tVect.SetX(value);
    _physicalAttributes.SetPosition(tVect);
    _physicalAttributes.SetPredictedPosition(tVect);
#ifdef PHYSICS_ENGINE_JOLT
    // For Jolt character actors, the per-tick movement sync at
    // movement.cc overwrites _position with the character body's
    // pose unless we also push the teleport into Jolt.
    {
        uint32_t charID = _physicalAttributes.JoltCharacterID();
        if (charID != kJoltInvalidBodyID)
            JoltCharacterSetPosition(charID, tVect);
    }
#endif
    break;
}
```

- `_physicalAttributes.JoltCharacterID()` is the inline accessor at [physical.hp:136](../../wfsource/source/physics/physical.hp) returning the cached `_joltCharID`.
- `kJoltInvalidBodyID` is the sentinel used throughout `physical.hpi` (see [`JoltMakeCharacter`](../../wfsource/source/physics/physical.hpi) at [physical.hpi:236-265](../../wfsource/source/physics/physical.hpi)) when an actor has no character body.
- The `#ifdef PHYSICS_ENGINE_JOLT` guard mirrors existing physics-conditional blocks in `actor.cc` (lines 510, 683, 719). When the legacy `physics/wf/` backend is selected at build time the new block compiles out and the original `_position`-only path runs.
- All three handlers (X/Y/Z) write **the full updated `tVect`**, not a single-axis update — `SetPosition` doesn't have a "preserve other axes" variant. This is fine: `tVect` is read from `_physicalAttributes.Position()` at the top of each handler, with the new axis applied, so the other axes are preserved.
- The order matters: WF's `_position` is updated **first**, then pushed to Jolt. If we did it the other way around, the `posCache` cached value would briefly diverge from `_position` for one statement, which is harmless but uglier.

## Smoke-test result

Engine boots `wflevels/qbert_practice-standalone.iff` and runs through the camshot intro pan + gameplay for the full 12-second timeout window with no `FATAL ERROR: PhysicalAttributes::Validate()` assert and no terminate. Z-coordinate Forth writes (`15 INDEXOF_Z_POS write-mailbox`) now take effect — Q*bert sits at his scripted Z on apex respawn instead of falling back to the previous Jolt-resolved pose.
