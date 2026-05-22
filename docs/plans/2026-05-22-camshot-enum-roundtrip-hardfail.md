# Plan: CamShot enum round-trip — hard-fail on DATA/STR mismatch

**Date:** 2026-05-22
**Status:** In progress
**Related:** [investigation](../investigations/2026-05-22-blender-snowgoons-untextured.md),
[blender-roundtrip-oracle-dependencies](2026-04-19-blender-roundtrip-oracle-dependencies.md)

## TL;DR — the "untextured" symptom was the camera, not textures

The Blender-built snowgoons renders flat gray **not** because of any texture-pipeline
bug. Proven:

- Atlas / RUV / meshes / materials are **byte-identical** oracle↔Blender (the
  1687-byte `.iff` diff is entirely in the LVL/actor region; everything from the
  meshes onward is identical).
- The GL **draw streams are byte-identical** (instrumented `WF_TRACE_DRAW` in
  `backend_modern.cc`): same `useTex`, white vertex colours, UVs, atlas binding.
- Forcing the **oracle's camera** onto the Blender level (temp `WF_FORCE_CAM` in
  `camera.cc`) renders it fully textured — red house, pink box, green hedge
  (`tests/screenshots/blender_oraclecam.png`, chroma 9.1 ≈ oracle 8.4).

The real difference is the **CamShot tracking toggles** on `camshot_12`:
`Rotation` flipped Track(1)→Fixed(0) and `Position X/Y/Z` Relative(1)→Absolute(0)
(`Track Object` still `player_33`). With Fixed/Absolute the BungeeCam ignores the
player and parks at a static wide view — the gray snow. Patching only those 7
enum bytes back to 1 makes the Blender level render the colourful tracked view
(`tests/screenshots/blender_cammode.png`, chroma 9.5).

The earlier "camera euler a↔c shuffle" lead was a **misread**: those EULR deltas
are on `statplat_20/21` and are the *same rotation* (correction matrix = identity
to 0.01°) — a different valid euler decomposition near gimbal lock, not a bug.

## Root cause of the toggle loss — the import/export round-trip

The decompiled source `wflevels/snowgoons-blender/snowgoons.lev:4368` is
**internally inconsistent**:

```
{ 'I32' { 'NAME' "Rotation" }   { 'DATA' 0l } { 'STR' "Track" } }     // DATA=0 (Fixed) vs label "Track" (=1)
{ 'I32' { 'NAME' "Position X" } { 'DATA' 0l } { 'STR' "Relative" } }  // DATA=0 (Absolute) vs label "Relative" (=1)
```

`DATA` says index 0, `STR` says the index-1 label. The Blender importer
(`export_level.py:_apply_field_chunks`, Enum branch ~887) **prefers DATA over
STR**, so it imports "Fixed"/"Absolute", and re-exports them
(`snowgoons-blender.lev:1246`). The camera loses tracking → gray.

These toggle fields classify as `FieldKind::Enum` (pipe items `"Fixed|Track"`,
`wf_attr_schema/src/lib.rs:308-314`). The current levcomp decompiles the oracle
consistently (`DATA 1l` / `STR "1"`); the poisoned `snowgoons.lev` came from a
stale/buggy decompile.

## Fix

### Phase 1 — importer hard-fails on DATA/STR enum mismatch
`export_level.py` `_apply_field_chunks`, Enum branch: when a `DATA` index **and**
a `STR` that is a known enum label are both present and disagree, **raise** with a
clear message (object, field, DATA value+label vs STR label) instead of silently
trusting DATA. A numeric `STR` (e.g. `"1"`) is not a label → no mismatch check;
DATA is used. This makes a corrupt `.lev` fail loudly rather than round-trip wrong.

### Phase 2 — regenerate the poisoned source + re-run the round-trip
- Re-decompile the oracle `wflevels/snowgoons.iff` with the current levcomp →
  `wflevels/snowgoons-blender/snowgoons.lev` (consistent `DATA 1` / `STR "1"`).
- Headless Blender import→export to regenerate
  `wflevels/snowgoons-blender/snowgoons-blender.lev` carrying Track/Relative.
- With Phase 1 in place, importing the *old* poisoned `.lev` now hard-fails
  (regression guard); importing the regenerated one succeeds.

### Phase 3 — rebuild + A/B verify
- `bash wftools/wf_blender/build_level_binary.sh snowgoons-blender`
- Re-render `tests/screenshots/ab_blender.png`; confirm the Blender build now
  tracks the player and renders textured (chroma matching the oracle).

## Teardown
Remove temp instrumentation once verified: `WF_TRACE_DRAW` (`backend_modern.cc`),
`WF_DUMP_CAM`/`WF_FORCE_CAM` (`camera.cc`); delete throwaway test artifacts under
`tests/screenshots/` (`blender_modefix*`, `blender_cammode*`, `blender_oraclecam*`,
`*_f80*`, `trace_*`, `oracle_sa*`, patched `*-standalone.iff`).

## Gotchas logged to the level-design guide (per convention)
- "Blender build renders flat gray" → check the CamShot `Rotation`/`Position`
  tracking toggles first; a Fixed/Absolute camera parks at a static view that can
  look untextured even when textures are fine.
- A decompiled `.lev` enum field whose `DATA` and `STR` disagree is corrupt; the
  importer now hard-fails on it.
