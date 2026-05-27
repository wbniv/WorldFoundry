# Fire Mario's fireball — runtime-positioned spawn via a pooled, teleported `Generator`

> Plan authored before implementation (plan-workflow convention). Commit with the code.
> **Status:** **Done** (2026-05-26, ~1 h actual; estimate held at half-day–day average scale).
> Verified headless ([`tests/verify_smb_fireball.py`](../../tests/verify_smb_fireball.py), 6/6) +
> screenshots `tests/screenshots/smb_fireball_{01_right,02_left}_in_flight.png`. Approach A worked
> exactly as designed — no engine logic change. **One fix during bring-up:** the spawn was lifted
> to waist height (`Z_POS + 0.8`); spawning at Mario's feet (`Z_POS ≈ 0`, origin at feet) put the
> missile box flush on the ground slab (top `Z=0`) and `SafelyConstructTemplateObject`'s pre-check
> rejected it (`ConstructTemplateObject -> NULL`). The meshless-generator (no Jolt body), global
> activation, and facing split all behaved first try.
> **Estimate:** ~half a day to a day (average-programmer scale). **Zero engine C++ logic** — level
> authoring + Forth only. One caveat: the new `SMB_FIREBALL_*` constants are added to
> `mailbox.inc`, and the `INDEXOF_*` table is macro-generated from it at compile time
> ([`scripting_stub.cc`](../../engine/stubs/scripting_stub.cc)), so the engine must be rebuilt to
> see them (touch `scripting_stub.cc` — the stub `.o` mtime check ignores `mailbox.inc`). No C++
> *logic* change.

## Goal

Give Fire Mario (`SMB_MARIO_STATE == 2`) a fireball: press the fire button and a projectile
launches from in front of him, in his facing direction, travels horizontally, and despawns on a
timer. This is the first **runtime-positioned spawn** in WF — and the deliverable that proves
[Approach A](../investigations/2026-05-26-spawn-template-forth-primitive.md) (reuse a pooled,
teleported `Generator`) covers the need without the `spawn-template` engine syscall.

**Phase 1 (this plan):** spawn + travel + auto-despawn, gated on Fire state, facing-aware, on a
cooldown. **Phase 2 (follow-up):** fireball defeats an enemy on contact.

## Approach (why no engine change)

From the [investigation](../investigations/2026-05-26-spawn-template-forth-primitive.md): a
`Generator` spawns from its **live** `currentPos()` every fire, and a script can teleport any
actor by writing `X/Y/Z_POS` (the [2026-05-11 fix](2026-05-11-mailbox-pos-write-bypasses-jolt.md)
makes the write stick, including the Jolt push). So "spawn at a runtime position" = **park a
hidden, non-solid pool generator on the spawn point each tick, then pulse its activation
mailbox.** Two generators (one per facing direction) cover the baked-velocity limit.

Three facts make this clean, all verified against the engine:

1. **Non-solid generator.** A `Generator`'s Jolt static body is created **only** when
   `ModelType == MODEL_TYPE_MESH` ([`actor.cc:803`](../../wfsource/source/game/actor.cc)). Author
   the pool generators **without a mesh** → no Jolt body → they don't block Mario when parked on
   him. (The `Generator` *gameplay* collide flag is already `0` —
   [`objects.col:25`](../../wfsource/source/oas/objects.col) — so only the mesh-gated Jolt body
   matters.)
2. **Global activation = no actor-index fragility.** Point each generator's `Activation MailBox`
   at a **global** mailbox (1800-range). `Generato::update` reads it through the actor's mailbox
   accessor, which delegates global indices to the shared store
   ([`mailbox.cc:106`](../../wfsource/source/mailbox/mailbox.cc)) — so Mario pulses the global and
   the generator fires, **without** Mario needing the generator's actor index (which drifts per
   export). The generator self-parks by reading globals Mario publishes.
