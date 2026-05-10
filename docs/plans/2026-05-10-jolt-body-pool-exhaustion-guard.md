---
plan: jolt-body-pool-exhaustion-guard
date: 2026-05-10
status: Done
scope: ~30-50 LOC in [wfsource/source/physics/jolt/jolt_backend.cc](../../wfsource/source/physics/jolt/jolt_backend.cc)
---

# Jolt body-creation defensive guard against pool exhaustion

**Status:** Done — implemented and verified on 2026-05-10.

## Context

The 2026-05-10 cap-bump investigation ([docs/investigations/2026-05-10-qbert-engine-caps.md](../investigations/2026-05-10-qbert-engine-caps.md)) found that when the Jolt body pool is exhausted, `gBodyInterface->CreateAndAddBody()` returns `JPH::BodyID(0xFFFFFFFF)` (invalid). The previous wrapper code stored the invalid id in a registered `BodyEntry` and returned a valid wrapper handle anyway. Later, when the next `JoltMakeStaticMesh` ran and saw a non-invalid wrapper handle, `JoltBodyDestroy` called `RemoveBody(invalidID)` → segfault inside `JPH::BodyManager::DestroyBodies`.

Yesterday's symptom: Q*bert with 1344 cube actors and Jolt pool sized for 1024 → cubes 1025–1344 silently registered with invalid joltID → segfault on the next destroy. Diagnosed via gdb backtrace; the pool was bumped to 4096 to unblock the day, then reverted to 1024 once Phase 1 cube consolidation dropped to 28 bodies. The silent-failure-then-segfault behaviour is a footgun the next pool-exhaustion incident would rediscover.

This plan adds the defensive check at every Jolt body-creation site so future exhaustion produces a clean, loggable diagnostic ("jolt: body pool exhausted, returning kJoltInvalidBodyID") instead of an obscure crash.

## What this does NOT do

- Does not change the pool size (already restored to 1024 post Phase 1 cube consolidation).
- Does not add automatic resize / growth — caller-side fallback is the contract.
- Does not touch CharacterVirtual creation — that path doesn't call `CreateAndAddBody` (separate Jolt API; `JoltCharacterCreate` instantiates `JPH::CharacterVirtual` directly).
- Does not audit WF actor-layer callers for graceful degradation when `kJoltInvalidBodyID` is returned. See "Follow-up" below.

## Approach (implemented)

Three coordinated changes in [wfsource/source/physics/jolt/jolt_backend.cc](../../wfsource/source/physics/jolt/jolt_backend.cc), plus one file-scope constant.

### 0. File-scope pool-size constant

Captured the body-pool size as `static constexpr unsigned int kJoltBodyPoolMax = 1024;` near the other module-level state, and changed `gPhysicsSystem->Init(...)` to use it. This keeps the log message in sync with the actual pool size — bump in one place, log reflects it everywhere.

### 1. Defensive return at every CreateAndAddBody call site (3 wrappers)

All three production wrappers indirect through `CreateAndAddBody`:

| Wrapper | Indirection | CreateAndAddBody site |
|---|---|---|
| `JoltBodyCreate` | → `CreateJoltBodyKinematic` → `CreateJoltBodyImpl` | `gBodyInterface->CreateAndAddBody(cfg, act)` |
| `JoltBodyCreateStatic` | → `CreateJoltBody` → `CreateJoltBodyImpl` | same |
| `JoltBodyCreateStaticMesh` | direct | `gBodyInterface->CreateAndAddBody(cfg, JPH::EActivation::DontActivate)` |

For all three: after the inner Create returns, the wrapper now checks `id.IsInvalid()` (the idiomatic Jolt check; sentinel is `JPH::BodyID::cInvalidBodyID = 0xffffffff`, declared at [engine/vendor/jolt-physics-5.5.0/Jolt/Physics/Body/BodyID.h](../../engine/vendor/jolt-physics-5.5.0/Jolt/Physics/Body/BodyID.h)). If invalid:

