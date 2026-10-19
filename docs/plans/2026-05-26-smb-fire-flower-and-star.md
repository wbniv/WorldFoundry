# SMB Fire Flower + Star power-ups — World 1-1

> Plan authored before implementation (plan-workflow convention). Committed with the code.
> Status: **Done** (2026-05-26, ~half a day). All 7 checks pass headless
> ([`tests/verify_smb_fire_star.py`](../../tests/verify_smb_fire_star.py)); screenshots
> `tests/screenshots/smb_firestar_*.png`. The Starman bounce shipped via the real Jolt
> floor-contact normal (the planned collision-mailbox gate was sign/index-wrong — corrected
> below). `FACE_COLOR_TOP` *does* tint the multi-material player mesh (the caveat was moot).

## Context

The SMB W1-1 level (`wflevels/smb_w1_1/`) has a working Small↔Super power-up state
machine (`16503788`): a Super Mushroom is a `gold`-class collectible with `Gold Value = 0`
that slides like a coin, a proximity script raises `SMB_MUSHROOM_PICKUP`, and the Player's
Forth state machine consumes it → `SMB_MARIO_STATE` 0→1 + a render-scale grow. Damage
decrements the state. `SMB_MARIO_STATE` already reserves **`2 = Fire`** in its comment.

This plan makes the two remaining canonical W1-1 power-ups live, **reusing the `gold` class
a third and fourth time** (per explicit user direction — logged as taxonomy debt, see
[TODO updates](#todo-updates)):

- **Fire Flower** — a `gold`-class collectible that raises Mario to the **Fire** state
  (`SMB_MARIO_STATE = 2`): super-size + a fire visual, and the existing damage chain now
  steps Fire→Super→Small. **Fireball-throwing is deferred** (decided with the user): runtime
  projectile spawning from script needs the `spawn-template` Forth primitive that doesn't
  exist yet ([TODO §26](../../TODO.md)). Fire Mario here is the *state* + visual + extra hit
  buffer; it gates the future fireball work.
- **Star (Starman)** — a `gold`-class collectible that grants a **~10 s invincibility window**:
  enemies can't hurt Mario, and touching an enemy **defeats it** (no stomp needed), with a
  visual flicker.

Faithfulness note: this is the geometrically-compressed validation level (already ~49 tiles
vs the real ~212, two compressed pits, dedicated enemy/pit placements). It is *not* pixel-
faithful W1-1, so a **dedicated Fire block and a dedicated Star block** are added (mirroring
the one-shot `mushroom_block` generator) rather than the real game's single mushroom-or-flower
block and 1-1's lack of a Starman. The runtime-switchable mushroom-or-flower block is noted as
a follow-up. Everything is composition + Forth on proven primitives — **no new engine C++,
no new OAS fields.** Golden source is `wflevels/smb_w1_1/blender_create_smb.py`.

## New mailboxes (`wfsource/source/mailbox/mailbox.inc`, after line 33)

Add `MAILBOXENTRY` rows (named-constant convention; the verbose `INDEXOF_` prefix is the
scripting-side default we still follow — flagged for the eventual prefix removal):

| Constant | Slot | Purpose |
|----------|------|---------|
| `SMB_FIREFLOWER_PICKUP` | 1816 | Fire Flower's pickup script sets 1 on contact; Player consumes → Fire, then clears |
| `SMB_STAR_PICKUP` | 1817 | Star's pickup script sets 1 on contact; Player consumes → invincibility, then clears |
| `SMB_STAR_UNTIL` | 1818 | Level-time deadline of the Star invincibility window; **enemies read it** to die-on-touch, Player reads it for the flicker |
| `SMB_STAR_FLICKER_LATCH` | 1819 | 1 while flickering; lets the Player restore Mario's tint **once** when the window ends |

All `< GLOBAL_USER_MAX` (1900). `SMB_MARIO_STATE`'s comment already documents `2 = Fire` —
no change needed there.

## Fire Flower

### Collectible template — `_make_fireflower_template()` (clone of `_make_mushroom_template`, ~line 762)
Same `gold` / `Gold Value = 0` / Physics / `Mesh` collectible, **but stationary** (the real
flower sits on the block, it doesn't walk):
- White-and-red material (new `make_mat('fireflower', ...)`).
- `Running Deceleration = 0.9` (stop any landing drift) and the dispensing block pops it
  straight up with **`Object X Velocity = 0`**, so it rises and settles on the block top.
- Pickup script identical to `MUSHROOM_SCRIPT` but raises `SMB_FIREFLOWER_PICKUP`.

### Dispensing block — `fireflower_block` (clone of `mushroom_block`, ~line 787)
One-shot `generator`, `MUSHROOM_BLOCK_SCRIPT` idiom verbatim (bump-from-below → pulse →
latch USED/tan). `Object To Throw = 'fireflower_template'`, `Object X Velocity = 0`,
`Object Z Velocity = 6.0`. Place at **tile 10, X = 15.0** (clear: qblock_01 @12, entry pipe
@[16.5,19.5]).

### Player state machine (`blender_create_smb.py` ~line 925, after the mushroom block)
```forth
\ Fire Flower -> Fire. From Small OR Super, jump to Fire (2) + super-size; faithful
\ (a flower picked up small makes you big + fire directly). Already-Fire stays Fire.
INDEXOF_SMB_FIREFLOWER_PICKUP read-mailbox 0<> if
  INDEXOF_SMB_MARIO_STATE read-mailbox 2 < if
    2 INDEXOF_SMB_MARIO_STATE write-mailbox
    1.25 INDEXOF_X_SCALE write-mailbox 1.25 INDEXOF_Y_SCALE write-mailbox 1.9 INDEXOF_Z_SCALE write-mailbox
    0x{FIRE_TINT:06X} INDEXOF_FACE_COLOR_TOP write-mailbox
  then
  0 INDEXOF_SMB_FIREFLOWER_PICKUP write-mailbox
then
```

### Damage power-down must become **scale-aware** (fix existing branch, ~lines 930-935)
Today the Super→Small branch unconditionally resets scale to 1.0. With a Fire state, a
Fire→Super hit must **keep the big scale** and only clear the fire tint. Replace the fixed
reset with:
```forth
INDEXOF_SMB_MARIO_STATE read-mailbox 1 - dup INDEXOF_SMB_MARIO_STATE write-mailbox   ( newstate )
0 > if   \ still Super (or higher): keep big, clear fire tint
  1.25 INDEXOF_X_SCALE write-mailbox 1.25 INDEXOF_Y_SCALE write-mailbox 1.9 INDEXOF_Z_SCALE write-mailbox
else     \ dropped to Small
  1.0 INDEXOF_X_SCALE write-mailbox 1.0 INDEXOF_Y_SCALE write-mailbox 1.0 INDEXOF_Z_SCALE write-mailbox
then
0x{WHITE:06X} INDEXOF_FACE_COLOR_TOP write-mailbox   \ leaving Fire -> drop the fire tint
```

## Star

### Collectible template — `_make_star_template()` (clone of mushroom; **bounces**)
`gold` / `Gold Value = 0` / Physics, yellow material, `Running Deceleration = 0`, dispensed
with `Object X Velocity = 1.5`, `Object Z Velocity = 6.0`. It travels right and **bounces** —
the Starman's signature motion — driven by its own per-tick script (same script that does the
proximity-pickup signal), re-launching `ZSPEED` on each landing.

**Why not "real physics"?** The engine can't bounce a body via restitution: every
`MOBILITY_PHYSICS` actor is a Jolt **`CharacterVirtual`** (`actor.cc:772` → `JoltMakeCharacter`
destroys the rigid body), which zeroes vertical velocity on landing and has no restitution.
The Jolt backend never sets `mRestitution`; the `Vertical/Horizontal Elasticity` OAS fields
(`movebloc.inc:33`) are dead legacy (only the pre-Jolt `collision.cc` solver reads them, and
CharacterVirtual actors never reach it). True restitution is a real engine feature — logged as
a TODO, not done here (see [TODO updates](#todo-updates)).

The bounce is **ground-aware without that engine work** by triggering off the *real floor-contact
signal* the breakable-bricks work (`799bd82f`) wired into the per-actor collision mailboxes —
not a guessed Z-height band. **As-shipped** (the planned `COLLIDER_IDX != 0` + `NORMAL_Z > 0.5`
gate was wrong — verified against the engine during bring-up): landing on **static** ground
routes through `Actor::JoltStaticCollision`, which sets `COLLIDER_IDX = 0` (no actor) and
`COLLISION_NORMAL_Z < 0` (the normal points DOWN, the way the char pushes into the floor).
`_lastCollisionNormal` is **not** cleared per-frame (only `COLLIDER_IDX` is, `actor.cc:1106`),
so the script zeroes it to consume the contact and avoid re-firing mid-air on the stale value:
```forth
\ Re-launch on a real floor contact (NORMAL_Z<0 = landing); consume it so the
\ stale normal doesn't re-fire mid-air. Over a pit there's no contact -> falls in.
INDEXOF_COLLISION_NORMAL_Z read-mailbox -0.5 < if
  6.0 INDEXOF_ZSPEED write-mailbox
  0 INDEXOF_COLLISION_NORMAL_Z write-mailbox
then
( ... followed by the proximity test that raises SMB_STAR_PICKUP ... )
```
Constant `X` velocity + contact-triggered re-launch = the classic sawtooth. Because each
re-launch lifts the star clear, the contact ends and re-fires (`OnContactAdded`) on the next
landing — a clean self-sustaining oscillation. Only wall/pipe **X-reversal** remains as polish.

### Dispensing block — `star_block` (clone of `mushroom_block`)
One-shot generator, `Object To Throw = 'star_template'`. Place at **tile 38, X = 57.0** (past
pit1 @[51,54], before the flag @63 — a late "reward" slot). Placement is **no longer
load-bearing** now that the bounce is ground-aware, but this keeps it visually faithful.

### Player (after the Fire branch)
```forth
\ Star -> ~10 s invincibility. Orthogonal to size: do NOT touch state/scale.
\ Reuse the existing INVULN gate for damage-immunity (no edit to the hurt logic);
\ SMB_STAR_UNTIL drives enemy defeat-on-touch + the flicker.
INDEXOF_SMB_STAR_PICKUP read-mailbox 0<> if
  INDEXOF_TIME read-mailbox 10.0 + INDEXOF_SMB_STAR_UNTIL  write-mailbox
  INDEXOF_TIME read-mailbox 10.0 + INDEXOF_SMB_INVULN_UNTIL write-mailbox
  0 INDEXOF_SMB_STAR_PICKUP write-mailbox
then
\ Flicker the tint while the window is open; restore once when it closes.
INDEXOF_TIME read-mailbox INDEXOF_SMB_STAR_UNTIL read-mailbox < if
  INDEXOF_TIME read-mailbox 8.0 * 2 % if 0x{STAR_A:06X} else 0x{STAR_B:06X} then INDEXOF_FACE_COLOR_TOP write-mailbox
  1 INDEXOF_SMB_STAR_FLICKER_LATCH write-mailbox
else
  INDEXOF_SMB_STAR_FLICKER_LATCH read-mailbox 0<> if
    INDEXOF_SMB_MARIO_STATE read-mailbox 2 = if 0x{FIRE_TINT:06X} else 0x{WHITE:06X} then INDEXOF_FACE_COLOR_TOP write-mailbox
    0 INDEXOF_SMB_STAR_FLICKER_LATCH write-mailbox
  then
then
```
`%` casts to int in zForth (`/` does not — project gotcha); `8.0 * 2 %` ⇒ 0/1 toggle ≈ 8 Hz.

### Enemy defeat-on-touch (`ENEMY_SCRIPT`, ~line 1016, inside the `dx²<1` proximity branch)
Wrap the existing stomp/side-hit `dz` logic so the Star check takes precedence:
```forth
( inside: dx^2 < 1.0 if ... )
INDEXOF_TIME read-mailbox INDEXOF_SMB_STAR_UNTIL read-mailbox < if
  0 INDEXOF_ALIVE write-mailbox          \ Star active: defeated by touch, no bounce, no hurt
else
  ( existing dz: > 0.7 -> stomp+ALIVE=0+SMB_STOMP ; > -1.5 -> SMB_PLAYER_HURT )
then
```
Damage immunity itself needs no enemy change: the enemy still raises `SMB_PLAYER_HURT` on a
side-hit, but the Player's existing `TIME > SMB_INVULN_UNTIL` gate (we set it to `now+10`)
swallows it.

## Visual caveat
`FACE_COLOR_TOP` is proven on single-material blocks (qblock turns tan). The Player mesh is
multi-material (red/blue/skin). If the tint doesn't apply to it, the Fire/Star **mechanics
still verify** (state, invincibility, enemy death) — only the cosmetic tint is affected, and
the visual swap to a Visibility-mailbox blink or a per-material colour is a one-liner later.
The **authoritative visual proof** is the defeat-on-touch screenshot (Mario walks through an
enemy that vanishes), not the flicker.

## TODO updates
- **Append to TODO §69** (collectibles-shouldn't-masquerade-as-coins taxonomy): note that
  Fire Flower + Star *did* clone the `gold`-worth-0 hack (the 3rd and 4th instances), exactly
  the trigger §69 named — reinforcing, not creating a duplicate entry.
- **New TODO** (SCRIPTING ENGINES / SMB): Fire Mario fireball projectile deferred — blocked on
  the `spawn-template` Forth primitive ([§26](../../TODO.md)) or a pool of pre-placed fireball
  generators. Trigger: when `spawn-template` lands.
- **New TODO** (PHYSICS): no restitution/bounce for gameplay actors. Every `MOBILITY_PHYSICS`
  actor becomes a kinematic Jolt `CharacterVirtual` (`actor.cc:772`) that zeroes vertical
  velocity on landing; the Jolt backend never sets `mRestitution`, and the
  `Vertical/Horizontal Elasticity` OAS fields (`movebloc.inc:33`) are dead legacy (pre-Jolt
  `collision.cc` only). To get true physics bounce: add a dynamic-rigid-body mobility (or a
  per-actor dynamic-body opt-in) and wire the Elasticity fields into Jolt `mRestitution`,
  substepping the variable dt. Pairs with the standing "replace physics" follow-up
  (`project_followup_replace_physics`). Surfaced 2026-05-26 building the Starman bounce
  (shipped as a contact-mailbox script re-launch instead). Trigger: when a second bouncy actor
  appears, or the physics-replacement work starts.
- **New TODO** (SMB): faithful single **mushroom-or-flower power-up block** (throws a mushroom
  when Small, a flower when Super+) — needs a runtime-switchable `Object To Throw` or two
  co-located generators; current plan uses dedicated blocks. Plus Starman **wall/pipe
  X-reversal** (this plan ships the ground-aware vertical bounce; reversing horizontal
  direction off obstacles is the remaining polish).

## Build pipeline
1. `blender --background --python wflevels/smb_w1_1/blender_create_smb.py`
2. `task build-level -- smb_w1_1`
3. **`mailbox.inc` changed** → `touch wfsource/source/.../scripting_stub.cc` then `task build`
   (the stub `.o` mtime check ignores `mailbox.inc`; engine must recompile the constants — project gotcha).
4. `task run-smb`
5. `git checkout` any unrelated `.iff` that re-export jitter touches (TODO §142).

Append new template/block creations **after** the existing ones so earlier actor indices
don't shift (index-hardcoded test harnesses); re-probe via `X_POS` if a probe drifts.

## Verification (`tests/verify_smb_fire_star.py`, new — debug bridge)
Mirror `tests/verify_smb_brick_break.py` / `verify_smb_mushroom_spawn.py`: launch
`engine/wf_game -L wflevels/smb_w1_1-standalone.iff --debug-port 778x --debug-print-actors`,
discover indices from the actor log, inject mailboxes, step, screenshot to `tests/screenshots/`.

1. **Fire from Super:** `SMB_MARIO_STATE=1`, bump `fireflower_block` → fireflower spawns;
   teleport Player onto it → `SMB_MARIO_STATE=2`, scales 1.25/1.25/1.9. Screenshot.
2. **Fire from Small:** `SMB_MARIO_STATE=0`, pickup → state jumps straight to 2 + super size.
3. **Fire power-down keeps size:** state=2, inject `SMB_PLAYER_HURT` past invuln → state 2→1,
   **scale stays 1.25/1.9** (the bug this plan fixes); inject again → 1→0, scale 1.0. Screenshot.
4. **Star bounce:** bump `star_block` → star spawns; poll its `Z_POS` over several steps →
   assert a **sawtooth** (Z rises again after each landing), proving the contact-triggered
   re-launch fires. Confirm the re-launch coincides with `COLLISION_NORMAL_Z > 0.5`. Optional:
   spawn one over a pit and assert it falls through (ground-aware). Screenshot mid-bounce.
5. **Star invincibility:** pickup → `SMB_STAR_UNTIL ≈ TIME+10` and `SMB_INVULN_UNTIL` set.
   Place/inject an enemy adjacent → enemy `ALIVE=0`, **Player `GOLD` unchanged, no respawn**
   (HURT swallowed). Screenshot Mario beside the vanished enemy.
6. **Window expiry:** `set_mailbox SMB_STAR_UNTIL` to a past value (don't rely on `step`'s big
   dt — bridge gotcha) → enemy side-hit now triggers the normal hurt/power-down again.
7. **Regression:** re-run `verify_smb_mushroom*`, `verify_smb_brick_break.py`,
   `verify_coin_slide.py` — confirm prior indices still resolve (append-only proof).

## Critical files
- `wflevels/smb_w1_1/blender_create_smb.py` — golden source: 2 templates, 2 blocks, Player +
  enemy script edits (all level changes here)
- `wfsource/source/mailbox/mailbox.inc` — 4 new `MAILBOXENTRY` rows (1816-1819)
- `tests/verify_smb_fire_star.py` (new) — verification harness
- `TODO.md` — §69 append + 2 new entries
- Reference (read-only): `wfsource/source/game/generator.cc`, `gold.cc`, `actor.cc`

## Estimate
~half a day (Fire ≈ mushroom clone + the scale-aware power-down fix; Star ≈ collectible clone +
the enemy/Player invincibility wiring + bridge-harness bring-up). Fireballs explicitly out of scope.