3. **`Missile` is the right template class — not another `gold` clone.**
   `COLTABLEENTRY(Player, Missile, CI_NOTHING, CI_SPECIAL)`
   ([`objects.mac:93`](../../wfsource/source/oas/objects.mac)) means Mario neither collects nor
   blocks it (a `gold`-worth-0 fireball would be self-collected the instant it spawns on Mario),
   `Missile` is `MOBILITY_PHYSICS` + template by default
   ([`missile.oas`](../../wfsource/source/oas/missile.oas)), and `Explosion Delay` gives a
   built-in TTL despawn ([`missile.cc`](../../wfsource/source/game/missile.cc) `SetPendingRemove`).
   `CI_SPECIAL` vs `Enemy` is the Phase-2 defeat hook.

## Design

### New global mailboxes (add to [`mailbox.inc`](../../wfsource/source/mailbox/mailbox.inc))

All in the free `18xx` global range (SMB globals currently end at `SMB_STAR_FLICKER_LATCH` 1819).
Per the [named-mailbox-constant convention](../../wfsource/source/mailbox/mailbox.inc), add
`MAILBOXENTRY` rows so scripts reference `INDEXOF_<NAME>`, not literals:

| Name | idx | role |
|---|---|---|
| `SMB_FIREBALL_X` | 1820 | Mario publishes the spawn point X (his X + facing·offset) each tick |
| `SMB_FIREBALL_Y` | 1821 | spawn point Y |
| `SMB_FIREBALL_Z` | 1822 | spawn point Z |
| `SMB_FIREBALL_FIRE_R` | 1823 | right generator's `Activation MailBox`; Mario pulses 1 to fire right |
| `SMB_FIREBALL_FIRE_L` | 1824 | left generator's `Activation MailBox` |
| `SMB_MARIO_FACING` | 1825 | +1 = right, −1 = left; latched from last LEFT/RIGHT input |
| `SMB_FIRE_COOLDOWN` | 1826 | level-time until which Mario can't re-fire |
| `SMB_FIRE_LATCH` | 1827 | 1 while the fire button is held (edge-detect: one fireball per press) |

> **`INDEXOF_` prefix call-out** (per standing guidance): these will be referenced as
> `INDEXOF_SMB_FIREBALL_X` etc. The verbose `INDEXOF_` prefix is the convention today but the user
> wants it gone eventually (single source: `scripting_stub.cc`). Following it here; flagging rather
> than silently propagating.

### The fireball template — a `Missile` (in `blender_create_smb.py`)

A small `missile`-schema actor, flagged as a template (so the generator can throw it):

- `attach_schema(obj, 'missile')`, small box geometry + a simple bright material (orange/white).
- `Mobility = Physics` (the missile default) so it travels under the velocity the generator
  imparts. `Explosion Delay` ≈ 2 s (built-in despawn). `Explode On Impact = 1`.
- `Moves Between Rooms = 1` (missile default) — harmless on the single surface room; keep default.
- Marked as a template (not placed in the level directly); the generators reference it by name
  `'fireball_template'`.

### Two pool generators — `fireball_gen_r` / `fireball_gen_l`

