# SMB fireball defeats enemies (Phase 2 of the Fire Mario fireball)

> Plan authored before implementation (plan-workflow convention). Commit with the code.
> **Status:** **Done** (2026-05-27, ~3 h — most of it debugging a flaky test, see below).
> Verified headless ([`tests/verify_smb_fireball_defeat.py`](../../tests/verify_smb_fireball_defeat.py),
> 4/4 across repeated runs) + recording
> **[`tests/recordings/smb_fireball_defeat.mp4`](../../tests/recordings/smb_fireball_defeat.mp4)**.
> The defeat mechanic worked first try; the time went into the *test rig* (three real issues found
> below). Engine cost: three new `mailbox.inc` constants (rebuild to regenerate `INDEXOF_` — no C++
> logic). One feature tweak shipped: the fireball forward-offset went **1.2 → 1.8** (1.2 was
> marginal — Mario's idle +X drift intermittently put the spawn box inside his body → NULL spawn).
>
> **Three things the bring-up surfaced (all logged to the designer guide):**
> 1. **A killed actor (`ALIVE=0`) is removed; its change-only mailbox watch then freezes at stale
>    values.** Asserting a kill by watching `ALIVE → 0` is wrong (the watch keeps showing the
>    pre-death `1`). Probe despawn instead: `set_mailbox` on a removed actor replies *"actor not
>    found"*. This cost most of the debugging time.
> 2. **`SafelyConstructTemplateObject` expands the spawn box by `velocity × dt`** (to catch fast
>    objects). A +12 fireball under the bridge's variable step dt reaches ~1 unit ahead, so an
>    enemy parked in the narrow clear lane intermittently landed in the expanded box → NULL spawn.
>    The test now parks the enemy far away and drops it **onto the already-airborne fireball**.
> 3. The enemy defeat radius is **2.5** (r²), not 1.5 — the fireball flies at waist height (`Z≈1`)
>    while the enemy sits at `Z≈0.06`, so `dz²≈0.88` already eats most of a 1.5 budget.
> **Estimate:** ~half a day (average-programmer scale). Compose + Forth; the only engine cost is
> three new `mailbox.inc` constants (rebuild to regenerate the `INDEXOF_` table — no C++ logic).

## Goal

The [Fire Mario fireball](2026-05-26-fire-mario-fireball-pooled-generator.md) spawns, flies, and
despawns — but kills nothing. Phase 2: a fireball that reaches a Goomba/Koopa **defeats it on
contact** (the enemy dies, no bounce, no damage to Mario). This completes the fireball as a real
offensive tool.

## Approach (no engine logic)

Enemies can't receive a Jolt contact from the Missile (both are `MOBILITY_PHYSICS`
CharacterVirtuals — the same dispatch gap that makes enemies use **proximity** to the player
rather than collision). So reuse the proven idiom: **the fireball broadcasts its live position to
globals; the enemy self-defeats when a *fresh* fireball is within range** — exactly how the enemy
already handles the Star (`TIME < SMB_STAR_UNTIL` + proximity → `ALIVE = 0`) and the stomp.

The "fresh" gate is the key to avoiding a stale-position false positive: a fireball writes its
position **and** `LIVE_UNTIL = TIME + 0.1` every tick while alive (`Missile::update` ends in
`Actor::update()`, so the Missile runs its `wf_Script` — verified). When no fireball is alive,
nobody refreshes `LIVE_UNTIL`, `TIME` passes it, and enemies ignore the stale coordinates — the
same "until-deadline" pattern as `SMB_STAR_UNTIL`.

## Design

### New globals ([`mailbox.inc`](../../wfsource/source/mailbox/mailbox.inc), free 18xx range)

| Name | idx | role |
|---|---|---|
| `SMB_FIREBALL_LIVE_X` | 1828 | a live fireball broadcasts its X each tick |
| `SMB_FIREBALL_LIVE_Z` | 1829 | …its Z |
| `SMB_FIREBALL_LIVE_UNTIL` | 1830 | `TIME + 0.1` each tick a fireball is alive; enemies treat the position as valid only while `TIME <` this (freshness gate) |

(`INDEXOF_` prefix per the standing convention; called out as wanted-gone, not silently spread.)

### Fireball template gets a broadcast script (`blender_create_smb.py`)

The `fireball_template` Missile currently has no `wf_Script`. Add one:

```forth
\ wf
INDEXOF_X_POS read-mailbox INDEXOF_SMB_FIREBALL_LIVE_X write-mailbox
INDEXOF_Z_POS read-mailbox INDEXOF_SMB_FIREBALL_LIVE_Z write-mailbox
INDEXOF_TIME read-mailbox 0.1 + INDEXOF_SMB_FIREBALL_LIVE_UNTIL write-mailbox
```

