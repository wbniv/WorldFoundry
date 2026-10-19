# Template-object Jolt body sync on spawn

**Status:** **Done (Jolt position-sync fix) — but it was *not* the sole cause of the
block→coin crash; see the 2026-05-21 correction below.** The fix (Jolt-body sync inside
`setCurrentPos`) is in HEAD — see [`actor.hpi`](../../wfsource/source/game/actor.hpi)
`Actor::setCurrentPos`, which now calls `JoltCharacterSetPosition` / `JoltBodySetPosition`.
It landed *inside* commit `0adf1d4` ("refactor(rtti): push GetWatchObject up into
MovementHandler (step 3/7)") — i.e. **bundled into an unrelated RTTI commit**, which is
why this plan, the wf-status table, and the [engine-mutation-api](2026-05-19-engine-mutation-api.md)
status had all lagged at "Not started / spawn aborts." **Runtime confirmed 2026-05-20:**
Will played the rebuilt binary (engine changes #1+#2 of [smb-block-generator-coin](2026-05-19-smb-block-generator-coin.md)
compiled in) and bumped a `?` block in smb_w1_1 with **no `terminate`**. The Jolt-body
position-sync fix is correct and stands.

> **Correction (2026-05-21):** the "position desync was the *sole* cause" claim was
> wrong. That 2026-05-20 play-test predated engine #3 (the `Gold` class, `7bf3de0`), so
> the `coin_template` it spawned was **not yet a `gold`** — `Gold::kind()` never ran.
> Once the coin became a `gold`, the block→coin spawn aborted again, this time on a
> **stale `gold.oad`**: generated Apr 28 before `Gold_KIND` existed, it baked the
> `MovementClass` default as `0` (`NULL_KIND`) instead of `26` (`Gold_KIND`), failing
> `Gold::kind()`'s `assert(MovementClass == Gold_KIND)` — disguised as `terminate`
> because the failing `exit()` tears down the still-joinable debug-bridge thread. Plus
> `objects.{col,car}` were never regenerated for Gold → a follow-on OOB in
> `Actor::CanCollide`. Root-caused + fixed 2026-05-21 (regenerate `gold.oad` +
> `objects.{car,col,ctb}` from the masters); see
> [smb-block-generator-coin § Status](2026-05-19-smb-block-generator-coin.md) and
> [docs/level-building.md § Creating a new OAD class](../level-building.md#creating-a-new-oad-actor-class).

Diagnostic `fprintf`s in
`generator.cc` are intentionally retained until the SMB block-generator + Gold plan
completes (`feedback_debug_instrumentation_teardown`).
**Owner:** Claude (Will reviewing)
**Date:** 2026-05-19
**Branch:** `2026-new-level`

## Context

SMB W1-1 Phase 2 (`docs/plans/2026-05-19-smb-coin-fix-and-template.md`) refactored the coin from one pre-placed `qblock_NN_coin` per `?` block into a single `coin_template` actor + per-block `Generator`. With the spawner-Z gotcha fixed (see `docs/level-design-troubleshooting.md` "Generator + Template Object spawn position must clear collidable objects by ≥ template half-size"), the spawn pipeline now reaches `Level::ConstructTemplateObject` and returns non-NULL — but the engine crashes immediately after with `terminate called without an active exception`, and the Jolt body is created at the template's authored parking position `(-50, 0, 0)`, not at the spawn position `(11.88, -0.12, 8.38)`.

## Reproduction

With `engine/wf_game` at mtime ≥ 2026-05-19 05:49 (carrying the upstream-collision fprintfs from this session):

1. `cd wfsource/source/game && wf_game -L wflevels/smb_w1_1-standalone.iff --debug-port 7779`
2. Cheat-trigger Mario's bump via bridge (no need to drive Mario in-game):
   ```python
   b = BridgeClient(port=7779)
   b.set_mailbox(mailbox=3044, value=13,  idx=9)   # Mario.COLLIDER_IDX
   b.set_mailbox(mailbox=3047, value=1.0, idx=9)   # Mario.COLLISION_NORMAL_Z
   ```
3. Observe the log:
   ```
   Generato::FIRING objectToGenerate=12 _idxActor=15
   Generato: calling ConstructTemplateObject(idx=12, _idxActor=15, pos=(11.88,-0.12,8.38), vel=(0,0,8))
   jolt: character 1 created at (-50.00, 0.00, 0.00) ctr=(0.00,0.00,0.00)   ← wrong
   Generato: ConstructTemplateObject returned non-NULL
   Generato: AddObject(actor_idx=0) at pos
   terminate called without an active exception
   ```

## Root cause

`Level::ConstructTemplateObject` (`wfsource/source/game/level.cc:1687`):

```cpp
Actor* createdObject = SafelyConstructTemplateObject(templateObjectIndex, parentObjectIndex, position, velocity);
if(createdObject)
{
    createdObject->setCurrentPos(position);   // updates _position only
    createdObject->setSpeed(velocity);
    ...
}
```

`SafelyConstructTemplateObject` calls the OAS-generated `ConstructTemplateObject(type, startupData)`, which calls the actor constructor with `startupData->Position` = the *authored* template position (Blender `obj.location`, parked at `(-50, 0, 0)` so the template doesn't collide with the playfield at level load). The actor constructor creates a Jolt **CharacterVirtual** at that authored position (because `Mobility = Physics`).

Then `setCurrentPos(position)` is called with the spawn position. Definition (`actor.hpi:83-91`):

```cpp
inline void Actor::setCurrentPos( const Vector3& pos ) {
    ...
    _physicalAttributes.SetPosition(pos);
}
```

That sets `_position` (which the renderer consumes via `Matrix34(orientation, position)` in `renderassets/rendacto.cc:466`), but **does not move the Jolt body**. Net effect: renderer draws the coin at the spawn position, physics simulates it from the parked position, and the actor-index assignment fails downstream (`AddObject(actor_idx=0)`), terminating.

For comparison, the existing handlers for `EMAILBOX_X_POS / Y_POS / Z_POS` writes in `actor.cc:1415-1465` already do the right thing — they update `_position`, `_predictedPosition`, **and** call `JoltCharacterSetPosition(charID, tVect)` when the actor has a Jolt character handle. The plan that established this pattern is `docs/plans/2026-05-11-mailbox-pos-write-bypasses-jolt.md`. `setCurrentPos` was overlooked because before template objects shipped, no in-tree call site reached `setCurrentPos` with a position that differed from the authored Jolt body position.

## Fix

**Option A — push the Jolt sync into `setCurrentPos` itself** *(recommended — ALREADY APPLIED in HEAD via commit `0adf1d4`; see Status above. Verification still pending).*

`setCurrentPos` semantically means "this actor is now at this world position." Anything observable that derives from world position — renderer pose, predicted position, physics body, particle attachments — should agree afterward. The X/Y/Z_POS mailbox handlers had to copy the sync block three times specifically because `setCurrentPos` lacks the invariant; folding the sync into `setCurrentPos` lets those handlers shrink to a single call later (out of scope — separate cleanup).

Edit `wfsource/source/game/actor.hpi:83-91`:

```cpp
inline void Actor::setCurrentPos( const Vector3& pos ) {
    DBSTREAM1(
        if ( !GetMovementBlockPtr()->Mobility )
            cerror << "Actor::setCurrentPosition: " << *this
                   << " doesn't have mobility set!" << std::endl;
    )
    _physicalAttributes.SetPosition(pos);
    _physicalAttributes.SetPredictedPosition(pos);   // parity with mailbox handlers
#ifdef PHYSICS_ENGINE_JOLT
    {
        uint32_t charID = _physicalAttributes.JoltCharacterID();
        if (charID != kJoltInvalidBodyID)
            JoltCharacterSetPosition(charID, pos);
        uint32_t bodyID = _physicalAttributes.JoltBodyID();
        if (bodyID != kJoltInvalidBodyID)
            JoltBodySetPosition(bodyID, pos);
    }
#endif
}
```

Notes:
- `JoltBodySetPosition` also gets a branch because dynamic-body actors (`Mobility=Physics` doesn't *always* produce a CharacterVirtual — Generator-spawned non-character physics actors could use the `_joltBodyID` path). Cheap branch on a comparison; no harm if neither handle is valid (e.g. Mobility=Anchored with no Jolt at all).
- `SetPredictedPosition` mirrors what the mailbox handlers do — `_predictedPosition` is used by the next physics step's prediction; if we leave it stale, the next tick can teleport the actor back.
- `actor.hpi` already pulls `physical.hp` (which declares `JoltCharacterID`/`JoltBodyID`) and `jolt_backend.hp` is included via `actor.cc`. Need to verify `jolt_backend.hp` is reachable from `actor.hpi`'s translation units — if not, move the body out-of-line into `actor.cc` and leave a forward declaration in `actor.hpi`. Step 1 of implementation confirms this.

**Option B — fix only `Level::ConstructTemplateObject`** *(rejected)*.

Add a Jolt-sync block after `setCurrentPos` in `level.cc:1690`. Strictly more localized but it papers over the missing invariant on `setCurrentPos`. Future paths (path-following actors, warp actors, debug "teleport this actor" mailboxes) would each have to remember the sync. Per `feedback_root_cause_not_symptom`.

**Option C — sidestep entirely with scripted-coin** *(rejected by Will)*.

Make the coin `Mobility=Anchored` and drive its arc with a per-instance Forth `Z_POS write-actor-mailbox` script. Avoids the Jolt template-instantiation bug because the coin never has a moving Jolt body. Will explicitly chose Option A so coins use real physics (gravity, future Mario-coin collision, etc.).

## Implementation steps

1. **Verify header reachability.** Confirm `actor.hpi` translation units already pull `jolt_backend.hp`. If not, add `#include <physics/jolt/jolt_backend.hp>` to `actor.hpi` (or, if that creates a cycle, move the new code out-of-line into a new `Actor::setCurrentPos` non-inline definition in `actor.cc` and leave the declaration in `actor.hp`).
2. **Edit `setCurrentPos`** per Option A above.
3. **Rebuild engine** (`task build`).
4. **Re-run cheat-triggered spawn** (the bridge cheat from "Reproduction" §2). Expected log:
   ```
   Generato::FIRING ...
   Generato: ConstructTemplateObject returned non-NULL
   jolt: character 1 created at (-50, 0, 0)   ← still parked, OK (template registration step)
   jolt: character SetPosition charID=1 pos=(11.88, -0.12, 8.38)   ← new line from the sync
   Generato: AddObject(actor_idx=<reasonable number>) at pos
   ```
   No `terminate`. Coin visible in screenshot at (~11.88, -0.12, 8.38), then arcing under gravity (`Falling Acceleration = 12 m/s²` from coin template).
5. **Screenshot proof** — bridge `screenshot` op at t = +0.0s (spawn), +0.3s (rising), +0.8s (apex), +1.5s (falling). `~/tmp/smb-shots/coin_template_arc_*.png`. Read each via the `Read` tool to verify visually.
6. **Regression check — Mario movement.** Drive `joystick1_raw = JOY_RIGHT` for ~3s, verify Mario walks normally (`ball pos` X increases). Confirms `setCurrentPos` change didn't break Mario's per-tick movement (Mario goes through different code paths — `MarbleHandler::predictPosition` updates Jolt directly, not via `setCurrentPos` — but worth confirming.)
7. **Regression check — existing tests.** `pytest tests/test_disc_lure.py` etc., any test that uses `set_mailbox` to teleport an actor.

## Validation

Pass criteria:
- Coin spawn produces no `terminate`.
- `jolt: character N` shows the post-sync `SetPosition` line landing at the spawn pos.
- Screenshots show coin rising → apex → falling at the expected `(bx, 0, block_top + ε)` location.
- Mario walks and jumps normally.
- Existing tests green.

Fail criteria → rollback Option A and apply Option B as a fallback.

## Risks

- **Hidden callers of `setCurrentPos` that *want* `_position` to drift from Jolt body.** None spotted: the only call sites are template construction (`level.cc:1690`), path-follower update (`actor.cc:759` — for `Mobility=Path`, which doesn't have a Jolt character/body; the Jolt branch will no-op via `kJoltInvalidBodyID`), and any subclass overrides. Grep before merging.
- **`JoltCharacterSetPosition` on a body in mid-physics step** — safe per Jolt docs (`CharacterVirtual::SetPosition` just updates the position; next `Update` re-projects against the world).
- **Inlining cost.** `setCurrentPos` is currently `inline` in `actor.hpi`. Adding the Jolt block bloats every inlined call site. Mitigated by moving to a non-inline `actor.cc` body if the size cost matters; benchmark with `task build` before/after.

## Rollback

`git revert` the single commit that touches `actor.hpi` (and optionally `actor.cc` if step 1 forced out-of-line). Re-apply Option B as a strict subset of the change scope.

## Related

- `docs/plans/2026-05-11-mailbox-pos-write-bypasses-jolt.md` — established the X/Y/Z_POS-write Jolt-sync pattern this plan generalizes.
- `docs/plans/2026-05-19-smb-coin-fix-and-template.md` — the SMB coin template work that surfaced this bug.
- `docs/level-design-troubleshooting.md` — entry "Generator + Template Object spawn position must clear collidable objects by ≥ template half-size" covers the *previous* layer of this debug session.
