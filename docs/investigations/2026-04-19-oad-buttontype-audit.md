# OAD ButtonType audit — iff2lvl vs levcomp-rs

**Date:** 2026-04-19
**Purpose:** cross-reference every `ButtonType` variant from `wf_oad::ButtonType` (29 total) against how `wftools/iff2lvl` emits it and how `wftools/levcomp-rs/src/oad_loader.rs` emits it, to catch bugs like the obj[12]/obj[35] enum-label miss uncovered on 2026-04-19.

Drives a small repair punch list for `serialize_entry` + `int_value` + friends.

## Per-type table

Columns:

- **iff2lvl — outside common**: what `QObjectAttributeData::SaveStruct` writes to the per-object OAD payload for this type when not inside a `LEVELCONFLAG_COMMONBLOCK`…`LEVELCONFLAG_ENDCOMMON` range. Source: `wftools/iff2lvl/oad.cc:1616`ff.
- **iff2lvl — inside common**: what `QLevel::CreateCommonData` appends to the per-object `tempBlock` that gets `AddCommonBlockData`'ed at ENDCOMMON. Source: `wftools/iff2lvl/level3.cc:31`ff.
- **SizeOfOnDisk**: bytes the type contributes to per-object OAD size (ignored when inside common). Source: `wftools/iff2lvl/oad.cc:1493`.
- **levcomp-rs**: `serialize_entry` / `per_object_size` / `field_size` coverage. Source: `wftools/levcomp-rs/src/oad_loader.rs`.
- **Parity**: ✓ matches / ⚠️ partial / ✗ diverges / n/a.

