# SMB power-up block (mushroom-or-flower) + Starman wall-reversal

> Plan authored before implementation (plan-workflow convention). Committed with the code.
> Status: **Done** (2026-05-26, ~2.5 h). No engine rebuild (no `mailbox.inc` change).
> Verified headless: `tests/verify_smb_powerup_block.py` (3/3, state-aware dispense),
> the reversal check in `tests/verify_smb_fire_star.py` (9/9), and the
> `verify_smb_mushroom_spawn.py` / `verify_smb_brick_break.py` regressions.
> NOTE: the physics-resume checks (bounce, reversal, enemy-defeat) need a settled
> machine — running all harnesses back-to-back starves the headless engine and the
> star under-travels. Run them individually.

## Context

Two SMB World 1-1 polish follow-ups logged when Fire Flower + Star shipped
([plan](2026-05-26-smb-fire-flower-and-star.md), TODO "SMB power-up polish"):

1. **Faithful mushroom-or-flower power-up block.** Real W1-1 power-up blocks give a
   **mushroom when Mario is Small** and a **fire flower when he's Super+**. We currently
   have two single-purpose blocks: `mushroom_block`@9 always throws a mushroom,
   `fireflower_block`@15 always throws a flower. We want both to be **state-aware** so the
   item matches Mario's tier — and the natural demo path still works (grab the mushroom at
   block 9 → become Super → grab the flower at block 15).
2. **Starman wall/pipe X-reversal.** The bouncing star ships a ground-aware *vertical* bounce
   but slides through walls; faithfully it should **reverse horizontal direction** off a
   pipe/flagpole/wall.

Both are composition + Forth on proven primitives. **No new engine C++, no new OAS fields, and
no `mailbox.inc` change** (so no engine rebuild — level rebuild only).

## Key constraint (from the engine)

A `generator`'s `Object To Throw` is resolved once from the OAD (`generator.cc:84`), **not
switchable at runtime** — so one block can't throw two different templates, and co-locating two
collidable generator-blocks is messy. **Solution:** one self-determining collectible. Both
blocks throw a single `powerup_template` whose own script reads `SMB_MARIO_STATE` on its first
tick and *becomes* a mushroom (Small) or a flower (Super+) — color + motion + which pickup
signal it raises. The mushroom and flower are already identical placeholder boxes (`MUSH_*`
dims), so one template covers both.

## Goal 1 — state-aware power-up block

### One template replaces two — `powerup_template` (in `wflevels/smb_w1_1/blender_create_smb.py`)
Replace `mushroom_template` + `fireflower_template` with a single `powerup_template` built via
the existing `_make_powerup_template(...)`. **No latch / no new mailbox needed:** because the
blocks are one-shot, Mario's tier can't change between bump and catch, so the template reads
`SMB_MARIO_STATE` **live** every tick — it *becomes* the right item and raises the matching
pickup signal. (This is the faithful "a power-up gives you the next tier" behaviour, and the
mushroom/flower are already identical placeholder boxes, so identity = colour + motion only.)

`POWERUP_SCRIPT` (per tick):
```forth
\ wf
\ Identity from Mario's current tier. Small (0): stay the red mushroom that slides.
\ Super+ (>0): repaint orange and force stationary (the flower sits on its block).
INDEXOF_SMB_MARIO_STATE read-mailbox 0 > if
  0 INDEXOF_XSPEED write-mailbox
  0x{FLOWER_TINT} INDEXOF_FACE_COLOR_TOP write-mailbox
then
\ Proximity pickup -> raise the matching signal for Mario's tier (player logic unchanged).
INDEXOF_SMB_PLAYER_X read-mailbox INDEXOF_X_POS read-mailbox - dup *
INDEXOF_SMB_PLAYER_Z read-mailbox INDEXOF_Z_POS read-mailbox - dup *
+ 2.25 < if
  INDEXOF_SMB_MARIO_STATE read-mailbox 0 > if
    1 INDEXOF_SMB_FIREFLOWER_PICKUP write-mailbox
  else
    1 INDEXOF_SMB_MUSHROOM_PICKUP write-mailbox
  then
then
```
- **Colour:** the collectible box is **single-material** (every face `material_index=0`), and
  `FACE_COLOR_TOP` (3037) overrides `material[0]` — so it recolours the **whole** box, not just
  the top. Base material = mushroom red; the flower branch repaints it orange (`FLOWER_TINT`).
  No `_LIT`/`_SHADOW` needed (no `material[1]/[2]` on this mesh).
