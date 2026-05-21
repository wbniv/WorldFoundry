# Plan — OAD Codegen for `kPropMap` (M3)

**Date:** 2026-05-21
**Status:** In progress
**Branch:** `2026-new-level` (working in `2026-m3-oad-codegen` worktree)

---

## Context

`engine/mutation/wfmut.cpp` has a static `kPropMap` with 15 hand-curated entries covering 3 OAD blocks (COMMON, MOVEBLOC, MESH). The other ~62 fields in those same blocks are silent `NoOp` when the editor panel edits them — `SetActorField` returns an "unknown field" error. This is M3 of the SpawnActor→live-sync→OAD-codegen plan (see [harness plan](../../.claude/plans/confirm-spawnactor-live-velvet-lamport.md)).

## What

Replace the 15 hand-curated entries with an auto-generated `#include "kpropmap_generated.inc"`. The `.inc` is generated from the three `.ht` struct files by a new step in `regen-headers.sh` and is committed (so builds without the OAS toolchain still work).

## Implementation

### Step 1 — Add `gen-kpropmap` to `regen-headers.sh`

At the end of the script (after `.ht` + `objects.*` generation), add an awk pass over `common.ht`, `movebloc.ht`, `mesh.ht`:

- Filter lines where `$1 == "fixed32" || $1 == "int32"` (data fields, not accessor methods)
- Extract field name from `$2` (strip trailing `;`)
- Emit `{"block.name", {PropInfo::BLOCK, offsetof(Struct, name), true/false}},`
- Write to `engine/mutation/kpropmap_generated.inc`

### Step 2 — Commit `kpropmap_generated.inc`

Generated file covering:
- `_Common` (11 fields): `hp`, `NumberOfLocalMailboxes`, `Poof`, `IsNeedleGunTarget`, `WriteToMailboxOnDeath`, `Script`, `ScriptControlsInput`, `slopeA/B/C/D`
- `_Movement` (27 fields): all movebloc fields
- `_Mesh` (39 fields): all mesh fields

Total: ~77 entries (vs 15 hand-curated).

### Step 3 — Replace hand-curated block in `wfmut.cpp`

Lines 183–202 (the hand-curated map body) become:
```cpp
static const std::unordered_map<std::string, PropInfo> kPropMap = {
#include "kpropmap_generated.inc"
};
```

### Step 4 — Build + verify

```bash
cd /home/will/WorldFoundry.m3-oad-codegen
task gen-oas-headers        # regenerates inc
cmake --build build-editor --target wf_edit -j   # or equivalent
```

## Scope

- Only COMMON, MOVEBLOC, MESH blocks — matches the current `get_block()` switch.
- Other blocks (COLBLOC, CAMBLOC, etc.) out of scope until `get_block()` supports them.
- M2 (live structural sync) and M1 (SpawnActor confirmation) are separate plans.

## Critical files

| File | Change |
|------|--------|
| `wfsource/source/oas/regen-headers.sh` | Add `gen-kpropmap` step |
| `engine/mutation/kpropmap_generated.inc` | New generated file (committed) |
| `engine/mutation/wfmut.cpp` | Replace lines 183–202 with `#include` |
