# Widen the Editor Bridge to Use the Generated Map

**Status:** Done  
**Date:** 2026-05-21

## Context

The editor bridge (`engine/wf_edit/engine_bridge.cc`) hand-writes a 14-entry `nameToPath()` table that maps OAD field names (as stored in `.lev`/Doc) to wfmut `"block.member"` paths. Meanwhile, M3 generated `engine/mutation/kpropmap_generated.inc` with **77 fields** from the same OAD sources.

Result: ~63 wfmut-writable fields (`RunningDeceleration`, `StunThreshold`, `TurnRate`, all emitter/particle mesh fields, etc.) silently fall through as `NoOp` in the bridge — panel edits update the Doc but never reach the viewport.

This plan generates a companion file (`engine/wf_edit/name_to_path_generated.inc`) from the same OAS `.inc` sources, replacing the 14 hand-written entries and expanding live-preview coverage to all 77 kpropmap fields.

## Name Mapping Rule

OAD names (first arg of `TYPEENTRY*` macros in `.inc` files) map to C++ struct members by removing spaces:
- `"Step Size"` → `StepSize`
- `"Running Acceleration"` → `RunningAcceleration`
- `"generationType"` → `generationType` (no spaces, unchanged)
- `"hp"` → `hp`

`is_float` comes from the TYPEENTRY variant: `TYPEENTRYFIXED32` → `true`, all others → `false`.

## Changes

### `wfsource/source/oas/regen-headers.sh`

New awk pass after the kpropmap section. Parses `common.inc`, `movebloc.inc`, `mesh.inc` for all `TYPEENTRYFIXED32|INT32|BOOLEAN|COLOR|FILENAME|OBJREFERENCE|XDATA_CONVERT` lines and emits `engine/wf_edit/name_to_path_generated.inc`.

### `engine/wf_edit/name_to_path_generated.inc` (new, committed)

Generated file included into `engine_bridge.cc`.

### `engine/wf_edit/engine_bridge.cc`

Replaces the 14-entry static map body with `#include "name_to_path_generated.inc"`.

## Verification

- `task build` compiles clean.
- `DumpTranslations()` (`WF_EDIT_BRIDGE_DEBUG=1`) shows ~79 mapped fields (77 OAD + Position + Orientation) vs ~16 before.
- Editing a previously-NoOp field (e.g. "Running Deceleration") logs `FieldFloat` in the bridge and the engine accepts the write without error.
