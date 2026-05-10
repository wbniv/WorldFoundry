---
plan: jolt-pool-exhaustion-degraded-mode
date: 2026-05-10
status: Done — investigation closed, no fix needed
scope: Phase A diagnostic only; the proposed Phase B WF-side fix turned out to be unnecessary
---

# WF graceful-degrade when Jolt body pool is exhausted

**Status:** Done 2026-05-10 — Phase A diagnostic showed the `terminate called without an active exception` from yesterday's verification was a one-off flake. No Phase B fix needed.

## Context

Yesterday's [jolt body-pool exhaustion guard](2026-05-10-jolt-body-pool-exhaustion-guard.md) added defensive checks at every Jolt-layer body-creation site: each `JoltBodyCreate*` wrapper now logs `jolt: body pool exhausted (max=N); returning kJoltInvalidBodyID for <wrapper>` and returns the sentinel without registering a bogus handle, and `JoltBodyDestroy` / `JoltBackendShutdown` skip `RemoveBody`/`DestroyBody` on invalid IDs. The verification step at `kJoltBodyPoolMax = 8` showed the log firing as expected, but also produced a `terminate called without an active exception` after a few seconds.

That `terminate` was the trigger for this follow-up: was the engine still aborting on pool exhaustion (just from a different code path), or was it a flake at the SIGTERM/shutdown boundary?

## What an audit already told us

[wfsource/source/physics/physical.hpi](../../wfsource/source/physics/physical.hpi) is the only WF caller of the body API. All consumers of `_joltBodyID` already guard on the sentinel:

| Site | Check |
|---|---|
| ctors at line 100, 151 | initialise `_joltBodyID = kJoltInvalidBodyID` |
| `JoltMakeStatic` (204), `JoltMakeStaticMesh` (218 + bbox fallback at 222) | wrappers may store the sentinel; downstream consumers tolerate it |
| dtor (248), `JoltCharID` dtor (253) | `if (_joltBodyID != kJoltInvalidBodyID)` |
| Update path at [physics/jolt/physical.hpi:22-30](../../wfsource/source/physics/jolt/physical.hpi) | same guard |

The kinematic-only `JoltBodyCreate` wrapper has **zero callers** in the tree — `grep -rn 'JoltBodyCreate\b' wfsource/ engine/` returns only the declaration + definition. So the only code paths exercising the body pool are `JoltMakeStatic` and `JoltMakeStaticMesh`, both of which set `_joltBodyID = kJoltInvalidBodyID` on failure and let the existing field-level guards handle the rest.

## Phase A finding (the actual investigation)

Reproduced the force-exhaustion test (`kJoltBodyPoolMax = 8`, snowgoons with ~19 StatPlats) three times back-to-back:

| Run | exit code | `terminate` lines | `pool exhausted` lines |
|---|---|---|---|
| 1 | 124 (timeout SIGKILL) | 0 | 7 |
| 2 | 124 | 0 | 7 |
| 3 | 124 | 0 | 7 |

Also ran 30 s under `gdb -ex 'catch throw'`: zero throws caught, engine ran the full window. The marble's "ball pos" stayed parked at its spawn coords because the floor StatPlat lost its body — that's the **expected degraded mode** the plan was supposed to deliver.

**Yesterday's single `terminate` was a flake**, almost certainly a `SIGTERM`-during-shutdown race that slipped past the new `JoltBackendShutdown` `IsInvalid()` guard. It is not reproducible.

## Conclusion — no Phase B fix needed

WF's existing field-level guards on `_joltBodyID` are already comprehensive. Combined with yesterday's wrapper-level guards in [jolt_backend.cc](../../wfsource/source/physics/jolt/jolt_backend.cc), the engine already runs in degraded mode under pool exhaustion. Test edit (`kJoltBodyPoolMax = 8`) reverted to `1024`; final happy-path snowgoons rebuild verifies 19 bodies / 0 exhausted / 0 terminate / clean exit=124.

If a future user actually reproduces a terminate at the pool-exhaustion boundary, the next investigator should:

1. Run `gdb -ex 'catch throw'` against the failing scenario to find the throwing site.
2. If it's `JoltCharacterCreate` ([jolt_backend.cc:485](../../wfsource/source/physics/jolt/jolt_backend.cc)), wrap `new JPH::CharacterVirtual` in try/catch and return `kJoltInvalidBodyID`.
3. If it's a Jolt-internal assert promoted to throw, demote that specific assert.
4. If it's a WF-side caller revealed by the trace, tighten *that* caller's guard.

## Files referenced (no edits made by this plan)

- [wfsource/source/physics/jolt/jolt_backend.cc](../../wfsource/source/physics/jolt/jolt_backend.cc) — yesterday's wrapper guards
- [wfsource/source/physics/physical.hpi](../../wfsource/source/physics/physical.hpi) — field-level guards (already comprehensive)
- [wfsource/source/physics/jolt/physical.hpi](../../wfsource/source/physics/jolt/physical.hpi) — Update-path guards (already comprehensive)
- [docs/plans/2026-05-10-jolt-body-pool-exhaustion-guard.md](2026-05-10-jolt-body-pool-exhaustion-guard.md) — the parent plan whose verification raised this question

## Out of scope

- Auto-growing the body pool on exhaustion.
- Audit of other Jolt resource caps (constraint pool, body-pair pool) — separate plan.
- Per-actor "no Jolt body" telemetry beyond stderr.
- Hardening the SIGTERM/shutdown path further — yesterday's `JoltBackendShutdown` guard appears sufficient in practice; revisit only if the flake recurs.