| # | ButtonType | iff2lvl outside common | iff2lvl inside common | SizeOfOnDisk | levcomp-rs outside common | levcomp-rs inside common | Parity |
|---|------------|------------------------|----------------------|--------------|--------------------------|-------------------------|--------|
| 0 | `Fixed16`            | `assert(0)` (not allowed) | `assert(0)` | 2 | `serialize_entry` emits 2 bytes LE | matches outside-common path | ⚠️ levcomp-rs emits what iff2lvl asserts on. Would fire on real input. |
| 1 | `Fixed32`            | 4-byte `td.GetDef()` | 4-byte `td.GetDef()` | 4 | 4-byte `int_value(...)` | same | ✓ |
| 2 | `Int8`               | `assert(0)` | `assert(0)` | 1 | 1-byte `int_value(...)` as i8 | same | ⚠️ same as Fixed16 — levcomp-rs is permissive. |
| 3 | `Int16`              | `assert(0)` | `assert(0)` | 2 | 2-byte LE | same | ⚠️ |
| 4 | `Int32`              | 4-byte `td.GetDef()` | 4-byte `td.GetDef()` | 4 | 4-byte `int_value(...)` | same | ⚠️ **enum label lookup via `field_str_value` misses when DATA is binary.** Root cause of 2026-04-19 obj[12]/obj[35] bug. Fix below. |
| 5 | `String`             | 4-byte `td.GetDef()` (packed asset ID; `assert(ShowAs == FILENAME)`) | 4-byte `td.GetDef()` | 4 (note: SizeOfOnDisk falls through to FILENAME case) | writes `entry.len` raw bytes from the .lev STR, zero-padded | same | ✗ **big mismatch**: iff2lvl emits a 4-byte asset ID (via FILENAME fallthrough), we emit the raw string bytes. Not hit in snowgoons round-trip because `String` isn't used outside `ShowAs == FILENAME` paths, but this will bite any level that uses `String` for a non-filename. |
| 6 | `ObjectReference`    | 4-byte resolved index (`level.FindObjectIndex(td.GetString())`; empty name → 0; missing name → error) | 4-byte resolved index (`-1` if empty; `iff2lvl/level3.cc:99`) | 4 | 4-byte `name_to_idx.get(text)`; empty → 0 (outside) / -1 (inside) | same | ✓ |
| 7 | `Filename`           | 4-byte `td.GetDef()` (pre-packed asset ID) | 4-byte `td.GetDef()` | 4 | 4-byte `assets.add_iff_room(name, asset_room)` when text ends in `.iff`, else 0 | same | ⚠️ Close but ours only handles `.iff` filenames; iff2lvl handles any filename via its asset-ID pre-pass. For snowgoons this is fine; may break on levels with non-`.iff` filename fields. |
| 8 | `PropertySheet`      | — (no bytes) | break (no bytes) | 0 | 0 bytes | 0 bytes | ✓ |
| 9 | `NoInstances`        | — | — | 0 | 0 bytes | 0 bytes | ✓ |
| 10 | `NoMesh`            | — | — | 0 | 0 bytes | 0 bytes | ✓ |
| 11 | `SingleInstance`    | — | — | 0 | 0 bytes | 0 bytes | ✓ |
| 12 | `Template`          | — | — | 0 | 0 bytes | 0 bytes | ✓ |
| 13 | `ExtractCamera`     | `assert(0)` (deprecated) | no handler | 0 (+assert) | 0 bytes | 0 bytes | ✓ (permissive on deprecated type) |
| 14 | `CameraReference`   | — (commented-out `size = 4` in iff2lvl — ignored) | — | 0 | 0 bytes | 0 bytes | ✓ |
| 15 | `LightReference`    | — (commented-out `size = 4`) | — | 0 | 0 bytes | 0 bytes | ✓ |
| 16 | `Room`              | — | assert(0) inside common | 0 | 0 bytes | 0 bytes | ✓ |
| 17 | `CommonBlock`       | 4-byte `td.GetDef()` (offset into common area); sets `isInCommonBlock=true` | enters common; sets temp_td | 4 | 4-byte offset from `common.add(section)` | marker, triggers accumulation | ✓ |
| 18 | `EndCommon`         | — (just flips flag off) | close, emit `AddCommonBlockData(tempBlock)` and `SetDef` on the marker | 0 | — (just advances) | closes the accumulator | ✓ |
| 19 | `MeshName`          | (via FILENAME path — same 4-byte asset ID) | — | 4 (FILENAME fallthrough) | 4-byte `assets.add_iff_room(name, asset_room)` when `.iff`, else 0 | same | ✓ |
| 20 | `XData`              | 4-byte `td.GetDef()` (offset from Phase 1) when action ∈ {1..=4}, else 0 | 4-byte `td.GetDef()` when action ∈ {1..=4}, else skipped | 4 when action ∈ {1..=4}, else 0 | 4-byte from Pass-1 side table (after 2026-04-19 refactor) | same | ✓ (as of `8e2f244`) |
| 21 | `ExtractCamera2`    | not handled (no case in switch) | — | 0 | 0 bytes | 0 bytes | ✓ |
| 22 | `ExtractCameraNew`  | — (burns no space) | — | 0 | 0 bytes | 0 bytes | ✓ |
| 23 | `Waveform`          | — | — | 0 | 0 bytes | 0 bytes | ✓ |
| 24 | `ClassReference`    | 4-byte resolved class index (`level.GetClassIndex(td.GetString())`; empty → -1) | 4-byte resolved index (`-1` if empty; level3.cc:149) | 4 | **4-byte `name_to_idx.get(text)`** — that's the *object-name* table, not the class table! | same | ✗ **bug**: we resolve CLASS references against the object-name table. Benign for snowgoons (no class-reference fields in active classes) but would break on levels using them. |
| 25 | `GroupStart`        | — | — | 0 | 0 bytes | 0 bytes | ✓ |
| 26 | `GroupStop`         | — | — | 0 | 0 bytes | 0 bytes | ✓ |
| 27 | `ExtractLight`      | — (burns no space) | — | 0 | 0 bytes | 0 bytes | ✓ |
| 28 | `Shortcut`          | `assert(0)` | `assert(0)` (AssertMsg) | 0 | 0 bytes | 0 bytes | ✓ (permissive) |

## Punch list — fixes prioritized by blast radius

### ✗ Bugs (emit wrong bytes today)

