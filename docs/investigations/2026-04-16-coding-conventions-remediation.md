# Coding-conventions remediation — 2026 additions

**Date:** 2026-04-16
**Scope:** every line of code authored under `wfsource/source/` since
2026-01-01. This is the "worked example" that proves
[`docs/coding-conventions.md`](../coding-conventions.md) is actionable — and
an honest accounting of where my own recent additions don't yet follow the
rules they now propose.

## Audit universe

Enumeration command:

```
git log --since=2026-01-01 --name-only --pretty=format: -- 'wfsource/source/**' \
  | sort -u | grep -Ev '^$'
```

That raw list is large (~500 paths) because Batches 5–8 were mass-deletion
cleanup passes that touched many files. Deletions don't author new
convention violations, so the audit universe is narrowed to **substantive
2026 additions** — new files and hunks that introduced new logic:

| Subsystem | Files in scope | Nature |
|---|---|---|
| `physics/jolt/` | `jolt_backend.hp`, `jolt_backend.cc`, `jolt_math.hp`, `physical.hpi` | new files — Jolt integration (commit `b17a7ca` Phases 1–3) |
| `physics/` (non-jolt) | `physical.hp`, `physical.hpi` | hunks added for Jolt handle plumbing |
| `movement/` | `movement.cc` | `PHYSICS_ENGINE_JOLT` branches in `GroundHandler` / `AirHandler` |
| `hal/` | `halbase.h` | validation-off item-macro shims; `haltest.cc` is deletion-only |
| `input/` | spacebar→jump change in movement mapping (commit `48c17e1`) | small; reviewed |
| `scripting/` | Lua/Fennel/Wren/WAMR integration work | vendor-wrapper code; out of scope here — see follow-up |
| OAS | `oas/gold.oas` | new OAS type; verified against §9 compat rules |

**Excluded from this audit (by convention):**
- Vendored third-party code (Jolt, Lua, WAMR, Wren source trees) — §13.
- Batches 5–8 dead-code deletions (no new authored lines).
- Restored GL-pipeline renderer files (commit `ec49c72`) — restoration of
  pre-existing code, not fresh authoring.

Pure-deletion or move-only commits are out of scope: removing code can't
author a new violation.

---

## Findings

Severity key:

- **blocker** — violates a load-bearing rule (streams, Validate, STL in
  runtime, no-fallbacks). Should be fixed before the code ships as
  production runtime.
- **cleanup** — WF-local hygiene (names, headers, types, include guards,
  boilerplate). Fix in a sweep.
- **accept** — explicitly sanctioned by the guide (e.g. free-function API
  at a foreign-library boundary per §13). Recorded so future readers know
  it was audited, not missed.

