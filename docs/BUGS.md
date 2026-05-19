# BUGS

Genuine bugs that have laid dormant for years before something surfaced them. Not TODOs, not feature gaps — bugs that *worked anyway* due to luck, dead code paths, or the bug never being exercised in practice.

Format per entry:
- **Title** with the date it was finally surfaced
- **Status:** FIXED `<sha>` | OPEN | INVESTIGATING
- **Symptom**, **Root cause**, **Why dormant**, **Fix**, **Investigation** (link)

---

## `~Level::~Level` violated `HALLmalloc` LIFO across three sites — 2026-05-18

**Status:** FIXED Phase B of [host-gl-e2e plan](plans/2026-05-18-host-gl-e2e-harness-and-unload-fix.md) (commit pending).

**Symptom:** `wf_game --frame-step-smoke=N -L<level>` asserts at [`memory/lmalloc.cc`](../wfsource/source/memory/lmalloc.cc):308 (`(_currentFree - fl->_size) == mem`) inside `~Level::deleting template objects` after the run completes and unload starts.

**Root cause:** Three independent caller-side LIFO violations in `~Level::~Level` and its dependencies:
1. `_theLevelRooms` outer object freed in [`level.cc`](../wfsource/source/game/level.cc):649 second, despite being allocated at :465 — *before* `_theAssetManager`, `_commonBlock`, `_templateObjects` array, per-template entries.
2. Per-template-object loop iterated forward (`for idxActor = 0; idxActor < _numTemplateObjects; ++idxActor`) instead of reverse.
3. `Animate::_channels` ([`anim/anim.cc`](../wfsource/source/anim/anim.cc):120) and `ActorMailboxes::_localMailboxes` (via [`mailbox/mailbox.cc`](../wfsource/source/mailbox/mailbox.cc):54) defaulted `Array<T>::SetMax`'s memory pool to `HALLmalloc` — per-actor data ended up on the HAL stack interleaved with per-template-object data; actor-iteration-order destruction freed them out of HAL-allocation order.

**Why dormant:** Standalone `wf_game` never ran the full in-process `LoadLevel → UnloadLevel` cycle until the `--frame-step-smoke=N` CLI added 2026-05-18 (editor Phase 0b sub-task 1). In every prior run, window-close / SIGTERM / fatal-error `exit()` killed the process mid-loop, never reaching `~Level::~Level`. The bug had been latent across multiple unload paths since the original 1999-era LevelCon-era code.

**Fix:** Reorder `~Level::~Level` body to reverse-LIFO; split `MEMORY_DELETE(_theLevelRooms)` into manual `~LevelRooms()` (early) + late `HALLmalloc.Free` of the outer; reverse the per-template-object loop; route `Animate::_channels` and `ActorMailboxes::_localMailboxes` through the per-level DMalloc pool; add `Array<T>::Clear()` so `_actors._items` can be freed at its LIFO position in `~Level` body instead of by the implicit `~Array()` afterward.

**Investigation:** [`docs/investigations/2026-05-18-unloadlevel-lifo-bug.md`](investigations/2026-05-18-unloadlevel-lifo-bug.md).

---

## REST API server thread joined after `exit()` → `std::terminate` — 2026-04-17

**Status:** FIXED — `RestApi_Stop` registered as a `sys_atexit` handler so the server stops + thread joins before static destructors fire.

**Symptom:** Process aborted with `std::terminate` on clean window-close shutdown; backtrace pointed at the global `std::thread gServerThread` destructor running while `joinable() == true`.

**Root cause:** `engine/stubs/rest_api.cc` started a background thread on engine startup but never joined it on shutdown. C++ requires `std::thread` destructors to fire either after `join()` or `detach()`; otherwise `std::terminate` is called. With `gServerThread` declared at file scope, its destructor ran during static destruction *after* `main` returned — too late to call `Stop()` from anywhere except a registered atexit hook.

**Why dormant:** Few people quit `wf_game` from the X11 window-close path; most testing relied on Ctrl-C / SIGTERM which doesn't invoke static destructors anyway. The REST API was added recently enough that the bug was caught within months rather than years.

**Fix:** See [`docs/plans/2026-04-17-fix-rest-api-shutdown-crash.md`](plans/2026-04-17-fix-rest-api-shutdown-crash.md) — register `RestApi_Stop` via `sys_atexit` so it runs *before* C++ static destructors.

---

## `_PlatformSpecificUnInit` asserted on a never-initialised `stacks` allocator — 2026-05-16

**Status:** FIXED commit `c3f89a7`.

**Symptom:** Clean engine shutdown (`exit(0)` from `main`) asserted on `assert(stacks)` in `hal/linux/platform.cc` (now `platform_init.cc`).

**Root cause:** `stacks` is a vestigial PIGS-era tasker allocator that was never wired up on Linux. The assert `assert(stacks)` in `_PlatformSpecificUnInit` would have caught a legit double-init / out-of-order shutdown on other platforms, but on Linux `stacks` is always `NULL`.

**Why dormant:** Same as the LMalloc one — `_PlatformSpecificUnInit` was rarely reached in practice. Surfaced by the same Phase 0b work that surfaced the LMalloc bug.

**Fix:** `if (stacks) { delete stacks; stacks = NULL; }` — guard instead of assert. Investigation at [`docs/investigations/2026-05-16-stacks-assert-on-clean-exit.md`](investigations/2026-05-16-stacks-assert-on-clean-exit.md).

---

