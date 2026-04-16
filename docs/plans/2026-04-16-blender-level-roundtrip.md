# Plan: Blender ↔ Level Round-Trip

**Date:** 2026-04-16  
**Branch:** 2026-first-working-gap

## Context

Full edit cycle: snowgoons.iff → Blender (edit scripts + positions + other actor fields) → back into the running game engine. This evaluates the complete pipeline and fills the gaps needed to get there.

## What Already Works

- `wflevels/snowgoons/snowgoons.lev` exists (text IFF authoring format, 36 objects)
- `WF_OT_import_level` in `wf_blender/export_level.py` loads `.lev` → Blender scene with:
  - Real mesh geometry from binary MODL `.iff` files (house.iff, tree01.iff, etc.)
  - Textures from TGA files in the same directory
  - Most I32/FX32 OAD field values populated on objects
- `WF_OT_export_level` writes Blender scene → `.lev` with mesh `.iff` files regenerated
- Coordinate transform Y-up ↔ Z-up is correct and documented (`export_level.py:23-25`)
- `iffcomp-rs` compiles `.iff.txt` → binary

## Gap 1 — Orientation not applied on import ✅ DONE

**File:** `wftools/wf_blender/export_level.py`, inside `WF_OT_import_level.execute()`

EULR chunk is present in the `.lev` but never read. After the VEC3/BOX3 block, capture it:

```python
rot_wf = (0.0, 0.0, 0.0)
eulr = _child_by_tag(obj_chunk, 'EULR')
if eulr:
    d = _data_scalars(eulr)
    if len(d) >= 3:
        rot_wf = (float(d[0]), float(d[1]), float(d[2]))
```

After `blobj` is created, apply rotation (inverse of the export mapping `wf=(rot.x, rot.z, -rot.y)`):

```python
blobj.rotation_euler = (rot_wf[0], -rot_wf[2], rot_wf[1])
```

Note: all snowgoons static objects have zero EULR so this is a correctness fix, not visually impactful for snowgoons specifically.

## Gap 2 — Script text not imported ✅ DONE

**File:** `wftools/wf_blender/export_level.py`, `_apply_field_chunks()`

Script is stored as `{ 'STR' { 'NAME' "Script" } { 'STR' "..." } }` — no `DATA` child, just a nested `STR`. `_data_scalars()` only looks for `DATA`, returns `[]`, and the field is skipped.

Fix: after `data = _data_scalars(chunk)`, if data is empty and tag is `'STR'`, fall back to nested STR:

```python
data = _data_scalars(chunk)
if not data and tag == 'STR':
    str_child = _child_by_tag(chunk, 'STR')
    if str_child and str_child['scalars']:
        data = [str_child['scalars'][0][1]]
```

## Gap 3 — ScriptLanguage OAD field ✅ DONE

Implemented per `docs/plans/2026-04-16-script-language-oad-field.md`. All five steps complete:

1. Added `TYPEENTRYINT32(Script Language,ScriptLanguage,0,5,0,"Lua|Fennel|Wren|Forth|JavaScript|WebAssembly",SHOW_AS_DROPMENU)` to `wfsource/source/oas/common.inc` after the `Script` XDATA entry; regenerated `common.oad`; manually updated `common.ht`
2. Threaded `language` param through `EvalScript` → `RunScript` in `level.hp`, `level.cc`, `actor.cc`, `tool.cc`, `toolshld.cc`, `toolngun.cc`, `game.cc`, `scriptinterpreter.hp`
3. Replaced sigil sniff in `scripting_stub.cc` with a static dispatch table (`kDispatch[]`); added `fennel_engine` shim namespace (delegates to `lua_engine` after prepending `;` sigil if absent); all six language slots guarded by their respective `#ifdef` macros
4. Added `WF_OT_detect_script_language` operator to Blender addon (`operators.py`); panel renders "Detect from script text" button below the ScriptLanguage grid (`panels.py`)
5. `wf_game` builds and launches cleanly with all changes

## Gap 4 — Level compiler (in progress — Phases 1 + 2a landed)

The full build pipeline is several tools chained together:

```
.lev (text IFF)  --[iffcomp-rs]-->  .lev.bin (binary IFF)
  --[levcomp-rs]-->  .lvl (flat _LevelOnDisk binary)
  --[prep + iffcomp-rs with iff.prp template]-->  .iff (LVAS-wrapped)
  --[update cd.iff.txt and rebuild]-->  cd.iff  →  wf_game
```

