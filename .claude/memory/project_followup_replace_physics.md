---
name: project_followup_replace_physics
description: Replace WF physics with Jolt — plan at docs/plans/project_followup_replace_physics.md
metadata:
  type: reference
---

Plan: `docs/plans/project_followup_replace_physics.md`

Jolt chosen 2026-04-14; `CharacterVirtual` integrated + parity-tested on snowgoons. `MOBILITY_VEHICLE` (VehicleConstraint) landed 2026‑06‑03 (`a3e02904`, moon Lunar Cruisers) and a fixed-substep scheduler is in `jolt_backend.cc`. Open: restitution/bounce (Elasticity → mRestitution, needs dynamic-body opt-in).

**How to apply:** When an actor physics behaviour is missing or wrong, check whether it's a CharacterVirtual limitation before patching — the fix may belong in the broader Jolt integration rather than a workaround.
