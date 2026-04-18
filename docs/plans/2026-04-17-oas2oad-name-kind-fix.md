# Plan: fix oas2oad-rs name_KIND → correct MovementClass default

**Date:** 2026-04-17

## Context

`types3ds.s` sets `OASNAME = name` (the literal string "name") in every `TYPEHEADER`
expansion. So `movebloc.inc`'s `@e0(OASNAME@+_KIND)@-` always reduces to
`@e0(name_KIND)@-`. `oas2oad-rs` currently hardcodes `-Dname_KIND=0` in the g++
invocation (`main.rs:261`) with a comment calling it "cosmetic". It is not cosmetic:
every actor class calls `assert(GetMovementBlockPtr()->MovementClass == Actor::SomeClass_KIND)`
on construction, and that assert fires when `MovementClass` defaults to 0 instead of the
class's actual type index.

`levcomp-rs/src/oad_loader.rs:63–70` compensates by patching the `MovementClass` default
after loading each `.oad` schema, but the root cause is in `oas2oad-rs`.

## Implementation status — COMPLETE ✅

All steps done and committed:
- `oas2oad-rs/src/main.rs`: `--objects-lc` option, `parse_objects_lc()`, correct `name_KIND`, canonicalize fix
- All 42 `.oas` files rebuilt to `.oad` with correct `MovementClass` defaults
- `wftools/wf_oad/tests/fixtures/*.oad` (27 files) updated; expected entry counts updated in test
- `wftools/levcomp-rs/src/oad_loader.rs`: `MovementClass` patch removed, `class_index` param removed

## Fix

### 1. `wftools/oas2oad-rs/src/main.rs` ✅

Added `--objects-lc=<path>` option. Parses `objects.lc` to build a `stem → index` map.
Looks up current `.oas` stem (case-insensitive) and passes `-Dname_KIND={idx}` to g++.

If `--objects-lc` not supplied, falls back to `0` with a warning.

Also fixed: canonicalize `types_s` before `types_s.parent()` so relative paths don't
produce an empty `types_dir` that breaks `Command::current_dir`.

### 2. Rebuild all `.oad` files

Run `oas2oad-rs --objects-lc=wfsource/source/oas/objects.lc` on every `.oas` in
`wfsource/source/oas/`. The only field value that changes is `MovementClass.def`.

Copy rebuilt `.oad` files over `wftools/wf_oad/tests/fixtures/` where they exist.
The `parse_all_original_fixtures` test only checks entry counts and display names —
both unchanged — so all tests continue to pass.

### 3. Remove the compensating patch in `levcomp-rs`

Delete `wftools/levcomp-rs/src/oad_loader.rs:63–70` (the `MovementClass` default patch
and its doc comment). Remove `class_index` parameter from `load_dir` and call sites.

## Critical files

| File | Change |
|------|--------|
| `wftools/oas2oad-rs/src/main.rs` | ✅ Done — `--objects-lc`, correct `name_KIND`, canonicalize fix |
| `wfsource/source/oas/*.oad` | Rebuild with correct `MovementClass` defaults |
| `wftools/wf_oad/tests/fixtures/*.oad` | Update to match rebuilt fixtures |
| `wftools/levcomp-rs/src/oad_loader.rs` | Remove `MovementClass` patch + `class_index` param |

## Verification

```bash
# Rebuild one .oad and check MovementClass default changed
oas2oad --prep=wftools/prep/prep \
    --objects-lc=wfsource/source/oas/objects.lc \
    wfsource/source/oas/player.oas -o /tmp/player.oad
oaddump-rs /tmp/player.oad | grep -A3 "MovementClass"
# Expect: Default: 22  (Player_KIND = 22 in objects.p)

# All wf_oad tests still pass
cd wftools/wf_oad && cargo test

# snowgoons still loads
cd engine && ./build_game.sh && ./wf_game
```
