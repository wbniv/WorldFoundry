---
name: project_followup_replace_physics
description: Replace WF physics with Jolt — plan at docs/plans/project_followup_replace_physics.md
metadata:
  type: reference
---

Plan: `docs/plans/project_followup_replace_physics.md`

Jolt chosen 2026-04-14; `CharacterVirtual` integrated + parity-tested on snowgoons. Open: `MOBILITY_VEHICLE` (VehicleConstraint), restitution/bounce (Elasticity → mRestitution, needs dynamic-body opt-in), CharacterVirtual substepping.

**How to apply:** When an actor physics behaviour is missing or wrong, check whether it's a CharacterVirtual limitation before patching — the fix may belong in the broader Jolt integration rather than a workaround.