| # | File:Line | Rule (§) | Severity | Fix sketch |
|---|---|---|---|---|
| 1 | `physics/jolt/jolt_backend.cc:177,234,335,414,451,530,556,579` | §12 streams | **blocker** | 8× `std::fprintf(stderr, ...)` calls. Replace with `DBSTREAM3(cjolt << ... << std::endl;)` after registering `cjolt` per §12.4 |
| 2 | `physics/jolt/jolt_backend.cc:116,354` | §4 no STL in runtime | **blocker** | `std::vector<BodyEntry>`, `std::vector<CharEntry>` — replace with `Array<BodyEntry>` + explicit `Memory*` (or a fixed-size pool if max counts are known) |
| 3 | `physics/jolt/jolt_backend.cc` (whole file) | §5 Validate | **blocker** | Module-level `Validate()` equivalent missing. Add per-body and per-character invariant checks (`occupied` consistent with `bodyID` / `character` being non-null; handle < tables size) called on entry of every public function |
| 4 | `physics/jolt/jolt_backend.cc:469,473,481,489,497,543` | §7 no fallbacks | **blocker** | `if (handle >= gCharacters.size() || !gCharacters[handle].occupied) return <zero>;` — silent zero-return for a required handle is exactly the fallback pattern §7 warns about. Replace with `ValidateHandle(handle);` (asserts). Destroy functions can keep the `kJoltInvalidBodyID` sentinel branch since that's an explicitly-optional contract |
| 5 | `docs/compile-time-switches.md` | §9 cross-ref | **blocker** | `PHYSICS_ENGINE_JOLT` is not registered. Add a row under "Architectural Switches" |
| 6 | `physics/jolt/jolt_backend.hp:9`, `jolt_math.hp:15` | §2.2 include guards | cleanup | `#pragma once` → `#ifndef _JOLT_BACKEND_HP` / `#ifndef _JOLT_MATH_HP` |
| 7 | `physics/jolt/jolt_backend.hp:1`, `jolt_backend.cc:1`, `jolt_math.hp:1` | §2.3 file-header boilerplate | cleanup | No copyright / GPL v2 / Description+Author block. Add the canonical 24-line header |
| 8 | `physics/jolt/jolt_backend.hp:12` | §4 WF types | cleanup | `#include <cstdint>` — drop; use `uint32` from `pigsys` |
| 9 | `physics/physical.hp:35` | §4 WF types | cleanup | `#include <cstdint>` — drop; use `uint32` |
| 10 | `physics/jolt/jolt_backend.hp` (all `uint32_t`) | §4 WF types | cleanup | replace `uint32_t` with `uint32` project-wide in the file (22 occurrences) |
| 11 | `physics/jolt/jolt_backend.cc` (all `uint32_t`) | §4 WF types | cleanup | same rewrite (~25 occurrences); `(uint32_t)gBodies.size()` becomes `(uint32)<new container>.size()` after finding #2 |
| 12 | `physics/jolt/jolt_backend.hp:16` | §3 naming | cleanup | `kJoltInvalidBodyID` → `JOLT_INVALID_BODY_ID` (`ALL_CAPS_SNAKE` for constants) |
| 13 | `physics/jolt/jolt_math.hp:59` | §3 naming | cleanup | `kRevPerRad` → `REV_PER_RAD` |
| 14 | `physics/jolt/jolt_backend.cc:112,113` | §3 naming | cleanup | `kFixedStep` → `FIXED_STEP`; `kMaxSubsteps` → `MAX_SUBSTEPS` |
| 15 | `physics/jolt/jolt_backend.cc:118` | §3 naming | cleanup | `kZeroVec` → `ZERO_VEC` (or drop entirely; `Vector3::zero` already exists — see #4) |
| 16 | `movement/movement.cc:417,480,543,723` | §4 WF types (downstream) | cleanup | `uint32_t charID` → `uint32 charID` once finding #10 lands; `kJoltInvalidBodyID` references become `JOLT_INVALID_BODY_ID` |
| 17 | `physics/jolt/jolt_backend.cc:335` | comment hygiene | cleanup | commented-out `std::fprintf(...)` — delete rather than comment out; git history preserves it |
| 18 | `physics/jolt/jolt_backend.hp` (whole API) | §13 interop boundary | **accept** | Module-level C-style free-function API wrapping Jolt is the sanctioned pattern. Public header uses only WF types (once #8/#10 are fixed); Jolt headers stay in `.cc`. No change needed on this axis |
| 19 | `hal/halbase.h:147-158` | §7 (conditional) | **accept** | Item-macro shims for `!DO_VALIDATION` builds. This is §7's "optional with defined no-op" pattern, not a fallback — the macros *are* the contract when validation is off. OK |
| 20 | `oas/gold.oas` | §9 compat | cleanup | verify new OAS fields were appended (not inserted mid-struct) — spot-check against the OAD compat rule |

---

## Per-file narrative

### `physics/jolt/jolt_backend.hp`
Module-level C-style API over Jolt. The **shape** of the API is §13-compliant
(opaque `uint32` handles, WF types in signatures, no Jolt headers leaked).
The **WF-local details** need a sweep: `#pragma once`, missing file header,
`<cstdint>`+`uint32_t`, and the `kJoltInvalidBodyID` constant all violate
§2–§4. A single cleanup pass fixes all of it without touching the API shape.

### `physics/jolt/jolt_backend.cc`
Highest-density source of findings. Three real problems, in decreasing order
of importance:
1. Debug prints go through `std::fprintf(stderr, ...)` instead of a WF stream
   (§12). This is the load-bearing fix — it's the pattern contributors must
   never copy.
2. Body/character registries are `std::vector<...>`, which is forbidden in
   runtime code (§4). Replace with `Array<T>` + `Memory*`, or a fixed-size
   pool if max counts are bounded by design.
3. Bad-handle paths silently return zero vectors or early-return (§7). The
   contract is "callers pass valid handles"; missing that is an assert, not
   a soft no-op. `Destroy` functions can keep the `kJoltInvalidBodyID`
   sentinel because "destroy an invalid handle" is an explicit optional
   contract.

No `Validate()` equivalent on the module state (§5). The backend should at
least have a `Validate()` helper that checks table invariants, called from
every public entry point's debug build.

### `physics/jolt/jolt_math.hp`
Header-only math converters. `#pragma once`, no file boilerplate, `kRevPerRad`
naming. All cleanup-severity. The math itself (Euler↔JPH revolutions↔radians
conversion) is correct and matches §10 (angles are revolutions at the WF
boundary).

### `physics/jolt/physical.hpi`
Jolt-specific `PhysicalAttributes` accessors. The file's single inline
comment at line 42 correctly identifies that calling `Validate()` here would
be wrong for a particular reason (Jolt writes position between update and
next validate). Worth keeping — that's the kind of "why" comment §1 of
[CLAUDE.md] approves of, and the decision itself is sound.

### `physics/physical.hp`
One-line hunk: added `#include <cstdint>` (finding #9). Remove.

### `physics/physical.hpi`
No new violations authored in 2026 — modifications are small adaptors.

### `movement/movement.cc`
Three `#ifdef PHYSICS_ENGINE_JOLT { ... }` early-return blocks in
`GroundHandler::predictPosition`, `GroundHandler::update`,
`AirHandler::update`, `AirHandler::predictPosition`. The pattern itself is
fine — physics backend selection via compile-time switch is what §9's
compile-time-switch branch endorses. Downstream type cleanups (finding #16)
follow from the upstream `jolt_backend.hp` fixes; nothing movement-specific
violates a rule.

### `hal/halbase.h`
Added item-macro shims for `!DO_VALIDATION` builds. This looks like
fallback code on first read but isn't: `DO_VALIDATION=0` is a real build
configuration, and the macros *are* the contract for that configuration
(see `docs/compile-time-switches.md`). §7's optional-with-defined-no-op
applies. Keep.

### `hal/haltest.cc`
Deletion-only — out of scope.

### `oas/gold.oas`
New OAS object type added in 2026. Spot-check against §9.4: verify the
field order is compatible (new fields at the end; no reordering of the
`BUTTON_*` enum in `oas/oad.h`). Finding #20 — cleanup severity until
verified.

### Scripting engine integrations
Substantial 2026 work (Lua fixes, Fennel, Wren, WAMR, zForth plugs,
`ScriptRouter`). Mostly thin wrappers over vendored libraries. A proper
audit belongs in its own remediation doc since the patterns and target
files differ from the physics work. Tracked as follow-up.

---

## Applying the fixes

This doc lists findings only. Applying them is a separate follow-up. A
reasonable rollout:

1. **Stream migration first** (finding #1) — introduces `cjolt` the right
   way; proves the §12.4 procedure in the guide with a concrete example.
2. **Register `PHYSICS_ENGINE_JOLT`** (finding #5) — docs hygiene, low risk.
3. **Naming and type cleanup** (findings #6–#16) — one sweep across the
   Jolt files. Mechanical; can ride in a single commit.
4. **`std::vector` replacement** (finding #2) — needs a small design
   decision (fixed pool vs. `Array<T>` + `Memory*`). Medium effort.
5. **Fallback→Assert** (finding #4) — small per-site changes; test that
   destroy-on-invalid still works after the change.
6. **Add `Validate()`** (finding #3) — write invariants, wire into public
   entry points. Largest single item.
7. **OAS compat spot-check** (finding #20) — quick visual check against
   git history of `oas/gold.oas`.
