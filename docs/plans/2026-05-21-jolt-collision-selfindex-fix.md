# Plan — Fix `JoltContactDispatch` self-index bug (TODO:78)

**Date:** 2026-05-21
**Status:** In progress
**Owner:** Claude (Will reviewing)
**Branch:** `2026-new-level`

---

## Context

[`wfsource/source/game/actor.cc:1808`](../../wfsource/source/game/actor.cc):

```cpp
else
    charA->Collision(*charA, normal);  // no other-Actor known; collider idx → 0
```

The comment claims `collider idx → 0`, but it's wrong. `Actor::Collision` tests `IsActor(&other)`:

```cpp
if (IsActor(&other))
    _lastColliderIdx = static_cast<Actor&>(other).GetActorIndex();
else
    _lastColliderIdx = 0;
```

`*charA` IS an actor, so `IsActor(charA)` is true and `_lastColliderIdx` gets set to **Mario's own actor index**, not 0. Any script reading Mario's `COLLIDER_IDX` after he touches a wall or floor sees his own index — semantically meaningless.

Currently latent (Mario has no Script field in `smb_w1_1.lev`), but it's a ticking foot-gun for any future actor that reads its own `COLLIDER_IDX` to detect what it hit.

---

## Also: TODO:77 is already done

[`6bb9a14`](https://github.com/anthropics/wf/commit/6bb9a14) + [`7eb75ac`](https://github.com/anthropics/wf/commit/7eb75ac) + [`c23010e`](https://github.com/anthropics/wf/commit/c23010e) wired the full `CharacterContactListener → Actor::Collision` chain. The SMB `?`-block bump **does** work interactively. TODO:77 just wasn't checked off.

---

## Decisions

| # | Decision | Choice | Reason |
|---|----------|--------|--------|
| D1 | Fix API shape | Add `Actor::JoltStaticCollision(const Vector3& normal)` — sets `_lastColliderIdx = 0` and `_lastCollisionNormal = normal`, no `supportingObject` update. | `JoltContactDispatch` is a free function so can't access private members directly; a dedicated method is cleaner than a friend declaration or a new overload that looks like the existing `Collision(PhysicalObject&, Vector3)`. `supportingObject` is skipped because `movement.cc:437` confirms Jolt tracks ground state via `JoltCharacterIsOnGround`, not `supportingObject`. |
| D2 | Guard | `#ifdef PHYSICS_ENGINE_JOLT` around the method declaration in `actor.hp` and the call site. | Keeps the Jolt-specific API out of non-Jolt builds. |

---

## Milestones

### 1. Fix + mark both TODOs done — one commit

- `actor.hp`: add `void JoltStaticCollision(const Vector3& normal);` under `#ifdef PHYSICS_ENGINE_JOLT`.
- `actor.cc`: implement `Actor::JoltStaticCollision` — two assignments, no other side effects.
- `actor.cc` `JoltContactDispatch`: replace `charA->Collision(*charA, normal)` with `charA->JoltStaticCollision(normal)`.
- `TODO.md`: mark TODO:77 `[x]` and TODO:78 `[x]`.
- **Gate:** ASan-clean build; existing `wf_game_smoke_snow_cycle{1,2}` + `wf_host_gl_e2e_snow_cycle{1,2}` still pass; ctest 8/8 green.

---

## Verification

- Build + ctest (8/8 cycle tests).
- Run SMB interactively: bump a `?`-block from below — block should turn tan + coin pops (COLLIDER_IDX fires on the block, not Mario).
- After bumping a wall: Mario's `COLLIDER_IDX` should read 0 via bridge probe (not Mario's own index).

---

## Critical files

**Modify:** [`wfsource/source/game/actor.hp`](../../wfsource/source/game/actor.hp), [`wfsource/source/game/actor.cc`](../../wfsource/source/game/actor.cc), [`TODO.md`](../../TODO.md).

---

## Cross-references

- [Per-actor collision mailboxes commit `f4071a3`](https://github.com/anthropics/wf/commit/f4071a3)
- [Jolt collision wiring commits `6bb9a14` / `7eb75ac` / `c23010e`](https://github.com/anthropics/wf/commit/6bb9a14)
- [Bug logged: `8de17c4`](https://github.com/anthropics/wf/commit/8de17c4)
