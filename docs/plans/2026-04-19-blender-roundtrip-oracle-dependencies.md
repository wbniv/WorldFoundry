# Plan: Blender round-trip — oracle dependencies

**Date:** 2026-04-19
**Status:** Not started — inventory only; textures pipeline planned to tackle first

## Context

After the 2026-04-19 push (`c1550f7`), `wf_game -L snowgoons-blender.iff`
runs continuously — audio, physics, Bungee camera, per-frame loop, no
assertions.  But the final `.iff` is produced by **in-place LVL chunk
swap** (`/tmp/swap_lvl.py`): my `levcomp-rs` emits the `LVL` chunk,
and `swap_lvl.py` splices it into the oracle `snowgoons.iff`, reusing
everything else.  This plan enumerates what's still the oracle's
bytes so the standalone-build work can prioritise correctly.

## Oracle content reused

`swap_lvl.py` preserves every chunk in `snowgoons.iff` except the
LVL payload.  What that means concretely:

| Oracle chunk | What it holds | Blocker to regenerating |
|---|---|---|
| `L4` + `ALGN` + `LVAS` header + `TOC` | IFF wrapper + offsets/sizes for ASMP/LVL/PERM/RMn | `prep` + `iff.prp` + valid `asset.inc` can produce this; currently `prep` bails on missing texture atlases |
| `RAM` | Runtime memory budget (`OBJD`, `PERM`, `ROOM`, `FLAG` sizes) | Trivial; just hasn't been authored in `levcomp-rs` |
| `ASMP` | Packed-asset-ID → filename table | `levcomp-rs` emits the matching `asset.inc` text but doesn't produce the binary chunk yet |
| `PERM` | Permanent-residency: `palPerm.tga` + `Perm.tga/.ruv/.cyc` + permanent mesh `.iff` bytes | **textile atlases** (see "Texture pipeline" below); mesh bytes already emittable from Blender |
| `RM0`, `RM1`, … | Per-room assets: `palN.tga` + `rmN.tga/.ruv/.cyc` + per-room mesh `.iff` bytes | Same — textile atlases + packed asset IDs |

## Gaps still inside my LVL output

These are inside the LVL chunk my `levcomp-rs` produces, and they
differ from the oracle LVL in ways I haven't fully root-caused yet.
All are currently benign (the level runs) but they're the remaining
loose ends.

1. **`MeshName` asset-ID packing** — `asset_registry.rs` packs
   `[TYPE | ROOM | INDEX]` in first-seen order.  My IDs don't match
   the oracle's baked IDs, so when the runtime resolves a mesh's
   texture slot through the oracle's `ASMP` table, it lands on the
   wrong `PERM`/`RMn` entry.  **This is why the level renders
   untextured.**  Port `iff2lvl/level2.cc:228`'s ID-packing
   algorithm or align with the oracle's discovery order.

2. **`CamShot` BOX3** — ✅ root cause understood.  Reading
   `max2lev.cc:374` (first commit of `wfmaxplugins/max2lev/`):
   `process_bounding_box` gates the entire BOX3 emission on
   `os.obj->SuperClassID() == GEOMOBJECT_CLASS_ID`, so cameras,
   CamShots, directors, matte objects — anything without real
   geometry — get **no BOX3 chunk at all** from max2lev.  The
   iff2lvl default is then (0,0,0)-(0,0,0), which
   `expand_thin_bbox` widens to `(-0.25, -0.25, -0.25) → (0, 0, 0)`
   matching the oracle.  My current `.lev` from the Blender import
   has `(-0.5, -0.5, 0) → (0.5, 0.5, 1)` because the importer
   synthesises a unit-cube fallback mesh for abstract actors and
   the exporter recomputes the BOX3 from that.  Fix is analogous
   to the Mesh Name gate from 2026-04-19: stash a
   `wf_had_authored_bbox` flag on import and skip BOX3 emission on
   export when it was absent from the source.

3. **Actboxor01/02 object-index order** — oracle LVL has
   `obj[5] = Actboxor02`, `obj[17] = Actboxor01`; my compiler
   preserves `.lev` text order (`obj[5] = Actboxor01`,
   `obj[17] = Actboxor02`).  Both rooms end up with the right
   contents; just index ordering differs.  Cosmetic.

4. **`_PathOnDisk.base.rot` bytes** — iff2lvl's
   `new char[SizeOfOnDisk()]` leaves struct padding uninitialized;
   the `.a/.b/.c` u16s end up zero (from `WF_FLOAT_TO_SCALAR(0.0)`)
   but `order` + pad are heap garbage.  I write clean zeros.
   Semantically identical, just byte-different.

5. **Oracle Room02 entry list begins with `0` (NULL object)** —
   oracle: `[0, 1, 2, 4, 5, 9, …]`; mine: `[1, 2, 4, 9, …]`.  The
   engine's `Room::Construct` skips null entries at load
   (`if (masterObjectList[idx] != NULL)`), so the zero is benign.
   Unknown whether iff2lvl meant it as a sentinel or it's an
   off-by-one.

6. **`levelOad` member initialisation** — original engine asserts
   on `No LevelObject object in level`; the `level.cc` soft-fail
   that just landed in `5d184b4` logs a warning + uses zeros.
   Round-trip does contain a LevelObj so this doesn't fire, but
   the defaults-on-missing path hasn't been exercised.

## Texture pipeline (separate next-up plan, referenced here)

The biggest oracle dependency is the **texture atlas pipeline**.
Rebuilding PERM/RMn without reusing the oracle needs:

- **textile** (`wftools/textile/`, not yet ported) to pack individual
  TGAs into `palN.tga` + `rmN.tga` palette+texture-atlas pairs,
  emit `rmN.ruv` (per-UV lookup table) and `rmN.cyc` (colour-cycle
  list), and assign per-mesh asset IDs
- `prep` integration to run `iff.prp` on `asset.inc` + `ram.iff.txt`,
  producing the full `LVAS` text IFF
- `iffcomp-rs` to compile the resulting text IFF to binary

See 2026-04-13-blender-to-cd-iff-pipeline investigation for the
full spec.  That work will be captured in its own plan doc when
started.

## Exit criteria

This plan is "done" when `swap_lvl.py` is deleted and
`snowgoons-blender.iff` is produced end-to-end from the Blender
export alone, byte-diffing against the oracle `snowgoons.iff` with
only the known-OK differences listed above (and those either closed
or documented).

## Critical files

| File | What |
|---|---|
| `/tmp/swap_lvl.py` | Today's LVL-swap bridge; delete when standalone works |
| `wftools/levcomp-rs/src/asset_registry.rs` | MeshName asset-ID packing |
| `wftools/iff2lvl/level2.cc:228` | Oracle's asset-ID packing, port target |
| `wftools/textile/` (when ported) | Texture atlas packer |
| `wfsource/levels.src/iff.prp` | prep template that assembles LVAS |
| `wfsource/levels.src/ram.iff.txt` | RAM chunk template |
| `wftools/levcomp-rs/src/lvl_writer.rs` | LVL emitter — source of CamShot BOX3 / base.rot / entry-list diffs |
