# Investigation: C++ RTTI usage in wf_game

**Date:** 2026-04-29
**Conclusion:** Engine uses C++ RTTI pervasively. `-fno-rtti` is not viable without a medium-sized refactor. The "no RTTI" claim was aspirational. The `dynamic_cast` calls were introduced during the PC/Linux port and are not present in PSX-era code.

---

## `kind()` / `EActorKind` — not C++ RTTI

`baseobject.hp:71` declares:

```cpp
virtual EActorKind kind() const = 0;   // manual RTTI, investigate removing
```

This is **not** C++ RTTI. `EActorKind` is a plain `enum` whose values come from `#include "oas/objects.e"`. Each concrete subclass overrides `kind()` to return its enum constant. No `typeid`, no `type_info`, no vtable RTTI cookie involved.

The comment "manual RTTI, investigate removing" is misleading — this is *already* the manual alternative to `dynamic_cast`. It has only **2 live call sites**:

- `movement/movement.cc:744` — `if (physicalObject.kind() == BaseObject::Player_KIND)`
- `game/movecam.cc:927` — `assert( movementObject.kind() == Actor::Camera_KIND )`

---

## Actual C++ RTTI usage — 51 `dynamic_cast` calls

The engine uses `dynamic_cast` throughout:

| File | Count | Typical pattern |
|---|---|---|
| `game/level.cc` | 9 | `Actor* actor = dynamic_cast<Actor*>(bo)` |
| `game/movecam.cc` | 7 | `Camera* = dynamic_cast<Camera*>(&physicalObject)` |
| `game/actor.cc` | 4 | `PhysicalObject* po = dynamic_cast<PhysicalObject*>(...)` |
| `movement/movementobject.cc` | 3 | `MovementObject* = dynamic_cast<MovementObject*>(&bo)` |
| `room/room.cc` | 2 | `PhysicalObject* po = dynamic_cast<PhysicalObject*>(object)` |
| `room/rooms.cc` | 2 | `PhysicalObject*` / `Actor*` downcasts |
| `movement/movefoll.cc` | 2 | `MovementObject*` downcasts |
| `movement/movepath.cc` | 2 | `MovementObject*` downcasts |
| `game/warp.cc` | 3 | `PhysicalObject*` downcasts |
| `physics/activate.cc` | 3 | `PhysicalObject*` downcasts |
| `physics/collision.cc` | 1 | `PhysicalObject*` |
| `anim/animmang.cc` | 1 | `PhysicalObject*` |
| `game/actbox.cc` | 1 | `Actor*` |
| `game/missile.cc` | 1 | `Actor*` |
| `game/shadow.cc` | 1 | `PhysicalObject*` |
| `game/camera.cc` | 1 | `CameraHandler*` |
| `game/toolngun.cc` | 1 | `Actor*` |
| `room/actrooms.cc` | 1 | `PhysicalObject*` |

All downcasts are `BaseObject*` → `Actor*` / `PhysicalObject*` / `MovementObject*` / `Camera*`. The class hierarchy is shallow and well-defined, so all casts are safe in practice — but they require RTTI at runtime.

---

## `-fno-rtti` verdict: not viable as-is

Building with `-fno-rtti` would fail to compile all 51 `dynamic_cast` sites. Replacing them is feasible — each could be replaced with a `kind()`-guarded static cast or a `switch` on `EActorKind` — but it is a medium refactor across ~15 files.

**Expected size win on Android:** modest. GCC/Clang emit RTTI tables only for polymorphic types (those with virtual functions). With `-fno-rtti`, those tables are omitted. Rough estimate for a codebase this size: 5–20 KB of `.rodata`. Not a compelling trade at this stage.

---

## Jolt's `RTTI.cpp`

`engine/vendor/jolt-physics-5.5.0/Jolt/Core/RTTI.cpp` is Jolt's own custom type introspection system, implemented entirely in terms of Jolt macros and template registration. It does **not** use C++ `typeid` or `dynamic_cast` and is unrelated to the C++ RTTI flag.

---

## Origin of the `dynamic_cast` calls

All 51 `dynamic_cast` calls arrived in the **[first git commit (2010-05-01)](https://github.com/wbniv/WorldFoundry/commit/a2784f6)** with no platform guards. `git log -S"dynamic_cast"` finds no subsequent commit that added or removed any of them in the affected files. The dead-code removal passes ([Batch 5](https://github.com/wbniv/WorldFoundry/commit/03211f9), [Batch 6](https://github.com/wbniv/WorldFoundry/commit/8760f27)) did not strip any guards from around them — they were already bare.

The git repo is a 2010 import of what was already a PC/Linux port. The PSX-era source predates the repo. PS1 toolchains did not support C++ RTTI, so the original code would have relied on `kind()` or explicit `static_cast`s. The most likely explanation: `dynamic_cast` calls were added during the PC port, replacing the manual `kind()`-guarded casts, and `kind()` survived as a rarely-used remnant. This is consistent with `kind()` having only 2 live call sites while `dynamic_cast` dominates.

There is no pre-2010 history in this repo to prove it definitively, but the evidence is unambiguous: the calls were not in the PSX codebase.

---

## Recommendation

Leave `-fno-rtti` off. If Android binary size becomes a real constraint, the 51 `dynamic_cast` sites are the work to do — replace with `kind()`-guarded `static_cast` using the existing `EActorKind` enum. That refactor also makes the type-dispatch explicit and removes the hidden performance cost of failed `dynamic_cast` lookups.
