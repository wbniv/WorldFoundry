# Actor `kind` vs. capability vs. role — what `EActorKind` is conflating

**Status:** **Discussion / design exploration — no implementation.** Argue this on paper before any code moves; the SMB block-generator plan and the two built engine changes (#1 bidirectional collision, #2 generator-runs-script) stay where they are.
**Owner:** Claude + Will (thinking together)
**Date:** 2026-05-20
**Branch:** `2026-new-level`

## How we got here

Tracing why [`gold.oas`](../../wfsource/source/oas/gold.oas) is a class-less stub turned up a real `Gold : public Actor` in the pre-git CVS era (copyright 1995–99, in CVS 2000-02-12), **deleted 2002-10-31** by `kts` with the log *"finished removal of gold object type"* (`Attic/gold.cc,v` in the [SourceForge `wf-gdk` snapshot](https://sourceforge.net/code-snapshots/cvs/w/wf/wf-gdk.zip)). By its last live revision the whole class was:

```cpp
void Gold::update() {
  while (msgPort.GetMsgByType(SPECIAL_COLLISION, ...)) {
    if (Activated(...)) {                          // was it the activating actor?
      if (theLevel->_sfx[1]) SetMailbox(EMAILBOX_SOUND, 1);
      theLevel->SetPendingRemove(this);            // despawn
    }
  }
  Actor::update();
}
```

A C++ translation unit for "on collision, play a sound, despawn." The gold *economy* (player `numGold()`/`removeGold()`, tool/shield `ActivationCost`, enemy `NumberOfGold` drops, the player "Initial Gold" property) was gutted in the same era and survives only as `#if 0` blocks and a `#pragma message("...gold is gone")` in [`tool.cc:225`](../../wfsource/source/game/tool.cc) / [`toolshld.cc:49`](../../wfsource/source/game/toolshld.cc). Removal rationale (Will): *"the thinking was just to do what's needed in the script."*

That decision — *a thin concrete subclass doesn't earn its keep; push it to data + script* — is the seed of this whole question.

## The reframing

Today **one mechanism — "which `Actor` subclass is this?" (`Actor::kind()` → `EActorKind`)** — is forced to answer three unrelated questions:

1. **What can it do? (capability / verb)** — move, take damage, heal, emit sound. Cross-cutting; many kinds share each.
2. **Whose side is it on / what is its agency? (role)** — player-controlled (PC) vs AI (NPC), collectible vs hazard, friend vs foe.
3. **What concrete thing is it? (entity / prefab)** — gold, enemy, missile, spike. Ideally *nothing but* a named bundle of (1) + (2) + data.

(1) and (2) are abstract and composable. (3) is concrete and should be **assembled from** them, not run parallel to them.

## What WF *already* does about it (and does well)

The key insight: WF is **not** missing composition. It already has three mechanisms that factor the capability layer out of `kind()`:

| Axis | Mechanism | Evidence |
|------|-----------|----------|
| **Movement** (verb) | `MovementHandler` strategy hierarchy, composed onto Actor via `_movementManager` | `movement.hp:67` base + `GroundHandler`/`AirHandler`/`ClimbHandler`/`MarbleHandler`/`NullHandler`; `FollowHandler` ([`movefoll.hp:18`](../../wfsource/source/movement/movefoll.hp)), `PathHandler` ([`movepath.hp:55`](../../wfsource/source/movement/movepath.hp)). Held at [`actor.hp:239`](../../wfsource/source/game/actor.hp). |
| **Effects** (damage/heal/sound) | `MSG_TYPE` message bus — capabilities as data-driven messages | [`msgtypes.hp`](../../wfsource/source/baseobject/msgtypes.hp): `DELTA_POWER`, `DELTA_HEALTH`, `DELTA_SHIELD`, `MOVEMENT_FORCE_{X,Y,Z}`, `PLAY_SOUND_EFFECT`, `COLLISION`, `SPECIAL_COLLISION`. |
| **State / scripting** | Per-actor mailboxes | `mailbox.inc`; the entire Forth scripting surface. |

So the **capability/verb layer (1) is in good shape** — it's already strategies + messages + mailboxes, not subclass code. `MovementHandler` is the proof-of-concept that a cross-cutting capability *can* live outside `kind()` cleanly and without RTTI.

What is **not** factored out:

- **The role layer (2) has no clean home.** PC/NPC, collectible/hazard, friend/foe are smeared across `EActorKind`, the collision tables, and per-script convention.
- **`EActorKind` is overloaded across all three axes at once.** The flat enum ([`objects.mac:21-52`](../../wfsource/source/oas/objects.mac)) mixes:
  - *infrastructure that isn't a game "thing"* — `Room`, `Camera`, `Light`, `Director`, `CamShot`, `Shadow`, `Matte`, `Disabled`, `Alias`,
  - *roles* — `Player`, `Enemy`,
  - *concrete prefabs* — `Gold` (was), `Missile`, `Spike`, `Explode`, `Tool`, `Shield`, `StatPlat`, `Platform`, `Generator`.
- **Many concrete prefabs are thin nouns.** [`Spike`](../../wfsource/source/game/spike.hp) is ctor + `~dtor` + `update()` + `kind()` + `getOad()` + one `Activation` member — the same shape as deleted `Gold`. These barely justify a TU.
- **There's a precedent for deleting kinds wholesale.** `objects.mac` carries a graveyard of commented-out `OBJECTENTRY`s — `Continue`, `Movie`, `Meter`, `Handle`, `Merged`, `Font`, `Pole`, `File`, `Dir` — plus the Gold deletion. Kinds come and (often) go.

There's even a **nascent capability/role taxonomy already encoded as data** in the object-list macro arguments: the `collidable` flag (2nd arg), `OBJECTNOACTORENTRY` (never gets an Actor — `Room`, `Disabled`, `Alias`), `OBJECTONLYTEMPLATEENTRY` (template-only — `Missile`, `Explode`, `Shield`), and `OBJECTSUBENTRY` (derives from a parent). It's ad hoc and incomplete, but it's the right idea pointing in the right direction.

## Hard constraint: no RTTI

We just [eliminated all `dynamic_cast`](../plans/2026-04-29-eliminate-rtti.md) and turned on `-fno-rtti` — load-bearing on the fixed-point MCU targets. **Any role/capability query must be a data test (flag, mailbox, handler-present), never a cast.** This actively *favors* the composition/flag direction over a deeper virtual role-hierarchy, which would want `dynamic_cast` to ask "is this a Damager?" The `MovementHandler` model already shows the RTTI-free way: ask the Actor for its handler, don't cast the Actor.

## Options

### A — Name it, don't move it (doc-only)
Define the vocabulary (*infrastructure kind* / *role* / *capability* / *concrete prefab*), group `EActorKind` accordingly, annotate the OAS. Resolves the **nomenclature** half; structure unchanged.
*Cost:* ~hours. *Risk:* none. *Leaves:* the structural conflation.

### B — Lean into data-driven; delete thin prefab-kinds
The Gold story *is* the argument. A kind that's just "on collision, do X, despawn" goes to OAS + Forth on a generic Actor; `Spike`/`Target`/`Gold`-tier classes become prefabs (mesh + OAS + script), not TUs. Engine keeps only true primitives. Matches the engine's own 2002 vote and the current [block-is-generator](../plans/2026-05-19-smb-block-generator-coin.md) work.
*Cost:* per-class; incremental. *Risk:* pushes logic into Forth → wants good script ergonomics + the [deferred DAP debugger](../plans/2026-05-19-engine-mutation-api.md). *Leaves:* infrastructure + role kinds as classes (correctly).

### C — Generalize `MovementHandler` into capability-handlers
Make `Damageable`/`Healable`/`Collectible`/`Damager` first-class composable handlers attached by OAS flag, exactly as movement already is. Concrete "type" = a recipe of handlers + data. Queried by *which handlers are present*, never by cast.
*Cost:* real engineering. *Risk:* over-build if most behaviors are one-liners better left to script (see B). *Not* a full ECS — that's the wrong scale for a port.

### D — Split the axes with a capability/role bitset
Keep concrete subclasses but promote the macro-arg taxonomy into an explicit per-kind capability/role bitset (data): "is this a damager / NPC / collectible / collidable / template-only?" becomes a flag test. Lighter than C; kills the worst of the `EActorKind` overloading; finishes what the `collidable`/`NOACTOR`/`ONLYTEMPLATE` args started.
*Cost:* moderate. *Risk:* low. *Leaves:* the thin-class proliferation (compose with B).

## Recommendation

These aren't exclusive. The shape that fits the evidence:

1. **A first, cheaply** — agree on the words (*infrastructure / role / capability / prefab*) and write them into the OAS + a short `docs/` note. Most of the pain is that the distinction is unnamed.
2. **D for the role/identity gap** — formalize the macro-arg flags into a real capability/role bitset, RTTI-free, so "collectible?", "NPC?", "damager?" are data. This is the piece that genuinely has no home today.
3. **B for the thin prefab-kinds, opportunistically** — when a kind is just collision→effect→despawn, delete the TU and express it as OAS + Forth (Gold is the canonical case; engine-change #3 of the SMB plan is literally re-deleting it the right way).
4. **C only where a behavior is genuinely shared, stateful, and too heavy for script** — and even then, model it on `MovementHandler`, not on a new inheritance tree.

The throughline: **the capability layer is already composed (movement handlers + messages + mailboxes); the role layer should join it as data; and the concrete layer should shrink toward prefabs.** `kind()` should end up meaning only "infrastructure object vs. assembled game prefab," not doing the work of all three.

## Open questions

- Is the right home for the role bitset the OAS object-list macro (extending the `collidable` precedent), or a separate per-actor field? (Watch the [no-new-OAS-fields-before-first-level constraint](../plans/2026-05-19-smb-block-generator-coin.md) — enum/flag extensions to the existing macro args are cheaper than new fields.)
- Which current `EActorKind`s are *infrastructure* (keep as class), *role* (keep, but tag), or *thin prefab* (candidate for B)? A one-time triage of [`objects.mac`](../../wfsource/source/oas/objects.mac) would make B concrete.
- Does the collision table (`COLTABLEENTRY` in [`objects.es`](../../wfsource/source/oas/objects.es)) already encode role pairings ("PC × hazard → damage") that a role bitset would subsume or duplicate?

## References

- Deleted `Gold` class — `Attic/gold.{cc,hp},v`, `oas/Attic/gold.oas,v` in the [`wf-gdk` CVS snapshot](https://sourceforge.net/code-snapshots/cvs/w/wf/wf-gdk.zip) (unzipped at `~/tmp/wf-gdk-cvs/`); deletion rev 1.4, 2002-10-31, `kts`.
- The general pattern: [composition over inheritance](https://en.wikipedia.org/wiki/Composition_over_inheritance), the game-dev migration from deep actor trees to [entity-component systems](https://en.wikipedia.org/wiki/Entity_component_system) (cf. [Unity](https://docs.unity3d.com/Manual/GameObjects.html) `GameObject`/`Component`, [Unreal](https://dev.epicgames.com/documentation/en-us/unreal-engine/components-in-unreal-engine) `Actor`/`Component`), and Mick West's [*Evolve Your Hierarchy*](https://cowboyprogramming.com/2007/01/05/evolve-your-heirachy/).
- WF's existing composition: `MovementHandler` ([`movement.hp:67`](../../wfsource/source/movement/movement.hp)), `MSG_TYPE` ([`msgtypes.hp`](../../wfsource/source/baseobject/msgtypes.hp)), the kind enum source ([`objects.mac`](../../wfsource/source/oas/objects.mac)).
- [Eliminate-RTTI plan](../plans/2026-04-29-eliminate-rtti.md) — the `-fno-rtti` constraint this design must respect.
- [SMB block-generator + Gold plan](../plans/2026-05-19-smb-block-generator-coin.md) — the active work that surfaced this.
