# The 2003 `BaseObject` extraction — archaeology, critique, recommendation

**Date:** 2026-05-30
**Status:** Discussion / design review — **no code changed.** Proposes a targeted refactor of the hierarchy.
**Owner:** Claude + Will
**Branch:** `2026-new-level`
**Scope note:** The RTTI / `kind()` / `dynamic_cast` question is **deliberately out of scope** — see [`2026-04-29-rtti-audit.md`](2026-04-29-rtti-audit.md) and [`../plans/2026-04-29-eliminate-rtti.md`](../plans/2026-04-29-eliminate-rtti.md). This doc judges the *class boundary* and the *member placement*, on the design's own merits — not on the code's age or churn risk.

## TL;DR

On **2003-05-15**, Kevin&nbsp;T.&nbsp;Seghetti (`kts`) created `BaseObject` as a new abstract root above the then-root `PhysicalObject`. Two separable things happened in that sitting:

- **(a) Consolidation** — hoist the message-port code (duplicated in `game/` and `physics/`), plus `CommonBlock` and the read-only OAD-data pointer, into one shared ancestor. **Correct then, correct now.** It is what gives the engine its acyclic module graph.
- **(b) A new class boundary** — split that ancestor into a *distinct* `BaseObject` above `PhysicalObject`, justified by anticipated **non-physical game objects**.

The non-physical objects never arrived, so the chain is strictly linear and the `Is*` predicates are `return bo;`. But the layers turn out to earn their keep for a *different* reason `kts` didn't state: they are **interface-segregation seams** that let `physics/`, `movement/`, and `anim/` compile against an abstract object **without** depending on `game/Actor`. Judged on pure CS, the defects are narrow and specific:

1. **One layer is genuinely redundant.** `physics/`+`anim/` depend on `PhysicalObject` (Actor-free ✓), `movement/` depends on `MovementObject` (Actor-free ✓) — those seams are real. But **no module depends on `BaseObject` without also depending on `PhysicalObject`**, so the `BaseObject`↔`PhysicalObject` split decouples nothing. It is the speculative (b) boundary itself.
2. **Several members sit above the lowest-common-ancestor of their callers** (ISP). `GetMsgPort`/`sendMsg` are on `BaseObject` but their highest caller is `PhysicalObject&`; `KillSelf` is on `BaseObject` but its highest caller is `MovementObject&`.
3. **Two helpers are named the inverse of what they do** (`UpcastTo*` that downcast).

**Recommendation: targeted refactor** — fold `BaseObject` into `PhysicalObject` (one root, not two), drop each member to its caller-LCA, rename the helpers. Keep `PhysicalObject` and `MovementObject` (load-bearing seams). Not a revert (loses (a)); not an ECS rewrite (wrong scale for the actual defect).

---

## 1. The changeset (archaeology)

Not in git — git's first commit is [`a2784f6`](https://github.com/wbniv/WorldFoundry/commit/a2784f6) (2010-05-01). The change lives in the SourceForge `wf-gdk` CVS snapshot (see [`../sourceforge-cvs-snapshot.md`](../sourceforge-cvs-snapshot.md)). CVS has no atomic changesets, so this is one ~90-minute sitting by `kts`, reconstructed by grouping `,v` revisions on shared timestamp+log:

| Time (2003-05-15) | Files (rev) | Verbatim CVS log |
|---|---|---|
| 05:29:04 | `baseobject/baseobject.{hp,cc,hpi}` 1.1 | **"first added: base class which all game objects are derived from, contains common block pointer, and OAD pointer"** |
| 05:30:16 | `baseobject/commonblock.*` 1.1 | "simple commonblock pointer container" |
| 05:30:41 | `baseobject/msgport.*`, `msgtypes.hp` 1.1 | "message port code moved from game" |
| 05:34:04 | `physics/msgport.*`, `msgtypes.hp` → **dead** | "msgport code moved to baseobject" |
| 05:41:56 | `physics/physicalobject.cc` 1.5 | "moved sendMsg functions to baseobject" |
| **05:46:46** | `physics/physicalobject.hp` 1.11 | **"moved msgport.hp to baseobject, PhysicalObject is now derived from BaseObject"** |
| 06:32:42 | `game/actor.hp` 1.34 | "moved msgport to baseobject directory, moved _oadData down into BaseObject" |
| 06:58:12 | `game/level.hp` 1.30 | **"_actors & _tempObjects are now arrays of pointers to BaseObject instead of Actor"** |

