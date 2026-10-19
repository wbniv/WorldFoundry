# SMB W1-1 — Super Mushroom + power-up state machine

**Status:** Done + verified (2026-05-26). Headless bridge tests green: state machine ([`tests/verify_smb_mushroom.py`](../../tests/verify_smb_mushroom.py)) and full producer chain ([`tests/verify_smb_mushroom_spawn.py`](../../tests/verify_smb_mushroom_spawn.py)) — block bump → one mushroom → slide → pickup script → Mario Super; power-down keeps the life; Small death still costs one. Screenshots in `tests/screenshots/smb_mushroom_*.png`. Interactive-confirm note: the held-bump one-shot (USED latch) can't be faked headless (collision system resets `COLLIDER_IDX`).

## Context

The Super Mushroom was the most iconic W1-1 element still missing. Mario only had the Small state — no power-up progression, and any enemy/pit/timeout hit cost a life. This adds **Small → Super**: the new mushroom block reveals a mushroom that pops out and slides along the ground; touching it makes Mario "Super" (visibly bigger + survives one hit). It lays the state-machine groundwork for Fire Mario and brick-breaking later.

The [SMB→WF primitives mapping](../investigations/2026-05-25-smb-features-to-wf-primitives.md) classed this as 🔧 *compose + Forth*. The state machine and power-down are pure Forth on the existing `Player`; the mushroom reuses the `gold` class (no new class — see below).

## Design

### Mushroom = `gold` template, `Gold Value = 0`, + a pickup script (no new class)

A *moving* collectible needs `Gold`'s unique collision profile, and only `Gold` has it:

| Class | `collide` | vs. Player | Fit |
|-------|-----------|-----------|-----|
| `Gold` | 1 | `CI_SPECIAL`/`CI_NOTHING` (walk-through) + `CI_PHYSICS` vs. floor | ✅ the only stock fit |
| `StatPlat` / `Platform` | 1 | solid — blocks Mario | ❌ |
| `Enemy` | 1 | `Enemy::update()` sends `DELTA_HEALTH -10` ([`enemy.cc:67`](../../wfsource/source/game/enemy.cc)) | ❌ damages |
| any `collide=0` | 0 | doesn't collide with the floor → falls through | ❌ can't slide |

`Gold`'s only baggage is that its C++ pickup credits coins, and two facts in [`gold.cc`](../../wfsource/source/game/gold.cc) defuse it:
- `TryPickup` adds `getOad()->GoldValue` to the player's GOLD (`:57`) — `Gold Value = 0` ⇒ awards zero, just removes the actor on contact.
- `Gold::update()` still calls `Actor::update()` (`:79`) ⇒ the mushroom's own `wf_Script` runs each tick and writes `SMB_MUSHROOM_PICKUP` on the same proximity the C++ uses to remove it.

So the mushroom is a `gold` coin "worth 0" with a script — a small semantic hack (a mushroom is not a coin), filed as a class-taxonomy follow-up in [`TODO.md`](../../TODO.md) § LEVEL / GAMEPLAY.

### Super size = visual scale only

Super scales the mesh via `X_SCALE`/`Y_SCALE`/`Z_SCALE` (mailboxes 3040–42): `1.25 / 1.25 / 1.9` (taller, slightly wider). The Mario mesh origin is at the **feet** (baked in `_build_mario`, `blender_create_smb.py:705`), so the scale grows Mario upward from the floor — no sink, no `Z_POS` nudge. The Jolt `CharacterVirtual` capsule (built once from the ColSpace AABB, [`jolt_backend.cc:605`](../../wfsource/source/physics/jolt/jolt_backend.cc)) is **not** resized — hitbox stays Small-sized; "survive one hit" is fully script-driven. True capsule resize is a follow-up.

### Scope

Small ↔ Super only. Fire Mario needs the `spawn-template` Forth primitive (fireballs); the state machine reserves state 2 but the Fire Flower is deferred.

## Changes

| File | Change |
|------|--------|
| [`wfsource/source/mailbox/mailbox.inc`](../../wfsource/source/mailbox/mailbox.inc) | `SMB_MARIO_STATE` (1814), `SMB_MUSHROOM_PICKUP` (1815) |
| [`wfsource/source/oas/gold.oas`](../../wfsource/source/oas/gold.oas) + `gold.ht` | `Gold Value` min lowered 1→0 |
| [`wflevels/smb_w1_1/blender_create_smb.py`](../../wflevels/smb_w1_1/blender_create_smb.py) | `mushroom_template` (gold, `Gold Value 0`, pickup script) + one-shot mushroom `Generator` block at X=9 + Mario state machine (pickup→Super scale; power-down on hurt) |
| [`TODO.md`](../../TODO.md) | object-model / class-taxonomy follow-up |

**Mario state machine** (inlined into the per-tick script; zForth has no nested `:` defs, `not` = `state == 0`):
- Mushroom pickup → if state 0, set state 1 + write the Super scale; clear the flag.
- The existing `SMB_PLAYER_HURT` handler now branches on state inside the i-frame gate: state > 0 → decrement state, reset scale to 1.0, brief i-frames, **keep the life**; state 0 → existing death/respawn path.

## Known limitation (v1)

`Gold Value = 0` is **dropped at export today**: the Blender exporter reads the stale fixtures `OAD_DIR`, whose `gold.oad` predates the `Gold Value` field ([TODO § Blender level export uses a STALE OAD dir](../../TODO.md)). So the mushroom currently also awards its **default +1 coin** on pickup. Harmless on a validation level; clears once `OAD_DIR` is repointed to the canonical OADs. The `gold.oas`/`gold.ht` min was lowered to 0 regardless so the authoring is correct when that lands.

## Build

1. Run `blender_create_smb.py` in Blender (`blender --background --python wflevels/smb_w1_1/blender_create_smb.py`) → re-export `smb_w1_1.lev` + `mushroom_template.iff`.
2. `task build-level -- smb_w1_1` → `.iff` + `-standalone.iff`.
3. `task build` (engine — picks up the new `mailbox.inc` constants).

## Verification (headless, screenshots required)

1. **Spawn + slide:** bump the mushroom block (X=9); confirm exactly one mushroom pops out, slides +X, block turns tan. Screenshot.
2. **Pickup → Super:** walk into the mushroom; confirm `SMB_MARIO_STATE` 0→1 and Mario visibly grows. Screenshot (Small vs Super).
3. **Power-down, not death:** while Super, take a hit; confirm `SMB_MARIO_STATE` 1→0, scale resets, `LIVES` unchanged, brief invuln. Screenshot.
4. **Small death still works:** while Small, hit → loses a life + respawns (regression).

## Follow-ups

- **Object-model / class taxonomy** — base `Collectible` with the walk-through+floor-landing profile + pluggable pickup, so `Gold`/`Mushroom`/`Star`/`1-Up` stop cloning/hacking. Filed in `TODO.md`; trigger = the second power-up.
- **True runtime capsule resize** — new mailbox + recreate the Jolt `CharacterVirtual` so Super's hitbox actually grows.
- **Fire Flower / Fire Mario** — blocked on `spawn-template`; state machine reserves state 2.
- **Repoint `OAD_DIR`** (existing TODO) — clears the +1-coin limitation.
