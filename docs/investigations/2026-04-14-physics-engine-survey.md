# Physics Engine Survey

**Date:** 2026-04-14  
**Context:** WF currently ships its own physics implementation, which a recent Lua-scripting spike exposed as containing at least one bad `reinterpret_cast` in `BungeeCameraHandler` / `SPECIAL_COLLISION` (`movecam.cc:1007`). The user's stated intent is to replace physics wholesale rather than patch. This report surveys available options — open source / free software first, then economical commercial offerings — and evaluates fit for a general-purpose 3D game physics target at the level of Mario 64 and beyond.

---

## What "Mario 64-level physics" actually requires

Mario 64's physics is a useful baseline because it is well-studied and covers most of what an action game needs:

- **Rigid-body kinematics** — position + velocity + orientation, Euler-integrated each frame.
- **Character controller** — capsule or sphere cast against static world geometry; slope handling; one-way platforms; coyote time / snap-to-ground.
- **Static mesh collision** — arbitrary triangle soups, not just boxes and spheres. This is the hard part.
- **Simple dynamics for objects** — crates, coins, enemy ragdolls when killed. No articulated simulation needed; impulse-and-forget is enough.
- **Triggers / overlap queries** — "is Mario inside this water volume?", "did the player step on this floor panel?"
- **Ray / shape casts** — for camera visibility, line-of-sight AI, ground checks, bullet tests.
- **No continuous fluid, cloth, or soft-body** — those are optional extras, not baseline.

"And better" implies room for constraint-based jointed bodies (doors on hinges, pulleys, chains) and potentially vehicles. These are within reach of any modern rigid-body engine.

What this *does not* require: GPU physics, destruction, large particle counts, or determinism across platforms unless multiplayer is planned.

---

## Open-source / free-software options

### 1. Jolt Physics

| | |
|-|-|
| **License** | MIT |
| **Language** | C++17 (header-heavy) |
| **Geometry** | Triangle mesh, convex hull, sphere, box, capsule, cylinder, height-field, compound |
| **Constraints** | Fixed, point, hinge, slider, cone, pulley, motor — full articulated-body support |
| **Character** | Dedicated `CharacterVirtual` class — handles slope, step, ledge, one-way platforms |
| **Query API** | Ray cast, shape cast, collide-shape, broadphase overlap |
| **Platforms** | x86_64, ARM64, WASM (via emscripten), RISC-V |
| **Determinism** | Yes — bit-exact across platforms with same SIMD config |
| **Active** | Yes — Guerrilla Games (Horizon Forbidden West, Forbidden West) ships it; PR velocity is high |
| **Size** | ~300 KB static lib at -O2, stripped (x86_64 Linux) |

**Assessment:** The strongest open-source option today. `CharacterVirtual` solves the hardest single problem for a Mario-style game (character-vs-world), constraint system handles doors/chains/vehicles, and the determinism story is clean. The C++17 requirement is the only portability concern — if WF targets a pre-C++17 toolchain on any platform, this is ruled out. SIMD paths are SSE2/AVX2 on x86_64, NEON on ARM64; scalar fallback exists but is slow. At ~300 KB it is not a free lunch on a 2 MB system, but it is the smallest full-featured option.

---

### 2. Bullet Physics (btBullet / Bullet3)

| | |
|-|-|
| **License** | zlib |
| **Language** | C++ (03-compatible core) |
| **Geometry** | Triangle mesh (BVH, GImpact), convex hull, sphere, box, capsule, cylinder, compound, height-field, soft-body |
| **Constraints** | Point, hinge, cone-twist, 6DoF, slider, generic; supports motors |
| **Character** | `btKinematicCharacterController` — workable but known rough edges on slopes and penetration recovery |
| **Query API** | Ray test, convex sweep, contact test |
| **Platforms** | Portable C; any target with a C++ compiler |
| **Determinism** | No |
| **Active** | Maintenance mode. Last significant feature work ~2020; bugs get PRs but no roadmap |
| **Size** | ~500–700 KB static lib at -O2 on x86_64 (BulletDynamics + BulletCollision + LinearMath, stripped) |

