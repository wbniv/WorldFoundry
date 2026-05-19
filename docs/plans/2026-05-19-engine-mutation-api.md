# Plan — Engine mutation API (`wfmut::`)

**Date:** 2026-05-19
**Status:** **Done 2026-05-19 (~3 h vs ~1–2 wk estimate).** Six implementation commits + one consolidation commit on top of the wfcrdt wrapper, plus the user-feedback-driven WF_DEBUG_BRIDGE-independence refactor. `wfmut::` surface covers Set/GetActorPos + Set/GetActorOrientation + Set/GetActorField (int64/double/string) + Set/GetActorFieldString stub + ReloadActorScript + SpawnActor + RemoveActor + Set/GetMailbox + thread-local lastError. Bridge SET_TRANSFORM / SET_PROP / SET_MAILBOX cases now route through wfmut; the duplicate `kPropMap` in debug_server.cc is gone. `wf-edit` (editor build) smoke = 24/24 green (6 transform + 12 field + 3 spawn/remove + 3 mailbox); `wf_game` (lean) and `wf-edit` (editor stack) coexist as separate binaries. Happy-path spawn tests (SR1/SR2/SR7/SR8/SR10) deferred to manual / bridge-integration verification — first runtime-spawnable template in smb_w1_1 aborts on generic spawn-at-player-pos, needs a known-safe fixture.
**Estimate:** ~1–2 weeks per the [collaborative editor design doc](../investigations/2026-05-18-collaborative-level-editor-design.md) (line 780). Actual ~3 h.

---

## Context

The [wfcrdt C++ RAII wrapper landed today](/home/will/WorldFoundry.2026-new-level/docs/plans/2026-05-19-wfcrdt-cpp-raii-wrapper.md) (commits `dbfbe99..e6e4a03`, then docs `55c89f2`). It gives editor code `wfcrdt::Doc / Map / Array / Transaction / Output / Subscription` over the Yrs C ABI. The CRDT bridge is the next consumer in line — but right now there is no engine-side surface for it to call.

The [collaborative editor design](/home/will/WorldFoundry.2026-new-level/docs/investigations/2026-05-18-collaborative-level-editor-design.md) locked in the architecture 2026-05-19 (line 767):

> **The editor owns the Y.Doc, engine stays Rust-free, engine exposes a plain C++ mutation API that the editor's CRDT bridge drives. Same surface serves DAP debugger + replay UI + headless test harness, not just the editor.**

Today the only mutation surface is informal: [engine/stubs/debug_server.cc](/home/will/WorldFoundry.2026-new-level/engine/stubs/debug_server.cc) does its own ad-hoc field-resolution table (`kPropMap` at line 222), threads `PendingUpdate` records through a queue, and `const_cast`s into OAD blocks at line 696. The [REST API box POC](/home/will/WorldFoundry.2026-new-level/engine/stubs/rest_api.cc) maintains a parallel `gBoxes` map — a different surface entirely, debug-only.

This plan extracts the in-place actor-mutation primitives `debug_server.cc` already proved out, wraps them in a clean `wfmut::` API, and refactors `debug_server.cc` to consume the new surface. The bridge keeps owning consumer concerns (queueing, undo, pause/step, broadcast).

