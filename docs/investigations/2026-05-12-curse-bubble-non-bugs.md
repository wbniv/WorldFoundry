# Curse-bubble didn't render / didn't track — false trails and the actual root causes

**Date:** 2026-05-12
**Status:** Resolved (commit `2229963`)
**Related:** [plan 2026-05-11-qbert-player-death-and-curse-bubble.md](../qbert/plans/2026-05-11-qbert-player-death-and-curse-bubble.md), [docs/level-building.md](../level-building.md)

## TL;DR

While wiring the Q✱bert curse-bubble overlay onto the player death animation, two separate "the bubble doesn't show up" symptoms appeared. I burned a lot of conversation cycles speculating about engine internals (OAD class defaults, Forth int/float coercion) before tracing each through the source. Both real causes are mundane and have nothing to do with the speculative explanations I'd been writing into docs:

1. **Bubble actor invisible** — its authored center was outside every room's bbox, so levcomp-rs never added it to any room's render list. Fixed by expanding the single room to a global bbox.
2. **Bubble Z not tracking the player on death** — the player script's death state machine never executed during my A/B test, because the player was in GAME OVER state (mb 420 = 1) and the player script's early-return-on-game-over branch ran first. My "zForth doesn't auto-promote int + float" theory was invented — `2` and `2.0` compile to byte-identical encodings in zForth.

This document is the post-mortem because both wrong theories made it into committed docs. The corrections were re-committed, but the failure mode is worth a separate writeup: **speculate-then-verify produced two confidently-wrong docs in one afternoon. Verify first.**

## Symptom 1 — bubble actor doesn't render

### What I observed

A `wf_Mesh Name = 'curse_bubble.iff'`, `wf_Model Type = 'Mesh'`, `wf_Visibility Mailbox = 1`, `Mass = 0`, `Mobility = 'Anchored'` actor with `wf_schema_path = ENEMY_OAD` did **not** appear in the rendered scene, even when I bridge-wrote its X/Y/Z position mailboxes to a clearly-visible spot (apex+4) and scaled it to 4×. The engine reported `Level::Level: object count = 59` (the bubble was in the object table) but `grep -c RenderActor3DAnimates wf_game.log` was 41 — one short of the count expected for the level's animated meshes.

### What I wrote in the docs (twice — both wrong)

**First attempt (commit 8803ade):** "OAD schema choice silently controls rendering. ENEMY_OAD has different defaults that put the actor in a not-yet-active state."

The user corrected me: *Blender properties expose all OAS fields; the override-vs-default theory is wrong.*

**Second attempt (commit 07a9105):** "OAS class determines the C++ Actor subclass (StatPlat vs Enemy). Enemy's non-statplat construction path runs `_InitInput`/`_InitScript` and asserts `hp > 0` — possibly fails silently when hp is default 0." Filed a TODO to actually trace it.

This was less wrong (the C++ subclass split is real) but still missed the cause. The Enemy/StatPlat divergence is in *Actor construction*, not in *whether the render actor gets created*.

### Actual root cause

Tracing through the build + engine:

1. [`wftools/levcomp-rs/src/rooms.rs:168-178`](../../wftools/levcomp-rs/src/rooms.rs) at level-export time:
   ```rust
   for (i, obj) in objects.iter().enumerate() {
       if room_of_obj[i] != -2 { continue; }
       let center = obj_center(obj);
       for (r, room) in rooms.iter_mut().enumerate() {
           if point_in_box(center, room.bbox) {
               room.entries.push((i + 1) as i16);
               room_of_obj[i] = r as i16;
               break;
           }
       }
   }
   ```
   Non-room actors get added to the first room whose bbox contains their world-space center. Actors outside every room's bbox are silently left unassigned.