### Enemy gains a fireball-defeat branch (`ENEMY_SCRIPT`)

Add, independent of the player-proximity block (a fireball can hit an enemy nowhere near Mario):

```forth
\ Fireball defeat: a FRESH fireball within range kills us — no bounce, no player hurt.
INDEXOF_TIME read-mailbox INDEXOF_SMB_FIREBALL_LIVE_UNTIL read-mailbox < if
  INDEXOF_SMB_FIREBALL_LIVE_X read-mailbox INDEXOF_X_POS read-mailbox - dup *
  INDEXOF_SMB_FIREBALL_LIVE_Z read-mailbox INDEXOF_Z_POS read-mailbox - dup *
  + 2.5 < if
    0 INDEXOF_ALIVE write-mailbox
  then
then
```

`2.5` = radius² (r≈1.58 m). Bumped from the planned 1.5 during bring-up: the fireball flies at
waist height (`Z≈1`) while a grounded enemy sits at `Z≈0.06`, so `dz²≈0.88` consumes most of a
1.5 budget before any horizontal slack.

## Known limitations (documented, not blocking)

- **One tracked fireball at a time.** Both pool fireballs write the same `LIVE_*` globals each
  tick, so the value reflects whichever ran last that tick. With two fireballs airborne, an enemy
  under either is still hit within a tick or two (both sample across consecutive ticks), but it's
  not a clean per-fireball model. Faithful-enough for W1-1; the per-fireball version waits on
  `read-actor-mailbox` / a spawn registry.
- **Fireball passes through (doesn't die on first hit).** Real SMB fireballs vanish on contact;
  ours keeps flying (the enemy-side check can't despawn the Missile cross-actor, and the Missile's
  `SPECIAL_COLLISION`→explode path doesn't fire under Jolt). It still despawns on its 2 s
  `Explosion Delay`. Follow-up.
- **Tap-fire detonates early.** `Missile::update` explodes on `justReleased(kBtnGrenade)` (= B), so
  *holding* B flies the fireball full-range but *tapping* cuts it short. Pre-existing Missile
  behaviour; logged as a fidelity follow-up. (The test holds B, so it's unaffected.)

## Verification

[`tests/verify_smb_fireball_defeat.py`](../../tests/verify_smb_fireball_defeat.py) (debug bridge),
4/4 across repeated runs — the rig is shaped by the two gotchas above:
1. Discover `player` + the `goomba`; force Fire state; park the Goomba **far away** (X=40) so it
   can't sit in the velocity-expanded spawn box.
2. Hold B → one fireball spawns cleanly and flies right; once it's airborne in the clear lane
   (`6 < LIVE_X < 8`), teleport the Goomba **onto the live fireball** for a few ticks (no spawn
   pre-check is involved for an existing actor → deterministic). Screenshot the impact.
3. Confirm the kill by **despawn probe**, not by watching `ALIVE`: `set_mailbox` on the Goomba —
   a *"actor not found"* reply proves it was removed. Also assert `SMB_PLAYER_HURT` never fired
   (clean ranged kill).
4. **Recording:** `python3 tests/verify_smb_fireball_defeat.py --record` →
   **[`tests/recordings/smb_fireball_defeat.mp4`](../../tests/recordings/smb_fireball_defeat.mp4)**
   (512×384, ~4.2 s), per the
   [recording convention](2026-05-26-fire-mario-fireball-pooled-generator.md#recording-checked-in-proof).

Regression: `tests/verify_smb_fireball.py` (spawn/facing/one-per-press) still passes after the
1.2 → 1.8 offset change. Run harnesses individually (back-to-back runs starve the headless engine).

## Build & run

1. `blender --background --python wflevels/smb_w1_1/blender_create_smb.py`
2. `task build` (engine — new `mailbox.inc` constants; touch `scripting_stub.cc`)
3. `task build-level -- smb_w1_1`
4. `python3 tests/verify_smb_fireball_defeat.py --record`

## Follow-ups

- Fireball **dies on first hit** + **multi-fireball** tracking (needs `read-actor-mailbox` or a
  spawn registry).
- Tap-fire early-detonation (`Missile` `justReleased(kBtnGrenade)`).
- Score award on a fireball kill (the stomp path also awards nothing today — settle enemy scoring
  together).

## Sources

- [Fire Mario fireball plan (Phase 1)](2026-05-26-fire-mario-fireball-pooled-generator.md)
- [`missile.cc`](../../wfsource/source/game/missile.cc) — `update()` ends in `Actor::update()` (script runs); `justReleased(kBtnGrenade)` detonation
- `ENEMY_SCRIPT` in [`blender_create_smb.py`](../../wflevels/smb_w1_1/blender_create_smb.py) — existing Star/stomp self-defeat idiom
