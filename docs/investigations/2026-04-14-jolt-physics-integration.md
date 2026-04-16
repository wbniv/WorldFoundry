# Investigation: Integrate [Jolt Physics](https://jrouwe.github.io/JoltPhysics/) as the WF physics backend

**Date:** 2026-04-14
**Status:** **Functional** — `WF_PHYSICS_ENGINE=jolt` is the default; snowgoons is playable. Legacy `physics/wf/` retained pending parity on a second level.
**Depends on:** `docs/investigations/2026-04-14-physics-engine-survey.md` (Jolt selected over Bullet/PhysX/Rapier on size, license, character-controller quality, and maintenance trajectory).

## Context

WF's current physics lives in `wfsource/source/physics/wf/` (selected by `-DPHYSICS_ENGINE_WF`) and its handlers in `wfsource/source/movement/`. The recent Lua-scripting spike unmasked a bad `reinterpret_cast` in `BungeeCameraHandler`'s `SPECIAL_COLLISION` path at `wfsource/source/game/movecam.cc:1004-1007` — symptomatic of a deeper design where kinematic queries, camera logic, and collision response are entangled. Patching locally is brittle; the desired direction is a wholesale replacement.

The survey report recommended **Jolt Physics** (MIT, ~300 KB stripped, C++17, active upstream, `CharacterVirtual` solves the exact character-vs-world problem WF's current code handles badly). Exploration confirmed: WF already builds with `-std=c++17`; there's an existing `PHYSICS_ENGINE_ODE` compile-time branch in `physics/physical.hp` that demonstrates the backend-swap pattern; vendor convention (`wftools/vendor/<lib>-<version>/`) is established by wasm3/quickjs/jerryscript. Scripts do not currently invoke physics directly — they only read/write mailboxes — so there is no scripting-host-function ABI to break.

**Known constraint up front:** WF's tick rate varies (and historically took significant effort to get right). Jolt prefers a fixed step. Any integration must subdivide the variable game `dt` into fixed-size substeps internally — never feed Jolt the raw variable `dt`. See Open questions §"Frame-rate coupling".

Intended outcome when this work is scheduled: `WF_PHYSICS_ENGINE=jolt` produces a `wf_game` binary in which actor movement, collision, and camera queries are driven by Jolt; the legacy code stays compiled behind `WF_PHYSICS_ENGINE=legacy` (default) until parity is proven; snowgoons runs identically under both; the `movecam.cc:1007` cast is deleted rather than patched.

## Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Engine | **Jolt Physics** (latest tagged release, e.g. `v5.x.x`) | MIT, ~300 KB stripped, `CharacterVirtual`, deterministic, active upstream (Guerrilla). Survey report is the justification. |
| Build flag | **`WF_PHYSICS_ENGINE=legacy\|jolt`** (env var, default `legacy`) | Mirrors `WF_WASM_ENGINE` / `WF_JS_ENGINE` pattern. `legacy` = `-DPHYSICS_ENGINE_WF`; `jolt` = `-DPHYSICS_ENGINE_JOLT`. The defunct `PHYSICS_ENGINE_ODE` branch is removed in Phase 0 before any Jolt work lands. |
| Drop ODE first | **Delete `physics/ode/` and every `PHYSICS_ENGINE_ODE` compile branch as Phase 0** | Never compiled, never selected, no ODE library is linked. It's dead code that confuses the backend-swap pattern. Removing it first makes the Jolt branches land in a cleaner header. |
| Vendor layout | **`wftools/vendor/jolt-physics-<version>/`** (upstream tarball, SHA256 in `wftools/vendor/README.md`) + **`wftools/vendor/jolt-physics-<version>-wf/`** for WF-specific glue (type converters, selftest) | Matches wasm3 precedent. Jolt's upstream CMake is large; we compile only the TUs we need via direct `g++` calls from `build_game.sh`, same as wasm3. |
| Adapter location | **`wfsource/source/physics/jolt/`** (new) | Mirrors existing `physics/wf/` dir. `jolt/jolt_backend.{hp,cc}` holds the `PhysicalAttributes` impl for `PHYSICS_ENGINE_JOLT`. |
| Scope of PhysicalAttributes rewrite | **Keep the public API byte-for-byte**; swap private state to `JPH::BodyID` + cached pose | Minimal blast radius. Every caller of `Position()`, `Rotation()`, `LinVelocity()`, `CheckCollision()`, etc. keeps working. Euler ↔ Quaternion conversion happens inside the accessors. |
| Character controller | **Replace GroundHandler + AirHandler's collision math with `JPH::CharacterVirtual`** | This is the single biggest win. Slope, step, one-way platforms, snap-to-ground all come "free" from Jolt. |
| Camera collision (BungeeCameraHandler) | **Rewrite around `JPH::NarrowPhaseQuery::CastRay` / `CastShape`** | Deletes the `reinterpret_cast` in `movecam.cc:1007` wholesale — replaced by a typed Jolt query, not patched. |
| World geometry load | **Convert WF static-mesh / level geometry to a `JPH::MeshShape`** at level-load time | Jolt builds a BVH internally. Source geometry already exists in WF's level loader; adapter walks the triangle list once per level. |
| Math bridging | **Inline converter helpers in `physics/jolt/jolt_math.hp`**: `Vector3↔JPH::Vec3`, `Euler↔JPH::Quat`, `Matrix34↔JPH::Mat44` | No changes to WF's math types. Scalars are already `float` via `-DSCALAR_TYPE_FLOAT`, so no precision conversion needed. |
| Tick coupling | **Adapter internally substeps at fixed 60 Hz; WF calls with variable `dt`** | WF's variable tick rate is load-bearing (see Open questions). Jolt must not see the raw `dt`. |
| Scripting surface | **No change in this plan.** Mailboxes continue to read/write position/velocity the same way. | Scripts never called physics directly. Adding `ray_cast` or similar to scripts is a follow-up (see Follow-ups §1). |
| Legacy removal | **Do not delete `physics/wf/` in this plan.** | Kept until Jolt passes snowgoons parity + at least one other level. Removal is a separate, reviewable commit. |

## Implementation

### Phase 0 — Remove the defunct ODE branch

Goal: `physics/ode/` and every `PHYSICS_ENGINE_ODE` reference are gone before Jolt work starts. No library has ever been linked against this; the branch is pure dead code.

1. Delete `wfsource/source/physics/ode/` in its entirety.
2. Remove the `#if defined PHYSICS_ENGINE_ODE` / `#include "ode/ode.hp"` block at `physics/physical.hp:46-48`.
3. Remove the `PHYSICS_ENGINE_ODE` branch at `physics/physical.hp:155-161` (the `ode::dBodyID _body;` / `dGeomID _geom;` members). Leave the `#error physics engine not defined!` guard in place but with `JOLT`/`WF` as the only accepted values (updated again in Phase 1).
4. Grep the tree for any other `PHYSICS_ENGINE_ODE`, `ode::`, or `ode/` references in source files; delete them. Expect hits only in `physics/physical.{hp,cc,hpi}` and possibly `physics/collision.cc`.
5. **Verify:** `WF_PHYSICS_ENGINE=legacy` (i.e. default) build produces a byte-identical-minus-timestamp `wf_game` to the pre-Phase-0 binary. `grep -r PHYSICS_ENGINE_ODE wfsource/` returns nothing. Single small commit.

### Phase 1 — Vendor Jolt and land a no-op build flavour

Goal: `WF_PHYSICS_ENGINE=jolt ./build_game.sh` produces a binary that compiles and links Jolt, prints a selftest line at runtime, and otherwise behaves identically to `legacy` (no physics is routed through Jolt yet).

1. Download Jolt release tarball (latest stable) into `wftools/vendor/jolt-physics-<version>/`. Record SHA256 in `wftools/vendor/README.md`.
2. Identify the minimal TU set (Jolt's `Jolt/**/*.cpp` minus `Jolt/Physics/SoftBody/*` and the debug renderer). Jolt's upstream `CMakeLists.txt` lists them — mirror that list into `build_game.sh` alongside the wasm3 TU list.
3. Add `WF_PHYSICS_ENGINE` case to `build_game.sh` (model after `WF_WASM_ENGINE` at `build_game.sh:39-73`):
   - `legacy` → `-DPHYSICS_ENGINE_WF` (today's behaviour, unchanged)
   - `jolt` → `-DPHYSICS_ENGINE_JOLT -I"$VENDOR/jolt-physics-<ver>"` and compile Jolt TUs into `OBJS`
4. Add a stub `wftools/wf_viewer/stubs/physics_jolt.cc` (mirrors `scripting_wasm3.cc`) with `JoltRuntimeInit()` / `JoltRuntimeShutdown()`; called from wherever the engine initialises subsystems (likely near `LuaInterpreter` ctor / `ScriptInterpreterFactory`). The selftest creates a `PhysicsSystem`, inserts a falling sphere, steps 10 frames, asserts it moved downward, and logs `jolt: selftest ok`.
5. **Verify:** `WF_PHYSICS_ENGINE=legacy` unchanged (binary size delta = 0). `WF_PHYSICS_ENGINE=jolt` compiles, links, prints selftest line, runs snowgoons identically to legacy (because no actor code is on the Jolt path yet).

### Phase 2 — PhysicalAttributes backed by Jolt bodies

Goal: Each actor's `PhysicalAttributes` holds a `JPH::BodyID` instead of a WF `_body`. Read paths hit Jolt and convert; write paths update Jolt bodies. Substep adapter lives here.

1. Add `PHYSICS_ENGINE_JOLT` branch in `physics/physical.hp` (in the slots vacated by Phase 0's ODE removal) alongside the `WF` branch. Private state: `JPH::BodyID _body;` plus a cached `Euler _orientationCache` and `Vector3 _positionCache` refreshed after each Jolt step.
2. Implement `physics/jolt/jolt_backend.{hp,cc}`:
   - Global singleton `JoltWorld` holds the `PhysicsSystem`, `TempAllocator`, `JobSystem`, `BroadPhaseLayerInterface`.
   - `PhysicalAttributes::Construct(...)` creates a `BodyCreationSettings` with a box shape matching `(minPoint,maxPoint)` and calls `BodyInterface::CreateAndAddBody`.
   - `Position()` / `Rotation()` / `LinVelocity()` read from Jolt's `BodyInterface` (cached per-frame to avoid lock churn).
   - `SetPosition` / `SetLinVelocity` / `AddLinVelocity` → `BodyInterface::SetPosition` / `SetLinearVelocity` / `AddLinearVelocity`.
   - `CheckCoarseCollision` / `CheckCollision` → `NarrowPhaseQuery::CollideShape` with a box shape derived from `colSpace`.
   - **Step function** `JoltWorld::Step(dt_game)`: accumulates `dt_game`, drains into fixed 1/60 s substeps via `PhysicsSystem::Update`, with a hard cap (e.g., max 4 substeps per call) to prevent spiral-of-death on long frames.
3. `jolt_math.hp` inline converters: `ToJph(Vector3)`, `FromJph(JPH::Vec3)`, `ToJph(Euler)`, `FromJph(JPH::Quat)`. Euler order must match WF's existing convention (check `math/euler.hp`).
4. Level-load hook: walk the level's static geometry, build a single `MeshShape` (triangle soup + BVH), add as one static body. Location: wherever `ColSpace` is currently populated at level init (identify during implementation; likely `wfsource/source/game/*level*.cc`).
5. **Verify:**
   - Snowgoons loads under `WF_PHYSICS_ENGINE=jolt`. Actors appear at correct initial positions (read path parity).
   - Drop-in test: edit snowgoons so the player starts in mid-air; confirm it falls (write path + step loop).
   - Substep sanity: log substep count per frame across a playthrough; confirm it stays bounded and tracks `dt` reasonably.
   - Legacy still default; `legacy` build still passes snowgoons play-through.

### Phase 3 — Character controller via CharacterVirtual

Goal: The player and any humanoid NPC move via `JPH::CharacterVirtual`, not WF's `GroundHandler` + `AirHandler` collision math.

1. In `movement/movement.cc`, add a `PHYSICS_ENGINE_JOLT` branch in `GroundHandler` and `AirHandler`: replace the current `PremoveCollisionCheck` + slope math with a `CharacterVirtual::ExtendedUpdate` call.
2. Tunable inputs (slope limit, step height, jump velocity) come from existing actor properties (identify during implementation — likely in `actor.hp` or a tunable struct).
3. Contact callbacks (`CharacterContactListener`) forward into WF's existing collision-event machinery so scripting / damage / trigger systems see contacts as they do today.
4. **Verify:**
   - Snowgoons: player walks up slopes, jumps correctly, does not sink into floors, steps onto platforms — parity with legacy.
   - Compare playthrough videos side-by-side (legacy vs. jolt). Any divergence is a bug in the adapter or a legitimate Jolt improvement (slope behaviour is likely to be *better*; note these separately).

### Phase 4 — Fix the camera cast

Goal: Delete the `reinterpret_cast` in `movecam.cc:1007` as part of rewriting `BungeeCameraHandler`'s collision query onto Jolt.

1. In `movecam.cc`, replace the `SPECIAL_COLLISION` block with a Jolt `NarrowPhaseQuery::CastRay` from the player position toward the camera's desired position. Hit distance shortens the bungee.
2. `msgData` union access that required the cast disappears entirely — the query is typed end-to-end.
3. **Verify:** Snowgoons camera clamps correctly behind walls; no stuck-behind-geometry issues; manual playthrough shows parity.

### Phase 5 — Size matrix and retirement gate

1. Run the same per-engine measurement methodology from the wasm3 plan (§Verification step 7). Add a `Physics` section to `docs/scripting-languages.md` (or a new `docs/engine-size-matrix.md`): whole-binary stripped delta `legacy` vs. `jolt`, per-.o runtime size, static RAM, per-body RAM.
2. Retirement gate: once snowgoons and at least one other level run cleanly under `jolt`, write a follow-up commit that removes `physics/wf/`, the `PHYSICS_ENGINE_WF` compile branches, and the `legacy` arm of `WF_PHYSICS_ENGINE`. Keep this change small and isolated so history stays clean.

## Critical files

| File | Change |
|------|--------|
| `wftools/wf_engine/build_game.sh` | Add `WF_PHYSICS_ENGINE` switch; compile Jolt TUs under `jolt` |
| `wftools/vendor/README.md` | Add Jolt entry with SHA256 |
| `wftools/vendor/jolt-physics-<ver>/` | New — upstream tarball |
| `wftools/vendor/jolt-physics-<ver>-wf/` | New — selftest + any WF-specific glue |
| `wfsource/source/physics/ode/` | **Deleted in Phase 0** — dead code, never compiled |
| `wfsource/source/physics/physical.hp` | Phase 0: remove ODE branches. Phase 2: add `PHYSICS_ENGINE_JOLT` branches in the freed slots |
| `wfsource/source/physics/physical.cc` + `.hpi` | Branch all accessor impls on `PHYSICS_ENGINE_JOLT` |
| `wfsource/source/physics/jolt/jolt_backend.{hp,cc}` | New — the adapter (incl. variable-dt substep scheduler) |
| `wfsource/source/physics/jolt/jolt_math.hp` | New — Vector3/Euler/Matrix34 ↔ JPH converters |
| `wfsource/source/movement/movement.cc` | `CharacterVirtual` branch in GroundHandler / AirHandler |
| `wfsource/source/game/movecam.cc:1004-1007` | Delete the `reinterpret_cast`; replace SPECIAL_COLLISION with Jolt ray cast |

## Reuses

- `-DPHYSICS_ENGINE_*` compile-time select pattern (present in `physical.hp`; Phase 0 simplifies it from `WF|ODE` to `WF` before Phase 1 adds `JOLT`).
- `WF_WASM_ENGINE` / `WF_JS_ENGINE` env-var + case-match structure in `build_game.sh:39-73` — identical shape for `WF_PHYSICS_ENGINE`.
- Vendor directory layout (`wftools/vendor/wasm3-v0.5.0/` + `wasm3-v0.5.0-wf/`) — same split for Jolt.
- WF math types — no new math library needed; Jolt's `Vec3`/`Quat`/`Mat44` stay inside the adapter.
- Existing collision-event dispatch in `PhysicalObject::Collision(other, normal)` — `CharacterContactListener` forwards into it.

## Verification

1. **`legacy` default unchanged.** `WF_PHYSICS_ENGINE=legacy` produces bit-identical (or near-identical modulo timestamps) binary to today's build. Snowgoons play-through unchanged.
2. **`jolt` selftest.** `WF_PHYSICS_ENGINE=jolt ./build_game.sh` succeeds; `wf_game` prints `jolt: selftest ok` at startup.
3. **Snowgoons parity under `jolt`.** Player walks, jumps, collides with slopes and walls, camera clamps, scripted mailbox state readbacks (position/rotation/velocity) match legacy within float tolerance.
4. **Substep scheduler stability.** Log substep count per frame under normal and artificially-stalled conditions; confirm bounded, no spiral-of-death, no visible judder across realistic frame-rate swings.
5. **Size matrix.** Published to `docs/engine-size-matrix.md`:
   - whole-binary stripped delta (`legacy` vs `jolt`) at `-O2`
   - per-.o text/data/bss for the physics runtime TUs alone (same methodology as wasm3 plan §7)
   - static RAM (RSS delta across `JoltRuntimeInit`)
   - per-body RAM (RSS delta across loading snowgoons)
6. **`movecam.cc` cast deleted.** `grep -n reinterpret_cast wfsource/source/game/movecam.cc` returns nothing in the Phase-4 commit.
7. **Second-level smoke test** before Phase 5 retirement: pick one non-snowgoons level, load it under `jolt`, verify player movement and camera.

## Follow-ups (out of scope for this plan)

1. **Physics in scripting.** Expose `ray_cast(ox,oy,oz, dx,dy,dz) → (hit, dist, nx,ny,nz)` to Lua/Fennel/wasm via the mailbox bridge or a new host-function pair. AI line-of-sight and trigger queries benefit. Design the ABI once, all engines bind to it.
2. **Jolt determinism + replay.** Pin SIMD config, capture input stream, replay for bug repro. Requires lockstep-friendly input capture that doesn't exist today.
3. **Constraint-based props.** Doors, chains, pulleys, elevators as `JPH::HingeConstraint` / `SliderConstraint`. Needs a level-format change to encode constraints — own plan.
4. **Retire `physics/wf/`.** Separate commit after Phase 5 gate passes. (ODE is already gone — Phase 0.)
5. **Platform audit.** If/when a non-x86_64 target re-enters the build (PSX/console/ARM), verify Jolt's SIMD fallbacks and C++17 availability on that toolchain.

## Open questions

- **Frame-rate coupling — primary risk.** WF's tick rate varies and historically took significant effort to get right; the variability is load-bearing and not negotiable. Jolt prefers a fixed step. The adapter **must** accept a variable `dt` and internally subdivide into fixed-size substeps before calling `PhysicsSystem::Update` — never feed Jolt the raw variable `dt`. Budget a spike in Phase 2 to prove this: drive Jolt at a fixed 60 Hz internal step with `N = ceil(dt_game / (1/60))` substeps, clamp `N` to prevent spiral-of-death under long frames, and verify stable behaviour across low and high frame rates. If substep accumulation proves unstable for WF's interaction patterns (physics-driven platforms, bungee camera, fast-moving actors), that is a design-level blocker worth raising before committing further phases.
- **Euler convention.** WF's `Euler` order (XYZ? ZYX? intrinsic/extrinsic?) must match the Jolt quaternion conversion. Check `math/euler.hp` during Phase 2; if ambiguous, add a round-trip unit test.
- **Level static-mesh source.** Where in the level-load path does WF today populate static-world `ColSpace` instances? The adapter hooks in at the same place. Need to identify this during Phase 2 — not yet located by exploration.
- **Actor shape approximation.** Actors today have AABB collision boxes. Jolt's `CharacterVirtual` prefers capsules. Start with box shape for parity; migrate character-controlled actors to capsule in Phase 3 to get `CharacterVirtual`'s slope behaviour.
