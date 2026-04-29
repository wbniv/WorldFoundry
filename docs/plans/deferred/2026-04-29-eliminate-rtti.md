# Plan: Eliminate C++ RTTI — restore `kind()`-based dispatch

**Date:** 2026-04-29
**Status:** Deferred. Research complete; implementation not started.
**Related:** `docs/investigations/2026-04-29-rtti-audit.md`

---

## Why

The PSX/2000-era codebase had zero `dynamic_cast`. In 2003, when `Actor*` containers
were generalised to `BaseObject*` / `PhysicalObject*` iterators, the refactor author
reached for `dynamic_cast` instead of the existing `kind()` dispatch. The original
pattern was correct and appropriate for the target platforms.

Removing RTTI:
- Restores original intent (`kind()` is the right tool here — always was)
- Enables `-fno-rtti` on Android (5–20 KB `.rodata` saving; small but free)
- Removes hidden perf cost of failed `dynamic_cast` table walks at runtime
- Makes type dispatch explicit and greppable

---

## Scope

**51 `dynamic_cast` calls** across 18 files. All are guaranteed downcasts —
no call uses null-checking for conditional logic. Every call is either
immediately asserted (`assert(ValidPtr(...))`) or used unconditionally.

---

## Class hierarchy (relevant portion)

```
BaseObject (abstract)
  └── PhysicalObject (abstract)
        └── MovementObject (abstract)
              └── Actor (abstract)
                    └── [21 concrete subclasses — all have _KIND values]
```

`EActorKind` enum values exist for every **concrete** class. Abstract intermediate
classes (`PhysicalObject`, `MovementObject`, `Actor`) have no enum value.

---

## Replacement patterns

### Pattern A — guaranteed downcast to concrete type (45 of 51 calls)

```cpp
// Before
Camera* camera = dynamic_cast<Camera*>(&physicalObject);
assert(ValidPtr(camera));

// After
assert(physicalObject.kind() == BaseObject::Camera_KIND);
Camera* camera = static_cast<Camera*>(&physicalObject);
```

### Pattern B — unconditional use, no assert (6 of 51 calls)

```cpp
// Before
PhysicalObject* po = dynamic_cast<PhysicalObject*>(bo);
po->DoSomething();

// After — assert added to preserve safety guarantee
assert(bo->kind() >= BaseObject::LOCAL_PHYSOBJ_KIND_START);  // see below
PhysicalObject* po = static_cast<PhysicalObject*>(bo);
```

### Abstract intermediate types (`PhysicalObject*`, `MovementObject*`, `Actor*`)

These have no individual `_KIND` value. The replacement is a range check over
the enum, or a helper predicate:

```cpp
// Option 1: range check (requires enum ordering guarantee)
inline bool IsPhysicalObject(const BaseObject* bo) {
    // all EActorKind values are for Actor subclasses, which are all PhysicalObjects
    return bo->kind() != BaseObject::NULL_KIND;
}

// Option 2: explicit set (safer, more explicit)
inline bool IsPhysicalObject(const BaseObject* bo) {
    auto k = bo->kind();
    return k != BaseObject::NULL_KIND && k != BaseObject::Disabled_KIND;
}
```

Since **all** concrete objects in the current game are `PhysicalObject` subclasses
(the class hierarchy has no non-PhysicalObject BaseObject leaf classes), every
`dynamic_cast<PhysicalObject*>(bo)` where `bo` is non-null is a guaranteed cast.
These can become unconditional `static_cast` with a comment.

Similarly, `dynamic_cast<MovementObject*>` and `dynamic_cast<Actor*>` — all concrete
objects are ultimately `Actor` subclasses, so these are also always valid.

### `CameraHandler*` (1 call — `camera.cc:98`)

`CameraHandler : public MovementHandler` adds `virtual GetWatchObject()`.
`Camera::GetWatchObject()` casts the handler to `CameraHandler*` purely to
call `GetWatchObject()`. The `#pragma message` comment already acknowledges
this is a camera-only invariant.

**Fix:** add `virtual const PhysicalObject* GetWatchObject(const MovementObject&) const`
to `MovementHandler` with a default `return nullptr`. `CameraHandler` already
overrides it. `Camera::GetWatchObject()` then calls it directly on the
`MovementHandler&` — no cast needed.

```cpp
// movement/movement.hp — add to MovementHandler:
virtual const PhysicalObject* GetWatchObject(const MovementObject&) const { return nullptr; }

// game/camera.cc — replace cast with direct call:
const PhysicalObject* Camera::GetWatchObject() const {
    Validate();
    assert(ValidPtr(_nonStatPlat));
    auto& handler = _nonStatPlat->_movementManager.GetMovementHandler(*this);
    const PhysicalObject* wo = handler.GetWatchObject(*this);
    assert(ValidPtr(wo));
    return wo;
}
```

This eliminates the last `dynamic_cast` with no exceptions.

---

## File-by-file breakdown

| File | `dynamic_cast` count | Notes |
|---|---|---|
| `game/level.cc` | 9 | All `Actor*` or `PhysicalObject*`; all guaranteed |
| `game/movecam.cc` | 7 | Mix of `Camera*`, `PhysicalObject*`, `CamShot*` |
| `game/actor.cc` | 4 | `PhysicalObject*` and `MovementObject*` |
| `movement/movementobject.cc` | 3 | All `MovementObject*` |
| `room/room.cc` | 3 | All `PhysicalObject*` |
| `room/rooms.cc` | 2 | `PhysicalObject*` and `Actor*` |
| `game/warp.cc` | 2 | Both `PhysicalObject*` |
| `movement/movefoll.cc` | 2 | Both `MovementObject*` |
| `movement/movepath.cc` | 2 | Both `MovementObject*` |
| `physics/activate.cc` | 3 | All `PhysicalObject*` |
| `game/camera.cc` | 1 | `CameraHandler*` — push `GetWatchObject()` up into `MovementHandler` |
| `game/actbox.cc` | 1 | `Actor*` |
| `game/missile.cc` | 1 | `Actor*` |
| `game/shadow.cc` | 1 | `PhysicalObject*` |
| `game/toolngun.cc` | 1 | `Actor*` |
| `anim/animmang.cc` | 1 | `PhysicalObject*` |
| `physics/collision.cc` | 1 | `PhysicalObject*` |
| `room/actrooms.cc` | 1 | `PhysicalObject*` |

---

## Implementation order

1. Add `IsPhysicalObject()` / `IsActor()` / `IsMovementObject()` inline helpers to
   `baseobject.hp` (or a new `baseobject_cast.hp`)
2. Replace all 50 replaceable calls file-by-file, starting with the smallest files
3. Leave `camera.cc:98` (`CameraHandler*`) as `dynamic_cast` with a comment
4. Add `-fno-rtti` to the build and confirm it compiles clean
5. Run snowgoons smoke test

---

## Verification

```bash
# Confirm no dynamic_cast remain (except camera.cc exception)
grep -rn "dynamic_cast" wfsource/source/ | grep -v "camera.cc"

# Build with -fno-rtti
WF_EXTRA_CXXFLAGS="-fno-rtti" bash engine/build_game.sh

# Smoke test
wf_game -L wflevels/snowgoons.iff
```

---

## Effort estimate

~3–4 hours. Mechanical substitution; no logic changes. The main risk is the
abstract-type casts (`PhysicalObject*`, `MovementObject*`) — those need the
helper predicates verified against the full object set before going unconditional.
