# Plan: Eliminate C++ RTTI — restore `kind()`-based dispatch

**Date:** 2026-04-29 (drafted), refreshed 2026-05-19 for implementation.
**Status:** Done (2026-05-19).
**Related:** [docs/investigations/2026-04-29-rtti-audit.md](../investigations/2026-04-29-rtti-audit.md)

---

## Why

"No C++ RTTI" is a load-bearing architectural constraint of the WF engine —
not aspirational. Two original reasons (per project owner, 2026-05-19):

1. **RTTI was expensive** on the era's target platforms; prohibited on cost grounds.
2. **Implementation was spotty** across the compilers/platforms in use, so even
   where you paid the cost you couldn't rely on it working uniformly.

The PSX/2000-era codebase had **zero** `dynamic_cast`. In 2003, when `Actor*`
containers were generalised to `BaseObject*` / `PhysicalObject*` iterators, the
refactor author (kts, CVS revs Jan–May 2003) reached for `dynamic_cast` instead
of restoring the existing `kind()`-guarded dispatch. The breach went undetected
for ~22 years because no one was actively using the engine and `-fno-rtti` was
never enabled in CI.

This is catalogued as a dormant constraint-breach bug; a BUGS.md entry will be
added when the fix-commit lands. See `[[project_no_rtti_architectural_constraint]]`.

### Payoffs

- Restores the original `kind()` dispatch convention.
- Enables `-fno-rtti` everywhere: drops `type_info` tables from `.rodata`
  (5–20 KB on Android per the 2026-04-18 audit) and removes the runtime
  `dynamic_cast` table walks.
- Makes type dispatch explicit, greppable, and CI-enforceable.

---

## Scope (refreshed 2026-05-19)

**68 `dynamic_cast` call sites across 25 files** (was 51/18 in the original
2026-04-29 draft — drifted by +17 / +7 since then; the original draft missed
4 header files and the `engine/` non-`wfsource/` consumers entirely).

All are `BaseObject*` → `Actor* / PhysicalObject* / MovementObject* / Camera* /
CamShot* / CameraHandler*` downcasts. All are guaranteed downcasts in practice:
no call uses null-checking for conditional logic.

---

## Class hierarchy (relevant portion)

```
BaseObject (abstract, baseobject/baseobject.hp:43)
  └── PhysicalObject (abstract, physics/physicalobject.hp:45)
        └── MovementObject (abstract, movement/movementobject.hp:47)
              └── Actor (abstract, game/actor.hp:99)
                    └── [21 concrete subclasses, all `: public Actor`]
```

The 21 concrete `: public Actor` subclasses:
ActBox, ActBoxOR, Camera, CamShot, Destroy(er), Director, Enemy, Explode,
Generato(r), Light, Matte, Missile, Platform, Player, Shadow, Shield, Spike,
StatPlat, Target, Tool, Warp.

`EActorKind` (defined in `baseobject.hp:65` via `oas/objects.e`) has 26 entries.
Five of them are **sentinel values with no live `kind()` override**:
- `NULL_KIND` (placeholder)
- `Room_KIND` (legacy — `Room` is not a `BaseObject`)
- `LevelObj_KIND` (level-data type tag, not an Actor — used by `level.cc:149,231`)
- `Disabled_KIND`, `Alias_KIND` (only referenced in generated `oas/objects.c`)

**Consequence:** every live `bo->kind()` returns one of the 21 concrete-Actor
values. Therefore every non-null `BaseObject*` *is* a `PhysicalObject*`, a
`MovementObject*`, and an `Actor*`. The plan's predicate logic doesn't need
to enumerate sentinels — a non-null `BaseObject` is always a fully-typed Actor.

---

## Replacement patterns

### Pattern A — guaranteed downcast to concrete type (most calls)

```cpp
// Before
Camera* camera = dynamic_cast<Camera*>(&physicalObject);
assert(ValidPtr(camera));

// After
assert(physicalObject.kind() == BaseObject::Camera_KIND);
Camera* camera = static_cast<Camera*>(&physicalObject);
```

### Pattern B — abstract intermediate types (`Actor*`, `MovementObject*`, `PhysicalObject*`)

Since every non-null `BaseObject` is an `Actor`, these become unconditional
`static_cast`:

```cpp
// Before
Actor* actor = dynamic_cast<Actor*>(&bo);
if (actor) { ... }

// After
Actor* actor = static_cast<Actor*>(&bo);
// or, where the null-check was load-bearing on bo itself:
if (&bo) { Actor* actor = static_cast<Actor*>(&bo); ... }
```

### Pattern C — `CameraHandler*` (1 call — `camera.cc:98`)

`CameraHandler : public MovementHandler` adds `virtual GetWatchObject()`.
`Camera::GetWatchObject()` casts the handler to `CameraHandler*` purely to call it.

