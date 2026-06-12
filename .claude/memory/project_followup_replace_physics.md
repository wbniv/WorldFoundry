---
name: project_followup_replace_physics
description: Replace WF's custom physics layer with Jolt Physics — chosen engine, integration status, open work items
metadata:
  type: project
---

Replace WF's hand-rolled physics layer with **Jolt Physics** (MIT, C++17, `CharacterVirtual`, full constraint set). Decision made 2026-04-14 after surveying Jolt/Bullet/ReactPhysics3D/PhysX; Jolt chosen for CharacterVirtual quality, determinism, and active maintenance (Guerrilla Games ships it).

**Why:** WF's physics contains at least one bad `reinterpret_cast` in `BungeeCameraHandler / SPECIAL_COLLISION` (`movecam.cc:1007`). Rather than patch the custom solver, replace it wholesale.

**Integration status (as of 2026-06):** Jolt backend merged and parity-tested on snowgoons (`MOBILITY_PHYSICS` actors use `CharacterVirtual`). The rigid-body path (`gBodies`, pre-Jolt impulse solver in `collision.cc`) is still present but bypassed for CharacterVirtual actors.

**Open work that blocks on this:**
- `MOBILITY_VEHICLE` — Jolt `VehicleConstraint` body for lunar cruisers; CharacterVirtual slide-hack is the current stand-in. See [[Moon Site 01 vehicle physics TODO]].
- Restitution / bounce — Elasticity OAS fields (`movebloc.inc:33`) are dead; CharacterVirtual actors never reach the old impulse solver. Real fix: dynamic-rigid-body mobility opt-in + `mRestitution` wired from Elasticity. See [[no restitution bounce TODO]].
- `CharacterVirtual` substepping — variable dt accumulates error at low frame rates; substepping the Jolt update would fix it.

**How to apply:** When an actor physics behaviour is missing or wrong, check whether it's a CharacterVirtual limitation before patching — the fix may belong in the broader Jolt integration rather than a workaround in the actor script.