`levcomp-rs` is the Rust port of C++ `iff2lvl` — it reads `.lev.bin` and an
`objects.lc` class-index file, then writes a flat binary `.lvl` matching the
`_LevelOnDisk` layout the runtime reads via `GetCommonBlockPtr()`.

### Phase 1 (landed)

- `wftools/levcomp-rs` crate exists; builds clean
- Parses `.lev.bin` via `wf_iff::read_chunks` (proper IFF walk, no hardcoded offsets)
- Parses `objects.lc` (NullObject at index 0, real classes follow)
- Writes `_LevelOnDisk` header (52 bytes) + object offset array + `_ObjectOnDisk` records
- `_ObjectOnDisk` is **68 bytes** with natural alignment (2-byte pad after `type`, 1-byte pad after rotation `order`) — verified byte-for-byte against the LVL chunk extracted from `snowgoons.iff`
- Rotation units: `.lev` stores fixed32 radians; flat binary stores low 16 bits of `fixed32(radians / 2π)` (matches `iff2lvl` / `WF_FLOAT_TO_SCALAR`)
- Scale default: fixed32 1.0 (= 0x10000); NULL\_Object at index 0 gets scale=0 + unit-cube bbox (matches `iff2lvl` QLevel ctor)
- Rotation order byte: 0xFE (iff2lvl Euler default)
- Also fixed a pre-existing layout bug in `wftools/lvldump-rs` (it had 65-byte packed header; real layout is 68 bytes aligned)
- Paths/channels/rooms/common block: sections present but empty (MVP accepts loss of runtime features)
- Parity on snowgoons: 29/37 object headers match bytewise; remaining 8 differ in bbox (iff2lvl extends bboxes using mesh data — Phase 2) and 2 differ in rotation (Phase 2 investigation)

### Phase 2a — OAD field serialization (landed)

Four correctness fixes discovered via iterative byte-diff against `iff2lvl` output,
documented in `docs/investigations/2026-04-16-levcomp-rs-reverse-engineering.md`:

1. **Thin bbox expansion** — `expand_thin_bbox` in `lvl_writer.rs` ensures every bbox
   axis has `max − min ≥ 0.25` (fixed32 `0x4000 = 0x00004000`).  Mirrors
   `iff2lvl/level.cc:573-598`.  Engine colbox constructor asserts `max > min`; objects
   with no BOX3 in their `.lev` (lights, mattes, zero-mesh actors) would otherwise trigger
   it.

2. **XDATA sentinel table** — empty XDATA fields in `oad_loader.rs::serialize_entry` now
   write the correct sentinel per action type:
   - `COPY (1)` / `CONTEXTUALANIMATIONLIST (3)` / `SCRIPT (4)` → `-1`
   - `OBJECTLIST (2)` → offset pointing at a `0xffffffff` terminator word in the common
     block (engine iterates the list until terminator; a `-1` offset would crash)

3. **ObjectReference/ClassReference context** — outside a COMMONBLOCK the correct
   default is `0`; inside it is `-1` (OBJECT_NULL).  Mirrors `iff2lvl/oad.cc:1677` vs
   `level3.cc:99`.  `serialize_entry` now accepts an `in_common: bool` parameter.

4. **MovementClass default patch** — `oas2oad-rs` evaluates the `@e0(OASNAME_KIND)` prep
   macro to 0, so every compiled `.oad` has `MovementClass.def = 0`.  The correct default
   is the class's index in `objects.lc` (e.g. 5 for `statplat`).  `OadSchemas::load_dir`
   now accepts a `class_index: impl Fn(&str) -> Option<i32>` closure and patches
   `MovementClass.def` after loading each class's OAD.

### Phase 2b (not started)

1. **Paths and channels** — animated objects reference a pathIndex; paths contain 6
   channel indices for position and rotation curves.  Channels hold keyframe arrays.
   (MVP emits one dummy all-zero path so path-animated objects load without assertion;
   they will be static at runtime.)
2. **Rooms** — port `iff2lvl::SortIntoRooms()`: objects assigned to rooms by bbox-center
   containment.  Room records hold object indices + adjacency.