Before rev 1.11, `physicalobject.hp` declared `class PhysicalObject` with **no base**; the refactor inserted `BaseObject` above it. (Inference, flagged honestly: the pre-2003 msgport *duplication* is read from the CVS log + the surviving `state dead` `physics/msgport.*` envelopes, not from the 2003 source text directly.)

> Aside: the class was **never literally named `PhysicalBaseObject`** — that string appears nowhere in the snapshot. The remembered name conflates `PhysicalObject` (old root) and `BaseObject` (new one).

## 2. What it looks like today

```
BaseObject              abstract root (2003). Data: _oadData, _commonBlock.
  │                     Iface: sendMsg, GetMsgPort*, GetMailboxes*, KillSelf*, kind*,
  │                     BindAssets/UnBindAssets.   ◄── REDUNDANT with PhysicalObject:
  │                                                    no module depends on it without
  │                                                    also depending on PhysicalObject.
  └─ PhysicalObject     SEAM (real). physics/ + anim/ build against it Actor-free.
       │                Collision() [overridable], currentDir(), GetPhysicalAttributes*,
       │                GetMovementBlockPtr() [33 call sites].
       └─ MovementObject SEAM (real). movement/ builds against it Actor-free.
            │            GetMovementManager*, predictPosition/update, Path* _path.
            │            (holds the movement *interface*; the state lives in Actor —
            │             which is correct for an interface seam.)
            └─ Actor     implementation. ~16 KB of state + logic.
                 ├─ Player ├─ Enemy ├─ Platform ├─ Camera ├─ Light ├─ Spike
                 ├─ Tool(→ToolNeedleGun/ToolShield) ├─ Warp ├─ Director ├─ Generator
                 └─ Missile, Gold, Matte, Shadow, Shield, Target, StatPlat, ActBox,
                    ActBoxOR, CamShot, Explode, Destroy …  (≈23 leaves — ALL are Actors)
```

The chain is strictly linear; the code says so itself (`baseobject.hp:103-114`), with `IsActor`/`IsMovementObject`/`IsPhysicalObject` all `return bo;`. The interesting question is *why that's mostly fine* — and where it isn't.

## 3. Critique (on the design's merits; RTTI excluded)

### 3.1 The layers are dependency-inversion seams, not subtype-speculation

`kts`'s stated rationale — non-physical objects populating `BaseObject*` lists — never materialized. But the structure he built does real work that doesn't depend on that rationale: **it inverts the module dependency graph.** Verified against the live tree:

- `physics/` builds **Actor-free** — `colbox.cc:34` is a commented-out `actor.hp`; nothing else names `Actor`. `physics/collision.cc:227` sends a collision message through `object1.sendMsg(...)` on a `PhysicalObject&`, never knowing what an `Actor` is.
- `anim/` operates on `PhysicalObject&` — `animmang.cc:331` calls `physicalObject.GetMsgPort()`.
- `movement/` builds **Actor-free** — only a forward `class Actor;` in `movefoll.hp:14`; the handlers operate on `MovementObject&`.

So `PhysicalObject` is the interface through which `physics/`+`anim/` manipulate game objects, and `MovementObject` is the interface through which `movement/` does — each without a compile dependency on `game/`. That is textbook dependency inversion, and an abstract layer holding little or no *state* is exactly what such a seam should be. **`PhysicalObject` and `MovementObject` earn their place.** The consolidation half (a) is what makes this possible: the shared root owns the message-port plumbing, so the lower modules need only the abstract handle.

(Caveat the panel overstated: this is *compile-firewall* decoupling within one `wfengine` static library — there is no per-module `.a`. It is real maintainability value, not a link boundary.)

### 3.2 The redundant layer: `BaseObject` vs `PhysicalObject`

