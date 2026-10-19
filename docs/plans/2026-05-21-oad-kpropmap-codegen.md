# Plan — OAD Codegen for `kPropMap` (M3)

**Date:** 2026-05-21
**Status:** **DONE 2026-05-21** (committed `6c98b1cb`). All four steps landed: `regen-headers.sh` gained the `gen-kpropmap` awk pass over `common.ht`/`movebloc.ht`/`mesh.ht`; the committed [`engine/mutation/kpropmap_generated.inc`](../../engine/mutation/kpropmap_generated.inc) holds **77** entries (COMMON 11 + MOVEBLOC 27 + MESH 39, vs the 15 hand-curated); `wfmut.cpp` now `#include`s it inside `kPropMap`; and the [`.ht` codegen oracle](2026-05-20-ht-codegen-repair.md) (`task test-codegen`) was extended to verify the `.inc` byte-for-byte (both TODO items closed). **Scope was the `wfmut` write surface only** — the editor's [`engine_bridge.cc`](../../engine/wf_edit/engine_bridge.cc) keeps its own ~15-entry name→path table (keyed on the human OAD `name`, e.g. "Step Size", not the struct member "StepSize"), so the editor's *live-viewport* preview still routes ~15 fields even though `wfmut::SetActorField` now accepts 77; generating that bridge table from the same source is a separate follow-up. **Follow-up closed 2026-05-22** (`1effceec`): `engine_bridge.cc` now `#include`s the generated `name_to_path_generated.inc` (77 entries) from `regen-headers.sh`, so the editor's live-viewport preview routes all 77 fields, matching `wfmut`'s write surface.
**Branch:** `2026-new-level` (landed; the `2026-m3-oad-codegen` worktree was merged and removed)

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