**Out of scope for v1:** observe-mutation-from-engine (cycle protection — engine doesn't write back to CRDT in the design), parent/hierarchy mutations (not in IFF schema today), shader hot-reload / screenshot / pause-step (stay in `debug_server`), Forth-scripting consumer (in-thread, no marshalling needed — keeps its own [scripting_libforth.cc](/home/will/WorldFoundry.2026-new-level/engine/stubs/scripting_libforth.cc) bridge buffer).

---

## Decisions

| Decision | Choice | Reason |
|---|---|---|
| Header location | `engine/mutation/wfmut.hpp` + `wfmut.cpp` | Matches [engine/crdt/wfcrdt.hpp](/home/will/WorldFoundry.2026-new-level/engine/crdt/wfcrdt.hpp) precedent (just landed). Editor-adjacent surfaces live under `engine/` in their own subdir. |
| Namespace | `wfmut::` | Matches `wfcrdt::` precedent — separate top-level namespace makes the editor-facing surface distinct from internal `wf::` engine types. |
| Threading | Synchronous, single-threaded. Callers responsible for marshalling (game-thread only). | Consumers (CRDT observer, DAP, replay, tests) all run on the game thread in the embedded-editor model. `debug_server.cc`'s network queue stays internal to that consumer. No `wfmut`-level mutex. |
| Identity | 1-based `idxActor` (matches `BaseObjectList` indexing, [actor.hpi:40-46](/home/will/WorldFoundry.2026-new-level/wfsource/source/game/actor.hpi)) | Engine-native; CRDT bridges maintain their own UUID↔idx mapping. No new identity scheme. |
| Field addressing | String paths `"block.field"` (e.g. `"common.hp"`, `"movebloc.Mass"`, `"mesh.ModelType"`) | Matches existing `kPropMap` keys, matches CRDT-bridge ergonomics (Y.Map keys are strings, types are read at observer time so the API can't be statically typed per field). |
| Field value type | Overloads on `int64_t`, `double`, `const char*` | Mirrors [wfcrdt::Map::insert](/home/will/WorldFoundry.2026-new-level/engine/crdt/wfcrdt.hpp) overload set. Fixed-point scaling is internal to `wfmut::` based on the field schema. |
| Error reporting | `bool` return for mutate ops; `std::optional<T>` for read ops; thread-local `wfmut::lastError()` string for diagnostics | Matches wfcrdt wrapper's optional-for-reads convention. Most callers will log on failure; bridge consumers can pull the diagnostic string for relay-back. |
| Read API in v1? | Yes — `GetActorPos`, `GetActorField`, `GetMailbox` siblings | Replay UI & headless test harness need reads. Cheap to add now while the surface is being designed. |
| `kPropMap` location | Move it to `wfmut.cpp` (single source of truth) | The field-resolution table is the API's spine. Leaving a copy in `debug_server.cc` violates [feedback_root_cause_not_symptom](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_root_cause_not_symptom.md) — two surfaces would drift. |
| Compile-time gating | **Two flags, with wfmut at the union.** `WF_DEBUG_BRIDGE` (default ON, forced OFF on mobile) for the Blender ↔ engine TCP/JSON bridge — independent debug infrastructure used by level designers and AI agents. `WF_ENABLE_EDITOR` (default OFF, forced OFF on mobile) for the collaborative editor app (CRDT, replay UI, DAP). `WF_REST_API` stays as its own small flag (default ON). wfmut::, wfmut_smoke, and the `--wfmut-smoke` CLI are compiled when EITHER `WF_DEBUG_BRIDGE` or `WF_ENABLE_EDITOR` is set — both consumers drive the mutation API. | Two iterations on this: my original plan said "fold into libwfengine.a, no opt-out" — wrong because wfmut won't build on Android/iOS where the editor host doesn't exist, and shipped mobile builds shouldn't carry editor-stack symbols. First fix collapsed everything into a single `WF_ENABLE_EDITOR`; the user clarified mid-refactor (2026-05-19): "`WF_DEBUG_BRIDGE` is independent of the editor mode and is needed by level designs and agents debugging alike — we'd like `WF_DEBUG_BRIDGE` on in general." So the bridge is general-purpose debug infrastructure, not editor-app code. The editor *uses* wfmut, the bridge *uses* wfmut, so wfmut sits at their union. Memory: [feedback_editor_code_compile_gate](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_editor_code_compile_gate.md). |
| Refactor `debug_server.cc`? | Yes, in the same plan (step 7) | The whole point of unifying is to have one mutation path. Leaving `debug_server.cc`'s duplicate alive defeats the goal. |
| Mailbox API addressing | `(level, idxActor, mailboxIndex, value)` — direct, no global constants table | Mailboxes are addressed by integer index throughout the engine. The named-constants concern from [feedback_named_mailbox_constants](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_named_mailbox_constants.md) is **scripting-side**, not engine-side. **Plan flags this:** per [feedback_indexof_prefix_wanted_gone](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_indexof_prefix_wanted_gone.md), the `INDEXOF_` prefix should eventually go — but that migration is independent of this API and is called out explicitly so it doesn't quietly become a `wfmut::` concern. |
| Spawn signature | `SpawnActor(level, templateIdx, pos)` returning `std::optional<uint32_t>` (new idx) + convenience `SpawnActorByTemplateName(level, name, pos)` if a name→index lookup utility already exists | Underlying `Level::ConstructTemplateObject(templateObjectIndex, parentObjectIndex, pos, vel)` at [level.cc:1695](/home/will/WorldFoundry.2026-new-level/wfsource/source/game/level.cc) is the primitive; v1 wraps it directly. Name-lookup convenience is opt-in if a utility exists; otherwise add as a `wfmut::` v2 helper. |
| Remove signature | `RemoveActor(level, idx)` → `bool` (queued for removal, deferred deletion) | Wraps `Level::SetPendingRemove(actor)` at [level.cc:1333](/home/will/WorldFoundry.2026-new-level/wfsource/source/game/level.cc). Deletion runs in `Level::update()` → `removePendingObjects()` at line 1038. |

---

## API surface (full sketch)

```cpp
// engine/mutation/wfmut.hpp
#pragma once
#include <cstdint>
#include <optional>
#include <string>

class Level;
class Vector3;
class EulerAngles;  // or whatever the engine's orientation type is — check before writing

namespace wfmut {

// ── Identity ────────────────────────────────────────────────────────────────
// idxActor is 1-based, matches Level::GetObject() indexing.
using ActorIdx = std::uint32_t;

// ── Errors ──────────────────────────────────────────────────────────────────
const char* lastError();  // thread-local; empty after a successful call.

// ── Transform ───────────────────────────────────────────────────────────────
bool SetActorPos(Level& level, ActorIdx idx, const Vector3& pos);
std::optional<Vector3> GetActorPos(const Level& level, ActorIdx idx);

bool SetActorOrientation(Level& level, ActorIdx idx, const EulerAngles& e);  // angles in revolutions per [feedback_angles_in_revolutions]
std::optional<EulerAngles> GetActorOrientation(const Level& level, ActorIdx idx);

// ── OAD field writes ────────────────────────────────────────────────────────
// fieldPath = "common.hp" / "movebloc.Mass" / "mesh.ModelType" / etc.
// Internal kPropMap dispatches on path → block accessor + offset + fixed32 flag.
// Writes are in-place (NOT copy-on-write); shared OAD pages affect every actor
// pointing at them. Full COW is deferred to a follow-up plan when a consumer
// hits the dedup-collision problem.
bool SetActorField(Level& level, ActorIdx idx, const char* fieldPath, std::int64_t value);
bool SetActorField(Level& level, ActorIdx idx, const char* fieldPath, double      value);
bool SetActorField(Level& level, ActorIdx idx, const char* fieldPath, const char* value);

std::optional<std::int64_t> GetActorFieldInt(const Level& level, ActorIdx idx, const char* fieldPath);
std::optional<double>       GetActorFieldFloat(const Level& level, ActorIdx idx, const char* fieldPath);
std::optional<std::string>  GetActorFieldString(const Level& level, ActorIdx idx, const char* fieldPath);

// ── Spawn / remove ──────────────────────────────────────────────────────────
std::optional<ActorIdx> SpawnActor(Level& level, int templateIdx, const Vector3& pos,
                                   ActorIdx parentIdx = 0);
bool RemoveActor(Level& level, ActorIdx idx);

// ── Mailbox ─────────────────────────────────────────────────────────────────
// Note: scripting-side callers should reference INDEXOF_* / MB_* constants from
// mailbox.inc, not bare integers — see feedback_named_mailbox_constants. The
// engine-internal API takes a raw int because the constant table is
// scripting-side.
bool SetMailbox(Level& level, ActorIdx idx, int mailboxIndex, double value);
std::optional<double> GetMailbox(const Level& level, ActorIdx idx, int mailboxIndex);

} // namespace wfmut
```

---

## Implementation steps

Each step is its own commit per [feedback_commit_after_each_phase](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_commit_after_each_phase.md). Standing directives during execution: log gotchas to [docs/level-design-troubleshooting.md](/home/will/WorldFoundry.2026-new-level/docs/level-design-troubleshooting.md) as they surface ([feedback_log_discoveries_in_todo](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_log_discoveries_in_todo.md)); keep [wf-status.md](/home/will/WorldFoundry.2026-new-level/wf-status.md) row + plan-doc `**Status:**` in sync ([feedback_plan_status_sync](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_plan_status_sync.md)).

### 1. Skeleton + CMake + plan-doc copy

- Create `engine/mutation/wfmut.hpp` with all declarations from the API sketch.
- Create `engine/mutation/wfmut.cpp` with stub bodies that return `false` / `std::nullopt` and set `lastError()` to `"not implemented"`.
- Add a CMake target / source-list entry parallel to [engine/crdt/CMakeLists.txt](/home/will/WorldFoundry.2026-new-level/engine/crdt/CMakeLists.txt) (or extend the main CMakeLists if mutation lives in `wfengine`). Build target should be `libwfmut.a` or fold into `libwfengine.a` — decide based on the wfcrdt precedent (wfcrdt is a separate static lib so it can be opted-out; mutation has no such optionality, so fold into `libwfengine.a`).
- Copy this plan to `docs/plans/2026-05-19-engine-mutation-api.md` and add a row to `wf-status.md` Active table.
- `task build` stays green.

### 2. Transform: `SetActorPos` / `GetActorPos` / `SetActorOrientation` / `GetActorOrientation`

- `SetActorPos` calls `level.GetObject(idx)` → `dynamic_cast<Actor*>` → `actor->setCurrentPos(pos)`. Per [actor.hpi:84-110](/home/will/WorldFoundry.2026-new-level/wfsource/source/game/actor.hpi), `setCurrentPos` already syncs the Jolt body and Jolt character via `JoltCharacterSetPosition` / `JoltBodySetPosition` if valid IDs exist — no extra physics-sync work needed in `wfmut`. The existing `Mobility==0` cerror warning at [actor.hpi:88](/home/will/WorldFoundry.2026-new-level/wfsource/source/game/actor.hpi) stays where it is; `wfmut::SetActorPos` returns `true` even when the warning fires (the mutation succeeded, just on an unwanted target — caller's problem). Tests for mobility=0 actors must suppress or expect the cerror output.
- `GetActorPos` reads `actor->currentPos()`.
- `SetActorOrientation` / `GetActorOrientation` — find the engine's orientation accessor (likely `currentEuler()` / a member of `_physicalAttributes`) before writing; angles in revolutions per [feedback_angles_in_revolutions](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_angles_in_revolutions.md). If Jolt-body sync isn't automatic on orientation, mirror the position pattern.
- Tests: see [Test matrix § Transform](#test-matrix).

### 3. Fields: move `kPropMap` from `debug_server.cc` → `wfmut.cpp`

- Lift the `PropInfo` struct and `kPropMap` table from [debug_server.cc:214-241](/home/will/WorldFoundry.2026-new-level/engine/stubs/debug_server.cc) into `wfmut.cpp` (file-scope `static`).
- Lift the `debug_get_block(actor, block_id)` helper from [debug_server.cc:244-256](/home/will/WorldFoundry.2026-new-level/engine/stubs/debug_server.cc) similarly.
- Implement `SetActorField` overloads. Internal flow: look up path → resolve block + offset + `is_fixed32` → for `double`, multiply by 65536 if fixed32, truncate to `int32`; for `int64`, treat as raw; for `const char*`, only allowed on `common.Script` field (matches existing `forth_engine::ReloadActorScript` path at [debug_server.cc:840](/home/will/WorldFoundry.2026-new-level/engine/stubs/debug_server.cc)).
- Implement `GetActorFieldInt` / `GetActorFieldFloat` / `GetActorFieldString` siblings.
- Refactor `debug_server.cc`'s `kPropMap` consumers (`SET_PROP` case in `DrainQueue`, lines ~660–700) to call `wfmut::SetActorField` instead. **Do NOT delete `debug_server.cc`'s undo bookkeeping** — `gChangeStack` / `gPropOriginals` are consumer-side state; bridge keeps owning those. The mutation API is plain — undo is a debug-bridge concern.
- **Resolve `common.Script` semantics before implementing the `const char*` overload.** In `debug_server.cc:657-659`, `common.Script` is rejected as read-only via `SET_PROP`; script source updates go through `reload_script` → `forth_engine::ReloadActorScript`. Three options: (a) `SetActorField(idx, "common.Script", str)` returns `false` and `lastError() = "use wfmut::ReloadActorScript"`; (b) DWIM and call `forth_engine::ReloadActorScript` under the hood; (c) leave the overload accepting strings for any future string-typed OAD field but reject `common.Script` specifically. **Recommendation: (a)** + add `wfmut::ReloadActorScript(level, idx, src)` as a sibling primitive. Keeps the field-write API honest (only stable OAD scalar fields) and surfaces script reload as its own first-class op. Adds one extra commit step (step 3b) for the script-reload primitive.
- Tests: see [Test matrix § Fields](#test-matrix).

### 4. Spawn / remove: `SpawnActor` / `RemoveActor`

- `SpawnActor`: wraps [Level::ConstructTemplateObject(templateObjectIndex, parentObjectIndex, pos, vel)](/home/will/WorldFoundry.2026-new-level/wfsource/source/game/level.cc) at line 1695. `parentIdx` defaults to 0 (no parent). Velocity defaults to `Vector3::zero` — check for existing constant per [feedback_check_existing_constants](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_check_existing_constants.md). Return value: the new actor's `idxActor` (read from the freshly spawned actor's `GetActorIndex()`), or `std::nullopt` if `ConstructTemplateObject` returned null.
- `RemoveActor`: wraps `Level::SetPendingRemove(actor)` at [level.cc:1333](/home/will/WorldFoundry.2026-new-level/wfsource/source/game/level.cc). Returns `true` on successful queueing. Removal is deferred — actor stays alive until `Level::update()` reaches `removePendingObjects()` at [level.cc:1038](/home/will/WorldFoundry.2026-new-level/wfsource/source/game/level.cc).
- Frame-step driver for tests: use `WFGame::StepFrame(do_swap=false, &dt)` from [Phase 0b frame-step API](/home/will/WorldFoundry.2026-new-level/docs/plans/2026-05-18-engine-frame-step-api.md) so the test runs headless. Tests stepping a frame to observe deferred removal use this entry point.
- Tests: see [Test matrix § Spawn/Remove](#test-matrix).

### 5. Mailbox: `SetMailbox` / `GetMailbox`

- Wrap `Mailboxes::WriteMailbox(idx, value)` and the matching read accessor. Resolve the actor first (`level.GetObject(idx) → Actor*`), then access its mailboxes via the same path `debug_server.cc:807-809` uses.
- Refactor `debug_server.cc`'s `SET_MAILBOX` case to call `wfmut::SetMailbox`. Undo bookkeeping stays in `debug_server.cc`.
- Tests: see [Test matrix § Mailbox](#test-matrix).

### 6. Refactor `debug_server.cc`'s `SET_TRANSFORM` to call `wfmut::SetActorPos`

- Replace direct `actor->setCurrentPos(pos)` call in the `SET_TRANSFORM` handler with `wfmut::SetActorPos(level, idx, pos)`. Undo bookkeeping for transform (already at `debug_server.cc:644-645` saving original `currentPos()` on first touch) stays in the bridge — it's a consumer concern.
- After this step, every `wfmut`-eligible op in `debug_server.cc`'s `DrainQueue` routes through the API. The remaining drain handlers (`pause`/`step`/`resume`/`undo_step`/`revert_all`/`watch`/`unwatch`/`inject_input`/`set_shader`/`reload_script`/`screenshot`) stay in `debug_server.cc` — they're not mutation-API surface (control flow, debug overlays, GL hot-reload, undo, observation).
- Manual verification: launch `wf_game` with `--debug-port 7777`, connect Blender bridge, move an actor in Blender, confirm it teleports in the game window. Same `task run-debug` flow that's documented in the live-editor-bridge plan.

### 7. Docs + status sync

- Plan-doc `**Status:**` → `Done YYYY-MM-DD (~Xh vs Y estimate)` with one yffi-style discovery note if anything surprising came up. Per [feedback_plan_duration_tracking](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_plan_duration_tracking.md), round to hours for sub-day work.
- [wf-status.md](/home/will/WorldFoundry.2026-new-level/wf-status.md): prepend a one-sentence Summary paragraph (per [feedback_wf_status_paragraph_length](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_wf_status_paragraph_length.md)) linking to this plan; update Active row.
- [Editor design doc](/home/will/WorldFoundry.2026-new-level/docs/investigations/2026-05-18-collaborative-level-editor-design.md) Tier 2 section: append "Engine mutation API landed YYYY-MM-DD; CRDT bridge can now consume `wfmut::Set/GetActorField` etc." Note that direct-read engine bridge (1–2 wk estimate at line 665) now has its second-of-three building blocks complete (Yrs C ABI + RAII wrapper + **mutation API**); remaining piece is IFF↔Y.Doc translator (~2–3 wk).
- [TODO.md](/home/will/WorldFoundry.2026-new-level/TODO.md): if any incidental discoveries surfaced during implementation, log them per [feedback_log_discoveries_in_todo](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_log_discoveries_in_todo.md).

---

## Test matrix

All cases load `wflevels/smb_w1_1.iff` (or a smaller dedicated fixture if available), get a known stable actor idx (player), and drive frame-steps via [`WFGame::StepFrame(do_swap=false, &dt)`](/home/will/WorldFoundry.2026-new-level/docs/plans/2026-05-18-engine-frame-step-api.md). Each section's tests live in `engine/mutation/wfmut_test.cc`.

### Transform

| # | Case | Expected |
|---|---|---|
| T1 | `SetActorPos` happy round-trip with positive/negative/zero components | `true`; `GetActorPos` returns the written value (component-equal under `Scalar` precision) |
| T2 | `SetActorPos` with `Vector3::zero` | `true`; round-trips cleanly |
| T3 | `SetActorPos` on idx=0 | `false`; `lastError() != ""` |
| T4 | `SetActorPos` on idx=Size()+1 (out of range) | `false`; `lastError() != ""` |
| T5 | `SetActorPos` on idx pointing to non-Actor `BaseObject` | `false`; `lastError() != ""` |
| T6 | `SetActorPos` on actor with `Mobility==0` | `true` (write succeeded), cerror surfaces from `actor.hpi:88`; test redirects stderr or matches |
| T7 | `SetActorPos` on player → step a frame → Jolt body position matches via `JoltCharacterGetPosition` | Jolt sync confirmed |
| T8 | `SetActorPos` with NaN / +Inf components | Document behaviour (probably `true` written, engine instability possible; flag as "don't do this") |
| T9 | `SetActorOrientation` happy round-trip at rev=0.0, 0.25, 0.5, 0.99 | All round-trip cleanly |
| T10 | `SetActorOrientation` at rev=1.0 | Wraparound semantics confirmed (engine convention: `0 ≤ rev < 1` per [feedback_angles_in_revolutions](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_angles_in_revolutions.md)) |
| T11 | `GetActorPos` / `GetActorOrientation` on bad idx | `std::nullopt` |

### Fields

| # | Case | Expected |
|---|---|---|
| F1 | `SetActorField(idx, "common.hp", 100.0)` then `GetActorFieldFloat` | round-trips with fixed32 scaling (`hp` is `is_fixed32=true` per [debug_server.cc:224](/home/will/WorldFoundry.2026-new-level/engine/stubs/debug_server.cc)) |
| F2 | `SetActorField(idx, "movebloc.Mass", 1.5)` then read | fixed32 round-trip; precision loss documented (`1.5 × 65536 → 98304 → ÷65536 = 1.5` exact) |
| F3 | `SetActorField(idx, "movebloc.MovementClass", int64_t{2})` then read | raw int32, no scaling |
| F4 | `SetActorField(idx, "mesh.ModelType", int64_t{3})` then read | covers `mesh.*` block |
| F5 | `SetActorField(idx, "mesh.AnimationMailbox", int64_t{INDEXOF_INPUT_value})` then read | int32 mailbox-index field; ensures `mesh.*` raw-int path is tested |
| F6 | `SetActorField(idx, "common.Script", "src")` (string overload) | per the step-3 design resolution above: returns `false`, `lastError() = "use wfmut::ReloadActorScript"`. Test asserts that decision. |
| F7 | `wfmut::ReloadActorScript(level, idx, src)` happy path | `true`; script source replaced; next frame's script tick uses new body |
| F8 | `wfmut::ReloadActorScript` with malformed Forth | `false`; `lastError()` includes the Forth compile log |
| F9 | `SetActorField(idx, "common.NotARealField", 0)` | `false`; `lastError() = "unknown field path"` |
| F10 | `SetActorField` type mismatch — write `double{1.5}` to a non-fixed32 raw-int field | document behaviour: truncate to int32? reject? Recommended: truncate, log a warning |
| F11 | Fixed32 overflow — `SetActorField(idx, "movebloc.Mass", 1e9)` (would be `1e9 × 65536 > INT32_MAX`) | document behaviour: saturate? wrap? Recommended: clamp to `INT32_MIN/MAX` and set `lastError()` |
| F12 | Bad idx on `SetActorField` | `false` (all idx-validation paths share one check) |
| F13 | **OAD page sharing semantics** — write `common.hp` to actor A; if any actor B is reachable that shares A's `_Common` page (template dedup), assert that B's `common.hp` ALSO changed (in-place behaviour) | Document the limitation; this test pins behaviour so future COW work is a clean change in test expectations |
| F14 | Bridge `gWatches` regression — register watch on `movebloc.MaxGroundSpeed`, drive `wfmut::SetActorField` from the test, confirm `BroadcastState` would have flagged a change | refactor in step 7 didn't break the bridge's read-side broadcast |

### Spawn / Remove

| # | Case | Expected |
|---|---|---|
| SR1 | `SpawnActor(level, validTemplateIdx, pos)` | returns new idx; `GetActorPos(newIdx)` succeeds in same drain step (same-frame visibility) |
| SR2 | `SpawnActor` returned-idx invariant — confirm `level.GetObject(newIdx)->GetActorIndex() == newIdx` | identity round-trip is consistent |
| SR3 | `SpawnActor` with `parentIdx = 0` (no parent) | succeeds |
| SR4 | `SpawnActor` with valid `parentIdx` (existing actor) | succeeds; parent linkage observable if engine exposes it |
| SR5 | `SpawnActor` with non-existent `parentIdx` | reject? Silent fallback to 0? Document the actual `Level::ConstructTemplateObject` behaviour and pin it. |
| SR6 | `SpawnActor` with negative or out-of-range `templateIdx` | `std::nullopt` |
| SR7 | `RemoveActor(validIdx)` then `GetActorPos(idx)` BEFORE next StepFrame | actor still readable (deferred deletion) |
| SR8 | `RemoveActor(validIdx)` then StepFrame → `GetActorPos(idx)` | `std::nullopt` (actor cleaned up) |
| SR9 | `RemoveActor` then `SetActorField(idx, ...)` before StepFrame | document behaviour: silent success? Error? Set is a write to the still-alive `_Common` block — likely succeeds and the change is lost on deletion. Pin the behaviour. |
| SR10 | Double-remove: `RemoveActor(idx)` twice in same drain | second call returns `false` cleanly (not assert/crash) |
| SR11 | `RemoveActor(0)` / out-of-range idx | `false`; `lastError()` populated |
| SR12 | **ASan stress** — `for i in 0..1000 { newIdx = SpawnActor(...); RemoveActor(newIdx); StepFrame(); }` | no leaks; runtime stable |
| SR13 | Identity invariance — track if `idxActor` slots are reused after deletion or always monotonic; document & pin | regression-test the engine's identity-allocation policy |
| SR14 | Spawn from inside an Actor's tick (re-entrancy) — drive via a tiny test script that calls `wfmut::SpawnActor` indirectly | safe; no `Level::update()` re-entry issues |

### Mailbox

| # | Case | Expected |
|---|---|---|
| M1 | `SetMailbox(level, idx, 5, 42.0)` then `GetMailbox` | `42.0` |
| M2 | `SetMailbox` at mailbox idx 0 (first slot) | `true`; round-trips |
| M3 | `SetMailbox` at `NumberOfLocalMailboxes - 1` (last valid slot) | `true`; round-trips |
| M4 | `SetMailbox` at `NumberOfLocalMailboxes` (one past end) | `false`; `lastError()` populated. Pin this — also relevant to [project_followup_mailbox_999_crash](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_followup_mailbox_999_crash.md) |
| M5 | `SetMailbox` with negative mailbox idx | `false` |
| M6 | `SetMailbox` on an actor without mailboxes (cast-check fails per `debug_server.cc:807-809`) | `false` |
| M7 | `SetMailbox` with NaN / Inf value | document behaviour |
| M8 | Mailbox 999 (the [known-crash boundary](/home/will/.claude/projects/-home-will-WorldFoundry/memory/project_followup_mailbox_999_crash.md), `GLOBAL_USER_MAX`) | reject at API boundary cleanly; do NOT propagate to the level-storage off-by-one. This is the right place to fix the symptom even if root cause is in level storage — flag as TODO per [feedback_root_cause_not_symptom](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_root_cause_not_symptom.md). |
| M9 | Bad actor idx on `SetMailbox` / `GetMailbox` | `false` / `std::nullopt` |

### Cross-cutting

| # | Case | Expected |
|---|---|---|
| X1 | `lastError()` is thread-local and clears on the next successful call | Confirmed; concurrent-test-safe |
| X2 | `lastError()` returns `""` (or `nullptr`) after a successful call | Defined empty state |
| X3 | Build with `WF_ENABLE_CRDT=OFF` | `wfmut` still compiles + links + tests pass — `wfmut` does NOT depend on `wfcrdt` |
| X4 | Build with `-DWF_ASAN=ON -DCMAKE_BUILD_TYPE=Debug` | All tests above pass with zero ASan leak reports |
| X5 | Cross-thread defensive — call `wfmut::SetActorPos` from a `std::thread` (debug-only) | In debug builds: assert + abort with a clear message ("wfmut must be called on game thread"). In release: UB, documented. Captures the game-thread id once on first call. |
| X6 | Bridge regression manual test — `task run-debug -- wflevels/smb_w1_1.iff`, connect Blender, drag Mario in viewport | Mario teleports in-engine same as before refactor. Capture screenshot per [feedback_screenshots_for_proof](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_screenshots_for_proof.md). |
| X7 | Bridge regression: `scene:set_prop` for `movebloc.MaxGroundSpeed`, observe Mario's run feels different — same outcome as pre-refactor | bridge consumer flow unchanged after step 7 |
| X8 | Bridge regression: `set_mailbox` op → check engine mailbox value via the bridge's `watch` notification | mailbox write + read-side broadcast both still work |

### Out-of-scope tests (explicit deferral list)

- Multi-Level test (loading two `.iff`s sequentially; `wfmut` operates on whichever is current). v1 single-level only.
- True COW behavior tests (current behaviour is in-place — F13 pins the limitation). When COW lands, replace F13's expectation.
- DAP-debugger consumer integration tests. Lands with the DAP plan.
- CRDT-bridge integration tests. Lands with the IFF↔Y.Doc translator plan.

---

## Critical files

**To modify or create:**

- **NEW** `engine/mutation/wfmut.hpp` — public API surface.
- **NEW** `engine/mutation/wfmut.cpp` — implementation. Hosts the relocated `kPropMap`.
- **NEW** `engine/mutation/wfmut_test.cc` — round-trip tests for each primitive.
- **NEW** `engine/mutation/CMakeLists.txt` (or fold into root `CMakeLists.txt`).
- **NEW** `docs/plans/2026-05-19-engine-mutation-api.md` — copy of this plan into the repo.
- Modify `engine/stubs/debug_server.cc` — remove `kPropMap` (lines 214–256), refactor `SET_PROP` / `SET_TRANSFORM` / `SET_MAILBOX` cases in `DrainQueue` to call `wfmut::*`.
- Modify [wf-status.md](/home/will/WorldFoundry.2026-new-level/wf-status.md) — prepend Summary paragraph + Active row.
- Modify [docs/investigations/2026-05-18-collaborative-level-editor-design.md](/home/will/WorldFoundry.2026-new-level/docs/investigations/2026-05-18-collaborative-level-editor-design.md) — Tier 2 entry append.

**To read (no edits):**

- [wfsource/source/game/actor.hpi](/home/will/WorldFoundry.2026-new-level/wfsource/source/game/actor.hpi) — `setCurrentPos` (line 84) already does Jolt sync; orientation accessor needed.
- [wfsource/source/game/level.cc](/home/will/WorldFoundry.2026-new-level/wfsource/source/game/level.cc) — `ConstructTemplateObject` (line 1695), `SetPendingRemove` (line 1333), `removePendingObjects` (line 1038).
- [wfsource/source/oas/common.ht, movebloc.ht, mesh.ht](/home/will/WorldFoundry.2026-new-level/wfsource/source/oas/) — block field layouts for `offsetof`.
- [engine/crdt/wfcrdt.hpp](/home/will/WorldFoundry.2026-new-level/engine/crdt/wfcrdt.hpp) — naming + namespace + overload-set precedent.
- [docs/plans/2026-05-19-wfcrdt-cpp-raii-wrapper.md](/home/will/WorldFoundry.2026-new-level/docs/plans/2026-05-19-wfcrdt-cpp-raii-wrapper.md) — recent plan-doc shape to mirror.

---

## Verification

1. **`task build` clean** with the new `wfmut` sources.
2. **`wfmut_test` passes** — round-trip each primitive (transform, field-int/float/string, spawn/remove, mailbox) against `smb_w1_1` load. Run as a CTest entry next to `wfcrdt_wrapper_test`.
3. **Existing C smoke + wrapper tests still green** — `wfcrdt_smoke`, `wfcrdt_wrapper_test`, and the Blender bridge manual test ([Phase 1 verification recipe](/home/will/WorldFoundry.2026-new-level/docs/plans/2026-04-29-live-editor-bridge.md)) all continue to pass after the `debug_server.cc` refactor.
4. **ASan clean** — build with `-DWF_ASAN=ON -DCMAKE_BUILD_TYPE=Debug`, run `wfmut_test` + `wfcrdt_wrapper_test`. Zero leaks.
5. **Bridge regression** — `task run-debug -- wflevels/smb_w1_1.iff`, connect Blender, move player, confirm position propagates. This proves `debug_server.cc`'s `SET_TRANSFORM` / `SET_PROP` / `SET_MAILBOX` cases still work after their internals were rewired through `wfmut`.
6. **Screenshot proof** per [feedback_screenshots_for_proof](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_screenshots_for_proof.md): capture before/after of the Blender drag → engine teleport flow with the refactored bridge.

---

## Cross-references

- Parent design: [Collaborative editor design § Tier 2 Engine↔CRDT bridge](/home/will/WorldFoundry.2026-new-level/docs/investigations/2026-05-18-collaborative-level-editor-design.md) (line 767, 780).
- Predecessor plans: [Yrs C ABI binding (landed)](/home/will/WorldFoundry.2026-new-level/docs/plans/2026-05-18-yrs-c-abi-binding.md), [wfcrdt C++ RAII wrapper (landed today)](/home/will/WorldFoundry.2026-new-level/docs/plans/2026-05-19-wfcrdt-cpp-raii-wrapper.md).
- Sibling consumer plan: [Live editor bridge (Phase 1, 2a, 3 implemented)](/home/will/WorldFoundry.2026-new-level/docs/plans/2026-04-29-live-editor-bridge.md) — this plan unifies the bridge's mutation paths under `wfmut::`.
- Memory: [feedback_commit_after_each_phase](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_commit_after_each_phase.md), [feedback_plans_in_project](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_plans_in_project.md), [feedback_named_mailbox_constants](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_named_mailbox_constants.md), [feedback_indexof_prefix_wanted_gone](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_indexof_prefix_wanted_gone.md), [feedback_angles_in_revolutions](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_angles_in_revolutions.md), [feedback_check_existing_constants](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_check_existing_constants.md), [feedback_plan_duration_tracking](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_plan_duration_tracking.md), [feedback_plan_status_sync](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_plan_status_sync.md), [feedback_log_discoveries_in_todo](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_log_discoveries_in_todo.md), [feedback_screenshots_for_proof](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_screenshots_for_proof.md), [feedback_root_cause_not_symptom](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_root_cause_not_symptom.md).
- External: [Yrs C ABI](https://github.com/y-crdt/y-crdt), [Yjs document updates](https://docs.yjs.dev/api/document-updates).
