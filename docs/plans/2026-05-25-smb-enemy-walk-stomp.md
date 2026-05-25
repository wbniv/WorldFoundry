# SMB Goomba/Koopa — walk + stomp + player hurt/death/respawn

**Status:** Done + verified (2026-05-25). All three phases land. Two deviations from the plan:

1. **Detection is PROXIMITY, not collision mailboxes.** Verified empirically that player↔enemy
   contact (both `MOBILITY_PHYSICS` = CharacterVirtual) pushes them physically but does **not**
   fire the Jolt collision dispatch (neither is in `gBodies` — the same reason Gold uses
   proximity; the touching Koopa left `LIVES` unchanged). So the enemy script compares the
   broadcast player X/Z to its own position: `dx²<1` near, then `dz>0.7` ⇒ stomp (enemy
   `0→ALIVE`, `SMB_STOMP→1`), else side ⇒ `SMB_PLAYER_HURT→1`. `SMB_PLAYER_IDX` was dropped;
   `SMB_PLAYER_Z` added. This sidesteps the `NORMAL_Z`-sign question entirely.
2. **Built-in `Enemy` −10 damage is already inert under Jolt** (rides `SPECIAL_COLLISION`, the
   legacy path that skips Jolt actors) — no neutralization needed; the script signal is the only
   hurt path.

**Verified** (debug bridge + screenshots): Goomba walks left ≈4 m/s; HUD `LIVES` seeds 0→**3**
([boot](../../tests/screenshots/smb_enemy_walk_stomp.png)); Mario dropped onto a Goomba → it's
**removed** (stomp) and `SMB_STOMP` bounce; enemies reaching Mario decrement `LIVES` (3→2→1) and
respawn him in place with i-frames. `LIVES<1 → END_OF_LEVEL` (game over). **Build gotcha:** adding
`MAILBOXENTRY` rows to `mailbox.inc` does NOT trigger a recompile of the `scripting_stub.cc`
constant table — `task build` relinked stale and the new `INDEXOF_*` were missing (scripts
silently rejected with `error 7 not_a_word`); fixed by `touch`-ing `scripting_stub.cc` +
`mailbox.cc` before `task build`. Logged in the troubleshooting guide.

## Context

Goombas (×24) and Koopas (×24) in [`smb_w1_1`](../../wflevels/smb_w1_1/blender_create_smb.py) are
inert `Anchored` placeholders. Make them **walk**, let Mario **stomp** them (enemy dies), and
wire the reverse: side-contact **hurts** Mario → **death → respawn** (lose a life). Player
death/respawn/lives is currently **unbuilt** (a `game.cc` pragma "handle lives and restarting").

Reuses three proven patterns: coin-slide movement (MarbleHandler + `Running Deceleration=0`), the
per-actor collision mailboxes (`?`-block/flagpole-proven), and the marble-madness **script
respawn** ([`marble-madness-2/gen_level1.py`](../../wflevels/marble-madness-2/gen_level1.py):
write own `X/Y/Z_POS` + zero `*SPEED`). This is the highest-impact 🔧 in the
[SMB→primitives mapping](../investigations/2026-05-25-smb-features-to-wf-primitives.md).

## Mechanisms (from investigation)

- [`Enemy::update()`](../../wfsource/source/game/enemy.cc) (`enemy.cc:68`) deals **−10 health** on
  `SPECIAL_COLLISION`; default Mobility = Physics; no built-in walking.
- Collision: bidirectional dispatch ([`actor.cc:1796`](../../wfsource/source/game/actor.cc))
  populates **both** actors' `COLLIDER_IDX` (3044) + `COLLISION_NORMAL_*` (3045–47). **The
  `NORMAL_Z` sign for top-vs-side must be verified empirically** (the `?`-block did the same).
- Death from script: `0 → INDEXOF_ALIVE` (3004) → `SetPendingRemove` (`actor.cc:1419`).
- Respawn from script: write own `X/Y/Z_POS` + zero `*SPEED` (marble-madness).
- Lives: mailbox **72** (HUD reads it, `game.cc:553`).
- Player identity: `ACTOR_INDEX` (3005, own index) — broadcast to a global so an enemy can tell
  "the player hit me" from "a wall hit me".

## Phase 1 — Enemy walk