**Fix:** push the method up. Add to `MovementHandler`:
```cpp
virtual const PhysicalObject* GetWatchObject(const MovementObject&) const { return nullptr; }
```
`CameraHandler` already overrides. `Camera::GetWatchObject()` then calls
directly on the `MovementHandler&` — no cast needed.

### Inline helpers (optional)

Add to `baseobject.hp` for readability:

```cpp
inline bool IsActor(const BaseObject* bo) { return bo != nullptr; }
inline bool IsMovementObject(const BaseObject* bo) { return bo != nullptr; }
inline bool IsPhysicalObject(const BaseObject* bo) { return bo != nullptr; }
```

These are trivial today (every BaseObject is an Actor) but provide named
intent and a single point to update if a non-Actor BaseObject is ever added.

---

## File-by-file breakdown

### `wfsource/source/` — 58 calls across 22 files

| File | Count | Lines | Cast target |
|---|---|---|---|
| `game/level.cc` | 10 | 118,592,788,1049,1177,1207,1300,1347,1652,1725 | `Actor*`/`const Actor*`/`PhysicalObject*`/`BaseObject*` |
| `game/movecam.cc` | 9 | 190,218,227,433,560,745,983,1000,1055 | `Camera*`/`CamShot*`/`PhysicalObject*` |
| `game/actor.cc` | 6 | 233,255,271,1337,1728,1738 | `PhysicalObject*`/`Actor*`/`MovementObject*` |
| `room/room.cc` | 3 | 276,361,381 | `PhysicalObject*` |
| `room/rooms.cc` | 3 | 136,159,190 | `PhysicalObject*`/`Actor*` |
| `physics/activate.cc` | 3 | 80,102,118 | `PhysicalObject*` |
| `movement/movementobject.cc` | 3 | 101,129,146 | `MovementObject*` |
| `game/warp.cc` | 3 | 84,87,119 | `PhysicalObject*`/`const PhysicalObject*` |
| `physics/physicalobject.hpi` | 2 | 72,83 | `PhysicalObject*` non-const + const |
| `movement/movepath.cc` | 2 | 102,198 | `MovementObject*` |
| `movement/movefoll.cc` | 2 | 79,105 | `MovementObject*` |
| `game/level.hpi` | 2 | 124,149 | `Actor*` |
| `room/actrooms.cc` | 1 | 87 | `PhysicalObject*` |
| `physics/collision.cc` | 1 | 483 | `PhysicalObject*` |
| `movement/movementobject.hpi` | 1 | 92 | `MovementObject*` |
| `game/toolngun.cc` | 1 | 91 | `Actor*` |
| `game/shadow.cc` | 1 | 180 | `PhysicalObject*` |
| `game/missile.cc` | 1 | 121 | `Actor*` |
| `game/camera.cc` | 1 | 98 | `CameraHandler*` — Pattern C (push GetWatchObject up) |
| `game/actbox.cc` | 1 | 140 | `Actor*` |
| `anim/animmang.cc` | 1 | 150 | `PhysicalObject*` |
| `movement/movementobject.hp` | 1 | 100 | **commented stub** — delete |

### `engine/` non-`wfsource/` consumers — 10 calls across 3 files

| File | Count | Lines | Cast target |
|---|---|---|---|
| `engine/stubs/debug_server.cc` | 8 | 600,668,694,726,740,953,1004,(+1) | `Actor*` |
| `engine/mutation/wfmut.cpp` | 1 | 76 | `Actor*` |
| `engine/mutation/wfmut_smoke.cpp` | 1 | 68 | `Actor*` (boolean form) |

Total: **68 sites, 25 files.**

### Jolt vendor code

Jolt's `Jolt/Core/RTTI.{h,cpp}` is its own custom type-introspection macro
system — no C++ `dynamic_cast` or `typeid` anywhere in the Jolt sources
(verified: zero hits in `engine/vendor/jolt-physics-5.5.0/Jolt/`). `-fno-rtti`
is safe to apply globally.

---

## Build wiring — `-fno-rtti`

Two build paths both need the flag. Coordinate carefully — drift between
them is a separate latent risk.

### `CMakeLists.txt` (Android + iOS, plus Linux when built via CMake)

Add `-fno-rtti` to both `wfengine` (line 549) and `wf_game` (line 602)
`target_compile_options`. Also Jolt's release block (line 623) already lists
`-fno-exceptions` — `-fno-rtti` belongs there too for binary-size parity.

### `engine/build_game.sh` (canonical Linux dev build)

Add `-fno-rtti` to the `CXXFLAGS` block at line 135.

### Verification