- Log to stderr: `"jolt: body pool exhausted (max=N); returning kJoltInvalidBodyID for <wrapper>\n"` (N = `kJoltBodyPoolMax`, so any future pool-size change is reflected).
- Skip `AllocEntry()` — would consume a wrapper-handle slot we can't honour.
- Return `kJoltInvalidBodyID` (the sentinel callers expect; declared in [jolt_backend.hp](../../wfsource/source/physics/jolt/jolt_backend.hp)).

The check lives inside the public wrapper functions, immediately after the inner-helper return, so each wrapper logs its own name without threading a name parameter through `CreateJoltBodyImpl`.

### 2. Guard in `JoltBodyDestroy`

Belt-and-suspenders: if a registered entry's `joltID` somehow ended up invalid (which the wrappers above now prevent), skip the `RemoveBody`/`DestroyBody` pair — they segfault inside `BodyManager::DestroyBodies` on an invalid id. Still mark `e.occupied = false` so the wrapper-handle slot is reclaimed.

### 3. Same guard in `JoltBackendShutdown`

Mirrors `JoltBodyDestroy`: the shutdown loop iterates `gBodies` and calls `RemoveBody`/`DestroyBody` on every occupied entry. Now wraps that pair with `if (!e.joltID.IsInvalid())` for the same reason.

## Critical files

| File | Change |
|---|---|
| [wfsource/source/physics/jolt/jolt_backend.cc](../../wfsource/source/physics/jolt/jolt_backend.cc) | new `kJoltBodyPoolMax` constant + `Init` uses it; per-wrapper `IsInvalid` check after `CreateAndAddBody` (3 sites); guard in `JoltBodyDestroy`; guard in `JoltBackendShutdown` |

No header changes; no caller changes; no test fixtures.

## Existing facts reused

- `kJoltInvalidBodyID` (already declared in [jolt_backend.hp](../../wfsource/source/physics/jolt/jolt_backend.hp)) — the sentinel callers already check against. Existing fallback at [physical.hpi](../../wfsource/source/physics/physical.hpi) (`if (_joltBodyID == kJoltInvalidBodyID) _joltBodyID = JoltBodyCreateStatic(...)`) demonstrates the contract.
- `JPH::BodyID::IsInvalid()` ([BodyID.h](../../engine/vendor/jolt-physics-5.5.0/Jolt/Physics/Body/BodyID.h)) — single-line check, no allocation.

## Verification

1. **Engine builds clean** with `bash engine/build_game.sh` — done, no warnings introduced.
2. **Snowgoons happy-path boot** with default pool (1024): 19 Jolt bodies created, no `pool exhausted` log lines, no asserts, clean run until SIGTERM.
3. **Force-exhaustion test** with `kJoltBodyPoolMax = 8`: `jolt: body pool exhausted (max=8); returning kJoltInvalidBodyID for JoltBodyCreateStatic` fired 7 times. **No segfault** in `JoltBodyDestroy` or `JoltBackendShutdown` (confirms the IsInvalid guards work). The downstream `terminate called` originates from WF actor-layer code that doesn't gracefully handle `kJoltInvalidBodyID` — out of plan scope; see Follow-up.
4. Test edit reverted; final boot with `kJoltBodyPoolMax = 1024` re-verified clean.

## Follow-up (separate plan if anyone hits it)

The Jolt layer is now safe under pool exhaustion, but the WF actor layer still aborts (`terminate called without an active exception`) when too many actors get `kJoltInvalidBodyID` back. The existing fallback at [physical.hpi](../../wfsource/source/physics/physical.hpi) only covers one path. A follow-up sweep would let the engine actually run in degraded mode (collision-less actors) instead of aborting, but that's a wider audit and is deferred until someone hits it for real.

Other deferred items from the cap investigation:

- Auto-growing the body pool on exhaustion (would require Jolt-side support; risky without throughput testing).
- Per-actor "tried to create body but pool was full" telemetry beyond stderr (no current sink).
- Audit of other Jolt resource caps (constraint pool, body-pair pool, etc.) for similar silent-failure modes.