Authored once, near the start of the level (position doesn't matter — they self-park). For each:

- `attach_schema(b, 'generator')`, `Mobility = Anchored`.
- **No mesh** — leave `Model Type` at the non-`Mesh` default (and no `Mesh Name`) so **no Jolt
  static body** is created. This is what keeps the parked generator from blocking Mario.
- `Visibility Mailbox = 0` (hidden — it's an invisible spawner).
- `Object To Throw = 'fireball_template'`.
- `Generation Rate = 20.0` (fast; a one-tick activation pulse yields exactly one missile).
- `Object X Velocity = +V` for `_r`, `−V` for `_l` (e.g. `V = 12`). `Y = 0`. `Z = 0` (flat travel;
  a ground bounce is Phase-2 polish — see follow-ups).
- `fireball_gen_r['wf_Activation MailBox'] = SMB_FIREBALL_FIRE_R` (global 1823);
  `_l` → `SMB_FIREBALL_FIRE_L` (1824).
- **Self-park script** (each tick, reads Mario's published spawn point, writes its own position —
  same-actor write on an Anchored actor, so it sticks with no Jolt sync to fight):

```forth
\ wf
INDEXOF_SMB_FIREBALL_X read-mailbox INDEXOF_X_POS write-mailbox
INDEXOF_SMB_FIREBALL_Y read-mailbox INDEXOF_Y_POS write-mailbox
INDEXOF_SMB_FIREBALL_Z read-mailbox INDEXOF_Z_POS write-mailbox
```

> 1-tick lag is intrinsic: `Generato::update` checks the activation mailbox and spawns at
> `currentPos()` **before** `Actor::update()` runs this script. So a fireball spawns at Mario's
> position from the previous tick — sub-pixel at frame rate, invisible in play.

### Mario's fire logic (append to the player `wf_Script`)

Inserted alongside the existing pickup/state blocks. Pseudocode → Forth:

1. **Facing latch.** `RIGHT (0x2000)` held → `SMB_MARIO_FACING = 1`; `LEFT (0x4000)` → `−1`;
   else keep. (Raw bits per [`sjoystic.h`](../../wfsource/source/hal/sjoystic.h): DOWN 0x1000,
   RIGHT 0x2000, LEFT 0x4000, button A 0x1, **button B 0x2**.)
2. **Publish the spawn point** every tick with a **forward offset** so the missile's colspace
   doesn't overlap Mario at spawn (else `SafelyConstructTemplateObject`'s collision pre-check —
   `[Missile][Player] = CI_SPECIAL`, non-zero — would block it or poof it):
   `SMB_FIREBALL_X = X_POS + FACING · 1.0`, `SMB_FIREBALL_Y = Y_POS`, `SMB_FIREBALL_Z = Z_POS`.
3. **Fire** on a B-press, edge-detected and cooldown-gated, only in Fire state:
   - read B (`HARDWARE_JOYSTICK1_RAW & 0x2`).
   - if `SMB_MARIO_STATE == 2` **and** B held **and** `SMB_FIRE_LATCH == 0` **and**
     `TIME > SMB_FIRE_COOLDOWN`: pulse the facing-matched activation global
     (`FACING > 0 → SMB_FIREBALL_FIRE_R = 1` else `SMB_FIREBALL_FIRE_L = 1`), set
     `SMB_FIRE_LATCH = 1`, set `SMB_FIRE_COOLDOWN = TIME + 0.5`.
   - **clear the activation globals to 0 every tick** *except* on the firing tick → the pulse is
     naturally one tick wide (next tick the cooldown blocks), so the generator fires exactly once.
   - clear `SMB_FIRE_LATCH = 0` when B is **released** (one fireball per distinct press — faithful
     to SMB; combined with the cooldown it also caps the rate).

## Build & run steps

The SMB W1-1 pipeline (same as prior SMB plans):

1. `blender --background --python wflevels/smb_w1_1/blender_create_smb.py` — regenerate the `.lev`.
2. `task build-level -- smb_w1_1` — [`build_level_binary.sh`](../../wftools/wf_blender/build_level_binary.sh)
   → `.lvl` + `smb_w1_1-standalone.iff`.
3. Verify + screenshot: `task run-debug -- wflevels/smb_w1_1-standalone.iff` (bridge) and/or
   `task run-smb` (interactive).
4. `git checkout` any unrelated `.iff` re-export jitter; commit the new `fireball_template.iff` +
   the two generators are scriptless `.iff`s only if a mesh is emitted (they shouldn't be — no
   mesh).

## Validation

New `tests/verify_smb_fireball.py` (debug bridge, mirrors the existing SMB harnesses):

1. Boot, walk Mario in, force Fire state (`set_mailbox SMB_MARIO_STATE 2`).
2. Inject a B press (`joystick1_raw` bit `0x2`), step, and assert a `Missile` actor appeared —
   count `Generato: AddObject ok` stderr lines (the perf-actor count is pool size, not live
   actors) and/or probe the new actor's `X_POS`/`XSPEED` (should be Mario.X + ~1 and ≈ +12).
3. Flip `SMB_MARIO_FACING` (inject LEFT), fire, assert `XSPEED ≈ −12` and the **left** generator
   fired.
4. Assert the cooldown gates a held button to one missile per 0.5 s, and that the missile despawns
   (`set_mailbox` on its slot → "not found" after `Explosion Delay`).
5. **Screenshot** the fireball in flight to `tests/screenshots/smb_fireball_*.png` (gameplay
   features need a visual capture as proof, not just a passing test).

Regression: the existing power-up blocks, bricks, coin, and Star harnesses must still pass (they
don't touch the new mailboxes; run them individually — back-to-back runs starve the headless
engine, per the power-up-block plan note).

## Risks & gotchas

- **Spawn blocked by Mario.** Mitigated by the forward offset (design step 2). If a fireball still
  fails to appear when Mario faces a wall, that's the pre-check working as intended (no fireball
  into a wall) — not a bug.