[`blender_create_smb.py`](../../wflevels/smb_w1_1/blender_create_smb.py) goomba/koopa:
`Mobility=Physics`, `Turn Rate=0` (→ MarbleHandler), `Running Deceleration=0`, `Max Ground
Speed` ≥ walk speed. Per-enemy script: store heading in a `LOCAL_USER` mailbox (init −1 = left);
each tick write `XSPEED = dir*speed`; on wall contact (`COLLIDER_IDX≠0` & large
`|COLLISION_NORMAL_X|`) flip `dir`. (W1-1 is mostly flat → walk left, reverse at walls,
ledge-fall acceptable for v1.)

## Phase 2 — Player-index broadcast + stomp

- New named global `SMB_PLAYER_IDX` (add `MAILBOXENTRY` to
  [`mailbox.inc`](../../wfsource/source/mailbox/mailbox.inc)). Player script each tick:
  `INDEXOF_ACTOR_INDEX read-mailbox INDEXOF_SMB_PLAYER_IDX write-mailbox`.
- Enemy **stomp** branch: `COLLIDER_IDX == SMB_PLAYER_IDX` AND `NORMAL_Z` = from-above (verified
  sign) → `0 INDEXOF_ALIVE write-mailbox` (enemy dies). Optional polish: a `SMB_STOMP` global →
  player adds a small +Z bounce.

## Phase 3 — Player hurt + death + respawn + lives  *(script-based — chosen)*

- New named globals: `SMB_PLAYER_HURT`, `SMB_INVULN_UNTIL` (+ existing `LIVES`=72).
- Enemy **hurt** branch: `COLLIDER_IDX == SMB_PLAYER_IDX` AND side (not from-above) →
  `1 INDEXOF_SMB_PLAYER_HURT write-mailbox`.
- **Drive hurt via the script signal, not the built-in −10 damage** (which routes to `die()` →
  `SetPendingRemove(player)` with no respawn). Verify whether `SPECIAL_COLLISION` fires under
  Jolt; if it does and would remove the player, neutralize it (player HP high/`INDESTRUCTIBLE`,
  or zero the enemy `Health Modifier`).
- Player respawn state machine (script, marble-madness style): on `SMB_PLAYER_HURT` while not
  invulnerable → decrement `LIVES`; reposition to spawn (`MARIO_SPAWN_* → X/Y/Z_POS`, zero
  `*SPEED`); set `SMB_INVULN_UNTIL = TIME + ~2 s`; clear `SMB_PLAYER_HURT`. Ignore hurt while
  `TIME < SMB_INVULN_UNTIL`. Seed `LIVES` (e.g. 3) at level start. `LIVES <= 0` → game over (v1:
  write `END_OF_LEVEL`; a real game-over screen is the same missing win/end-screen infra noted in
  the [SMB mapping](../investigations/2026-05-25-smb-features-to-wf-primitives.md) 🚧 list).
- **Respawn mechanism: script-based** (no engine change; mirrors working marble-madness). The
  engine `game.cc` lives/level-restart pragma route is the heavier reusable alternative —
  deferred.

## Verification (during implementation, via debug bridge + screenshots)

1. Empirically read a Goomba's `COLLISION_NORMAL_Z` for Mario-lands-on-top vs side-hit; gate the
   stomp on the verified sign.
2. Confirm `SPECIAL_COLLISION`/built-in damage behavior under Jolt; neutralize if it removes the player.
3. Bridge scenarios + screenshots: (a) Goomba walks (X changes, reverses at a wall); (b) Mario
   stomps → Goomba removed (+ bounce); (c) Mario side-hits → `LIVES`−−, respawn at start, brief
   invuln; (d) `LIVES`→0 → game over.
4. Regression: `python3 tests/verify_smb_scroll.py` 4/4.

Commit per phase. Log gotchas to
[`docs/level-design-troubleshooting.md`](../level-design-troubleshooting.md) as discovered.

## Files

| File | Change |
|------|--------|
| [`wflevels/smb_w1_1/blender_create_smb.py`](../../wflevels/smb_w1_1/blender_create_smb.py) | enemy Mobility + walk/stomp/hurt scripts; player index-broadcast + respawn state machine; lives seed |
| [`wfsource/source/mailbox/mailbox.inc`](../../wfsource/source/mailbox/mailbox.inc) | new named globals `SMB_PLAYER_IDX` / `SMB_PLAYER_HURT` / `SMB_INVULN_UNTIL` (+ `SMB_STOMP` if bounce) |
| level binaries (`.lev`/`.lvl`/`.iff`/`-standalone.iff`) | rebuilt |
