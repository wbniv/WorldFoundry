# Investigation: C++ RTTI usage in wf_game

**Date:** 2026-04-29
**Conclusion:** Engine uses C++ RTTI pervasively. `-fno-rtti` is not viable without a medium-sized refactor. The "no RTTI" claim was aspirational. The `dynamic_cast` calls were **introduced in 2003** when `Actor*` containers were generalised to `BaseObject*` iterators — confirmed via SourceForge CVS history. The PSX/2000-era code used `kind()` throughout and had zero `dynamic_cast`.

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

### What the pre-2003 code looked like

Before the 2003 refactor, iterators returned `Actor*` directly. Type dispatch was a plain `kind()` comparison — no cast involved because the element type was already known:

```cpp
// Pre-2003 (actor.cc ~Rev 1.42): ActiveRoomsActorIter yields Actor* — no cast needed
Actor* colActor;
ActiveRoomsActorIter actIter( theLevel );
while ( !actIter.Empty() )
{
    colActor = &(*actIter);                          // already Actor* — no cast
    if ( actbox->ActivatedByClass == colActor->kind() )
    {
        const PhysicalAttributes& pa = colActor->GetPhysicalAttributes();
        if ( pa.CheckCollision( GetPhysicalAttributes() ) )
            return colActor;
    }
    ++actIter;
}
```

The 2003 refactor generalised `ActiveRoomsActorIter` to `BaseObjectIteratorWrapper` (returning `BaseObject&`). The element type was no longer statically known, so the author reached for `dynamic_cast` rather than restoring the `kind()`-guarded pattern:

```cpp
// Post-2003 (actor.cc Rev 1.43+): BaseObjectIteratorWrapper yields BaseObject& — cast required
BaseObjectIteratorWrapper poIter = theRoom.GetCollisionIter();
while ( !poIter.Empty() )
{
    Actor* colActor = dynamic_cast<Actor*>( &(*poIter) );  // dynamic_cast introduced here
    if ( colActor && actbox->ActivatedByClass == colActor->kind() )
    {
        // ...
    }
    ++poIter;
}
```

The correct fix (which is what the [elimination plan](../plans/deferred/2026-04-29-eliminate-rtti.md) proposes) was always available: check `kind()` first, then `static_cast`. The original pattern already used `kind()` — the 2003 author just didn't apply it to the new downcast:

```cpp
// Correct pattern (not written in 2003, what the plan restores):
BaseObjectIteratorWrapper poIter = theRoom.GetCollisionIter();
while ( !poIter.Empty() )
{
    BaseObject& bo = *poIter;
    if ( bo.kind() != BaseObject::NULL_KIND &&   // or a specific KIND check
         actbox->ActivatedByClass == bo.kind() )
    {
        Actor* colActor = static_cast<Actor*>( &bo );
        // ...
    }
    ++poIter;
}
```

---

### SourceForge CVS confirms: introduced in 2003, not PSX-era

The pre-git history is preserved in the [World Foundry GDK CVS repository on SourceForge](https://sourceforge.net/projects/wf-gdk/) ([snapshot](https://sourceforge.net/code-snapshots/cvs/w/wf/wf-gdk.zip)). Reconstructing revisions from the RCS `.v` files gives the full picture:

| File | Feb 2000 (SourceForge import) | First `dynamic_cast` | CVS log message |
|---|---|---|---|
| `actor.cc` | 0 | Rev 1.43, **Jan 11, 2003** | "changed Actor::Activated to use PhysicalObjectIterator instead of ActiveRoomsActorIter" |
| `movecam.cc` | 0 | Rev 1.18, **Jan 11, 2003** | "removed Actor from most movement handler functions" |
| `level.cc` | 3 (transitional) | Rev 1.62, **May 23, 2003** | "changed all PhysicalObjectIter references to BaseObjectIter, added dynamic_cast where needed" |

The Feb 2000 `actor.cc` used `kind()` directly for all type dispatch:

```cpp
// PSX-era (2000): pure kind() dispatch, no cast needed
colActor = theLevel->getActor(*alIter);
if ( actbox->ActivatedByClass == colActor->kind() )
```

`baseobject.hp` itself didn't exist until 2003 — it was created as part of the same refactor that introduced `dynamic_cast`, migrating `EActorKind`/`kind()` from `actor.hp` into the new base class.

**Root cause:** in 2003, `Actor*` containers were generalised to `PhysicalObject*` / `BaseObject*` iterators to support the multi-type object system. That made downcasts necessary, and whoever did the refactor reached for `dynamic_cast` rather than `kind()`-guarded `static_cast`. `kind()` survived as a remnant with only 2 call sites.

---

## Recommendation

Leave `-fno-rtti` off. If Android binary size becomes a real constraint, the 51 `dynamic_cast` sites are the work to do — replace with `kind()`-guarded `static_cast` using the existing `EActorKind` enum. That refactor also makes the type-dispatch explicit and removes the hidden performance cost of failed `dynamic_cast` lookups.