## Jolt `JPH_ENABLE_ASSERTS` ODR violation — Jolt.a built without NDEBUG, consumers with NDEBUG — 2026-05-18

**Status:** FIXED — `target_compile_definitions(Jolt PUBLIC NDEBUG)` in our top-level [CMakeLists.txt](../CMakeLists.txt) (Jolt section) forces NDEBUG into Jolt.a's own TUs AND propagates to consumers.

**Symptom:** The `wf_host_gl_e2e_test` external-host harness (Phase 0b sub-task #3) reached `HALStart`, got through pigsys/audio/joystick init, then SIGTRAP'd at `BodyManager.cpp:126` (`active_bodies = new BodyID[inMaxBodies]`) inside Jolt's `RunSelftest()`. gdb showed `BodyManager::mActiveBodies[1] = 0xa9a9a9a900000000` (stack-fill pattern) instead of the nullptr the default-member-initializer `BodyID* mActiveBodies[2] = { };` was supposed to produce.

**Root cause:** Macros in Jolt's headers (`JPH_IF_ENABLE_ASSERTS`, etc.) expand differently depending on whether `NDEBUG` is defined at the include site. `ConstraintManager` even has a constructor that ONLY exists when JPH_ENABLE_ASSERTS is defined ([ConstraintManager.h:32](../engine/vendor/jolt-physics-5.5.0/Jolt/Physics/Constraints/ConstraintManager.h)):
```cpp
#ifdef JPH_ENABLE_ASSERTS
    ConstraintManager(PhysicsLockContext inContext) : mLockContext(inContext) { }
#endif
```

Jolt.a's own TUs (BodyManager.cpp etc.) compiled WITHOUT NDEBUG → `JPH_DEBUG` auto-defined → `JPH_ENABLE_ASSERTS` defined → ConstraintManager has the explicit ctor → PhysicsSystem's inline ctor calls `mConstraintManager(&mBodyManager)`.

wfengine's TUs (which set NDEBUG via `WF_DEFS`, [CMakeLists.txt:396](../CMakeLists.txt)) saw `JPH_DEBUG` NOT defined → `JPH_ENABLE_ASSERTS` NOT defined → ConstraintManager had NO user-declared ctors → compiler generated an implicit default ctor → PhysicsSystem's inline ctor did NOT explicitly init mConstraintManager.

When wfengine's physics_jolt.cc declared `JPH::PhysicsSystem ps;` on the stack, the COMPILER inlined the version of the ctor it could see (the one without `mConstraintManager(...)`), leaving the member half-initialised. Jolt.a's runtime code (BodyManager::Init's `JPH_ASSERT(active_bodies == nullptr)`) was compiled with ASSERTS ON and read the surrounding stack memory expecting properly-initialised state. wf_game's stack happened to have nullptr-like patterns in the right spots; the harness's stack had the 0xa9 fill pattern that tripped the assert.

**Why dormant:** wf_game was the only consumer of Jolt headers compiled with NDEBUG, and its stack frame in `RunSelftest()` happened to be quiet enough that the half-initialised state didn't fire the assert in practice. Adding a second external consumer (the e2e harness) — with even slightly different stack layout — surfaced the violation immediately. Could equally have manifested as silent corruption of physics state in a Release build.

**Fix:** [`CMakeLists.txt`](../CMakeLists.txt) Jolt section now calls `target_compile_definitions(Jolt PUBLIC NDEBUG)` so:
- Jolt.a's TUs compile with NDEBUG → JPH_DEBUG/JPH_ENABLE_ASSERTS off
- All consumers (wfengine, wf_game, harness, anything linking Jolt) inherit NDEBUG → same view
- `JPH_IF_ENABLE_ASSERTS` macro expands consistently everywhere
- `ConstraintManager` has the same ctor set in every TU
- No more ODR violation

This also removes runtime asserts from Jolt's compiled code, which is fine for our build (we're already on the side of "no asserts" via NDEBUG; the bug was the mismatch, not the asserts themselves).

---

## `BungeeCameraHandler` / `SPECIAL_COLLISION` reinterpret_cast type confusion — 2026-04-14

**Status:** OPEN — bypassed by the in-progress physics-engine replacement (Jolt, [`project_jolt_physics_functional`]).

**Symptom:** Lua spike (multi-script-engine development) immediately hit a segfault in `movecam.cc:1007`; bisection showed a `reinterpret_cast` from `BungeeCameraHandler*` to `Actor*` (or similar) where the underlying object layout doesn't match.

**Root cause:** Hand-rolled vtable-style dispatch in old physics code uses `reinterpret_cast` between unrelated class hierarchies. Worked in practice because the receiving function only read fields that happened to be at compatible offsets in the original layouts; new code that added members to one side broke the assumption.

**Why dormant:** The crash only fires when SPECIAL_COLLISION dispatch hits a code path that touches the post-misaligned fields. Snowgoons' geometry happened to avoid that combination.

**Fix:** Wholesale replace the physics layer ([`project_followup_replace_physics`]) — Jolt is the chosen replacement, currently parity-tested on snowgoons ([`project_jolt_physics_functional`]).

---

## Template

```
## <Title with what failed> — YYYY-MM-DD

**Status:** FIXED `<sha>` | OPEN | INVESTIGATING

**Symptom:** What the user (or a test) sees.
**Root cause:** What's actually wrong, with file:line citations.
**Why dormant:** Which exercise path was missing, or what masked it.
**Fix:** Minimal description; link the commit / plan.
**Investigation:** Link to docs/investigations/<date>-<slug>.md if there was one.
```