- **Cross-room.** Position-writes move the body but not room membership; keep the generators and
  the fireball in Mario's surface room (W1-1 is one surface room — fine). Don't fire across the
  pipe-warp boundary.
- **1-tick ordering / pulse width.** Covered by the every-tick activation-clear + cooldown; if a
  fireball ever double-fires, the pulse is leaking past one tick — check the clear runs
  unconditionally.
- **Non-mesh generator still needs a colspace.** The spawn center comes from the generator's
  colspace; give it a small authored box extent so `GetColSpace().GetCenter()` resolves to its
  position. Confirm a missile actually spawns (not silently zero-sized).
- **Interactive keyboard binding for B.** The bridge test injects the raw bit directly; confirm a
  desktop key is mapped to button B (`0x2`) for hands-on play, or add the binding (follow-up).

## Follow-ups

- **Phase 2 — fireball defeats enemies.** Missile↔Enemy are both `MOBILITY_PHYSICS`
  (CharacterVirtual), so the Jolt contact dispatch likely won't fire (same limitation that made
  enemies use **proximity** to the player). Wire it the same way: the missile broadcasts its
  position to a global, enemies check proximity and set their defeat signal. Reuses the
  stomp/Star enemy-defeat path.
- **Ground bounce.** Real SMB fireballs bounce. Reuse the Star's ground-aware re-launch idiom
  (`COLLISION_NORMAL_Z` consume) on the missile, or give it a small `Object Z Velocity` arc. Polish.
- **Approach B trigger.** If a later mechanic needs *arbitrary runtime velocity* or *concurrent
  bursts from one spawner* (many-projectile patterns, enemy drops at scale), build the
  [`spawn-template` syscall](../investigations/2026-05-26-spawn-template-forth-primitive.md) — the
  design is ready.
- **Fix `wfmut::SpawnActor`** to call `AddObject` (latent editor/bridge spawn bug surfaced by the
  investigation) — independent of this plan.

## Sources

- [Investigation: spawning template actors from script](../investigations/2026-05-26-spawn-template-forth-primitive.md) (Approach A)
- [`generator.cc`](../../wfsource/source/game/generator.cc), [`actor.cc:803`](../../wfsource/source/game/actor.cc) (mesh-gated Jolt body), [`missile.oas`](../../wfsource/source/oas/missile.oas) / [`missile.cc`](../../wfsource/source/game/missile.cc), [`objects.mac`](../../wfsource/source/oas/objects.mac) (COLTABLE)
- [`wflevels/smb_w1_1/blender_create_smb.py`](../../wflevels/smb_w1_1/blender_create_smb.py) — player script + power-up block/template idioms to mirror
- [Mailbox `X/Y/Z_POS` write fix](2026-05-11-mailbox-pos-write-bypasses-jolt.md)