**Assessment:** The industry workhorse for most of the 2010s — used in GTA V, Halo, countless Unreal projects, Blender, and many others. Extremely well-understood; StackOverflow has answers for every sharp edge. The character controller is its weakest point: `btKinematicCharacterController` has well-documented quirks on slopes, stairs, and ceiling scrapes that require application-side workarounds. For WF, the bigger concern is size: at 500–700 KB it costs roughly 25–35% of a 2 MB system budget in text alone. Use it if C++03 compatibility, existing industry knowledge, or the soft-body support is a hard requirement; prefer Jolt otherwise.

---

### 3. PhysX (NVIDIA)

| | |
|-|-|
| **License** | BSD 3-Clause (since v5.x, 2023) |
| **Language** | C++14 |
| **Geometry** | Triangle mesh, convex mesh, height-field, sphere, capsule, box, custom shapes |
| **Constraints** | Full articulated system; `PxArticulationReducedCoordinate` for robotics-style jointed bodies |
| **Character** | `PxController` — capsule and box, solid slope/step handling |
| **Query API** | Ray cast, sweep, overlap; batched scene queries |
| **Platforms** | x86_64, ARM64, SWITCH; GPU acceleration on NVIDIA hardware (optional) |
| **Determinism** | No (GPU path especially) |
| **Active** | Yes — Unreal Engine uses it as the default; NVIDIA actively maintains |
| **Size** | ~1.5–2 MB static lib at -O2 (x86_64, stripped, CPU-only, no GPU) |

**Assessment:** Industry-grade quality; `PxController` is one of the best-tested character controllers in existence; articulation system handles anything up to full humanoid ragdolls. The size is the killer for WF: 1.5–2 MB is the entire target system budget. Even on a desktop dev build it is a heavy dependency. The GPU optional features are irrelevant to WF's targets. Unless WF grows to a scale where the PhysX ecosystem (Unreal compatibility, GPU cloth, destruction) is directly valuable, this is overweight.

---

### 4. ODE (Open Dynamics Engine)

