# `spawn-template` — a Forth primitive to spawn template actors from script

**Date:** 2026-05-26
**Status:** Investigation / implementation reference (no code yet)

## Context

Today a level can only spawn a template-flagged actor by authoring a [`Generator`](../../wfsource/source/game/generator.cc)
actor in the `.lev` and firing it through its activation mailbox. That works for fixed
spawn points (the SMB `?`-block coin pops out of a per-block Generator), but it does not
work for **runtime-positioned** spawns: a fireball launched from wherever Fire Mario is
standing, an item dropped from a defeated enemy, a Hammer Bro's hammers, Bullet Bills from a
cannon. Each of those would need a Generator anchored at a *fixed* position in the level,
mediated through a mailbox — friction that scales badly with the number of spawn points and
can't express "spawn at the actor's current position."

This is the last engine-work blocker for several SMB World 1-1 enemies and for Fire Mario's
fireball ([SMB features → WF primitives](2026-05-26-smb-features-to-wf-primitives.md), backlog
item 3). It's already logged in [TODO.md](../../TODO.md) under SCRIPTING INFRASTRUCTURE. This
doc settles the design: the syscall mechanics, the layering, the authoring story for *naming* a
template from script, the edge cases, and a discrepancy it surfaces in the existing
`wfmut::SpawnActor`.

The shape we want, from the TODO:

```forth
( vx vy vz x y z template_idx -- new_actor_idx )
```

## How spawning works today

### The proven path — `Generator`

[`Generato::update()`](../../wfsource/source/game/generator.cc) is the only in-engine caller
that spawns at runtime. When its activation mailbox is non-zero it does **two** calls, in order:

```cpp
Actor* createdObject = theLevel->ConstructTemplateObject(objectToGenerate, _idxActor, pos, _vect);
if (createdObject) {
    theLevel->AddObject(createdObject, pos);   // <-- registers + assigns the actor index
}
```

Both calls matter:

- [`Level::ConstructTemplateObject`](../../wfsource/source/game/level.cc:1716) (`level.cc:1716`)
  → [`SafelyConstructTemplateObject`](../../wfsource/source/game/level.cc:1605) → the
  oas-generated factory. It allocates the actor, runs a **collision pre-check** at the spawn
  point, sets position/velocity (`setCurrentPos` + `setSpeed`), and binds assets. It does
  **not** register the actor in the level.
- [`Level::AddObject`](../../wfsource/source/game/level.cc:1287) (`level.cc:1287`) finds a free
  slot in the temporary-object region of `_actors[]`, calls `SetActorIndex`, adds the actor to
  its room's lists, and sets the mid-frame `HasRunPredictPosition` / `HasRunUpdate` flags so the
  freshly-added actor is skipped for the *rest of the current frame* (it joins the normal
  pipeline next frame).

A spawned actor that never gets `AddObject` has `GetObjectIndex() == 0`, is in no room list,
and so never updates or renders — it's an orphan. **`spawn-template` must mirror the Generator
and do both calls.**

### The collision pre-check is load-bearing, not optional

