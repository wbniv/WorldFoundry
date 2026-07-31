# Per-actor `ColSpace` authoring

**Date:** 2026-05-17
**Author:** Will Norris + Claude
**Status:** investigation — proposes follow-up work; partial mitigation already landed.

## TL;DR

`ColSpace` (the actor-level collision bounding box used by both the legacy swept-AABB system and the [Jolt](https://jrouwe.github.io/JoltPhysics/) port) **is** authored per-actor — but via the OAD `Global Bounding Box` field (a `BOX3` baked into the `.lev`'s `_CollisionRectOnDisk` struct), not via the [`PhysicalAttributes::SetColSpace`](../../wfsource/source/physics/physical.hpi) API. The bbox flows into the `PhysicalAttributes` constructor at actor-load time via [`actor.cc:600-631`](../../wfsource/source/game/actor.cc) (`OODMin` / `OODMax` → `Construct` → `_colSpace.SetBox`).

`SetColSpace` itself has had only one caller — [`camera.cc:60`](../../wfsource/source/game/camera.cc), for the camera — since the [first commit](https://github.com/wbniv/WorldFoundry/commit/a2784f6) (see archaeology below). The dead-code purge ([`03211f9`](https://github.com/wbniv/WorldFoundry/commit/03211f9), 2026-04-15, −22,000 LOC) didn't touch it. The Jolt integration ([`b17a7ca`](https://github.com/wbniv/WorldFoundry/commit/b17a7ca), same day) didn't add or remove any callers either. **No `SetColSpace` calls were lost in the Jolt transition.**

What the Jolt transition *did* change is the load-bearingness of `ColSpace`. The legacy swept-AABB collision treated `ColSpace` as event-trigger geometry — overlap fires a collision event the script handles; an inaccurate bbox just makes the event slightly mis-timed, never visibly broken. [`CharacterVirtual`](https://jrouwe.github.io/JoltPhysics/class_character_virtual.html) is a real physics body: its shape is the only thing keeping the actor out of the ground.

Mitigations landed in [`jolt_backend.cc:JoltCharacterCreate`](../../wfsource/source/physics/jolt/jolt_backend.cc) on 2026-05-17:

1. **Capsule shape, Z-up.** Replaced the prior `SphereShape(min(halfExt))` with a [`CapsuleShape`](../../engine/vendor/jolt-physics-5.5.0/Jolt/Physics/Collision/Shape/CapsuleShape.h) sized to fill the authored AABB — `radius = min(halfX, halfY)`, `halfHeight = halfZ - radius`. Wrapped in a [`RotatedTranslatedShape`](../../engine/vendor/jolt-physics-5.5.0/Jolt/Physics/Collision/Shape/RotatedTranslatedShape.h) (90° rotation about +X) to make the cylinder run along ±Z; without this `CapsuleShape` is Y-axis-aligned by default and the character behaves like a sphere of `min(halfX, halfY)` against a Z-up ground (the original "Mario sinks to z=-0.67" symptom).
2. **Fallback for default ColSpace.** If the actor arrives with the `ColSpace::ColSpace()` default `(0,0,0)→(1,1,1)` (which would only happen if an author shipped a level without the `Global Bounding Box` field set — currently impossible via [`wf_blender`](../../wftools/wf_blender/__init__.py), which always exports a derived bbox), substitute a humanoid Physics default of `(-0.5, -0.5, 0) → (+0.5, +0.5, 1.5)` and log a TODO line. Belt-and-braces — should never trigger in practice today.

## Archaeology — Jolt transition and `SetColSpace` history

Sequence of `git log` queries (`git log --all --oneline -S "SetColSpace" -- wfsource/`):

| Commit | When | What it changed about `SetColSpace` / `ColBox` |
|---|---|---|
| [`a2784f6`](https://github.com/wbniv/WorldFoundry/commit/a2784f6) "first commit" | 2026-04-15 | The single existing `SetColSpace` caller (`camera.cc:60`), the `PhysicalAttributes::SetColSpace` declaration in `physical.hp`, and the definition in `physical.hpi` were *all already present* at first commit. `ColSpace::ColSpace()` already defaulted to `(0,0,0)→(1,1,1)`. |
| [`03211f9`](https://github.com/wbniv/WorldFoundry/commit/03211f9) "dead-code: Batch 5" | 2026-04-15 | −22,000 LOC across `gfx/glpipeline`, `console`, `template`, `savegame`, `physics/ode`, `scripting/perl`, etc. Did not touch `SetColSpace` or any `colspace*` files. |
| [`b17a7ca`](https://github.com/wbniv/WorldFoundry/commit/b17a7ca) "physics: integrate Jolt as the WF physics backend (Phases 1–3)" | 2026-04-15 | Added `JoltMakeCharacter()` (calling `JoltCharacterCreate` with `_colSpace.UnExpMin()` / `UnExpMax()`), but added no new `SetColSpace` callers. The existing per-actor `Global Bounding Box` → `Construct` → `_colSpace.SetBox` path was reused as the source of truth. |
| `7af255b` "fix(jolt): defensive guard against body-pool exhaustion" | 2026-04-18 | No `SetColSpace` changes. |

**Conclusion:** the `SetColSpace` story has been flat since first commit — one caller, never touched. The Jolt port did not lose anything. The bug is structural: per-actor bbox authoring exists (via OAD), but `CharacterVirtual` was being handed a `SphereShape(min(halfExt))` regardless of authored shape, and the resulting sphere can't represent a humanoid silhouette.

## Where the bug bites

| Path | Authored bbox source | Pre-2026-05-17 shape | Symptom |
|---|---|---|---|
| Anchored mobility | OAD `Global Bounding Box` (or constructor default if absent) | Bbox used for legacy AABB overlap events only — no physics simulation | None — every committed level pre-SMB |
| Physics mobility (pre-2026-05-17) | OAD `Global Bounding Box` correctly piped to `_colSpace` | `SphereShape(min(halfX,halfY,halfZ))` regardless of actual ratio | Mario at `(-0.33, -0.36, 0)→(0.33, 0.36, 2)` sphere-collapsed to a 0.33m ball; rested with sphere center at z=0.33, actor.pos.z = 0.33 − ctr.z(1.0) = **−0.67** (Mario buried in ground) |
| Physics mobility (post-2026-05-17 fix) | OAD `Global Bounding Box` (unchanged) | Z-up `CapsuleShape` wrapped in `RotatedTranslatedShape` — `radius=min(halfX,halfY)`, `halfHeight=halfZ-radius` | Mario rests with actor.pos.z = 0; visual feet at ground top ✓ |
| `JoltMakeStaticMesh` (statplats) | Mesh verts directly (not ColSpace) | Mesh-shape collider | None |
| Legacy swept-AABB (pre-Jolt) | Same OAD bbox | Bbox used for trigger overlaps; collision response handled by script | Events fire ~where actor visibly is, since the bbox is already authored. Inaccuracy was never load-bearing. |

## Proposed long-term fix

The premise of the 2026-05-17 diagnosis was that "ColSpace is never authored per-actor" — that was **wrong**. ColSpace *is* per-actor (via OAD `Global Bounding Box`, auto-derived by [`wf_blender`](../../wftools/wf_blender/__init__.py) from the Blender mesh AABB at export). The actual fix is just "stop collapsing it to a sphere in `JoltCharacterCreate`", which is what landed today.

So the original (2a) / (2b) / (2c) framing collapses:

- **(2a) authored `wf_ColSpace` OAD field**: already exists as `Global Bounding Box`. No new field needed.
- **(2b) auto-derive from mesh AABB**: already done by `wf_blender` at export time.
- **(2c) hardcoded humanoid default**: shipped today as the fallback for the (practically impossible) case where the authored bbox is still the constructor default. Belt-and-braces only.

What might actually be worth adding later, if the auto-derived bbox proves wrong for stylised actors:

1. **Manual override field** — let an author tighten or loosen `Global Bounding Box` away from the auto-derived visual AABB (e.g. give Mario a forgiving 0.3m radius for "kid-friendly" pixel-perfect platforming).
2. **Shape-type override** — sphere vs capsule vs box, since some actors don't capsule well (Bullet Bill is a horizontal cylinder, Bowser is closer to a box).

## Other potential users of `ColSpace`

`Global Bounding Box` is already authored per-actor for everything; these consumers already see correct values. Listed here only as a check that the new capsule-shape logic in `JoltCharacterCreate` doesn't *break* any of them:

- `actboxor` trigger volumes — use the authored bbox for overlap-event detection; unaffected by character-shape change
- `enemy` / `statplat` walking-area bounds for AI patrol logic — same
- Pickability tests (`ColSpace::ContainsPoint`) in editor / debugger pick-actor flows — same
- Audio falloff distances (currently position-only, but the authored bbox is available if we want to improve)

## Files touched on 2026-05-17

- [`wfsource/source/physics/jolt/jolt_backend.cc`](../../wfsource/source/physics/jolt/jolt_backend.cc) — sphere → Z-up capsule (wrapped in `RotatedTranslatedShape`), + safety-net default substitution for unit-cube case
- [`wflevels/smb_w1_1/blender_create_smb.py`](../../wflevels/smb_w1_1/blender_create_smb.py) — `transform_apply` on the joined Mario body so feet sit at mesh-local z=0
- [`docs/level-building.md`](../level-building.md) — new "Physics-mobility actor authoring rules" subsection

## Open questions

- For non-humanoid actors that don't capsule well (Bullet Bill = horizontal cylinder, Bowser ≈ box, Cheep-Cheep = swimming-orientation capsule), is `CharacterVirtual` even the right primitive? `Mobility = Path` may be the answer for some; for the rest a shape-type override field would help.
- The auto-derived visual-mesh AABB is a tight fit. For platformers it's often desirable to use a *forgiving* hitbox (smaller than the visual silhouette) so jumps feel generous. Worth a `wf_HitboxScale` style field eventually.
- Does the Goomba (`enemy` class, future Physics actor) need the same fix path as Mario, or does the existing OAD `Global Bounding Box` already make him land correctly with the new capsule code? Testing pending.