| | |
|-|-|
| **License** | BSD / LGPL (user's choice) |
| **Language** | C (with C++ bindings) |
| **Geometry** | Sphere, box, capsule, cylinder, plane, ray, trimesh (via OPCODE or libccd), height-field |
| **Constraints** | Ball, hinge, slider, universal, hinge-2, piston, fixed; LCP-based solver |
| **Character** | None built-in; application must implement |
| **Query API** | Collision callback; space queries |
| **Platforms** | Portable C; widely ported |
| **Determinism** | Approximately; LCP solver is not bit-exact |
| **Active** | Very low — last release 0.16.5 in 2022, sparse commits |
| **Size** | ~200–250 KB static lib (stripped, -O2, single-precision) |

**Assessment:** ODE was the reference constraint-based engine of the mid-2000s; Second Life and many older games shipped it. Today it is largely superseded. The lack of a built-in character controller matters — you would implement capsule-vs-trimesh + depenetration + slope response from scratch, which is exactly the hard part. The LGPL clause (if chosen over BSD) requires dynamic linking or source disclosure. At ~200 KB it is the smallest of the simulation engines, but that frugality comes at significant capability cost. Not recommended for new projects in 2026 unless a very small footprint with an established constraint solver is the specific need.

---

### 5. Rapier

| | |
|-|-|
| **License** | Apache 2.0 |
| **Language** | Rust (with C FFI and WASM bindings) |
| **Geometry** | Ball, cuboid, capsule, cone, cylinder, convex polyhedron, triangle mesh (via parry), height-field, compound |
| **Constraints** | Fixed, prismatic, revolute, rope, spring, motor |
| **Character** | `KinematicCharacterController` — slope limit, step height, snap-to-ground, one-way platforms |
| **Platforms** | Any Rust target; WASM first-class (deterministic in WASM mode) |
| **Determinism** | Yes — guaranteed cross-platform in `rapier-wasm` builds |
| **Active** | Yes — Dimforge actively develops; bevy_rapier is the de-facto Bevy physics |
| **Size** | ~400 KB static lib (WASM stripped); C FFI layer adds ~50 KB |
| **C FFI** | `rapier_cxx` / manual bindings; no official stable C ABI yet |

**Assessment:** Excellent physics quality; the character controller is well-designed and handles the Mario cases cleanly. The determinism story is unusually strong — lockstep multiplayer physics is feasible without extra work. The complication for WF is C integration: Rapier is a Rust library. Using it from WF's C/C++ codebase requires either a C FFI shim (exists but is unofficial and does not expose 100% of the API) or rewriting the physics integration layer in Rust. If WF's Rust port momentum continues this becomes more attractive over time. Not recommended as the first physics choice unless the team is already writing Rust there.

---

### 6. ReactPhysics3D

| | |
|-|-|
| **License** | zlib |
| **Language** | C++11 |
| **Geometry** | Sphere, box, capsule, convex mesh, concave mesh, height-field |
| **Constraints** | Ball, hinge, slider, fixed; built-in solver |
| **Character** | None built-in |
| **Query API** | Ray cast, AABB overlap |
| **Platforms** | Portable C++11 |
| **Determinism** | No |
| **Active** | Maintained by Daniel Chappuis (solo); steady releases |
| **Size** | ~150–200 KB static lib (stripped, -O2) |

**Assessment:** Clean, readable codebase; the docs are excellent and the API is easy to integrate. Chappuis wrote it as a learning/teaching engine and it shows — the internals are comprehensible without a physics PhD. Practical ceiling: it handles the rigid-body and query cases well, but without a built-in character controller, concave-mesh collision for complex levels is slower than Jolt/Bullet (GJK+EPA loop without BVH acceleration at the contact-pair level). Good fit for small games with mostly convex geometry; for a Mario 64-style open world with complex terrain it would need a custom character layer on top.

---

### 7. Newton Dynamics

| | |
|-|-|
| **License** | zlib |
| **Language** | C++ |
| **Geometry** | Primitive shapes, convex hull, compound, static mesh, height-field |
| **Constraints** | Wide range; vehicle physics notable feature |
| **Character** | Player controller module exists |
| **Platforms** | Windows / Linux / macOS; less broad than Bullet |
| **Active** | Low — Julio Jerez maintains solo; releases infrequent post-v4 |
| **Size** | ~400–500 KB |

**Assessment:** Newton was notable in the 2000s for stable stacking and vehicle physics. It has not kept pace with Jolt or Bullet in community, documentation, or platform coverage. The solo-maintainer risk is higher here than for ReactPhysics3D. Not a strong recommendation in 2026.

---

### 8. Box2D (and Box2D v3)

| | |
|-|-|
| **License** | MIT |
| **Language** | C (v3) / C++ (v2) |
| **Geometry** | **2D only** — polygon, circle, capsule, chain |
| **Constraints** | Revolute, prismatic, pulley, gear, distance, weld, wheel, motor |
| **Character** | Platform-character demo ships with it |
| **Active** | Very — Erin Catto rewrote v3 from scratch in C; released 2024 |
| **Size** | ~60–80 KB stripped |

**Assessment:** The gold standard for 2D physics. Mentioned for completeness — not applicable to Mario 64-style 3D games. If WF ever makes a 2D title, Box2D v3 is the obvious first choice.

---

## Size summary (x86_64 Linux, -O2, stripped static lib)

| Engine | Size | License | C++std | Active | Character ctrl |
|--------|------|---------|--------|--------|----------------|
| Jolt | ~300 KB | MIT | C++17 | Yes | Built-in (excellent) |
| ReactPhysics3D | ~175 KB | zlib | C++11 | Yes (solo) | No |
| ODE | ~225 KB | BSD/LGPL | C | Low | No |
| Box2D v3 | ~70 KB | MIT | C | Yes | 2D only |
| Rapier (C FFI) | ~450 KB | Apache 2.0 | Rust | Yes | Built-in (excellent) |
| Bullet3 | ~600 KB | zlib | C++03 | Low | Included (rough) |
| Newton | ~450 KB | zlib | C++ | Low | Included |
| PhysX 5 | ~1.7 MB | BSD-3 | C++14 | Yes | Excellent |

All sizes are approximations; exact results depend on configuration flags and platform. Measuring `size libBulletDynamics.a libBulletCollision.a libLinearMath.a` style is the right methodology.

---

## Commercial options

The user noted WF is not a "top 10" AAA title budget. That said, a few commercial options are worth knowing:

### Havok Physics

Historically the dominant commercial engine (Half-Life 2, every Halo, Assassin's Creed, Skyrim, Dark Souls, etc.). Acquired by Microsoft in 2015. As of 2024, Havok is offered under a tiered model:

- **Free** for projects under a revenue threshold (self-reported; threshold has varied but was ~$500K/year as of the last public announcement).
- **Commercial** for larger studios — price is enterprise-negotiated, not published.

Quality is excellent: character controller, constraint solver, and query API are all battle-tested. The developer experience (documentation, support) is better than any open-source option. The dealbreaker for WF is that source code is not included at the free tier, and the binary SDK targets mainstream platforms (PC, console, mobile) — it is not a drop-in for embedded/custom targets.

**Verdict:** Worth a look if WF ships on PC/console under the revenue threshold. Not viable for embedded targets.

### Unity Physics / Havok Physics for Unity

Physics-as-a-library for non-Unity projects: not offered. Only relevant if WF switches to Unity as its engine, which is clearly not the plan.

### Physion (GameDev.tv) / other indie-tier commercial options

No commercial physics library in 2026 targets the indie-budget market at a price point that undercuts "just use Bullet" or "just use Jolt." The physics-library market consolidated: Havok is the premium tier, everything else is open source. There is no meaningful mid-tier commercial option.

**Summary:** The commercially meaningful option is Havok at its free-revenue-threshold tier, and only for mainstream platform targets. For WF's embedded/ROM-cart targets, commercial options do not apply.

---

## Recommendation for WF

### Short answer: Jolt Physics

Jolt is the strongest combination of quality, size, license, and maintenance trajectory. The `CharacterVirtual` class handles the exact problem WF's current physics is bad at (character-vs-static-world collision, slope, step), and it does so without requiring application-side workarounds. The constraint system provides everything needed for interactive objects (doors, chains, elevators). The MIT license is unencumbered. At ~300 KB it costs roughly 15% of a 2 MB system budget — significant but not budget-breaking, and it replaces WF's existing physics code rather than adding to it.

The C++17 requirement is the one thing to verify. If WF's embedded or cross-compile toolchain supports C++17, there is no obstacle. If any target is C++14-only, Jolt needs a compatibility shim or the next choice applies.

**Fallback: Bullet Physics (Bullet3)**  
If C++17 is unavailable or the existing team comfort/familiarity with Bullet is high, Bullet is still serviceable. Accept the 500–600 KB cost, plan to replace `btKinematicCharacterController` with a custom capsule-cast character, and pin to a known-good commit given the low upstream maintenance rate.

### What to do with WF's existing physics code

Do not patch incrementally. The `reinterpret_cast` in `movecam.cc` is a symptom: the design mixed kinematic queries, camera logic, and collision response in ways that make local fixes brittle. A wholesale replacement is the right call. The replacement strategy:

1. Keep the existing physics code compiled in but quarantined behind a `WF_PHYSICS_ENGINE=legacy` flag (same pattern as `WF_WASM_ENGINE`).
2. Write a thin adapter layer — same interface WF's actors call today — backed by Jolt.
3. Port the snowgoons level first (simplest physics load) to validate the adapter before touching the character controller.
4. Replace `BungeeCameraHandler`'s collision query with Jolt's ray/shape cast API; delete `movecam.cc`'s collision block.
5. Once snowgoons and the character run cleanly under Jolt, remove the `legacy` build path.

---

## Follow-ups (out of scope here)

- **Determinism and scripted replays.** If WF wants frame-accurate replays or lockstep multiplayer, Jolt's determinism documentation is the starting point. Requires pinning SIMD config.
- **Physics in scripting.** Scripts today write mailboxes; they do not directly query physics. Once Jolt is in, exposing `ray_cast(origin, dir) -> (hit, distance, normal)` to Lua/Fennel/wasm opens AI line-of-sight, projectile checks, and trigger queries from script. Design the host-function ABI before the physics integration is done, so the adapter layer is designed to support it.
- **Jolt WASM target.** Jolt builds for WASM via emscripten. If wasm scripting grows to the point where physics queries from wasm modules are desirable, the WASM Jolt build could be used for host-side validation of script-authored physics queries. Speculative; not needed for v1.
- **Measuring the replacement.** Before and after: `size wf_game` stripped with `WF_PHYSICS_ENGINE=legacy` vs `=jolt`, plus RSS peak during a snowgoons play-through. Publish next to the scripting-engine size table in `docs/scripting-languages.md` (or a new `docs/engine-size-matrix.md`).