`SafelyConstructTemplateObject` returns **NULL** when the spawn point is occupied by something
the template would collide with — or, if the template's OAD names a `Poof` object, it recurses
and spawns the Poof instead (and returns NULL only if the whole Poof chain is blocked). So
`spawn-template` can legitimately return `0` (no actor created), and **the script must tolerate
that** (e.g. a fireball that would spawn inside a wall simply doesn't). This is a feature, not a
failure mode to paper over.

### The syscall mechanism (zForth)

[`scripting_zforth.cc`](../../engine/stubs/scripting_zforth.cc) bridges Forth to the engine
through zForth's `sys` opcode. `ZF_SYSCALL_USER = 128`; each WF primitive is a one-line word
that pushes a syscall id and calls `sys`:

```forth
: read-mailbox        128 sys ;   \ custom 0  ( idx -- val )
: write-mailbox       129 sys ;   \ custom 1  ( val idx -- )
: write-actor-mailbox 130 sys ;   \ custom 2  ( val idx actor_idx -- )
```

The handler's `default:` branch computes `custom = id - ZF_SYSCALL_USER` and switches on it
([`scripting_zforth.cc:118`+](../../engine/stubs/scripting_zforth.cc)). The existing comment
already reserves the next slots:

> `Syscalls 3-71 are reserved for future WF primitives (read-actor-mailbox at custom 3,
> spawn-template, etc.).`

So **`read-actor-mailbox` takes custom 3 (syscall 131)** and **`spawn-template` takes custom 4
(syscall 132)** — `: spawn-template 132 sys ;`.

The running actor's own index is already available to the handler as the module-static
`g_curObj` (set by `RunScript` at [`scripting_zforth.cc:341`](../../engine/stubs/scripting_zforth.cc)).
That's exactly the `parentIdx` the spawn path wants — and it's always `> 0` for a real actor
script, which satisfies `SafelyConstructTemplateObject`'s `assert(parentObjectIndex > 0)`.

## The layering problem (and the fix)

`scripting_zforth.cc` is in the **`scripting`** library; `theLevel` /
`Level::ConstructTemplateObject` are in **`game`**. The dependency runs `game → scripting`
(the game calls `RunScript`), so the scripting backend **must not** `#include <game/level.hp>` —
that would be a circular dependency. Today the backend reaches the engine only through
`MailboxesManager& g_mgr`, which is *injected* at `Init(mgr)`
([`scripting_zforth.cc:272`](../../engine/stubs/scripting_zforth.cc)). `write-actor-mailbox`
works because it stays inside the `mailbox` lib (`g_mgr->LookupMailboxes(actorIdx)`); spawning is
the first primitive that genuinely needs the `game` layer.

**Fix: inject a spawn callback the same way `g_mgr` is injected.** The game layer owns a small
function that wraps the two `theLevel` calls; the scripting layer holds a function pointer and
calls it, never naming `Level`.

```cpp
// shared scripting-layer header (e.g. scriptinterpreter.hp), no <game/...> include:
//   returns the new actor index, or 0 if nothing was spawned (collision / bad template).
typedef int (*SpawnTemplateFn)(int templateIdx, int parentIdx,
                               float x,  float y,  float z,
                               float vx, float vy, float vz);
void SetSpawnTemplateFn(SpawnTemplateFn fn);   // called once by the game at startup
```

```cpp
// game layer (where forth_engine::Init is called from the game's script setup):
static int wf_spawn_template(int tmpl, int parent,
                             float x, float y, float z,
                             float vx, float vy, float vz)
{
    if (tmpl <= 0 || !theLevel->HasTemplate(tmpl)) return 0;   // pre-validate (see below)
    if (parent <= 0) return 0;
    Vector3 pos(Scalar::FromFloat(x),  Scalar::FromFloat(y),  Scalar::FromFloat(z));
    Vector3 vel(Scalar::FromFloat(vx), Scalar::FromFloat(vy), Scalar::FromFloat(vz));
    Actor* a = theLevel->ConstructTemplateObject(tmpl, parent, pos, vel);
    if (!a) return 0;                       // blocked spawn point / exhausted Poof chain
    theLevel->AddObject(a, pos);            // <-- the call wfmut::SpawnActor is missing
    return a->GetActorIndex();
}
```

This mirrors the dependency-injection already in place (`g_mgr`), keeps the scripting lib
buildable without `game`, and lets every script engine share one implementation.

## Pre-validate to avoid engine asserts

`SafelyConstructTemplateObject` is studded with asserts: `assert(objectToGenerate > 0)`,
`assert(parentObjectIndex > 0)`, `assert(ValidPtr(startupData))`. A bad template index from a
script would abort the engine rather than fail gracefully. [`Level::HasTemplate(idx)`](../../wfsource/source/game/level.cc:1706)
(`level.cc:1706`) is the public probe added for exactly this — it bounds-checks against
`_numTemplateObjects` and the null entries. The callback must gate on `HasTemplate` (and
`parent > 0`) *before* calling, and return `0` on failure, as sketched above.

## Prior art: `wfmut::SpawnActor` — and a bug it reveals

The engine-mutation API already has [`wfmut::SpawnActor`](../../engine/mutation/wfmut.cpp:343)
(`wfmut.cpp:343`), used by the debug bridge / editor. It does the same pre-validation
(`HasTemplate`, `parentIdx`, `resolve_actor`) — good template to copy. **But it calls only
`ConstructTemplateObject` and then returns `created->GetActorIndex()` without ever calling
`AddObject`.** Per the Generator path above, that produces an actor that was never registered or
slotted into a room — `GetActorIndex()` returns the stale/zero index and the actor never
updates. This matches the memory note that the wfmut "spawn path" is *committed-but-unconfirmed*
([engine mutation API plan](../plans/2026-05-19-engine-mutation-api.md), "Mostly done — spawn
path open").

**Action:** `spawn-template`'s callback should do the *full* Generator sequence
(`ConstructTemplateObject` + `AddObject`), and `wfmut::SpawnActor` should be fixed to match —
ideally both routed through one shared helper so the two spawn entry points can't drift. Logged
as a follow-up below.

## The authoring story — how does a script name a template?

This is the non-obvious part. `Generator` doesn't have this problem: its `Object To Throw` is an
OAS object-reference field that **levcomp resolves to a numeric template index at compile time**.
A Forth script, by contrast, has only the raw integer — and template indices are assigned in
"levelcon order" ([`level.cc:510`](../../wfsource/source/game/level.cc)), which is not something
an author should hardcode by hand (it shifts whenever the level's object list changes — the same
fragility we already hit with Mario's actor index drifting per-export, which the SMB headless
tests work around by probing `X_POS` rather than assuming a fixed index).

Options, cheapest first:

1. **Carry the index in a mailbox the level sets.** The Blender exporter already knows each
   template's index; have it write the fireball template's index into a named global mailbox
   (e.g. `SMB_FIREBALL_TEMPLATE`) at level start, and the script reads it:
   `... INDEXOF_SMB_FIREBALL_TEMPLATE read-mailbox spawn-template`. Zero new engine machinery,
   reuses the [named-mailbox-constant convention](../../wfsource/source/oas/mailbox.inc). Best
   first step.
2. **Emit template-name constants into the script constant array.** Extend the `IntArrayEntry`
   list ([`AddConstantArray`](../../engine/stubs/scripting_zforth.cc:316)) with
   `TEMPLATE_<NAME>` → index entries generated from the level's template table, so a script can
   write `TEMPLATE_FIREBALL spawn-template`. Cleaner authoring, but needs the template→name map
   plumbed from levcomp into the constant array. Do this if spawn points proliferate.
3. **Resolve by name in the primitive itself** (`spawn-template-named ( ... addr len -- idx )`).
   Most ergonomic, most work (string handling in zForth is awkward — see the `TELL` syscall
   stub). Not worth it yet.

**Recommendation:** ship the primitive with option 1 (mailbox-carried index) for the fireball,
and revisit option 2 only when a second runtime-spawn site lands. Flag the index-fragility
explicitly in the fireball plan rather than hardcoding a literal.

## zForth handler sketch

Add to the `default:` branch in [`scripting_zforth.cc`](../../engine/stubs/scripting_zforth.cc),
after the `custom == 2` case:

```cpp
} else if (custom == 4) {
    // spawn-template ( vx vy vz x y z template_idx -- new_actor_idx )
    // Pops top-first: template_idx, then z,y,x (pos), then vz,vy,vx (vel).
    int   tmpl = (int)zf_pop(ctx);
    float z    = (float)zf_pop(ctx);
    float y    = (float)zf_pop(ctx);
    float x    = (float)zf_pop(ctx);
    float vz   = (float)zf_pop(ctx);
    float vy   = (float)zf_pop(ctx);
    float vx   = (float)zf_pop(ctx);
    int idx = 0;
    if (g_spawnFn)
        idx = g_spawnFn(tmpl, g_curObj, x, y, z, vx, vy, vz);   // parent = running actor
    zf_push(ctx, (zf_cell)idx);   // 0 if not spawned — script must handle
}
```

and the word definition in `Init`:

```cpp
r = zf_eval(&g_ctx, ": spawn-template 132 sys ;");
```

`zf_cell` is `float`, so the index round-trips exactly for the actor-count range; positions and
velocities are already floats on PC dev (`Scalar::FromFloat` at the C++ boundary; fixed-point on
the real target, where these values stay exact for the actor-count / position ranges in play).

## The other engines

zForth is the canonical level-scripting engine ([CLAUDE.md](../../CLAUDE.md)), so it lands first
and is the only one the SMB work needs. For parity, the underscore form `spawn_template` should
also be exposed in the other backends that register the mailbox bridge —
[`scripting_lua.cc`](../../engine/stubs/scripting_lua.cc) (also covers Fennel, which compiles to
Lua) and [`scripting_quickjs.cc`](../../engine/stubs/scripting_quickjs.cc) — by registering a C
closure that calls the same shared `SetSpawnTemplateFn` callback. Because the callback is
injected once at the game layer and shared, the per-engine work is just the language binding, not
the spawn logic. (WASM/Wren/etc. follow the same pattern when/if their bridges grow this far —
all 8 engines stay [default-on, all optional](../../CLAUDE.md).)

## Edge cases & gotchas

- **Returns 0 legitimately.** Blocked spawn point, exhausted Poof chain, or bad template → `0`.
  Scripts that act on the result (e.g. tracking the fireball's index) must guard `dup 0 > if …`.
- **`Scalar::Random()` is broken — but irrelevant here.** Generator's *random displacement*
  fields crash ([TODO: `Scalar::Random` aborts](../../TODO.md)); `spawn-template` takes an
  **explicit** position, so it sidesteps that bug entirely. Don't route spawn jitter through
  `Scalar::Random`; compute it in script if needed.
- **Mid-frame add semantics.** `AddObject` sets `HasRunPredictPosition/HasRunUpdate` so the new
  actor sits out the rest of the spawning frame and joins the pipeline next frame — same as a
  Generator spawn. A script that spawns and then immediately reads the new actor's `X_POS` the
  same tick sees the spawn position, not a simulated one. Expected.
- **Temporary-object pool exhaustion.** `AddObject` asserts "Too many temporary objects" when
  the temp region of `_actors[]` is full. Runaway spawning (e.g. a per-tick fireball with no
  cooldown) will hit it. Give spawners a `LevelClock`-based cooldown (express it in **seconds**,
  not ticks — the loop runs variable-dt) and pair short-lived projectiles with the existing
  `gold`-style TTL despawn idiom.
- **Velocity inheritance.** `ConstructTemplateObject` already calls `setSpeed(velocity)`, so the
  spawned actor moves under its own physics immediately — no extra mailbox poke needed (unlike
  the coin, which inherits the Generator's `_vect`).
- **Parent index.** Passing `g_curObj` as parent satisfies the `> 0` assert and stamps
  `idxCreator` so the spawned actor knows who made it (used by some collision filters). Correct
  default; no reason to expose it as a script argument yet.

## Validation plan

1. **Headless unit via the debug bridge.** New `tests/verify_spawn_template.py`: load SMB W1-1,
   inject a one-line script on a scratch actor that calls `spawn-template` with a known template
   index + position, then assert (a) actor count incremented, (b) the new actor exists at the
   given position (`X_POS`/`Z_POS` mailboxes), (c) a blocked spawn point returns 0 and does
   **not** increment the count. Watch for the "AddObject ok" stderr line the Generator already
   emits (and count those lines for the spawn assertion — the bridge's perf-actor counts are
   pool size, not live actors).
2. **The real use case — Fire Mario's fireball.** Author a fireball template + a fire-button
   branch in Mario's per-tick script that spawns it at his position with +X velocity (mirrored on
   facing), on a cooldown. Screenshot the fireball in flight (gameplay features need a visual
   capture as proof, not just a passing test). This is the deliverable that justifies the
   primitive.
3. **Regression:** the existing Generator-based coin pop-out and brick debris must be unchanged
   (they don't touch the new syscall, but confirm the `Init` word additions didn't perturb the
   dict).

## Scope estimate

Average-programmer scale:

- **zForth primitive + injected callback:** ~half a day. ~15 LOC in `scripting_zforth.cc`, ~10
  LOC for the game-layer callback + registration, a shared typedef/setter in the scripting
  header, plus the `wfmut::SpawnActor` fix and a shared helper. The mechanism is a direct copy of
  `write-actor-mailbox` + `wfmut::SpawnActor`.
- **Headless test + fireball demo (the proof):** ~half a day to a day, including authoring the
  fireball template and the template-index mailbox plumbing.
- **Parallel engines (Lua/QuickJS):** ~half a day if/when wanted; not needed for SMB.

No `mailbox.inc` change, but **this does add an engine C++ syscall**, so it needs an engine
rebuild (`task build`; touch `scripting_zforth.cc` to force the stub recompile, since the stub
`.o` mtime check ignores some dependency changes).

## Follow-ups this surfaces

- **Fix `wfmut::SpawnActor` to call `AddObject`** (or route both spawn entry points through one
  shared `Level` helper so they can't drift). Closes the "spawn path open" item on the
  [engine mutation API plan](../plans/2026-05-19-engine-mutation-api.md).
- **`read-actor-mailbox` (custom 3)** is the sibling primitive reserved in the same comment block;
  worth landing in the same pass since the enemy↔player scripts want it too
  ([TODO](../../TODO.md), [SMB roadmap](2026-05-25-smb-features-to-wf-primitives.md) backlog 4).
- **Template-name → constant emission** (authoring option 2) once a second runtime-spawn site
  appears.

## Sources

- [`Generato::update()` — the proven spawn sequence](../../wfsource/source/game/generator.cc)
- [`Level::SafelyConstructTemplateObject` / `ConstructTemplateObject` / `AddObject` / `HasTemplate`](../../wfsource/source/game/level.cc)
- [`scripting_zforth.cc` — syscall dispatch + `Init`/`RunScript`](../../engine/stubs/scripting_zforth.cc)
- [`scriptinterpreter.hp` — the injection interface](../../wfsource/source/scripting/scriptinterpreter.hp)
- [`wfmut::SpawnActor` — prior art (and the missing `AddObject`)](../../engine/mutation/wfmut.cpp)
- [SMB features → WF primitives mapping](2026-05-25-smb-features-to-wf-primitives.md)
- [TODO.md — SCRIPTING INFRASTRUCTURE backlog](../../TODO.md)
