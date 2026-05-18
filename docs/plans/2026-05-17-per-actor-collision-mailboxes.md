# Per-actor collision mailboxes (enables `?`-block bump + beyond)

**Status:** Active 2026-05-17. Replaces the [parked plan](2026-05-17-smb-qblock-bump-parked.md) — the user reopened the design after parking, and the simpler mechanism makes the work small enough to do now.

## Context

User asked: *"isn't there some relatively trivial way to expose actors that collide vs. other actors… into the actors' local mailboxes?"* — yes. The parked plan over-scoped this as a new OAS field, which was the wrong abstraction. The simpler design: **add four LOCAL_SYSTEM mailboxes that the engine automatically populates for every Actor on every collision**. Scripts that care just read them; no per-actor authoring needed.

Three new findings (since the parked plan was written) change the calculus:

1. **`NUM_COLLISIONS = 4000` was already reserved** ([mailbox.inc](../../wfsource/source/mailbox/mailbox.inc) line 121) and there's a **commented-out clear** at [actor.cc](../../wfsource/source/game/actor.cc) line 874 — a previous dev had this exact same idea, just stopped halfway. We're finishing wiring that was started years ago.
2. **[collision.cc](../../wfsource/source/physics/collision.cc) lines 309–310 already call `Collision()` on both actors** with negated normals — so each actor receives a contact normal pointing AWAY from the other object. No engine work needed to "tell both sides"; physics already does.
3. **Per-actor system mailbox range** is 3000–3043 with `LOCAL_SYSTEM_MAX = 3043`. Room to bump to 3048 with 4 new entries. No collision with the SCRATCH range (4000+) or the GLOBAL_SYSTEM range (1901+).

`PhysicalObject::Collision()` default is no-op ([physicalobject.cc](../../wfsource/source/physics/physicalobject.cc) line 51) and `Actor::Collision()` is the only override doing meaningful work today (supportingObject tracking only) — so adding mailbox writes there gives this to every Actor-derived object for free. Statplats / pure-physical walls that don't subclass Actor pay nothing.

## Design

### New mailboxes — add to [mailbox.inc](../../wfsource/source/mailbox/mailbox.inc) just below `Z_SCALE` (3042)

```c
Comment("Last collision contact this frame (set by Actor::Collision, cleared per frame).")
Comment("COLLIDER_IDX is the 'fresh' indicator — 0 means no collision since last clear.")
Comment("Normal vector points AWAY from the other object (collision.cc negates for object2),")
Comment("so for a ?-block hit from below: NORMAL_Z < 0; for landing on top of something: NORMAL_Z > 0.")
MAILBOXENTRY( COLLIDER_IDX,       3044 )
MAILBOXENTRY( COLLISION_NORMAL_X, 3045 )
MAILBOXENTRY( COLLISION_NORMAL_Y, 3046 )
MAILBOXENTRY( COLLISION_NORMAL_Z, 3047 )
```

Bump `LOCAL_SYSTEM_MAX` and `LOCAL_MAX` from `3043` → `3048`.

### Engine write site — extend [actor.cc](../../wfsource/source/game/actor.cc) line 1676 `Actor::Collision`

```cpp
void Actor::Collision(PhysicalObject& other, const Vector3& normal)
{
    GetMailboxes().WriteMailbox(EMAILBOX_COLLIDER_IDX,        Scalar(other.GetIdxActor(), 0));
    GetMailboxes().WriteMailbox(EMAILBOX_COLLISION_NORMAL_X,  normal.X());
    GetMailboxes().WriteMailbox(EMAILBOX_COLLISION_NORMAL_Y,  normal.Y());
    GetMailboxes().WriteMailbox(EMAILBOX_COLLISION_NORMAL_Z,  normal.Z());

    // existing behaviour:
    if (normal.Z() < Scalar::zero) {
        if (GetMovementManager().GetMovementHandlerData()) {
            MovementObject* movementObject = dynamic_cast<MovementObject*>(&other);
            assert(ValidPtr(movementObject));
            GetMovementManager().GetMovementHandlerData()->supportingObject = movementObject;
        }
    }
}
```

**Multiple-collisions-per-frame** behaviour: only the LAST collision's data is preserved (each write overwrites). Acceptable for SMB use; future work can add a counter (`NUM_COLLISIONS` is right there waiting) if needed.

### Engine clear site — extend the existing stub at [actor.cc](../../wfsource/source/game/actor.cc) line 874

The commented-out `WriteMailbox(EMAILBOX_NUM_COLLISIONS, Scalar::zero)` line shows the original intent. Replace the comment with:

```cpp
GetMailboxes().WriteMailbox(EMAILBOX_COLLIDER_IDX, Scalar::zero);
// Don't bother clearing NORMAL_{X,Y,Z} — they're only valid when COLLIDER_IDX != 0,
// and writing four mailbox slots per actor per frame is wasted work.
```

This runs once per actor per frame in `Actor::Update()` (the function containing line 874). `O(N_actors)` per frame for the clear, one trivial write each. Compare to the write side which is `O(actual contacts)` — broad-phase-culled by Jolt's BVH.

**Ordering concern:** This works iff `Update()`'s clear runs BEFORE the physics step's `Collision()` writes for the same frame. Verify the per-frame ordering during implementation; if `Update()` runs AFTER physics, then the script's read on frame N would see frame N's contact (good), but the clear would wipe it before frame N+1's script could re-read. Either way the script-visible window is ≥1 frame; SMB is fine with that. Plan-time guess: physics runs after Update(), so the clear-before-write order works. Verify with a `fprintf` in both spots when implementing.

