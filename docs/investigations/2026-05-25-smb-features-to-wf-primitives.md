# SMB features → WF primitives mapping

**Date:** 2026-05-25
**Status:** Investigation / planning reference

## Context

A survey of WorldFoundry's OAD/actor classes (prompted by the flagpole end-of-level work)
showed that WF game objects are **compositions of small single-purpose primitives**, and that a
whole category of actors are *sensors / references designed to pair with another object*
(`ActBox`, `ActBoxOR`, `Warp`+`Target`, `Generator`+template, `Destroyer`, `Spike`, `Shield`,
`Shadow`). That reframes the rest of the Super Mario Bros conversion: most of it is **content +
composition of existing LIVE classes**, not new `EActorKind`s. This doc maps each SMB mechanic to
its composition and flags the (few) items that genuinely need engine work.

See the [composition pattern](../level-building.md#composing-actors--sensors--visuals-reach-for-this-before-a-new-class)
in the level-building guide, and the [SMB conversion brief](/home/will/wf-games/super-mario-bros.md).

## Legend

| | meaning |
|--|--|
| ✅ | **done** — already implemented and working |
| 🧩 | **compose** — wire existing LIVE primitives in the level; no engine change, little/no script |
| 🔧 | **compose + Forth** — existing primitives plus a per-actor script (state machine / AI) |
| 🚧 | **engine work** — needs a new movement mode, new class, or new UI; not expressible by composition today |

## Mapping

| SMB mechanic | Composition (WF primitives) | Status |
|---|---|---|
| Walk / run / jump | `Player` + Ground/Air handlers; variable jump in `AirHandler` | ✅ |
| Side-scroll camera (left-lock) | `Director` (ratchet script) + `CamShot` + `SMB_*` mailboxes | ✅ |
| `?`-block → coin | `Generator` (the block) + `Gold` (coin template); the **spawned** coin inherits the generator's +X velocity and slides right along the ground | ✅ |
| Standalone coin (placed at level start) | `Gold` — **spins in place** (Z-axis `ROTATION_C` script); it has no velocity so it does **not** move/slide. OAD `Gold Value` | ✅ |
| HUD score/coins (basic) | per-actor `GOLD` mailbox → global mb 70 → SCORE overlay | ✅ |
| **Flagpole → end of level** | `statplat` (pole+flag art) + `ActBox`(`MailBox`=`END_OF_LEVEL`,`=1`, ActivatedBy=Player) | 🧩 *(designed this session)* |
| **Pipe warp** | `Warp` + `Target` — Warp at pipe mouth teleports the entering actor to the Target in the destination area | 🧩 |
| **Pit / fall death** | `ActBox` volume below each gap → writes `SMB_PLAYER_HURT` → existing respawn (−1 life) | ✅ *(2026-05-25, [plan](../plans/2026-05-25-smb-pit-death-and-level-timer.md))* |
| **Spikes / lava / hazard** | `Spike` (applies `Health Modifier` on contact) | 🧩 |
| **Moving platform / lift** | `Platform` (path-driven) — see Path/CHAN note below | 🧩 / 🚧 |
| **Goomba** | `Enemy` + walk (constant velocity / path) + stomp (collision-normal script) | 🔧 |
| **Koopa + shell kick** | `Enemy` + shell-state script + kicked-velocity; collision mailboxes | 🔧 |
| **Stomp combat** (jump on enemy) | per-actor `COLLIDER_IDX` + `COLLISION_NORMAL_Z` (enemy detects player landing from above) → enemy dies + player bounce | 🔧 *(mechanism ✅, needs enemy script)* |
| **Piranha Plant** | `Enemy` + vertical oscillation (path/script) emerging from a pipe | 🔧 |
| **Hammer Bro / hammers** | `Enemy` + `Missile` (the hammers) | 🔧 |
| **Bullet Bill** | `Generator` (cannon spawns) + `Missile`/`Enemy` moving horizontally | 🔧 |
| **Fireball (Fire Mario)** | `Missile` spawned on fire-button when in Fire state | 🔧 *(needs spawn path — see backlog)* |
| **Super Mushroom** | a `gold` actor with `Gold Value = 0` + a proximity-pickup script (writes `SMB_MUSHROOM_PICKUP`), thrown by a one-shot `Generator` block; slides on real physics | ✅ *(2026-05-26, [plan](../plans/2026-05-26-smb-super-mushroom-powerup.md))* |
| **Fire Flower** | same collectible idiom as the mushroom, but Fire Mario needs the `spawn-template` primitive (fireballs) | 🔧 *(state 2 reserved; deferred)* |
| **Star (invincibility)** | **`Shield`** — the live "follows player + timed invulnerability + blink" primitive; Star = collectible that grants a Shield | 🧩 / 🔧 |
| **Power-up state machine** (Small/Super/Fire) | pure Forth state machine on `Player`; pickup raises `SMB_MARIO_STATE` + visual scale, a hit powers down instead of dying | ✅ *(Small↔Super 2026-05-26; Fire deferred, [plan](../plans/2026-05-26-smb-super-mushroom-powerup.md))* |
| **Breakable brick** (Super Mario) | `Generator`-style block + `Destroyer`/visibility on bump-from-below | 🔧 |
| **Level timer** (countdown) | `Director` script: 400-unit countdown off `TIME` → HUD slot 71; 0 = "TIME UP" → `SMB_PLAYER_HURT` (Mario dies) | ✅ *(2026-05-25, [plan](../plans/2026-05-25-smb-pit-death-and-level-timer.md))* |
| **Lives / death / respawn** | enemy contact + pit `ActBox` + timeout → `SMB_PLAYER_HURT` → player respawn (−1 life), game-over at 0 | ✅ *(enemy 2026-05-25; pit/timeout 2026-05-25)* |
| **Music / SFX per event** | audio system (miniaudio) + SFX-index mailbox writes (qbert SFX pattern) | 🔧 |
| **Flag slide-down + "COURSE CLEAR"** | flag move via mailbox (script); the *screen* has no infra | 🚧 |
| **Swim mode** (underwater W1-2) | new gravity/buoyancy movement mode | 🚧 |

## Notes on the non-obvious mappings

- **`Shield` ≈ the Star.** `Shield` (`shield.cc`) already follows the player, holds a timed
  invulnerability window, blinks, and absorbs hits. SMB's invincibility Star is almost exactly
  this — grant a `Shield` on Star pickup rather than hand-rolling an invuln timer.
- **Pipes are `Warp`+`Target`, and they're LIVE.** `Warp::update()` detects the entering actor
  via the same `activate.inc` filter and repositions it to the referenced `Target`. The only
  SMB-specific nuance is the "press *down* to enter" gate — likely a tiny script (or an ActBox
  that arms the Warp only while the down input is held).
- **Stomp uses the collision mailboxes we already hardened.** The `?`-block bump proved
  `COLLIDER_IDX`/`COLLISION_NORMAL_*` populate under Jolt. An enemy's script reads them: if the
  collider is the player **and** the contact normal points up (player came down on top) → enemy
  dies; otherwise the player takes damage. Same idiom, different actor.
- **`ActBox` for region events works under Jolt** (PA-based AABB, player in the collide list) —
  so pit-death volumes, pipe-entry zones, and the flagpole trigger are all viable composition,
  unlike anything routed through the dead legacy collision-event path.
- **Dead stubs:** `Pole`, `Meter`, `Movie` have `.oas` files but no C++ class — do **not** author
  against them (a flagpole is `statplat`+`ActBox`, not a `Pole`).

## Engine-work backlog this surfaces (the 🚧 / blocking 🔧)

These are the only items the composition model can't express today:

1. **Swim movement mode** — new buoyancy/gravity mode for the underwater variant (~1 wk per the
   brief). Genuinely new engine work.
2. **Course-clear / win screen** — `END_OF_LEVEL` just unloads; there is no completion
   overlay/animation. New UI infra (shared with any game's "you win").
3. **`spawn-template` Forth primitive** — fireballs/item-drops/projectiles from *variable*
   positions currently need a per-spawn `Generator` anchored in the level. Already a
   [TODO](../../TODO.md) (§ SCRIPTING INFRASTRUCTURE); land it before fireballs/Hammer Bro.
4. **`read-actor-mailbox` primitive** — cross-actor reads (enemy↔player) currently need a
   global-mailbox indirection. [TODO](../../TODO.md). Quality-of-life for the enemy scripts.
5. **Path/CHAN keyframes for `Platform`** — moving platforms need authored path/channel data;
   this is the Phase-2c gap from the [Blender round-trip plan](../plans/2026-04-16-blender-level-roundtrip.md).
6. **Flag slide-down** — minor; scriptable via a mailbox move, but there's no `Pole` behaviour.

Everything else is **content + composition + Forth** on classes that already work.

## Already done (for contrast)

Walk/run/jump, variable jump height, side-scroll left-lock camera, `?`-block → coin
(`Generator`+`Gold`), coin ground-slide, OAD `Gold Value`, basic HUD score/coins.

## Sources

- OAD class survey (this session): live classes from
  [`objects.lc`](../../wfsource/source/oas/objects.lc) / `objects.c` factory; capabilities from
  the per-class C++ in [`wfsource/source/game/`](../../wfsource/source/game/).
- [Composition pattern — level-building.md](../level-building.md#composing-actors--sensors--visuals-reach-for-this-before-a-new-class)
- [SMB conversion brief](/home/will/wf-games/super-mario-bros.md)
- [SMB W1-1 source](../../wflevels/smb_w1_1/blender_create_smb.py)
