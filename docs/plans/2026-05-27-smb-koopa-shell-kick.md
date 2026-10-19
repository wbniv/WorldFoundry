# SMB Koopa shell-kick

> Plan authored before implementation (plan-workflow convention). Commit with the code.
> **Status:** **Done** (2026-05-27, ~1.5 h). Verified headless
> ([`tests/verify_smb_koopa_shell.py`](../../tests/verify_smb_koopa_shell.py), 6 checks, 3/3 runs) +
> recording **[`tests/recordings/smb_koopa_shell.mp4`](../../tests/recordings/smb_koopa_shell.mp4)**
> (512×384, ~7 s: stomp → shell → kick → slide → the shell defeats the Goomba). Worked first try —
> reusing the now-mature patterns (stomp geometry, proximity-defeat broadcast + freshness gate, the
> Starman wall-reversal) and, crucially, the test idioms from the fireball-defeat saga (despawn
> probe, onto-the-projectile placement) meant **no debugging** this time. No Generator spawn, so
> none of the velocity-expanded-spawn-box trouble either. Fireball-defeat regression still green.
> **Estimate:** ~half a day to a day (average-programmer scale). Compose + Forth on patterns
> already built (stomp, proximity-defeat broadcast, Star wall-reversal). Engine cost: four new
> `mailbox.inc` globals (rebuild to regenerate `INDEXOF_` — no C++ logic).

## Goal

Faithful Koopa Troopa: stomping a Koopa doesn't kill it — it retreats into a **shell** that sits
still; touching the resting shell **kicks** it into a fast slide; the **sliding shell** defeats
other enemies on contact, reverses off walls, and hurts Mario on a side hit; re-stomping a sliding
shell stops it back to a resting shell.

Today the Koopa shares the Goomba's `ENEMY_SCRIPT` (walk → stomp = die). This gives it its own
3-state machine instead.

## State machine (`SMB_KOOPA_STATE`: 0 = walk, 1 = shell-at-rest, 2 = shell-sliding)

| From | Trigger | To | Effect |
|---|---|---|---|
| 0 walk | stomp (player above, `dz > 0.7`) | 1 rest | Mario bounces (`SMB_STOMP=1`); Koopa stops, shrinks to a shell |
| 0 walk | side touch (level) | 0 | hurts Mario (`SMB_PLAYER_HURT`) — a walking Koopa is dangerous |
| 1 rest | side touch (level) | 2 slide | kicked **away** from Mario: `XSPEED = −sign(dx)·SHELL_SPEED` |
| 2 slide | stomp (player above) | 1 rest | Mario bounces; shell stops |
| 2 slide | side touch (level) | 2 | hurts Mario (a moving shell is dangerous) |
| any | fireball / Star | — | dies (`ALIVE=0`) — unchanged from the shared enemy logic |

- **Stomp vs kick is separated by contact geometry** (already how the Goomba distinguishes stomp
  from side-hit): `dz > 0.7` = top = stomp; roughly level = side = kick/hurt. So landing on a Koopa
  retracts it (top), and walking into the resting shell (side) kicks it — no instant-kick on the
  stomp bounce.