1. ✅ **Int32 enum-label lookup misses when DATA is binary** — LANDED `21ca707` 2026-04-19. `int_value`'s enum path now uses `field_str_child_only` (defined in `lev_parser.rs`), which skips `DATA` and reads only the nested `STR`. Closed the 7-byte diff at obj[12]+120..132 and obj[35]+124..132 (CamShot `Rotation` / `Position X/Y/Z` toggle fields).
2. **ClassReference resolves against object-name table** — `serialize_entry` routes both `ObjectReference` and `ClassReference` through the same `name_to_idx.get(...)`, but iff2lvl's `level.GetClassIndex(...)` walks `objectTypes` (the class list from `.lc`). For any level with a `ClassReference` field that has a non-empty string, we'll return `None` (class name isn't in the object-name table) and write `0` / `-1` when iff2lvl writes the class index.
   **Fix**: take a `&ClassMap` in `serialize_entry` and resolve ClassReference via it.
3. **String emits raw bytes, iff2lvl emits 4-byte asset ID** — iff2lvl's `SizeOfOnDisk` for `BUTTON_STRING` falls through to the `BUTTON_FILENAME` case (line 1522 `case BUTTON_STRING:` missing `break`), so it's always 4 bytes of `td.GetDef()` (the packed asset ID). Our code emits `entry.len` raw string bytes padded with zeros. These disagree in both size and content. Not triggered by snowgoons because no class we use has a `BUTTON_STRING` field with `ShowAs != FILENAME`, but it's latent.
   **Fix**: treat `BUTTON_STRING` the same as `BUTTON_FILENAME` in both `field_size` and `serialize_entry` (4-byte packed asset ID via registry).

### ⚠️ Permissive where iff2lvl asserts

4. `Fixed16` / `Int16` / `Int8` — iff2lvl has `assert(0)` for these in both Save and SizeOfOnDisk ("only longwords allowed now"). Our code tolerantly emits 2- or 1-byte values. Fine if no schema uses them; potentially surprising if a future schema adds one.
   **Fix**: optional — leave permissive, or add a warning log. Not blocking.

### ✓ Already aligned

- All `LEVELCONFLAG_*` markers/flags (NoInstances, NoMesh, SingleInstance, Template, Room, ExtractCameraNew, ExtractLight, Shortcut, etc.).
- `Fixed32` / `Int32` (non-enum path).
- `ObjectReference`.
- `MeshName` / `Filename` for `.iff` files.
- `CommonBlock` / `EndCommon` markers (two-phase refactor `8e2f244`).
- `XData` (two-phase refactor `8e2f244`).
- `PropertySheet`, `GroupStart`, `GroupStop`.
- `CameraReference` / `LightReference` (both zero-size — iff2lvl has commented-out `size = 4` in those cases; confirming our zero matches).

## Notes on `PropertySheet` / `Group*` / flags

These types contribute no bytes to the per-object OAD payload and aren't allowed inside a COMMONBLOCK range. Our `field_size` returns 0 for all of them; `serialize_entry` hits the catch-all `_ => {}`.

## Notes on `Int32` enum handling

This is the bit that caused the obj[12]/obj[35] diff. iff2lvl reads both a `DATA` chunk (binary 4-byte int32) and a `STR` chunk (text enum label), stores them in separate fields (`_def` and `_string`), and at save time:

- Outside common block → writes `_def` as 4 bytes (numeric path).
- Inside common block → same: 4 bytes of `_def`.

But during `.lev` parse, the value written into `_def` is set from *either* DATA or STR depending on ShowAs. For `BUTTON_INT32` with enum items (ShowAs_ENUM or similar), iff2lvl maps the STR label to its enum index and stores that index in `_def`. For pure-numeric int32 fields (ShowAs_NUMBER) it reads DATA directly.

Our levcomp-rs `int_value` tries to do this but the order (`field_str_value` → `field_data`) is wrong for binary-DATA-plus-STR-label fields. The fix is a dedicated `field_str_child_only` helper used only in the enum branch.

## Critical files

| File | What |
|------|------|
| `wftools/levcomp-rs/src/oad_loader.rs:175` | `serialize_entry` — the dispatch table being audited |
| `wftools/levcomp-rs/src/oad_loader.rs:68`  | `field_size` — the outside-common byte count table |
| `wftools/levcomp-rs/src/lev_parser.rs:131` | `field_str_value` — the broken "prefer DATA over STR" accessor; add `field_str_child_only` alongside |
| `wftools/iff2lvl/oad.cc:1616`              | `SaveStruct` — iff2lvl per-object save dispatch |
| `wftools/iff2lvl/oad.cc:1493`              | `SizeOfOnDisk` per-entry |
| `wftools/iff2lvl/level3.cc:31`             | `CreateCommonData` — inside-common dispatch |
| `wftools/iff2lvl/oad.cc:955`               | `Apply` (DATA path) — reads DATA into `_def` |
| `wftools/iff2lvl/oad.cc:1130`              | `Apply` (STR path) — reads STR into `_string` or `_def` depending on ShowAs |

## Exit criteria

- Fix 1 (Int32 enum-label accessor): `cmp /tmp/my.lvl /tmp/oracle_lvl_payload.bin` loses the 7 byte-diffs at obj[12]+52..64 and obj[35]+56..64.
- Fix 2 (ClassReference): all levels with a non-empty class reference emit the right index (bench: any decompile / recompile round-trip that uses class references).
- Fix 3 (String as 4-byte asset ID): field_size and serialize_entry align on 4-byte packed-ID behavior.
- Fixes 4+ optional.
