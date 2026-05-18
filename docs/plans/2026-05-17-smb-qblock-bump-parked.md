# SMB `?`-block bump mechanic — **PARKED**

**Status:** Parked 2026-05-17.

**Trigger to unpark:** After SMB W1-1 ships as a screenshot/video (or whichever level next reaches shipped state). The first shipped level is the gate — once it's out the door, come back and implement bump-from-below with the architecture this exploration recommends.

## Context

Proposed mechanic: jump up under a `?` block → coin pops out the top, arcs briefly, disappears → block flips to a flat-tan "used" appearance. With the [MarbleHandler jump fix](../../wfsource/source/movement/movement.cc) just landed (commit 9a41e91), Mario can now physically reach the blocks (~8.2 m apex clears the block tops at z = 7.5 m).

User pushed back on the first-cut "per-block Forth poll" approach with: *"what if a level has 100 of these blocks? or 1000? or 10,000?"* — which is correct. Forth-polling-per-block is `O(N)` per tick regardless of Mario's location. 10,000 blocks × 60 Hz = 600,000 script invocations/sec just for bump detection, with no spatial culling. Doesn't scale.

User opted to defer the entire bump mechanic to a follow-up, after the level ships with everything else (walk, jump, [scrolling camera](2026-05-17-smb-scrolling-camera.md), walking enemies).

## Architectural decision to make at unpark time

Two scalable options exist; both require engine code. Pick one when unparking:

**Option A — Generic `OnBumpFromBelowMailbox` actor field.** Add one field to [common.inc](../../wfsource/source/oas/common.inc) / [common.pp](../../wfsource/source/oas/common.pp) / [common.ht](../../wfsource/source/oas/common.ht). When set on any actor, `Actor::Collision()` writes `1` to that mailbox when struck from below (`normal.Z() > 0`) by a player-class actor. ~30 LOC of engine change + 1 schema field. Each `?`-block authors the field; gameplay reaction stays in Forth. Reusable for any future "hit me" mechanic (enemy stomps, switches, breakable bricks). The "no new OAS fields pre-merge" rule treats this kind of add as the deferred-until-after-level-ships bucket — which is exactly the trigger for unparking, so the rule lines up.

**Option B — Dedicated `QBlock` C++ Actor subclass.** New `qblock.oad` schema + new C++ class + factory wiring. Cleaner separation but more boilerplate; doesn't generalize. Likely the wrong call unless `?`-blocks need significant unique state the common Actor doesn't have.

Recommendation when we come back: **Option A**.

Options ruled out:
- **Per-block Forth poll** — `O(N_blocks)` per tick, doesn't scale (user's pushback).
- **Per-block `actboxor` trigger** — exploration suggests [actboxor.cc](../../wfsource/source/game/actboxor.cc) line 78 iterates "all actors in room per update", so `O(N_actboxors × N_actors)` per frame. Worse than poll.
- **Player-side scan** — needs a "list actors within radius" Forth word that doesn't exist; would have to be added; even then it's `O(actors_near_player)` not `O(1)`.

## What this exploration found (so we don't re-explore)

- **`Actor::Collision(other, normal)`** at [actor.cc](../../wfsource/source/game/actor.cc) lines 1676–1687 already fires per-contact via Jolt's collision system, with a contact `normal`. `normal.Z() > 0` ⇒ "hit from below". Broad-phase BVH-culled, so only nearby pairs reach the callback — natural `O(actual contacts)`.
- **No `actboxor` face-discrimination** — `actboxor` uses bbox overlap only, no normal info.
- **No runtime mesh/texture swap** in the engine. State swap is best done by **two pre-spawned actors at the same position** with their `Visibility Mailbox` toggled — `qblock_question.iff` visible at start, `qblock_used.iff` hidden until bumped.
- **Per-face material colour override** exists (mailboxes 3037/3038/3039 — [actor.cc](../../wfsource/source/game/actor.cc) lines 1521–1541) but only changes solid colours; can't hide the `?` symbol since it's mesh geometry. Use the two-actor toggle instead.
- **Coin arc** — use an Anchored actor whose `INDEXOF_X_POS/Y_POS/Z_POS` (mailboxes 3009/3010/3011) are written each tick by a per-coin Forth script. qbert's bubble at [blender_create_qbert.py](../../wflevels/qbert_practice/blender_create_qbert.py) lines 687–689 shows the pattern: `INDEXOF_Z_POS read-mailbox 2 + 3011 33 write-actor-mailbox`.
- **Score popup** — qbert already has `popup_25/50/100/300/500` pre-spawned actors toggled via Visibility Mailbox. Add a `popup_200` following the same pattern when unparking.
- **Coin sound** — miniaudio plays via the existing audio path; sound has to be verified on a different machine (HDMI-only audio on dev). Wire it headlessly and let the user check.
- **Mailbox naming** — every new mailbox added when unparking gets a `MAILBOXENTRY` row in [mailbox.inc](../../wfsource/source/mailbox/mailbox.inc) and is referenced from Forth as `INDEXOF_<NAME>`. No bare integer literals in scripts.

## What to do *now* instead

Ship the rest of W1-1 first. Separate plans, not this one's responsibility:
- **Scrolling camera** — see [2026-05-17-smb-scrolling-camera.md](2026-05-17-smb-scrolling-camera.md) (active) and [2026-05-17-smb-scroll-engine-route.md](2026-05-17-smb-scroll-engine-route.md) (parked engine-side alternative).
- **Walking goomba + koopa** — needs basic enemy AI; also a candidate for a generic "Path" mobility revival rather than per-enemy script.
- **Some level geometry beyond the flat ground** (pipes, brick rows, hills) — pure authoring.
- **Mario death on touching an enemy from the side** — another hit-event mechanic; would benefit from the same `OnBumpFromBelowMailbox` (or a sibling `OnTouchByPlayerMailbox`) infrastructure as the `?`-block bump, so designing all hit-events together when unparking is the right move.

## When unparking, create

A fresh `docs/plans/<date>-smb-qblock-bump.md` with:
- Schema field name + which `.inc` / `.pp` / `.ht` lines to edit
- Engine change site in `Actor::Collision()` + [actor.cc](../../wfsource/source/game/actor.cc) line numbers (re-verify since the file evolves)
- Per-block mailbox naming (`SMB_QBLOCK_0_BUMPED` etc.) added to [mailbox.inc](../../wfsource/source/mailbox/mailbox.inc)
- Coin + popup_200 + used-block mesh authoring in [blender_create_smb.py](../../wflevels/smb_w1_1/blender_create_smb.py)
- Screenshot verification: Mario airborne mid-bump → coin visible above block → block now flat-tan