2. [`wfsource/source/game/level.cc:1681`](../../wfsource/source/game/level.cc) (`ObjectIsInWhichRoom`) at level load: walks each room's on-disk entry list looking for the actor's index. Returns -1 if not found. The actor still constructs (it's in `objArray`), but isn't tied to any room.

3. [`wfsource/source/room/actrooms.cc:83`](../../wfsource/source/room/actrooms.cc) (`ActiveRooms::LoadAndBindAssets`) iterates `ROOM_OBJECT_LIST_RENDER` of each active room and calls `BindAssets` on each entry. `BindAssets` is where `_renderActor = new RenderActor3DAnimates(...)` happens for `MODEL_TYPE_MESH` actors ([`actor.cc:407-431`](../../wfsource/source/game/actor.cc)). Actors not in any room's render list never get `BindAssets` called → no render actor → invisible no matter what `Model Type` / `Visibility Mailbox` / scale / position-via-bridge say.

The bubble was authored at `(-20, -20, 5)` and later `(0, 0, -100)`. The qbert_practice room's authored bbox was `(-15, -100, -38)` to `(75, 15, 52)`. Both bubble positions are outside that bbox in at least one axis, so levcomp-rs skipped them.

When I "fixed it by switching to STATPLAT_OAD", I had simultaneously moved the bubble's authored center to `(-6, 14.5, 17)` — *inside* the room bbox. The position change is what made it render. The schema swap was coincidental.

**Verification:** restored `ENEMY_OAD` with authored center inside the room bbox → bubble renders. `grep -c RenderActor3DAnimates` = 42. Schema irrelevant.

### Fix

For single-room levels, set the room bbox big enough that any reasonable authored position (including off-camera "parking" locations) lands inside. `qbert_practice` now uses `ROOM_BBOX_REL = (-200, -200, -207, 200, 200, 193)` around `ROOM_CENTRE = (0, 0, 7)` — a ~400-unit cube. Documented in [docs/level-building.md](../level-building.md) under the "Actors authored outside every room's bbox" warning.

## Symptom 2 — bubble doesn't track the player on death

### What I observed

With the room fix in place, during a bridge-triggered death (`set_mailbox(419, 1, idx=9)`), bubble X and Y mailboxes ended up matching the player's, but bubble Z stayed at its parked `-100`. The Forth that should have run is:

```forth
INDEXOF_X_POS read-mailbox 3009 30 write-actor-mailbox
INDEXOF_Y_POS read-mailbox 3010 30 write-actor-mailbox
INDEXOF_Z_POS read-mailbox 2 + 3011 30 write-actor-mailbox
```

X and Y writes succeeded, Z didn't.

### What I wrote in the patch comment (wrong — both file edit and PreEdit followup)

> NOTE: literals in the +2 must be FLOAT (`2.0`) — zForth `+` does not coerce int 2 against float Z silently, the write reaches the bubble at a garbage value leaving authored Z=-100 in place (verified empirically 2026-05-12).

This is **invented**. Source inspection in [`engine/vendor/zforth-41db72d1/src/linux/zfconf.h`](../../engine/vendor/zforth-41db72d1/src/linux/zfconf.h) and [`engine/stubs/scripting_zforth.cc:166`](../../engine/stubs/scripting_zforth.cc) shows zForth's `zf_cell` is `typedef float`, and the WF host parser parses literals via `strtof()`:

```cpp
zf_cell zf_host_parse_num(zf_ctx* ctx, const char* buf) {
    // ...
    float v = strtof(buf, &end);
    if (end && *end == '\0') return (zf_cell)v;
    // ...
}
```

`strtof("2")` and `strtof("2.0")` both return float 2.0f. The dictionary encoding ([`zforth.c:254`](../../engine/vendor/zforth-41db72d1/src/zforth/zforth.c) `dict_put_cell_typed`) detects exact-integer values and packs them in a 1-byte slot regardless of how they were written — `2` and `2.0` produce byte-identical compiled output. `PRIM_ADD` does `zf_push(d1 + d2)` on two zf_cells (both floats). There is no int-vs-float type at all in zForth — every stack value is a `float`.

### Actual root cause

The A/B test was confounded. When I read the player mailboxes during the supposed "fail" case, the dump showed:

```
player: {3009: 0.0, 3010: 8.485282, 3011: 15.0, 3042: 1.0, 418: 1.0, 419: 1.0, 420: 1.0}
```

`420: 1.0` is the GAME OVER flag. The player script reads it early and takes a `420 read-mailbox 1 = if ... exit` branch (game-over restart-detect) before ever reaching the FALL_PHASE block. So the death state-machine writes — including the bubble Z update — never ran in that test. X and Y still showed "matched" because the bubble was authored at `(0.0, 0.0, -100)` and the bridge-write to player Z=15 didn't propagate to bubble, but X and Y *coincidentally* matched the player (0.0 = bubble X = player X; 8.485 ≈ player Y but bubble's authored Y was 0.0 too — hmm, this would only be true if the bubble Y had been written earlier, e.g. from the previous test's FALL_PHASE block before the player entered GAME OVER). Possibly the X/Y reads were stale snapshot values from the bridge's `mailbox_values` dict before the GAME OVER flip.

I then "fixed" it by changing `2 +` to `2.0 +`, rebuilt (which also re-init'd the engine state, exiting GAME OVER), and tested again. The death animation worked. I attributed the fix to the literal-type change because that was the visible diff in the source. Wrong attribution.

**Verification of the real cause:** I reverted to `2 +`, rebuilt, *and made sure to inject_input to exit GAME OVER before triggering the fall*. Result:

```
test "2 +":
  bubble: {3011: 8.5, 3010: 8.485275, 3009: 0.0}
  player: {419: 14.0, 3011: 5.5, 3010: 8.485275, 3009: 0.0}
```

bubble Z = 8.5, player Z = 5.5, diff = 3.0 (the +2 plus one tick of player falling between bridge reads). **`2 +` works fine.** No Forth bug.

## What I learned (the actual deliverable)

These were both *speculate-then-verify* failures of the kind already flagged in memory (`feedback_verify_dont_hedge`). Recognising the pattern:

1. **I had a symptom**: an actor isn't where I expect.
2. **I had a guess** about the mechanism (OAS class, then int/float coercion).
3. **I wrote it into a doc / a comment** before tracing the code.
4. **The guess was confidently stated**, not hedged. Both made it past my own review and into commits.

The right loop is: symptom → grep for the source-of-truth function → read it → *then* explain. For (1), the right grep was for `RenderActor3DAnimates` → `BindAssets` → `Room::AddObject` → "who decides what's in the room?" → `rooms.rs`. For (2), the right step was to dump the relevant mailboxes (which I had already done) and *read them carefully* — `mb 420 = 1.0` would have flagged the GAME OVER state immediately.

Saving as feedback memory: when an actor or state behaves unexpectedly and I'm about to commit a "why" into a doc, check first that the diagnostic data I already have doesn't immediately falsify the theory. In symptom 2, the GAME OVER bit was visible in the same readout I was looking at. I never looked at it because I was already chasing the int/float story.

## Action items

- [x] Commit (`2229963`) reverts the bogus "OAS schema controls rendering" docs, replaces with the room-bbox mechanism traced through source.
- [x] Revert `2.0 +` → `2 +` (cosmetic since they compile identically; cleaner code).
- [ ] Open levcomp-rs ticket: print a warning at level-export time for any non-templated actor whose center is outside every room's bbox. ([TODO.md](../../TODO.md) entry filed.)
- [ ] Memory: `feedback_check_existing_diagnostics_before_theorising` — when about to commit a "why" claim to docs, look at the diagnostic data already in hand and check that it doesn't immediately falsify the theory.
