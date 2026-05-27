# Plan: SMB scoring system + 1UP mushroom

> Plan authored before implementation (plan-workflow convention). Commit with the code.
> **Status:** In progress.

## Goal

W1-1 currently shows coin count as the "score". This plan wires real point values to game
events (stomp=100, fireball kill=200, brick break=50, coin=200, flagpole height tier + time bonus)
and adds the hidden 1UP mushroom brick at tile 40 (x=60m).

## What's already working

- `HUD_SCORE` (mb 70), `HUD_TIMER` (mb 71), `LIVES` (mb 72) display in `display.cc`
- `GOLD` (mb 3001) accumulates coin count via `gold.cc::TryPickup`
- All enemy scripts, brick scripts, player hurt/respawn are in place

## What's missing

| Feature | Current state |
|---|---|
| Real score | `HUD_SCORE = GOLD` (raw coin count) |
| Stomp bonus | Not scored |
| Fireball kill | Not scored |
| Shell kill | Not scored |
| Brick break | Not scored |
| Flagpole height bonus | Not computed |
| Flagpole time bonus | Not computed |
| 100-coin 1UP | Not tracked |
| 1UP mushroom | No actor; no hidden brick |

## New mailboxes (`mailbox.inc`, free 183x)

| Name | idx | role |
|---|---|---|
| `SMB_SCORE` | 1838 | accumulated point bonus (coin 200, stomp 100, fireball 200, shell 100, brick 50, flagpole) |
| `SMB_LAST_GOLD` | 1839 | GOLD value at end of previous player-script tick; delta = GOLD − LAST_GOLD → coin scoring |
| `SMB_EOL_LATCH` | 1840 | 1 after the end-of-level flagpole bonus has been computed (edge-detect guard) |
| `SMB_ONEUP_PICKUP` | 1841 | 1UP mushroom sets this on proximity; player script grants +1 life and clears |

(`INDEXOF_` prefix per convention; wanted-gone but not silently changing.)

## Script changes

### PLAYER_SCRIPT

1. **HUD display** (moved to end of script): `SMB_SCORE → HUD_SCORE` (was `GOLD → HUD_SCORE`)
2. **Stomp score** (in stomp-consume block): `SMB_SCORE += 100`
3. **Coin delta scoring**: each tick compute `delta = GOLD − LAST_GOLD`; if `delta > 0`: `SMB_SCORE += delta × 200`; check 100-coin 1UP (`GOLD 100 % = 0 AND LAST_GOLD 100 % ≠ 0 AND GOLD > 0 → LIVES += 1`); update `LAST_GOLD = GOLD`
4. **1UP pickup**: `SMB_ONEUP_PICKUP ≠ 0 → LIVES += 1`, clear
5. **Flagpole height + time bonus** (edge-detect `END_OF_LEVEL`, guarded by `SMB_EOL_LATCH`):
   - Height tier (player Z at touch): ≥9.0→5000, ≥6.0→2000, ≥4.5→800, ≥3.0→400, ≥1.5→200, else→100
   - Time bonus: `HUD_TIMER × 50` points

### ENEMY_SCRIPT (Goomba)

- Fireball proximity → kill block: `SMB_SCORE += 200` before `ALIVE = 0`
- Shell proximity → kill block: `SMB_SCORE += 100` before `ALIVE = 0`

### KOOPA_SCRIPT

- Fireball proximity → kill block: `SMB_SCORE += 200` before `ALIVE = 0`

### BRICK_SCRIPT

- Super-hit break initiation block: `SMB_SCORE += 50` when `MARIO_STATE ≠ 0` triggers the break window

## New actors (`blender_create_smb.py`)

### `oneup_template` (green 1UP mushroom)

- `_make_powerup_template('oneup_template', mat_oneup, ONEUP_SCRIPT, 0.0, -65.0)`
- `mat_oneup = make_mat('smb_oneup', (0.0, 0.8, 0.0))` — green body
- `ONEUP_SCRIPT`: proximity check (dx² + dz² < 2.25) → `SMB_ONEUP_PICKUP = 1`; gold.cc despawns it (GoldValue = 0 via `_make_powerup_template`)

### `brick_1up` (hidden 1UP block, x = 40×T = 60m)

- Looks identical to a plain brick (`brick_tex`)
- Uses `POWERUP_BLOCK_SCRIPT` (one-shot: throws one item, turns tan after first hit)
- `Object To Throw = 'oneup_template'`, `Object X Velocity = 1.5` (slides right)
- Position: `ONEUP_BRICK_X = 40 * T` — between `star_block` (57m) and `flagpole` (63m)

## Scoring tier table (for reference)

| Event | Points |
|---|---|
| Stomp (Goomba or Koopa retract) | 100 |
| Fireball kill | 200 |
| Shell kill | 100 |
| Brick break (Super/Fire) | 50 |
| Coin pickup | 200 |
| Flagpole height ≥ top | 5000 |
| Flagpole other tiers | 100 / 200 / 400 / 800 / 2000 |
| Time remaining × 50 | varies |

## Verification

New `tests/verify_smb_scoring.py` (debug bridge):

1. **Coin score**: collect a coin → assert `HUD_SCORE` increases by 200.
2. **Stomp score**: stomp the Goomba → assert `HUD_SCORE` increases by 100.
3. **Fireball score**: fire a fireball at an enemy → assert `HUD_SCORE` increases by 200.
4. **Brick score**: as Super, hit a brick from below → assert `HUD_SCORE` increases by 50.
5. **1UP mushroom**: trigger `brick_1up` → mushroom spawns → collect → assert `LIVES` increases by 1.
6. **Flagpole bonus**: trigger `END_OF_LEVEL` → assert `HUD_SCORE` increased by at least 100.

Regression: existing enemy, fireball, brick, and piranha tests still pass.

## Known limitations

- Stomp chain multiplier (100→200→400→…) not implemented — all stomps score 100.
- Shell-kill chain multiplier not implemented.
- Score does not carry across level transitions (reset on respawn with timer).
- 100-coin 1UP detection uses GOLD mod 100 edge; if coins are collected at >1/tick
  rate (e.g. rapid sequential coin room pickups), a 100-boundary crossing within one
  tick could be missed. Acceptable for current level density.

## Sources

- [`gold.cc`](../../wfsource/source/game/gold.cc) — TryPickup, GoldValue, SetPendingRemove
- [`display.cc`](../../wfsource/source/gfx/gl/display.cc) — HUD rendering
- [`mailbox.inc`](../../wfsource/source/mailbox/mailbox.inc) — existing SMB mailboxes
- [`blender_create_smb.py`](../../wflevels/smb_w1_1/blender_create_smb.py) — all actor authoring
- Flagpole plan: [`2026-05-25-smb-flagpole-end-of-level.md`](2026-05-25-smb-flagpole-end-of-level.md)
- Piranha plan: [`2026-05-27-smb-piranha-plant.md`](2026-05-27-smb-piranha-plant.md)
