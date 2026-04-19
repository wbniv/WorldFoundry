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

1. **`MeshName` asset-ID packing** — ✅ matches oracle as of
   `0c399c0` + follow-up.  `lvl_writer` now pre-registers mesh
   assets in `[PERM, room 0, room 1, …]` order before the OAD
   serialization loop so per-(room,type) slot indices come out
   to `3fff001 / 3fff002 / 3fff003 / 3001001 / 3001002` matching
   the oracle.  Blender exporter preserves `wf_original_mesh_name`
   (instead of synthesizing `<obj.name>.iff`) so filename case
   follows the authoring source.  Remaining cosmetic gap: source
   `.lev` has mixed-case filenames but oracle binary has all
   lowercase — documented in the "Natural ASMP order" section
   below; fix is to lowercase at asset_registry emit time.

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

3. **Actboxor01/02 object-index order — NOTED AND DEFERRED
   (2026-04-19).**  Oracle LVL has `obj[5] = Actboxor02`,
   `obj[17] = Actboxor01`; my compiler preserves `.lev` text order
   (`obj[5] = Actboxor01`, `obj[17] = Actboxor02`).  Root cause is
   presumably max2lev's internal node-iteration quirk (not
   reverse-engineered), carried through to the oracle binary.  Both
   objects reach the correct room; semantically identical — same
   class, same containment outcome.  Possible clean fixes are:
   (a) preserve oracle order via `wf_lev_index` custom property on
   Blender objects and re-sort on export; (b) export objects in
   deterministic alphabetical order and regenerate the oracle.
   Both deviate from mirror-first for a 2-object cosmetic diff.
   **Accepting the diff as-is;** revisit after the texture pipeline
   lands and we drop `swap_lvl.py` (which is when we'd regenerate
   the oracle anyway, so option (b) becomes free).

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

## Natural Blender-exporter ASMP order vs oracle (2026-04-19)

Question: does the Blender exporter's natural object iteration
order match the oracle's ASMP order?

### Plain natural order (walk the .lev text top-to-bottom)

| # | source obj   | mesh              | MBR | room assignment |
|---|--------------|-------------------|-----|-----------------|
| 1 | House        | House.iff         | 0   | rm1 (by containment) |
| 2 | QuadPatch01  | QuadPatch01.iff   | 0   | rm1 (by containment) |
| 3 | Tree02       | Tree02.iff        | 1   | PERM (MovesBetweenRooms) |
| 4 | Tree03       | Tree03.iff        | 1   | PERM |
| 5 | Player       | Player.iff        | 1   | PERM |

The plain walk puts statplats (House, QuadPatch01) *first* because
that's the order max2lev emitted them into the .lev; the
MovesBetweenRooms actors come later.  Does **not** match oracle order.

### Room-grouped order (emit PERM first, then each room in index order; within each group, first-seen Blender order)

| # | source obj   | mesh              | MBR | room |
|---|--------------|-------------------|-----|------|
| 1 | Tree02       | Tree02.iff        | 1   | PERM |
| 2 | Tree03       | Tree03.iff        | 1   | PERM |
| 3 | Player       | Player.iff        | 1   | PERM |
| 1 | House        | House.iff         | 0   | rm1  |
| 2 | QuadPatch01  | QuadPatch01.iff   | 0   | rm1  |

### Oracle target

| # | mesh              | room |
|---|-------------------|------|
| 1 | tree02.iff        | PERM |
| 2 | tree03.iff        | PERM |
| 3 | player.iff        | PERM |
| 1 | house.iff         | rm1  |
| 2 | quadpatch01.iff   | rm1  |

### Verdict

**Room-grouped matches the oracle exactly** (modulo filename case —
see below).

So the natural recipe for a Blender-side ASMP emitter is:

1. Partition mesh-bearing objects into PERM + per-room buckets,
   using `MovesBetweenRooms` → PERM, otherwise room containment by
   world-space bbox centre.
2. For each bucket in `[PERM, room0, room1, …]`, walk Blender scene
   objects in insertion order; first-seen `MeshName` gets the next
   1-based index.
3. Pack `[type(8) | room(12) | index(12)]` and emit as
   `$<hex>l { 'STR' "<filename>" }`.

### Implementation — landed 2026-04-19 (`0c399c0` + follow-up)

`levcomp-rs::lvl_writer::write` now runs a pre-pass over
`plan.objects` partitioned `[PERM, room 0, room 1, …]` before the
OAD serialization loop, calling `plan.assets.add_iff_room` in
that order so the 1-based slot indices match the oracle.  Each
object's `serialize_entry("Mesh Name", …)` call then hits the
cache in `AssetRegistry` and retrieves the pre-assigned ID
unchanged.

Verified against oracle: packed IDs match `3fff001` / `3fff002` /
`3fff003` / `3001001` / `3001002` (PERM slots 1-3, rm1 slots 1-2).

The Blender export now also preserves the source `.lev`'s original
`Mesh Name` field (via `wf_original_mesh_name`) instead of
synthesizing from `obj.name` — so filename case follows the
authoring source, not the Blender scene name.

### Remaining filename-case oddity

Source `wflevels/snowgoons/snowgoons.lev` has **mixed case**:
`House.iff`, `QuadPatch01.iff`, `Player.iff` capitalised;
`tree02.iff`, `tree03.iff` lowercase.  Oracle binary ASMP has
**all lowercase**.  Round-trip preserves whatever the `.lev`
says, so my output still has mixed case for 3 of 5 entries.

Possibilities:
- max2lev or iff2lvl lowercased the `MeshName` field at write time
  (not reflected in the `.lev` source, which is the authoring
  form).  Some path lowercased on the way to binary.
- The `.lev` file we have got hand-edited (or decompiled
  incorrectly) after the oracle was compiled, upper-casing
  some names.

Either way, the correctness-preserving fix is to **lowercase at
`levcomp-rs::asset_registry` emit time** — the source `.lev`
lookup is already case-insensitive, so using `.to_ascii_lowercase()`
for the stored-name field (as well as the key) closes this.
Noted but not landed this session.

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
