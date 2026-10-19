# Replace WF physics layer with Jolt

**Status:** In progress — Jolt integrated and parity-tested on snowgoons; several open items remain.  
**Decision:** 2026-04-14 — see [physics engine survey](../investigations/2026-04-14-physics-engine-survey.md)  
**Initial integration:** [Finish the Jolt Physics integration](2026-04-16-jolt-physics-finish.md)

---

## Why

WF's hand-rolled physics contains at least one bad `reinterpret_cast` in
`BungeeCameraHandler / SPECIAL_COLLISION` (`movecam.cc:1007`). Patching the custom
solver is not worth the investment — replace it wholesale with **Jolt Physics**
(MIT, C++17, `CharacterVirtual`, full constraint set).

Jolt was chosen over Bullet/ReactPhysics3D/PhysX for:
- `CharacterVirtual` quality (slope, step, ledge, one-way platforms — the hardest
  single problem for a Mario-style game)
- Bit-exact determinism across platforms
- Active maintenance (Guerrilla Games ships it in Horizon Forbidden West)

---

## Current state

- Jolt backend merged; parity-tested on snowgoons.
- `MOBILITY_PHYSICS` actors use `CharacterVirtual`.
- Pre-Jolt rigid-body path (`gBodies`, `collision.cc` impulse solver) still present
  but bypassed for `CharacterVirtual` actors — `Elasticity` OAS fields are dead.

---

## Open work

| Item | Trigger |
|------|---------|
| `MOBILITY_VEHICLE` — Jolt `VehicleConstraint` for lunar cruisers; current CharacterVirtual slide-hack is the stand-in | Second vehicle type, or slide-hack becomes a design blocker |
| Restitution / bounce — wire `Elasticity` OAS fields (`movebloc.inc:33`) into Jolt `mRestitution`; needs dynamic-rigid-body mobility opt-in | Second bouncy actor, or physics-replacement work resumes |
| `CharacterVirtual` substepping — variable dt accumulates error at low frame rates | Visible judder at <30 fps |