A layer is justified, on pure CS, iff some client depends on its interface **but not on its subclasses**. Apply that test:

| Layer | A client that needs it but not its subclasses? | Verdict |
|---|---|---|
| `PhysicalObject` | `physics/`, `anim/` (Actor-free, never name `MovementObject`/`Actor`) | **earns it** |
| `MovementObject` | `movement/` (Actor-free) | **earns it** |
| `BaseObject` | — none found — every consumer of the `BaseObject` interface (`room/` asset code, `game/` `MailboxesManager`) **also** depends on `PhysicalObject` | **redundant** |

`room/` walks the object list as `BaseObject` for asset binding, but `room.cc:354-390` downcasts the same elements to `PhysicalObject*` for collision checks — so `room/` includes `physicalobject.hp` regardless. `MailboxesManager` (`level.cc:323-325`) uses a bare `BaseObject*`, but it lives in `game/`, which depends on everything. **No module is decoupled by the `BaseObject`↔`PhysicalObject` boundary.** That boundary is precisely the speculative (b) split, and it is the one part of the structure with no client to justify it. (Load-bearing claim — verified across `physics/ movement/ room/ anim/`; confirm there is no fourth external consumer before executing.)

The cost of the redundant layer is the **downcast tax**: ~51 `static_cast` sites across 21 files. Folding `BaseObject` into `PhysicalObject` retypes the object list `Array<BaseObject*>` → `Array<PhysicalObject*>` and **erases every `BaseObject`→`PhysicalObject` downcast** (the bulk of the 51) along with the vacuous `IsPhysicalObject`. The remaining downcasts (`→MovementObject`, `→Actor`) are legitimate — they cross the *real* seams.

### 3.3 Misplaced members (Interface Segregation)

Place each member at the **lowest-common-ancestor of its actual callers**. Two are too high:

- **`GetMsgPort` + `sendMsg`** are on `BaseObject`, but every caller invokes them on `PhysicalObject&` or lower — `collision.cc:227,233` (`PhysicalObject&`), `animmang.cc:331,337` (`PhysicalObject&`), `movement/*` and `movecam.cc:653,955` (`MovementObject&`), `actor.cc:860` (`this`). **Never on a bare `BaseObject&`/`*` (verified empty).** LCA = `PhysicalObject`.
- **`KillSelf`** is on `BaseObject`, implemented only in `Actor::KillSelf` (`actor.cc:1740`), called on `MovementObject&` (`movepath.cc:139`). LCA = `MovementObject`.

`GetMailboxes` is the counter-example that **stays at the root**: `level.cc:325` calls it on a bare `BaseObject*` (the index-keyed `MailboxesManager`), so it has a genuine root-level client. `BindAssets`/`UnBindAssets` likewise stay — `actrooms.cc:182,219` dispatch them polymorphically on a `BaseObject&` with **no** downcast (the room asset-transition walk). After the fixes, the root exposes exactly what its own comment claims — *"what the object list code refers to, as well as the asset handling code"* — and nothing it doesn't.

### 3.4 The `Upcast*` helpers are named backwards

```cpp
// physicalobject.hpi:69
PhysicalObject& UpcastToPhysicalObject(BaseObject* base) { … return *static_cast<PhysicalObject*>(base); }
```

`BaseObject` is the parent; `static_cast` parent→child is a **down**cast. `UpcastToPhysicalObject`/`UpcastToMovementObject` assert the opposite of their behavior — a comprehension trap and a fossil of the imagined world where generic `BaseObject`s flowed "up" through the system. (5 call sites in `shadow.cc`; defs in `physicalobject.{hp,hpi}`, `movementobject.{hp,hpi}`.) The `→PhysicalObject` pair mostly disappears with the §3.2 fold; the `→MovementObject` one stays and gets an honest name.

## 4. Recommendation: targeted refactor

The principled target hierarchy is **three layers**, each non-leaf layer an interface that some Actor-free module depends on:

