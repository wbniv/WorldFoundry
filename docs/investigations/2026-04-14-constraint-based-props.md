# Investigation: Constraint-based props (doors, chains, pulleys, elevators)

**Date:** 2026-04-14
**Status:** Deferred — plan captured for future work, not scheduled. Depends on Jolt integration landing first.
**Depends on:**
- `docs/investigations/2026-04-14-jolt-physics-integration.md` (this plan assumes `WF_PHYSICS_ENGINE=jolt` is the default by the time this work starts).
- **IFF binary chunk support** (referenced in the wasm3 plan's follow-ups). Hard prerequisite — this plan does not ship a text-encoded interim format. See Open questions for rationale.
**Related:** `docs/reference/2026-04-13-blender-to-cd-iff-pipeline.md`, `docs/reference/2026-04-13-oas-oad-format.md`, `docs/2026-04-10-worldfoundry-iffcomp-format.md`.

## Context

Once Jolt is the physics backend, the interesting new capability isn't rigid-body simulation on its own — it's **constraints between bodies**. Jolt exposes a full constraint set (`HingeConstraint`, `SliderConstraint`, `DistanceConstraint`, `PointConstraint`, `PulleyConstraint`, `FixedConstraint`, `ConeConstraint`, `SixDOFConstraint`) with optional motors and limits. These are the primitive behind:

- **Doors / hatches / lids / levers** — hinge, 1 rotational DOF, angle limits, optionally spring-closed.
- **Elevators / lifts / sliding doors / pistons / drawbridges** — slider, 1 translational DOF, position limits, motor-driven.
- **Chains / ropes / cables** — chain of `DistanceConstraint` or `PointConstraint` segments; not simulated cloth, just discrete links.
- **Pulleys / counterweights** — `PulleyConstraint` or paired sliders with a shared rope length.
- **Breakables** — any constraint with a break-force threshold.

None of this exists in WF today because the legacy physics has no constraint solver. Adding it requires three things in order:

1. A way to **author** constraints (Blender-side; the existing Blender→CD-IFF pipeline is the natural seam).
2. A way to **store** constraints in the level file (new IFF chunk type, or extension of an existing chunk).
3. A way for the **engine** to load constraints at level init and expose their state to scripts.

Intended outcome: a `doors/` test level with a lobby of constraint-driven props — a hinged door you push open, a scripted elevator, a swinging chain over a pit, a counterweighted drawbridge — all authored in Blender, round-tripped through the asset pipeline, and running under Jolt in `wf_game` with script-driven triggers via mailboxes.

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Backing simulation | **Jolt constraint types directly** — no WF abstraction layer beyond a thin registry | We already committed to Jolt; wrapping its constraint API adds maintenance cost for no portability win. |
| Authoring surface | **Blender Rigid Body Constraints** (native Blender feature) | Blender already has a full UI for hinge/slider/point/generic-6DOF constraints with limits. Pipeline walks `bpy.data.objects` looking for `rigid_body_constraint`. Zero new UI to design. |
| Constraint types in v1 | **Hinge, Slider, Distance, Point, Fixed** | Covers doors, elevators, chains, hung props, weld-joins. Defer `Pulley`, `Cone`, `SixDOF`, and break-force until a v1 level actually needs them. |
| Level format encoding | **New IFF binary chunk type `CNST`** containing a length-prefixed array of constraint records | Additive — levels without constraints don't pay for it. Binary format is the only format — this plan gates on iffcomp binary-chunk support landing first (see Depends on). No text-encoded interim. |
| Body references | **By actor ID (same ID scheme scripts use)**, plus a sentinel `ACTOR_WORLD` for constraints anchored to static geometry | Actors already have stable IDs for mailbox routing; reusing that scheme means no parallel naming system. |
| Scripting surface | **Mailboxes per constraint**: read current angle/position, read motor target, write motor target, read limit-hit flag | Fits the existing mailbox pattern. Named constraints get a mailbox range allocated at level load. |
| Author-time naming | **Blender object name is the script-visible identifier** | Script author writes `write_mailbox(CONSTRAINT_door_lobby_motor, 1.0)`. Name-to-mailbox-index mapping emitted alongside the level file, same as existing `INDEXOF_*` constants. |
| Motor model | **Position motor by default; velocity motor opt-in per constraint** | Position motor (`SetMotorState::Position`) is what elevators and scripted doors want. Velocity motor (`SetMotorState::Velocity`) is for continuously rotating props (fans, waterwheels). |
| Angle units on the script surface | **Revolutions** (0 ≤ rev < 1 for wrap-around, or signed -0.5..0.5 when direction matters). **Never radians, never degrees.** | WF-wide convention. Dimensionless, wraps cleanly at 1.0, sidesteps radian/degree confusion at every API boundary. Engine internals convert to radians at the Jolt boundary (`rad = rev * 2π`). |
| Distance units on the script surface | **WF's native game-world unit** (same unit the position mailboxes already speak) | No new unit system. Whatever `read_mailbox(INDEXOF_X_POS)` already returns is what `CONSTRAINT_elevator_TARGET` speaks. |
| Break-on-force | **Out of scope for v1** | Destructible constraints are a cool feature but need a separate authoring story (which constraints break? at what force? what event fires?). Revisit when a level needs it. |
| Determinism | **Constraints deterministic under Jolt's fixed-substep adapter** | No new substep logic needed — constraints ride the same step loop Phase 2 of the Jolt integration set up. |

## Level format: the `CNST` chunk

Proposed binary layout (little-endian, all offsets 4-byte aligned):

```
struct CnstChunkHeader {
    u32 magic;            // 'CNST'
    u32 version;          // 1
    u32 count;            // number of constraint records
    u32 name_table_ofs;   // offset to string table (script identifiers)
};

struct CnstRecord {              // 64 bytes, fixed-size
    u32 type;                    // 0=Hinge 1=Slider 2=Distance 3=Point 4=Fixed
    u32 body_a;                  // actor id, or ACTOR_WORLD
    u32 body_b;                  // actor id, or ACTOR_WORLD
    f32 anchor_a[3];             // attachment point, local to body A
    f32 anchor_b[3];             // attachment point, local to body B
    f32 axis[3];                 // hinge/slider axis (world-space at spawn)
    f32 limit_min, limit_max;    // revolutions for hinge, native units for slider/distance
    u32 motor_mode;              // 0=none 1=position 2=velocity
    f32 motor_target;            // initial value; scripts override via mailbox
    u32 name_ofs;                // offset into name table, 0 if unnamed
    u32 flags;                   // bit 0: spawn_sleeping, bit 1: collide_a_b, ...
};
```

Records are fixed-size so the loader can mmap the chunk and index it in O(1). Name strings are pooled in a trailing table to keep records fixed-width without wasting space.

This plan does **not** ship an interim text encoding. If iffcomp binary-chunk support hasn't landed when this work is scheduled, that work is the prerequisite, not a detour — finish it first, then return here.

## Implementation

### Phase 1 — Engine-side constraint loader, no authoring pipeline

Goal: Prove the constraint runtime by hand-writing a `CNST` chunk into a test iff and verifying Jolt spawns the constraints correctly.

1. In the Jolt adapter (`wfsource/source/physics/jolt/jolt_backend.cc`), add `JoltWorld::RegisterConstraint(const CnstRecord&)`. Switch on `type`; for each, build a `JPH::HingeConstraintSettings` / `SliderConstraintSettings` / etc., call `Create`, and store the resulting `Constraint*` in a registry indexed by name.
2. Level-load hook: when the level's IFF is parsed, find the `CNST` chunk (if any), walk its records, call `RegisterConstraint` for each. Resolve `body_a`/`body_b` actor IDs to Jolt `BodyID`s through the actor table.
3. Allocate a mailbox range per named constraint at level load — one mailbox for current value, one for motor target, one for limit-hit flag. Register `CONSTRAINT_<name>_ANGLE` / `_TARGET` / `_LIMIT_HIT` as script-visible constants alongside the existing `INDEXOF_*` set.
4. Per-frame update: before stepping Jolt, read each constraint's target mailbox and, if changed, call `SetTargetPosition` / `SetTargetVelocity` on its motor. After stepping, write the current angle/position back into the state mailbox.
5. **Author a test chunk by hand** — write a small Python script (`scripts/make_test_cnst.py`) that emits a `CNST` chunk with a hinge + slider + distance constraint, patch it into a minimal test level. No Blender involvement yet.
6. **Verify:** load the test level under `wf_game`, observe a door swinging, an elevator rising under script control, a chain settling under gravity. Mailbox reads return sensible angles/positions. Mailbox writes to the elevator's target mailbox move it to a commanded height.

### Phase 2 — Blender authoring pipeline

Goal: Author the same test props in Blender, export via the existing Blender→CD-IFF pipeline, and produce a byte-identical (or equivalent) `CNST` chunk to the hand-authored one.

1. Extend the pipeline's exporter (see `docs/reference/2026-04-13-blender-to-cd-iff-pipeline.md`) to walk `bpy.data.objects` looking for `obj.rigid_body_constraint`.
2. Map Blender constraint types to the `CnstRecord.type` enum:
   - `HINGE` → 0
   - `SLIDER` → 1
   - `GENERIC` with distance-only limits → 2 (distance)
   - `POINT` → 3
   - `FIXED` → 4
   - Anything else: warn, skip.
3. Extract anchor points (`constraint.pivot_x/y/z` in Blender local-space, convert to each body's local frame), axis (Blender uses the constraint object's Z-axis by default; convert), limits (`limit_ang_x/y/z_lower/upper` or `limit_lin_*`), and motor settings (custom property on the Blender object, since Blender's built-in rigid-body motor is Bullet-specific).
4. Emit `CNST` records in actor-ID order so the chunk is stable across re-exports (easier diff review).
5. **Verify:** export the same test scene, compare resulting `CNST` chunk to the Phase-1 hand-authored version (expect bit-equivalence modulo ordering). Load in `wf_game`; parity with Phase 1.

### Phase 3 — Scripted example level

Goal: A `doors/` level in `wflevels/` that demonstrates every v1 constraint type, with scripts that interact with each.

1. Hinged door you push open (physics-driven, no motor — just a hinge with angle limits, player's collision capsule pushes it).
2. Lever that, when pulled, triggers an elevator via a Lua/Fennel/wasm script writing the elevator's motor target mailbox.
3. Chain of 5 distance-constrained bodies hanging over a pit, settles under gravity, can be swung into.
4. Drawbridge: two fixed-constrained planks, with a lever-script that rotates them (motor-driven hinge).
5. **Verify:** play through; every prop behaves as authored; scripts read sensible state; no stuck geometry, no NaN explosions, no spiral-of-death under tick-rate variance (exercise the same substep stability check from the Jolt plan).

### Phase 4 — Documentation and follow-ups

1. New section in `docs/scripting-languages.md` (or a dedicated `docs/constraints.md`) documenting the `CONSTRAINT_*` mailbox surface for script authors.
2. Update the Blender pipeline docs with the rigid-body-constraint authoring story — screenshots of the Blender UI, custom-property names for WF-specific fields (motor mode, script name override if different from object name).
3. Backport to `docs/engine-size-matrix.md` the delta from constraints-enabled vs constraints-empty level (should be negligible; the Jolt constraint solver is already linked in Phase 2 of the Jolt plan).

## Critical files

| File | Change |
|------|--------|
| `wfsource/source/physics/jolt/jolt_backend.{hp,cc}` | Add `RegisterConstraint`, per-frame motor/state sync, name→index registry |
| `wfsource/source/game/level*.cc` (TBD during Phase 1) | Parse `CNST` chunk at level load |
| `wfsource/source/iff/` (TBD) | `CNST` chunk type registration in iff loader |
| `wftools/` Blender exporter (location TBD — see blender-pipeline plan) | Walk `rigid_body_constraint`, emit `CNST` records |
| `scripts/make_test_cnst.py` | New — hand-author test chunk for Phase 1 |
| `wflevels/doors/` | New test level |
| `docs/scripting-languages.md` or `docs/constraints.md` | Document `CONSTRAINT_*` mailbox surface |

## Reuses

- Jolt's `Constraint` / `ConstraintSettings` / `TwoBodyConstraint` hierarchy — the adapter is a thin translator, not a re-abstraction.
- Mailbox infrastructure — `INDEXOF_*`-style name→index registration already exists for actor state; constraints slot in the same way.
- Actor ID scheme — no new ID namespace.
- Blender's native rigid-body-constraint UI — no new authoring UI.
- IFF chunk loader — adding a chunk type is a registration call, not new framework.
- Substep step loop from the Jolt integration plan — constraints ride it for free.

## Verification

1. **`CNST` absent → no behaviour change.** A level with no `CNST` chunk loads and plays identically to today (snowgoons regression check).
2. **Hand-authored `CNST` plays correctly.** Phase 1's test level demonstrates each v1 constraint type.
3. **Blender-authored `CNST` matches hand-authored.** Byte-level diff of the two chunks returns empty (modulo allowed ordering variance, which should be nailed down).
4. **Script-driven motor control.** `write_mailbox(CONSTRAINT_elevator_TARGET, y)` moves the elevator to `y` smoothly over the motor's time constant.
5. **Substep stability.** Under simulated frame-rate swings (force 10 Hz and 120 Hz), constraints remain stable — no blow-ups, no tunnelling through limits.
6. **Size delta measurement.** Per-level iff size delta with/without `CNST` chunk, and per-constraint RAM cost (bytes per `HingeConstraint` etc.) published alongside the scripting/physics size matrix.

## Follow-ups (out of scope)

1. **Breakable constraints.** `Constraint::SetEnabled(false)` + a force-threshold listener. Useful for destructible props. Needs event-hook ABI and an authoring story (per-constraint break force in Blender custom props).
2. **Pulley / counterweight.** `PulleyConstraint`. Niche; add when a level needs it.
3. **Six-DOF constraints.** Ragdolls, vehicles. Huge scope (ragdoll rigging, vehicle tuning) — own plan.
4. **Motorised-with-spring.** Soft-limit springs on hinges (e.g., saloon door that swings back and settles). Jolt supports via `SpringSettings`; add once a level needs it.
5. **Chain/rope visual smoothing.** v1 chains are rigid-body segments — authors see the "tick-rate discontinuity" at joints. Real rope/cable rendering (Catmull-Rom fit or procedural mesh) is a separate rendering plan, not physics.
6. **Editor round-trip.** If Blender is replaced by a native WF level editor (per the broader Blender-pipeline direction), that editor must surface constraints too.

## Open questions

- **Actor-ID stability across edits.** Constraints reference actors by ID. If the Blender exporter re-assigns IDs on every export (unstable), constraint references break. Need to confirm the pipeline assigns stable IDs (name-hash, UUID, or monotonic registry) — this is a pipeline property, not a constraint-plan property, but it is load-bearing here.
- **World-anchor semantics.** `ACTOR_WORLD` means "attached to static level geometry." Jolt represents this as a constraint against the static body that already holds the level `MeshShape` (Jolt integration Phase 2). Confirm that one body-per-static-mesh is how that ships; if there are multiple static bodies, `ACTOR_WORLD` needs to pick the right one.
- **Does WF need joint-of-joints?** Ragdolls and vehicles are compositions of many constraints. v1 supports standalone constraints; hierarchical rigging (each ragdoll joint knowing about its parent) is a possible second layer. **Cost analysis (so the decision is informed later, not now):**
  - **Runtime speed:** effectively free. Jolt's solver already groups connected constraints into *islands* automatically via connected-components of the constraint graph, so a 15-joint ragdoll costs the same per frame whether we encode a group or not. Hierarchical metadata only costs something when we *use* it (LOD, batched enable/disable). The real ragdoll speed concern is solver **iteration count** for tight joint chains, which is a per-constraint tuning knob orthogonal to hierarchy encoding.
  - **RAM:** negligible. Group metadata is ~16-32 B per group + 4 B per constraint (e.g., 100 constraints in 5 groups ≈ +660 B). For scale: one `HingeConstraint` is ~500 B and a dynamic `Body` is ~800+ B, so a 16-body ragdoll is ~20 KB regardless of whether we encode the hierarchy.
  - **Spec surface:** three plausible shapes if we decide we need it later:
    1. Add `u32 group_id` to each `CnstRecord` (64 → 68 bytes, or pad to 72). +6–12% chunk size. Hierarchy is implicit.
    2. New optional `RIGG` chunk listing groups and their member body/constraint IDs. More flexible (per-group LOD distance, break-force, shared pose state), more loader code.
    3. Pure authoring hierarchy: Blender parents flattened at export, zero runtime spec change.
  - **Why defer is safe:** all three options are **additive** — a future `RIGG` chunk or an extended `CnstRecord v2` can ship without breaking v1 levels. No v1 design choice here is load-bearing for the later decision. Pick when a ragdoll or vehicle level is actually in scope.