- **No `mailbox.inc` change** → **no engine rebuild** (level rebuild only).

### Both blocks throw it, state-aware
`mushroom_block`@9 and `fireflower_block`@15 keep their names/positions but set
`Object To Throw = 'powerup_template'`. Throw velocity matches the *expected* item
(block 9: `Object X Velocity = 1.5` so the mushroom slides; block 15: `0` so the flower sits) —
and the template force-zeros `XSPEED` for a flower regardless, so a mis-tiered bump still
behaves. Both stay one-shot (`MUSHROOM_BLOCK_SCRIPT` unchanged). Player pickup handlers are
**unchanged** (mushroom→Super-if-small, flower→Fire). Remove `mushroom_template` +
`fireflower_template` (and their generated `.iff`s).

## Goal 2 — Starman wall/pipe X-reversal

Extend `STAR_SCRIPT` (in the same file) with a horizontal-contact reversal, mirroring the
vertical bounce. `COLLISION_NORMAL_X` (3045) is populated and consumed exactly like
`COLLISION_NORMAL_Z` (`actor.cc:1290/1627`); a side contact gives `|NORMAL_X| ≈ 1`, `NORMAL_Z ≈ 0`:
```forth
\ Hit a vertical wall/pipe/flagpole -> reverse horizontal direction; consume the normal.
INDEXOF_COLLISION_NORMAL_X read-mailbox dup * 0.25 > if    \ |NX| > 0.5
  0 INDEXOF_XSPEED read-mailbox - INDEXOF_XSPEED write-mailbox   \ negate XSPEED
  0 INDEXOF_COLLISION_NORMAL_X write-mailbox
then
```
The star spawns at X=57 and bounces right toward the **flagpole pole @63** (`blender_create_smb.py`
~1311); reversing there sends it left until it reaches **pit1 [51,54]** and falls in (the
vertical bounce is already pit-aware). No other obstacles in [54,66].

## Tests to update / add
- **`tests/verify_smb_mushroom_spawn.py`** — it counts `mushroom_template.iff` spawns (line ~70)
  and finds `mushroom_block` (line ~93). The block name is unchanged, but it now throws
  `powerup_template`; update the spawn-count regex to `powerup_template`. (Block discovery is
  unaffected.) Confirm "exactly one spawn per pulse" still holds.
- **`tests/verify_smb_fire_star.py`** — discovers by mesh name (`star_block`, enemies, player)
  and injects `SMB_*_PICKUP` directly, so it is unaffected by the template merge. Add a
  **wall-reversal check**: spawn the star, `resume`, sample `XSPEED` sign and confirm it flips
  after the star reaches the flagpole (or inject a `COLLISION_NORMAL_X` is wiped per-frame, so
  use the real contact — observe XSPEED sign change over a real run). Screenshot.
- **New `tests/verify_smb_powerup_block.py`** (or extend mushroom_spawn): bump the block with
  `SMB_MARIO_STATE=0` → a mushroom spawns (template `PU_TYPE`=0, raises `SMB_MUSHROOM_PICKUP`);
  bump with `SMB_MARIO_STATE=1` → a flower spawns (`PU_TYPE`=1, stationary, raises
  `SMB_FIREFLOWER_PICKUP`). Verify the player ends Super vs Fire respectively.

## Build & verify
1. `blender --background --python wflevels/smb_w1_1/blender_create_smb.py`
2. `task build-level -- smb_w1_1`  (no `mailbox.inc` change → **no engine rebuild**)
3. `task run-smb` / the bridge harnesses above; screenshots to `tests/screenshots/`.
4. `git rm` the dead `mushroom_template.iff` / `fireflower_template.iff`; `git checkout` any
   unrelated `.iff` re-export jitter (TODO §142).

## Critical files
- `wflevels/smb_w1_1/blender_create_smb.py` — `powerup_template` + script, two blocks repointed,
  `STAR_SCRIPT` reversal, remove the two old templates (all level changes here)
- `tests/verify_smb_mushroom_spawn.py` — spawn-count regex → `powerup_template`
- `tests/verify_smb_fire_star.py` — add wall-reversal check
- `tests/verify_smb_powerup_block.py` (new) — state-aware dispense check
- Reference (read-only): `wfsource/source/game/generator.cc`, `actor.cc`

## Estimate
~2–3 hours (one template + script, two one-line block repoints, the reversal snippet, and the
test updates). No engine rebuild. Smallest of the three logged follow-ups.