## Phase A — engine + verification (no game-side change)

1. **Edit [mailbox.inc](../../wfsource/source/mailbox/mailbox.inc)** — add the 4 entries; bump `LOCAL_SYSTEM_MAX`/`LOCAL_MAX` to 3048.
2. **Edit [actor.cc](../../wfsource/source/game/actor.cc) line 1676** — add 4 mailbox writes at top of `Actor::Collision`.
3. **Edit [actor.cc](../../wfsource/source/game/actor.cc) line 874** — replace commented stub with real clear of `COLLIDER_IDX`.
4. **Rebuild engine** ([engine/build_game.sh](../../engine/build_game.sh)).
5. **Verify via debug bridge** — watch Mario's actor-9 `COLLIDER_IDX` (mailbox 3044) and a `?` block's `COLLIDER_IDX` during a bridge-driven jump-into-block sequence. Expect: when contact occurs, Mario reads block_idx in his 3044, block reads `9` in its 3044. Confirm `NORMAL_Z` signs match physics convention (block sees negative, Mario sees positive).
6. **Temporary `fprintf` instrumentation** at both sites if mailbox watches are too sparse — remove before commit.

## Phase B — minimal SMB `?`-block bump demo

For the first concrete payoff: a `?` block visibly flips to "used" appearance when Mario bumps it. Just the state swap — coin/popup/sound deferred.

1. **Add `qblock_0_used.iff` mesh** in [blender_create_smb.py](../../wflevels/smb_w1_1/blender_create_smb.py) — flat tan box, same dimensions as `qblock_00.iff` but without the `?` symbol.
2. **Stack** a `qblock_0_used` actor at the same position as `qblock_00`, with `Visibility Mailbox = SMB_QBLOCK_0_USED_VIS` (initially 0 → hidden). Set `qblock_00`'s Visibility Mailbox to `SMB_QBLOCK_0_VISIBLE` (initially 1 → visible).
3. **Add 2 new mailboxes** to [mailbox.inc](../../wfsource/source/mailbox/mailbox.inc) in the SMB GLOBAL_USER range (after `SMB_MAX_CAM_X = 1802`):
   ```
   MAILBOXENTRY( SMB_QBLOCK_0_VISIBLE,      1803 ) Comment("? block visible (1 at start, 0 after bump)")
   MAILBOXENTRY( SMB_QBLOCK_0_USED_VISIBLE, 1804 ) Comment("used-block visible (0 at start, 1 after bump)")
   ```
   No bare integer literals in the Forth that follows — use `INDEXOF_SMB_QBLOCK_0_VISIBLE` etc.
4. **Per-block bump script** on `qblock_00`:
   ```forth
   \ wf
   INDEXOF_COLLIDER_IDX read-mailbox
   dup 9 = swap 0<> and                     \ collider is Mario AND nonzero
   if
     INDEXOF_COLLISION_NORMAL_Z read-mailbox 0 <
     if                                      \ block hit from below
       0 INDEXOF_SMB_QBLOCK_0_VISIBLE write-mailbox
       1 INDEXOF_SMB_QBLOCK_0_USED_VISIBLE write-mailbox
     then
   then
   ```
   (Forth syntax verified during impl — may need `swap`/`and` tweaks. Direction discrimination via normal.Z is sufficient; falls back to comparing self.Z vs Mario's Z if normal sign turns out to be inverted from what's expected.)
5. **Rebuild level** (Blender → [build_level_binary.sh](../../wftools/wf_blender/build_level_binary.sh)).
6. **Screenshot proof** — bridge sequence: walk right, jump under block, screenshot showing flat-tan used-state block. Compare to pre-bump screenshot. Two distinct PNGs = bump mechanic verified end-to-end.

## What's still out of scope (separate follow-up plans)

- Coin emerge + Z-arc + visibility window
- `popup_200` score label (mirror qbert's popup pattern)
- Coin "bing!" sound via miniaudio
- Generalizing the "hit me" handler to enemy stomps (goomba squash) — same mechanism, different scripted reaction
- `NUM_COLLISIONS` counter (the original stub) for multi-contact-per-frame scenarios
- Statplat exclusion optimization (likely unneeded; statplats may not subclass Actor at all)

## Critical files

- [wfsource/source/mailbox/mailbox.inc](../../wfsource/source/mailbox/mailbox.inc) — 4 LOCAL_SYSTEM entries + `LOCAL_SYSTEM_MAX` bump; 2 SMB GLOBAL_USER entries.
- [wfsource/source/game/actor.cc](../../wfsource/source/game/actor.cc) line 1676 — 4-line write extension in `Actor::Collision`.
- [wfsource/source/game/actor.cc](../../wfsource/source/game/actor.cc) line 874 — replace commented stub with real per-frame clear.
- [wflevels/smb_w1_1/blender_create_smb.py](../../wflevels/smb_w1_1/blender_create_smb.py) — add `qblock_0_used` actor + Visibility Mailbox wiring + per-block Forth bump script.

## Verification end-to-end

- [engine/build_game.sh](../../engine/build_game.sh) succeeds.
- Debug-bridge watch on Mario's mailbox 3044 (`INDEXOF_COLLIDER_IDX`) shows the block's actor index on jump-contact; same for the block's 3044 showing `9`.
- `wflevels/smb_w1_1/smb_w1_1.lev` rebuilds clean.
- Pair of screenshots: pre-bump (gold `?` block visible) vs post-bump (flat-tan used block). Both via existing `~/tmp/smb-shots/` driver pattern.