3. **Mesh bbox extension** — read mesh `.iff` files referenced by each object and extend
   its bbox to enclose the mesh (explains the 8 bbox mismatches in snowgoons).

### Phase 3 — LVAS wrapping (no new code needed)

After `levcomp-rs` produces a flat `.lvl`, the final `.iff` is built by running
`iffcomp-rs` with the `iff.prp` prep template (already in the tree at
`wfsource/levels.src/iff.prp`).  The template reads `asset.inc` and `ram.iff.txt`
and emits an `.iff.txt` that inlines the `.lvl` as the LVL sub-chunk of LVAS
alongside ASMP/PERM/RM* asset chunks.

### What levcomp-rs must do

For each `OBJ` in the `.lev`:
1. Look up the actor's `.oad` file by class name
2. Serialize all field values (I32, FX32, STR/XDATA, FileRef, etc.) into the binary OAD data block that the engine reads via `GetCommonBlockPtr()`
3. Package script text as XDATA
4. Emit the binary actor chunk (position/BB/orientation + OAD data block)
5. Assemble all actors into the outer level chunk (`L4`)

### Reference material

- `wflevels/snowgoons.iff.txt` — decompiled existing level; oracle for correct output structure
- `wftools/wf_oad/src/lib.rs` — OAD binary layout already parsed in Rust; writer is the inverse
- `wftools/wf_iff/src/lib.rs` — IFF chunk writer already exists
- `wftools/wf_attr_serialize/src/lib.rs` — already serializes to `.iff.txt`; extend with binary path

### Recommended approach

New crate `wftools/levcomp-rs/`:
- Reuse `wf_oad`, `wf_iff`, `wf_attr_schema`, `wf_attr_validate`
- Parse `.lev` in Rust (port the Python tokenizer, or shell out to iffdump-rs as pre-step)
- Add binary OAD data block serializer to `wf_attr_serialize` (parallel to `.iff.txt` path)

### cd.iff packing

After `levcomp-rs` produces a binary level `.iff`, rebuild `cd.iff` from `cd.iff.txt` via `iffcomp-rs`. The `.iff.txt` already references level files by name — updating it to point at the new level output is the intended workflow, not slot-injection.

## Orientation check verdict

The coordinate transform is correct:
- Export: `wf_x=bl_x, wf_y=bl_z, wf_z=-bl_y`
- Import: `bl_x=wf_x, bl_y=-wf_z, bl_z=wf_y`

Objects will appear in the correct WF-relative positions in Blender. The only orientation issue is the missing EULR apply (Gap 1).

## Critical files

| File | Change |
|------|--------|
| `wftools/wf_blender/export_level.py` | Gap 1: apply EULR; Gap 2: fix STR/XDATA import |
| `wfsource/source/oas/common.inc` | Gap 3: add ScriptLanguage field |
| `wftools/engine/stubs/scripting_stub.cc` | Gap 3: enum dispatch table |
| `wfsource/source/game/level.hp` + `level.cc` | Gap 3: language param |
| `wfsource/source/game/actor.cc` | Gap 3: pass ScriptLanguage |
| `wfsource/source/scripting/scriptinterpreter.hp` | Gap 3: language param |
| `wftools/levcomp-rs/` (new) | Gap 4: level compiler |
| `wftools/wf_attr_serialize/src/lib.rs` | Gap 4: binary OAD data block serializer |

## Verification

1. **Gap 1+2:** Import `snowgoons.lev`; player object shows script text in its Blender panel
2. **Gap 3:** `ScriptLanguage=0` on player; snowgoons runs identically; `grep 'p\[0\]\|sigil' wftools/engine/stubs/scripting_stub.cc` → empty
3. **Gap 4:** `levcomp-rs snowgoons.lev -o snowgoons_new.iff`; update `cd.iff.txt` to reference it; `iffcomp-rs cd.iff.txt -o cd.iff`; `wf_game` loads and plays snowgoons identically to original

## Sequencing

1. ✅ Gaps 1 + 2 — `export_level.py` EULR + STR/XDATA import fixes
2. ✅ Gap 3 — ScriptLanguage OAD field, dispatch table, Blender panel
3. ⏳ Gap 4 — Phase 1 + 2a landed (headers + OAD serialization); Phase 2b + 3 ahead
