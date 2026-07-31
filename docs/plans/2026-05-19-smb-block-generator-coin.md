# SMB `?`-block coin — block-IS-generator + collectible `Gold`

**Status:** Needs user play-test (2026-05-21). Spawn crash fixed — `tests/repro_gold_spawn_crash.py` passes (clean `AddObject ok`, no `terminate`, no ASan abort). All three engine changes landed (bidirectional dispatch `actor.cc:1805`; generator-runs-script `4d4dff8`; Gold class `7bf3de0`). All level wiring done: three `generator` `?` blocks with 3-state Forth self-detect script, `coin_template` as `gold` class. **HUD COINS wired (2026-05-21):** player script syncs per-actor GOLD mailbox (3001) → global mb 70 every tick → HUD "SCORE N" shows coin count. Interactive pickup (Mario walks into coin → disappears + HUD increments) requires user play-test at full frame rate. Coin pickup SFX deferred. See [docs/level-building.md § Creating a new OAD class](../level-building.md#creating-a-new-oad-actor-class) for the Gold spawn-crash trap (stale `.oad` pre-`Gold_KIND`).

**Spawn-crash history:** the [Jolt-body-sync fix](2026-05-19-template-object-jolt-body-sync.md) (step 0, landed in `0adf1d4`) corrected the spawned coin's Jolt body being built at the parking pos `(-50,0,0)` — that fix stands. But it was **not** the sole cause of the block→coin `terminate`: once the `coin_template` became a `gold` (engine #3), the real abort was the stale-`gold.oad` `MovementClass` default described in the Status line above (a failed `assert`, disguised as `terminate` because the failing `exit()` tore down the still-joinable debug-bridge thread). Fixed 2026-05-21.

## Context

Phase 2 (committed in `0adf1d4`) landed a working coin spawn, but only for the leftmost `?` block, and with the *player* (Mario) doing the detection: Mario's Forth script watched his own `COLLIDER_IDX`, flipped block 0's visibility, and pulsed a global spawn mailbox that a separate Generator consumed. Blocks 1 & 2 had no coin wiring.

User's redesign — **the block owns the coin spawn, not the player.** Each `?` block becomes a **single self-contained actor** that:

1. **Is a `Generator`** (class change from `StatPlat`) with a block mesh + solid collision. Semantically correct: a `?` block literally *is* a thing that generates a coin.
2. **Self-detects** the bump-from-below (reads its *own* collision mailboxes), so no player routing, no "which block" disambiguation, no per-block global mailboxes.
3. **Swaps its own material gold→tan** (qbert-style per-face color override) — one block, no second co-located statplat.
4. **Pulses its own per-actor activation mailbox**, which `Generato::update` consumes to throw one `coin_template`.

This collapses the whole Phase-2 player-side machinery: Mario's script loses all block/coin logic, the `_used` statplat disappears, and the per-block `NORMAL`/`USED`/`COIN_SPAWN` *global* mailboxes go away (replaced by material swap + per-instance local mailboxes).

It also upgrades the behavior to the **arcade-faithful multi-coin brick**: the first bump-from-below opens a 4-second window and spawns a coin; every bump within the window spawns another; when the window closes the block turns tan and is permanently spent (until level reset). Modeled as a 3-state machine (NORMAL → ACTIVE → USED) entirely inside the block's own script — see the block-script design below.

**Stance on engine gaps (user directive):** block-as-generator "certainly SHOULD work, and if it doesn't, that's a deficiency we have to fix." So engine limitations surfaced during execution get **fixed at the root**, not worked around (`feedback_root_cause_not_symptom`).

### Verified mechanisms (Explore pass)

- **Struck body is NOT notified under Jolt.** `JoltContactDispatch` (`actor.cc:1754-1763`) only calls `Collision()` on the *character* (Mario); the struck body is resolved (`FindActorForBodyID`) but never notified. The legacy bidirectional path (`collision.cc:513-520`) is skipped whenever either party is a Jolt character (Mario always is). → **Engine change #1 required** (below).
- **`Generato::update` early-returns when idle**, skipping `Actor::update()` (the script). A block-generator's detect-script wouldn't run while idle. → **Engine change #2 required**.
- **Material swap exists:** `EMAILBOX_FACE_COLOR_TOP/LIT/SHADOW` (mailboxes 3037/3038/3039) take a packed `0xRRGGBB`; `Actor::WriteMailbox` (`actor.cc:1555-1577`) calls `_renderActor->SetMaterialColor(idx, color)`. Per-material-index (0/1/2); re-assert each tick to persist. Qbert drives these via `write-actor-mailbox` (`blender_create_qbert.py` ~2998).
- **Generator inherits `actor.inc`** (`generator.oas:11`) → can have Model Type=Mesh, collision box, Mobility, and a `wf_Script`. `Activation MailBox` accepts 0–3999, so a **per-actor local slot (2000+)** is valid — the block pulses its *own* activation, no global needed.
- **Statics register for actor lookup** via `JoltBodySetActor` (`actor.cc:570,737`), so once the block-generator is a solid static body, `FindActorForBodyID` resolves it for dispatch.

### Standing directive — level-designer's-guide updates during execution

Touches level authoring + engine collision semantics. Per `feedback_level_plans_log_to_designer_guide`, log any gotcha/technique **immediately when discovered**, not batched:
- Symptom + workaround → [`docs/level-design-troubleshooting.md`](../../docs/level-design-troubleshooting.md).
- New convention/technique → [`docs/level-building.md`](../../docs/level-building.md).

Likely entries: **bidirectional Jolt collision now notifies the struck body**; **block-IS-generator idiom** (solid mesh + collision + self-detect script + own activation mailbox); **per-face material swap to express block state** (replaces co-located visibility-toggle statplats); **Generator runs its `wf_Script` every tick** (post-fix).

---

## Design

### Engine change #1 — bidirectional collision dispatch

`JoltContactDispatch` (`wfsource/source/game/actor.cc:1754-1763`): after notifying the character, also notify the struck body so its per-actor collision mailboxes (`COLLIDER_IDX` 3044, `COLLISION_NORMAL_*` 3045-3047) populate:

```cpp
if (Actor* otherA = static_cast<Actor*>(otherActor)) {
    charA->Collision(*otherA, normal);
    otherA->Collision(*charA, normal);   // sign of normal for the struck body: confirm empirically
}
```

The normal sign as seen by the block (hit-from-below) is confirmed via the existing `Actor::Collision` debug fprintf during step (verify): Mario bumping up reads `normal.Z > 0`; the block should read the opposite. If it needs negating, pass `-normal` to `otherA`. The block's detect gate uses whichever sign the dispatch actually delivers for "struck from below."

### Engine change #2 — Generator runs its script every tick

**Why the early-return exists (investigation):** the idle branch's load-bearing behavior is the **timer reset** (`_timeToGenerate = now`). Per the in-code `// kts added 4/9/96 ... prevent over-generation` intent, pinning the timer to "now" while the activation mailbox is 0 means that on *re-activation* the generator fires one object immediately rather than a catch-up burst for all the idle time (the `while (_timeToGenerate < now) _timeToGenerate += delay` fast-forward loop handles the still-active case). The `return` itself is **not** the optimization — it's just an idle short-circuit whose side effect happens to skip `Actor::update()` (and thus the `wf_Script`).

> Note (corrected): an earlier draft claimed generators "historically had no meaningful script." That is **unverified** — the only Generator-class actor in any `.lev` in this repo is the SMB one added in Phase 2, so there's no historical instance to examine. The defensible statement is just: skipping `Actor::update()` is incidental to the idle short-circuit, and running it unconditionally restores parity with every other Actor subclass. Whether any out-of-repo WF level relied on a generator script is unknown; if such a level exists, this change *helps* it (its script would start running while idle), it doesn't break it.

**Keep the optimization, drop the side effect.** Preserve the timer reset; remove the `return`; call `Actor::update()` unconditionally:

```cpp
void Generato::update() {
    if (theLevel->LevelClock().Current() >= _timeToGenerate) {
        if (GetMailboxes().ReadMailbox(_generateMailBox) != Scalar::zero) {
            ... existing spawn body (FIRING / ConstructTemplateObject / AddObject) ...
        } else {
            _timeToGenerate = theLevel->LevelClock().Current();   // keep the reset; was: reset + return
        }
    }
    Actor::update();   // always runs — the block's detect script lives here
}
```

The only behavior change for existing generators is that their `wf_Script` now runs every tick — which is exactly what every *other* Actor subclass already does (`Actor::update` at `actor.cc:935-943`); generators were the anomaly. The anti-burst guarantee is unchanged.

Frame ordering that makes the one-tick pulse work: `Generato::update` reads activation at the top (spawn check), then `Actor::update()` runs the script at the end. So tick N: spawn-check sees 0 (no spawn) → script detects bump, sets activation=1. Tick N+1: spawn-check sees 1 → spawns coin → script clears activation=0 (clear-before-set latch). Tick N+2: 0.

#### Coin-count control — one coin per bump, bounded by the 4 s window

Four layers, none weakened by engine-change #2. (This is *not* single-shot — the block legitimately emits multiple coins; the layers ensure exactly **one coin per distinct bump**, and **no coins outside the active window**.)

1. **Idle-reset (preserved verbatim):** while `activation == 0`, `_timeToGenerate = now` each tick pins the timer to the present, so a wait between bumps never accumulates a backlog to "catch up" on. The 1996 anti-over-generation behavior, kept exactly.
2. **One-tick pulse (one coin per bump):** the block raises `activation` for exactly one tick per bump and clears it the tick after the generator reads it. Within one `Generato::update`, spawn-check (top) and clear (in `Actor::update`, bottom) are sequential — no race — so each pulse yields exactly one spawn. **Load-bearing on this dev box** (dt≈1 s ≫ the 0.1 s generation period): if `activation` were ever held high, the fast-forward loop would emit one coin per tick (a stream). The one-tick clear prevents that.
3. **4 s window via DIE time (multi-coin phase bound):** coins are only pulsed while `now < DIE` (where `DIE = first_hit + 4.0`, set once). The window opens on the first bump and is *not* extended by later bumps (DIE is fixed at first hit). Each bump inside the window pulses one coin; bumps outside it do nothing.
4. **USED latch (terminal cap):** when `now ≥ DIE` the block sets `SMB_QBLOCK_USED`, swaps to tan, and the detect branch is gated off for the rest of the level (until reset). No coin can be pulsed after the window closes.

The `while (_timeToGenerate < now) _timeToGenerate += delay` fast-forward loop is untouched and still guards the held-active case.

**Per-distinct-bump guarantee** rests on the edge-only `OnContactAdded` dispatch (Phase-2 fix): `COLLIDER_IDX` is set only on the tick a *new* contact forms, so Mario must separate and re-jump to score each coin — staying pressed against the block does not stream coins.

### Engine change #3 — `Gold` collectible class

The spawned coins ARE the collectibles, so `coin_template` becomes a new `Gold` actor class backing the existing [`gold.oas`](../../wfsource/source/oas/gold.oas) stub (today `TYPEHEADER(Gold,Gold)` with **no backing C++ class**).

**Wiring (verified):**
- **Enum:** add `Gold_KIND` to [`wfsource/source/oas/objects.es`](../../wfsource/source/oas/objects.es) (the codegen source; `objects.h`/`objects.e` are generated — `objects.e` header says "created from object.es, DO NOT MODIFY"). Append after `Alias_KIND` so existing kind values don't renumber.
- **Factory:** wire the `Gold` case into the OAS object factory ([`objects.c`](../../wfsource/source/oas/objects.c) switch on `EActorKind`, mirroring `Generator_KIND`/`Spike_KIND`).
- **New TU** `wfsource/source/game/gold.{hp,cc}`, modeled on the minimal `spike`/`target` subclasses: `class Gold : public Actor`, `kind()` returns `Gold_KIND`, plus the `Collision` override below.

**Behaviour** — `Gold::Collision(PhysicalObject& other, const Vector3& normal)`:
```cpp
if (other.kind() == Actor::Player_KIND) {
    // value = 1 hardcoded (no new OAS field, feedback_no_new_oas_fields_premerge);
    // per-actor GOLD mailbox (3001) is the long-term per-coin value home.
    Mailboxes& pm = static_cast<Actor&>(other).GetMailboxes();
    pm.WriteMailbox(INDEXOF_GOLD, pm.ReadMailbox(INDEXOF_GOLD) + Scalar::one);
    // tiny poof: throw an Explode template (optional — can land after first cut). SFX deferred.
    SetPendingRemove();
}
Actor::Collision(other, normal);
```
- **Running total = the *player's* own per-actor `GOLD` mailbox (3001)** — reuses reserved infra, **zero new global mailboxes**. HUD reads the player's `GOLD` (render via `DrawHud`; reuse qbert's mb-70 score-line pattern — verify SMB HUD setup during execution).
- **Pickup detection rides engine change #1** (bidirectional dispatch): without the struck body being notified, the coin never learns Mario touched it. Same fix, two consumers (block self-detect + coin pickup).
- **Do NOT revive the old gold economy** (`tool.cc:225` "Tools now free because gold is gone", echoed `toolshld.cc:49`) — this is fresh collectible behaviour filling the stub, not the old tool-charging economy.
- Despawn is **pickup-driven**; uncollected-coin lifetime is a minor open item (for the 3-block demo, coins arc + land + remain collectible; add a self-remove timer if they accumulate).

### Block actor = Generator (`wflevels/smb_w1_1/blender_create_smb.py`)

Replace the `add_statplat` `?`-block(s) + the separate `coin_spawner` + the `_used` statplat with **one Generator per block**. Driven off `QBLOCK_XS` so all three are identical:

```python
for i, bx in enumerate(QBLOCK_XS):
    blk = <new generator actor with block mesh>           # gold ? mesh, solid collision box
    blk.location = (bx, 0, BLOCK_Z)
    attach_schema(blk, 'generator')
    blk['wf_Mobility']        = 'Anchored'
    blk['wf_Model Type']      = 'Mesh'                     # visible + collidable
    blk['wf_Mesh Name']       = 'qblock.iff'              # shared ? block mesh, ≥1 material slot
    blk['wf_Object To Throw']    = 'coin_template'
    blk['wf_Object Z Velocity']  = 8.0
    blk['wf_Generation Rate']    = 10.0                   # effective one-shot per pulse
    blk['wf_Activation MailBox'] = MB_SMB_QBLOCK_ACTIVATE # per-actor LOCAL slot (e.g. 2010)
    blk['wf_Script']             = QBLOCK_SCRIPT          # below
```

The block mesh should have the material slot(s) that `FACE_COLOR_*` overrides target (verify slot count; if 1 slot, write `FACE_COLOR_TOP` only; if 3, write all three for shaded top/lit/shadow like qbert). Gold is the authored base; tan is the runtime override.

**Block behavior — SMB multi-coin brick (3-state machine).** Arcade-faithful: the *first* bump-from-below starts a 4-second window and spawns a coin; *every* bump within that window spawns another coin; when the window expires the block flips ? → tan and is permanently dead (until level reset). State is tracked by two per-actor locals (`SMB_QBLOCK_DIE` = level-time at which the window closes, i.e. `first_hit + 4.0`; `0` = not yet hit; `SMB_QBLOCK_USED` = 1 = dead):

- **NORMAL** (`DIE==0`, `USED==0`): gold ?, never hit. On bump-from-below → set `DIE = now + 4.0`, pulse a coin.
- **ACTIVE** (`DIE!=0`, `USED==0`): gold ?, window running. Each tick: if `now ≥ DIE` → swap material to tan, set `USED=1`. Else, on bump-from-below → pulse a coin.
- **USED** (`USED!=0`): tan, dead. Re-assert tan; ignore bumps.

Storing the **die time** (computed once, `now + 4.0`, at first hit) keeps the hot path a bare comparison (`DIE > now`) instead of recomputing `now - start` every tick.

**Block `wf_Script`** (per-instance; same string for all three — uses only local + self mailboxes). Stack-juggling pattern (`… read-mailbox dup 0= if drop … else … then`) mirrors the coin template's suicide script, already proven working this session:

```forth
\ wf
INDEXOF_SMB_QBLOCK_USED read-mailbox 0<> if
  0x<tan> INDEXOF_FACE_COLOR_TOP write-mailbox             ( USED: keep tan asserted; + LIT/SHADOW if 3-material )
else
  \ clear last tick's activation pulse (clear-before-set one-tick latch)
  INDEXOF_SMB_QBLOCK_ACTIVATE read-mailbox 0<> if
    0 INDEXOF_SMB_QBLOCK_ACTIVATE write-mailbox
  then
  INDEXOF_SMB_QBLOCK_DIE read-mailbox dup 0= if
    drop                                                    ( NORMAL: not yet hit )
    INDEXOF_COLLIDER_IDX read-mailbox 0<> if
      INDEXOF_COLLISION_NORMAL_Z read-mailbox <sign> if     ( hit-from-below; sign confirmed empirically )
        INDEXOF_TIME read-mailbox 4.0 + INDEXOF_SMB_QBLOCK_DIE write-mailbox   ( die = now + 4 s )
        1 INDEXOF_SMB_QBLOCK_ACTIVATE write-mailbox                             ( spawn first coin )
      then
    then
  else                                                      ( ACTIVE: stack holds DIE )
    INDEXOF_TIME read-mailbox > if                          ( DIE > now : window still open? )
      INDEXOF_COLLIDER_IDX read-mailbox 0<> if              ( still active: each bump spawns )
        INDEXOF_COLLISION_NORMAL_Z read-mailbox <sign> if
          1 INDEXOF_SMB_QBLOCK_ACTIVATE write-mailbox
        then
      then
    else                                                    ( now >= DIE : window over )
      0x<tan> INDEXOF_FACE_COLOR_TOP write-mailbox          ( swap to tan )
      1 INDEXOF_SMB_QBLOCK_USED write-mailbox               ( latch dead )
    then
  then
then
```

(`DIE now >` → `DIE > now`, true while the window is open.) `SMB_QBLOCK_USED`, `SMB_QBLOCK_ACTIVATE`, `SMB_QBLOCK_DIE` are **per-actor local** mailboxes — every block-generator instance has its own copy, so the *same* names serve all three blocks with no cross-talk and **zero new global mailboxes**. Uses absolute `INDEXOF_TIME` (not dt accumulation) per `feedback_timing_in_seconds_not_ticks` — robust to the dev box's ~1 s/tick.

**Per-hit edge semantics:** with the edge-only `OnContactAdded` dispatch (Phase-2 fix), each *distinct* bump (Mario separates and re-jumps into the block) re-sets `COLLIDER_IDX` for one tick → one coin. Holding against the block does not re-fire. Exactly SMB.

### Coin template — becomes a `Gold` collectible

`coin_template`'s class changes **`Missile` → `Gold`** (engine change #3 below). It keeps `Mobility = Physics` (gravity arc out of the block) and the yellow disc mesh. The old Forth `INDEXOF_TIME`/`SMB_COIN_ELAPSED` suicide script is **deleted** — despawn is now pickup-driven inside `Gold::Collision` (`SMB_COIN_ELAPSED` (2000) frees up). All three block-generators throw it.

> Supersedes the earlier "use Missile auto-explode for despawn" note: with the class now `Gold`, despawn is pickup-driven, not timer-driven. (The Missile auto-explode insight stands as the right call *for a Missile* — it's just moot once the coin is a collectible.)

### Mario's script — strip block/coin logic

`player['wf_Script']` reverts to just the joystick→INPUT merge + the `X_POS → SMB_PLAYER_X` scroll broadcast. All `SMB_QBLOCK_*` reads/writes and the bump-detection branch are removed.

### Mailboxes (`wfsource/source/mailbox/mailbox.inc`)

- **Remove** the now-unused globals `SMB_QBLOCK_0_NORMAL` (1803), `SMB_QBLOCK_0_USED` (1804), `SMB_QBLOCK_0_COIN_SPAWN` (1805) — visibility-toggle is replaced by material swap; activation is now per-actor local.
- **Add** three per-actor LOCAL named constants (2000-2099 range; per `feedback_named_mailbox_constants`): `SMB_QBLOCK_ACTIVATE` (e.g. 2010, generator pulse), `SMB_QBLOCK_USED` (e.g. 2011, terminal-dead flag), `SMB_QBLOCK_DIE` (e.g. 2012, window-close level-time).
- **Remove** `SMB_COIN_ELAPSED` (2000) — the coin's suicide script is deleted (despawn is pickup-driven now).
- Gold pickup count reuses the **player's existing per-actor `GOLD` mailbox** (3001) — no new global.
- Net: **zero new global mailboxes**; three `SMB_QBLOCK_0` globals + `SMB_COIN_ELAPSED` removed.

## Implementation steps

1. **Engine #1** — bidirectional dispatch in `actor.cc` `JoltContactDispatch`.
2. **Engine #2** — `generator.cc` `Generato::update` always calls `Actor::update()`.
3. **Engine #3** — add `Gold_KIND` to `objects.es`, wire the factory in `objects.c`, add `gold.{hp,cc}` (`Gold : public Actor`, `kind()`, `Collision` → credit player's `GOLD` mailbox + `SetPendingRemove`).
4. **`mailbox.inc`** — remove the 3 `SMB_QBLOCK_0` globals + `SMB_COIN_ELAPSED`; add `SMB_QBLOCK_ACTIVATE` + `SMB_QBLOCK_USED` + `SMB_QBLOCK_DIE` locals.
5. **`blender_create_smb.py`** — block-as-generator per `QBLOCK_XS` (gold mesh, solid, self-detect/material-swap/pulse script); change `coin_template` class `Missile`→`Gold` and drop its suicide script; strip Mario's block/coin logic; ensure the HUD renders the player's `GOLD` count.
6. **Rebuild engine** — `WF_ENABLE_EDITOR=1 task build` (→ `engine/wf-edit`) or `engine/build_game.sh`.
7. **Rebuild level** — `(cd wflevels/smb_w1_1 && blender --background --python blender_create_smb.py)` then `wftools/wf_blender/build_level_binary.sh smb_w1_1` + iffcomp standalone.
8. **Verify bidirectional collision** — with the existing `Actor::Collision` fprintf, bump a block and confirm BOTH Mario and the block log a `Collision`, and read off the block's `COLLISION_NORMAL_Z` sign to lock the script's hit-from-below gate.
9. **Verify multi-coin window + swap** — drive Mario into each of the 3 blocks from below: (a) first bump spawns a coin + stays gold; (b) repeated bumps within ~4 s each spawn another; (c) after the window flips gold→tan (USED latch); (d) coins arc + are collectible. Screenshots per `feedback_screenshots_for_proof`. (1 fps dev box makes the 4 s window only a few ticks wide — fine for logic; full cadence needs a normal-frame-rate run.)
10. **Verify pickup** — Mario touches a coin → it vanishes (poof), the player's `GOLD` count increments by 1, HUD updates. Screenshots.
11. **Regression** — Mario moves/jumps with the stripped script; `--debug-print-actors` returns to baseline after coins despawn (no leak); engine changes don't regress snowgoons (smoke).
12. **Tear down** Phase-2 + new debug fprintfs (generator.cc/missile.cc/level.cc/actor.cc/gold.cc) in one commit, once visually signed off (`feedback_debug_instrumentation_teardown`).
13. **Commit** per phase (`feedback_commit_after_each_phase`).

## Critical files

- `wfsource/source/game/actor.cc` — `JoltContactDispatch` bidirectional notify (engine #1).
- `wfsource/source/game/generator.cc` — `Generato::update` always-run-script (engine #2).
- `wfsource/source/oas/objects.es` + `objects.c` — `Gold_KIND` enum + factory case (engine #3).
- `wfsource/source/game/gold.{hp,cc}` — new `Gold` collectible class (engine #3).
- `wfsource/source/mailbox/mailbox.inc` — drop 3 globals + `SMB_COIN_ELAPSED`, add 3 locals.
- `wflevels/smb_w1_1/blender_create_smb.py` — block-as-generator, material-swap script, coin→Gold, Mario script strip, HUD gold count.
- Regenerated: `wflevels/smb_w1_1/smb_w1_1.{lev,lvl,iff.txt,ini}`, `wflevels/smb_w1_1.iff`, `wflevels/smb_w1_1-standalone.iff`, block/coin `.iff` meshes.

## Risks / "deficiency → fix" items

- **Generator-as-solid-visible-block** — confirm a Generator with Model Type=Mesh + collision actually renders + creates a static Jolt body (registered via `JoltBodySetActor`). If a Generator suppresses rendering/collision anywhere, that's a deficiency to fix (per user), not route around.
- **Bidirectional dispatch side-effects** — notifying the struck body might affect other actors' scripts that read `COLLIDER_IDX` (e.g. enemies). Snfrom-regression smoke in step 9; gate the new call narrowly if needed.
- **Material swap on the block mesh** — verify the `?` block mesh's material-slot count so `FACE_COLOR_*` targets land; if the mesh is single-material, only `FACE_COLOR_TOP` is needed.
- **zForth signs/words** — confirm the hit-from-below comparison word (`<`/`0<` vs `>`/`0>`) exists and the per-instance local mailbox reads/writes behave; the script uses only already-proven words (`0<>`, `read/write-mailbox`, `if/then`) plus one inequality.
- **Frame ordering of the one-tick pulse** — confirm spawn-check-then-script ordering inside `Generato::update` yields exactly one coin (no double-fire, no miss). Covered by step 8.

## Deferred — spec'ed, not in this plan

- **Coin pickup SFX** (the poof's sound) — spec'ed, deferred by user. The `SOUND` mailbox (3017) already works (`actor.cc:1357,1650`), so it's a one-line add in `Gold::Collision` whenever wanted.

## Out of scope

- A Forth `spawn-template` primitive (block-as-generator may make it unnecessary).
- Bricks / multi-coin blocks beyond the three `?` blocks.