- **Movement by state:** 0 = the existing dormant-until-onscreen leftward walk; 1 = `XSPEED 0`
  (parked shell); 2 = carry velocity (frictionless, `Running Deceleration 0` already set) +
  **reverse off walls** by negating `XSPEED` on a side contact and consuming `COLLISION_NORMAL_X`
  (the exact Starman idiom — see [floor/wall bounce](../level-design-troubleshooting.md#script-driven-bounce-off-the-floor--read-the-contact-normal-and-consume-it)).

## The sliding shell defeats other enemies (reuse the fireball-defeat idiom)

A sliding shell (state 2) broadcasts its live position + freshness each tick to new globals
`SMB_SHELL_LIVE_X/Z/UNTIL`, exactly like the fireball
([Phase 2 plan](2026-05-27-smb-fireball-defeats-enemies.md)). The **Goomba's** `ENEMY_SCRIPT`
gains a second proximity-defeat branch (alongside the fireball one) that kills it when a fresh
shell is within range. When the shell isn't sliding, nobody refreshes `SHELL_LIVE_UNTIL`, so the
stale position is ignored.

## New globals ([`mailbox.inc`](../../wfsource/source/mailbox/mailbox.inc), free 18xx range)

| Name | idx | role |
|---|---|---|
| `SMB_KOOPA_STATE` | 1831 | 0 walk / 1 shell-rest / 2 shell-slide (single Koopa in W1-1 → a global is fine; multi-Koopa would need a per-actor local slot) |
| `SMB_SHELL_LIVE_X` | 1832 | a sliding shell broadcasts its X each tick |
| `SMB_SHELL_LIVE_Z` | 1833 | …its Z |
| `SMB_SHELL_LIVE_UNTIL` | 1834 | `TIME + 0.1` while sliding; enemies treat `SHELL_LIVE_X/Z` valid only while `TIME <` this (freshness gate) |

(`INDEXOF_` prefix per the standing convention; flagged as wanted-gone, not silently spread.)

## Authoring (`blender_create_smb.py`)

- New `KOOPA_SCRIPT` (the state machine above), applied to `koopa_00` **instead of** the shared
  `ENEMY_SCRIPT` (call `_apply_enemy_movement` then override `wf_Script`). `SHELL_SPEED ≈ 14`
  (faster than the walk; a kicked shell is quick).
- **Visual cue for the shell:** on entering state 1, drop the Koopa's Z-scale (e.g. `Z_SCALE`
  ~0.5) so the head tucks down into a flatter shell; restore-free since it stays a shell. Per-actor
  scale is visual-only (collision unaffected — that's fine here). Placeholder-level cue; a proper
  retracted-shell mesh is a follow-up.
- **Goomba** `ENEMY_SCRIPT`: add the shell-defeat proximity branch (mirror the fireball branch,
  reading `SMB_SHELL_LIVE_*`).

## Verification

New `tests/verify_smb_koopa_shell.py` (debug bridge), modelled on the fireball-defeat rig:
1. Discover `player` + `koopa`. Force Fire state off; walk/teleport so the player is **above** the
   Koopa and stomp it → assert `SMB_KOOPA_STATE` 0 → 1 **and the Koopa is still alive** (NOT
   despawned — the despawn probe should *fail*, proving it became a shell rather than dying).
2. Touch the resting shell from the side → assert `SMB_KOOPA_STATE` → 2 and `XSPEED` magnitude is
   high (kicked), directed away from the player.
3. Put the Goomba in the sliding shell's path (drop it onto `SMB_SHELL_LIVE_X`, the
   onto-the-projectile rig from the fireball-defeat test) → assert the Goomba despawns
   (`set_mailbox` → "actor not found").
4. Re-stomp the sliding shell → `SMB_KOOPA_STATE` → 1, `XSPEED` ~ 0.
5. **Recording:** `python3 tests/verify_smb_koopa_shell.py --record` →
   **[`tests/recordings/smb_koopa_shell.mp4`](../../tests/recordings/smb_koopa_shell.mp4)** (engine
   `-record_video`, per the
   [recording convention](2026-05-26-fire-mario-fireball-pooled-generator.md#recording-checked-in-proof)).

Reuse the **despawn-probe** kill detection and the **onto-the-projectile** placement from the
[fireball-defeat test](../../tests/verify_smb_fireball_defeat.py) (don't watch `ALIVE` — a removed
actor's change-only mailbox freezes stale; both gotchas are in the
[designer guide](../level-design-troubleshooting.md)).

Regression: the Goomba's existing walk/stomp/fireball behaviour and `verify_smb_fireball*.py` must
still pass — run harnesses individually (back-to-back runs starve the headless engine).

## Build & run

1. `blender --background --python wflevels/smb_w1_1/blender_create_smb.py`
2. `task build` (engine — new `mailbox.inc` constants; touch `scripting_stub.cc`)
3. `task build-level -- smb_w1_1`
4. `python3 tests/verify_smb_koopa_shell.py --record`

## Known limitations / follow-ups

- **Single-Koopa state.** `SMB_KOOPA_STATE` is global; W1-1 has one Koopa. Multiple Koopas need a
  per-actor local state slot (and `read-actor-mailbox` to let the shell defeat by reading the
  victim, rather than the victim polling a single shared broadcast). Same ceiling as the
  one-tracked-fireball limit.
- **A kicked shell can hit Mario himself** — faithful, but our side-hit hurt is symmetric, so a
  shell kicked into a wall and bouncing back will hurt. Intended.
- **Retracted-shell mesh** — v1 uses a Z-scale squash as the cue; a dedicated shell mesh is polish.
- **Shell-vs-shell / shell stacking** — out of scope (one Koopa).

## Sources

- [Fireball defeats enemies (Phase 2)](2026-05-27-smb-fireball-defeats-enemies.md) — the
  broadcast + freshness + proximity-defeat idiom this reuses.
- `ENEMY_SCRIPT` + Koopa build in [`blender_create_smb.py`](../../wflevels/smb_w1_1/blender_create_smb.py).
- [Designer guide: script-driven wall/floor bounce; killed-actor stale mailbox; velocity-expanded spawn box](../level-design-troubleshooting.md).