```
PhysicalObject  (root)   ← absorbs BaseObject: _oadData, _commonBlock, GetMailboxes,
  │                         BindAssets/UnBindAssets, kind, sendMsg/GetMsgPort, Validate.
  │                         The object-list / asset / physics handle.
  └─ MovementObject        ← movement seam; gains KillSelf (its caller-LCA).
       └─ Actor            ← implementation.
```

### The moves (each follows from a CS principle, not from risk appetite)

1. **Fold `BaseObject` into `PhysicalObject`** (YAGNI + the layer-justification test, §3.2). Delete the `BaseObject` class; move its members onto `PhysicalObject` as the new root. Retype `Array<BaseObject*>`→`Array<PhysicalObject*>` and the `BaseObjectIterator` family. Erases the `→PhysicalObject` downcasts and `IsPhysicalObject`.
2. **Drop `GetMsgPort`/`sendMsg` to `PhysicalObject`** and **`KillSelf` to `MovementObject`** (ISP, §3.3). After the fold, messaging naturally lands at the new root (`PhysicalObject`), which is correct; `KillSelf` moves one further level down to its caller-LCA.
3. **Rename `UpcastTo*` → `DowncastTo*`** (§3.4).
4. **Keep `PhysicalObject` and `MovementObject`.** They are load-bearing seams (§3.1); collapsing them would couple `physics/`/`anim/`/`movement/` back into `game/`.
5. **Land it with characterization tests** for the two genuinely-polymorphic paths — collision `sendMsg` dispatch and the room `BindAssets`/`UnBindAssets` transition — so the refactor *proves* it preserves behavior. (Behavior preservation is a correctness obligation discharged by tests, not a reason to defer.)

### Options not taken

| Option | Why not |
|---|---|
| **Revert** | Restores the pre-2003 state where msgport was duplicated across `game/` + `physics/`. The consolidation (a) is good independent of the speculation (b). |
| **Leave-as-is** | Lets a redundant layer, two mis-placed interfaces, and two backwards-named helpers stand — all identifiable from the code alone. |
| **ECS / full re-engineer** | Wrong scale for the actual defect. The seam structure (DIP via abstract layers) is sound and idiomatic; the problem is one redundant layer and member altitude, not the use of inheritance. Composition already exists where it belongs (`MovementHandler`, the mailbox bus). |

### Decision rule (CS, not calendar)

> **A layer earns its place iff some module depends on its interface but not on its subclasses; a member belongs at the lowest-common-ancestor of its callers.** By that rule: `PhysicalObject` and `MovementObject` stay (real Actor-free clients), `BaseObject` folds in (no client depends on it without `PhysicalObject`), and `GetMsgPort`/`sendMsg`/`KillSelf` drop to their caller-LCA. If a genuine non-physical object is ever authored, re-extract a physics-agnostic root *then* — when a real client for it exists — rather than carrying the empty seam speculatively.

### One honest counter-argument

Keeping a physics-agnostic root named `BaseObject` documents "object-list element" as a concept distinct from "physical thing," and pre-positions the seam for a future non-physical object. Pure-CS YAGNI rejects carrying that speculatively (re-extracting a base class is cheap *when* the need is real), but it is the one defensible argument for the status quo, recorded here for the reader to weigh.

## 5. How this verdict was reached

Multi-agent review: 4 fact-gatherers → 4 critique lenses (YAGNI, cohesion/SRP, historical steelman, engineering economics) → 1 adversarial synthesizer. The panel initially leaned "leave-as-is," but several of its supports were errors I caught and **verified against the live tree** before they reached this doc: it called `PhysicalObject` "hollow" (false — `currentDir`/`GetMovementBlockPtr`/`Collision`, 33 call sites), and it mis-read the layering as dead speculative generality (it is dependency-inversion seams — `physics/`/`movement/`/`anim/` build Actor-free). Removing those errors, plus discarding the panel's age/stability and churn-risk arguments as non-reasons, leaves the recommendation above, which rests only on ISP / DIP / YAGNI applied to the verified call graph. The one adjacent modernization doc, [`2026-05-20-actor-kind-vs-capability.md`](2026-05-20-actor-kind-vs-capability.md), concerns the `EActorKind` **leaf** taxonomy under `Actor`, not this spine — it neither blesses nor blocks the recommendation.