Once both are wired:
```bash
# Confirm zero dynamic_cast / typeid remain
grep -rn "dynamic_cast\|typeid(" wfsource/source/ engine/mutation/ engine/stubs/

# Linux dev build
bash engine/build_game.sh

# Android NDK build (Release)
task build-cmake-android

# UBSan sweep
cmake -B build-ubsan -DWF_ASAN=ON -DCMAKE_BUILD_TYPE=Debug
cmake --build build-ubsan
# run snowgoons + qbert smoke from build-ubsan

# Smoke tests
cd wfsource/source/game && ../../../engine/wf_game  # snowgoons default
cd wfsource/source/game && ../../../engine/wf_game -L wflevels/qbert.iff
```

---

## Cleanup tasks (do alongside)

- `baseobject.hp:71` comment "manual RTTI, investigate removing" → update to
  reflect that `kind()` is now load-bearing, not aspirational removal target.
- `movement/movementobject.hp:100` — delete the commented `dynamic_cast` stub.
- Add BUGS.md entry once the fix-commit lands (template in commit notes;
  date by fix-commit date for reverse-chronological ordering).

---

## Implementation order

1. **Plan & helpers** ✓ (`8d5ef7b`): refresh this plan; add inline
   `IsActor()` / `IsPhysicalObject()` / `IsMovementObject()` helpers to
   `baseobject.hp`; update `:71` comment.
2. **Push `GetWatchObject()` up** ✓ (`0adf1d4`): add virtual to `MovementHandler`,
   simplify `Camera::GetWatchObject()` — eliminates the lone `CameraHandler*` cast.
3. **Replace `.hpi` inline-template sites** ✓ (`8b83391`): 5 sites across
   `level.hpi`, `physicalobject.hpi`, `movementobject.hpi`; delete the
   commented stub at `movementobject.hp:100`.
4. **Replace `.cc` sites in `wfsource/source/`** ✓ (`6ea4872` 5a collision-free,
   `38664aa` 5b `level/actor/missile`, `02f583e` 5c-prefix conversions): batched
   by subsystem. **Including `actor.cc:1729`** — investigated 2026-05-19 and found
   it is *not* a conditional cast: `PhysicalObject`/`MovementObject` are abstract
   (neither overrides `kind()`), so the only instantiable types are the 21 `Actor`
   subclasses and the legacy `collision.cc:309-310` path always passes Actors. Now
   `IsActor()` + `static_cast`; the `→ 0` else stays as the documented update point.
   The stale "coordinate with worker" blocker (former `actor.cc:1728`) is closed —
   the per-actor collision-mailbox feature it depended on landed in `f4071a3`.
5. **Replace `.cc` sites in `engine/`** ✓ (`02f583e`): `debug_server.cc` ×5,
   `wfmut.cpp` ×1, `wfmut_smoke.cpp` ×3 — all `Level`-lookup guaranteed downcasts.
   The editor is now RTTI-free, so step 6 can extend `-fno-rtti` to editor TUs
   with no carve-out.
6. **Add `-fno-rtti` to both build paths** ✓ (`fbf9f7d`): `-fno-rtti` in
   `CMakeLists.txt` `wfengine` / `wf_game` / `Jolt` / `wf_host_gl_e2e_test`
   (the e2e harness closes the last coverage gap) and in `build_game.sh`
   CXXFLAGS.
7. **Verify** ✓: clean from-scratch `-fno-rtti` `build_game.sh` build links
   (exit 0) and the binary carries zero `typeinfo for Actor/Camera/...` symbols
   (`nm`); full CTest green + Android NDK build green (2026-05-19 background
   tasks); snowgoons (level 0) + qbert (level 1) both boot and step frames under
   the `-fno-rtti` binary; BUGS.md entry added (2026-05-19). UBSan sweep wired as
   `task test-wfmut-asan` (optional gate).

**Status: Done (2026-05-19).** Zero `dynamic_cast`/`typeid` (and no
`std::any`/`type_index`/`type_info`) remain in our non-vendor code; `-fno-rtti`
is committed across every TU and the `type_info` tables are gone from the
binary. The closed `BaseObject ← PhysicalObject ← MovementObject ← Actor`
hierarchy (abstract intermediates) is what makes the `static_cast`s valid; the
`IsXxx()` helpers are the single update point if a non-`Actor` `BaseObject` is
ever added. BUGS.md entry landed.

Commit after each step (per `[[feedback_commit_after_each_phase]]`).

---

## Actuals vs estimate

**Estimate:** 4–6 hours. **Actual implementation:** commits span 11:08–21:15 on
2026-05-19 in two clusters (~2 h active hands-on; the gap was unrelated work),
plus this close-out. Recorded per `[[feedback_plan_duration_tracking]]`; the
4–6 h estimate stays on the average-programmer scale per
`[[feedback_estimate_average_programmer_scale]]` and is **not** revised down.

---

## Effort estimate (refreshed)

**4–6 hours.** Original estimate was 3–4 hours for 51 sites in 18 files;
refreshed scope is 68 sites in 25 files, plus two build-system updates and
NDK+UBSan verification.
