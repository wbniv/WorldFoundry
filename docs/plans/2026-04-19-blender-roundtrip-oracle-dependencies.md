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
| `L4` + `ALGN` + `LVAS` header + `TOC` | IFF wrapper + offsets/sizes for ASMP/LVL/PERM/RMn | `prep` + `iff.prp` + valid `asset.inc` can produce this; currently `prep` bails on missing texture atlases. **TOC form** now understood: entries are `.offsetof(X) - .offsetof(LVAS) .sizeof(X)` (LVAS-header-relative), with a 6th `FAKE` sentinel that cross-wires `LVL`'s offset with `ASMP`'s size — see [iffcomp-offsetof-arithmetic](../investigations/2026-04-19-iffcomp-offsetof-arithmetic.md) for the grammar archaeology and [snowgoons.iff.txt](../../wflevels/snowgoons.iff.txt) for the reconstructed source. `.sizeof()` returns payload size (not header+payload). |
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
   ✅ mirrored as of `6cc4a8c`.  iff2lvl's QObject list has
   NULL_Object at slot 0 with identity bbox centred at origin,
   and `SortIntoRooms` iterates starting from index 0, so
   Room02 (whose world bbox contains the origin) always gets a
   leading `0` entry.  `rooms::sort` now pre-pushes `0` into
   whichever room's world bbox contains the origin before the
   real-object pass.  Round-trip room entry lists now match:
   `orig room[1] = [0, 1, 2, 4, 5, 9, ...]` and
   `blen room[1] = [0, 1, 2, 4, 9, 10, ...]` (remaining 5↔17
   diff is the deferred Actboxor ordering item).  Engine skips
   null entries at load so this has no runtime effect — purely
   a byte-identity mirror.  Drop-the-sentinel cleanup is
   deferred-deviation (f) below.

6. **`levelOad` member initialisation** — ✅ non-issue.  snowgoons
   has a `LevelObj` object (schema: `wfsource/source/oas/levelobj.oad`;
   carries Number Of Temporary Objects=200, mailbox counts,
   matte/skybox settings, 128 SFX slots, 128 localised-text slots,
   and the default character-physics values from `actor.inc`).
   The `level.cc` soft-fail lands a warning + zero defaults if
   any future level is authored without a LevelObj; round-trip
   of snowgoons never exercises it.  Remove from this list — it's
   not an oracle-reproduction concern.

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

### ✅ Implementation — landed 2026-04-19 (`0c399c0` + follow-up)

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

### Filename-case oddity — ✅ root-caused (2026-04-19)

Source `wflevels/snowgoons/snowgoons.lev` has **mixed case**:
`House.iff`, `QuadPatch01.iff`, `Player.iff` capitalised;
`tree02.iff`, `tree03.iff` lowercase.  Oracle binary ASMP has
**all lowercase**.

Investigation (both tools' source code):

- **max2lev does NOT lowercase.** `wfmaxplugins/max2lev/oadobj.cc`
  just copies the Max OAD-editor string verbatim:
  `strcpy(entry->GetTypeDescriptor()->string, oe.GetString())`
  and emits via `_iff->out_string(oadEntry->GetString())`.  The
  `.lev`'s mixed case is authentic — it's what the Max user
  typed in the OAD editor per object.
- **iff2lvl DOES lowercase**, explicitly and knowingly, at
  `wftools/iff2lvl/level2.cc:220-222`:

      // kts this strlwr needs to go away, but first the levels in
      // wflevels need to be updated to have the proper case
      strlwr(oldName);

  Same pattern at `level2.cc:275`.  So the oracle binary's
  lowercase filenames are an iff2lvl normalisation step on top of
  the authentic mixed-case `.lev`.
- **Neither levcomp-rs decompile nor Blender importer touches
  case** — confirmed by grep for `to_lowercase`/`to_ascii_lowercase`
  in `wftools/levcomp-rs/src/decompile.rs` and
  `wftools/wf_blender/export_level.py`: no hits.  The `.lev` we
  have carries the original max2lev case straight through to
  Blender and back out.

Fix for mirror-first: **apply `strlwr` in
`levcomp-rs::asset_registry::add_iff_room`** — same workaround
iff2lvl applied, same "until the .lev files get normalized"
caveat.  Lands in the same commit as this note.

### Filename-case — Blender side also lowercases now (2026-04-19)

The fix above handles the *`asset.inc` / ASMP* side of the
lowercase normalization. On the **Blender export side**, the
exporter was also silently capitalising mesh filenames: objects
with no `wf_original_mesh_name` (newly-created in Blender) got
`<obj.name>.iff` synthesized, which used whatever case Blender's
scene had (`House.iff`, `Player.iff`, `QuadPatch01.iff`). That
produced a capitalised `.iff` *file* on disk next to the lowercase
one `asset.inc` referenced — half-migrated state where 2 of 5
meshes (`tree02`, `tree03`) had `wf_original_mesh_name` preserved
from the authoring source and exported lowercase, while 3 of 5
(House/Player/QuadPatch01) exported uppercase and were effectively
unused by the `asset.inc`-driven pipeline.

Fix: lowercase the synthesized filename at
`wftools/wf_blender/export_level.py:1026`:

```python
mesh_filename = (orig_mesh if orig_mesh else obj.name + ".iff").lower()
```

With both ends lowercased (exporter + asset_registry), the
Blender-regenerated `.iff` file and the `asset.inc` reference
agree; no capitalised duplicates get left behind.

### Footnote on `tree02.iff` / `tree03.iff` vs `player.iff` / `house.iff` / `quadpatch01.iff` — which meshes are Blender-regenerated today (2026-04-19)

Current `wflevels/snowgoons/` working-tree state per mesh:

| Mesh             | Size     | HEAD size | Source                           |
|------------------|---------:|----------:|----------------------------------|
| `tree02.iff`     | 10,024 B | 10,164 B  | **Blender re-export** (140 B smaller) |
| `tree03.iff`     | 10,024 B | 10,164 B  | **Blender re-export** (140 B smaller) |
| `player.iff`     | 728 B    | 728 B     | original max2lev-committed       |
| `house.iff`      | 18,628 B | 18,628 B  | original max2lev-committed       |
| `quadpatch01.iff`| 22,144 B | 22,144 B  | original max2lev-committed       |

The 280-byte PERM-chunk size gap against oracle I chased while
working on `levcomp-common-block-two-phase` turned out to be
exactly this: Blender re-exports of the trees trimmed 140 B each,
so the PERM chunk (which embeds all five per-mesh `.iff` files via
`'ASS' $3fff001l [ "tree02.iff" ]` entries) is 280 B shorter than
the oracle's PERM. Not a levcomp-rs or textile-rs bug — the
Blender exporter's mesh-write path is 140 B tighter than max2lev's
for these specific objects. Restoring `HEAD:wflevels/snowgoons/tree02.iff`
(max2lev-original) into the working tree brings the PERM chunk
byte-identical to oracle.

Meaning: oracle byte-identity on PERM will require *both*
re-using max2lev-era meshes (or round-tripping them through
Blender without the size drift) *and* the lowercase-filename fix
above. Since Blender's trim is consistent, flipping to "all meshes
are Blender-regenerated" gives a stable new snapshot that differs
from oracle by a predictable amount — acceptable once we're no
longer chasing oracle byte-identity as the target.

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

---

## Deferred deviations — execute after oracle reproduces

Each item below is a known-cleaner-than-oracle behaviour that we
hold off on until `snowgoons-blender.iff` reproduces the oracle
binary exactly.  Policy: mirror first, then run these as a single
breaking-compat batch alongside
[`2026-04-16-script-language-oad-field`](2026-04-16-script-language-oad-field.md).

**a. Lowercase `.lev` filenames, drop iff2lvl's `strlwr` workaround.**
Source `.lev` files have mixed-case mesh filenames that iff2lvl
normalised with `strlwr(oldName)` at `level2.cc:222`/`:275` — KTS's
own comment: "this strlwr needs to go away, but first the levels
in wflevels need to be updated to have the proper case."
Historical context: WF started on DOS/Windows 3.1 with 8.3 FAT
filenames (no case); the strlwr was a case-insensitive
compatibility shim that stuck around after the toolchain moved to
long-filename hosts.  levcomp-rs now replicates the strlwr; after
the batch, normalise the `.lev` files to lowercase and remove the
call.

**b. Alphabetical export order, regenerate Actboxor indices.**
Oracle has `obj[5] = Actboxor02`, `obj[17] = Actboxor01` from
max2lev's Max-node iteration order.  Export in deterministic
alphabetical-by-name order and regenerate the oracle; both
Actboxors end up in the right rooms already, only their LVL
indices shift.

**c. Zero `_PathOnDisk.base.rot`.**
levcomp-rs emits the literal 8-byte oracle sequence
`b1 02 85 c6 00 00 20 4f` (investigation:
[path-base-rot-oracle-mystery](../investigations/2026-04-19-path-base-rot-oracle-mystery.md)).
After reproduction, flip to 8×0x00 and soak-test; if gameplay
unchanged, drop the literal.

**d. Drop iff2lvl's spurious CamShot BOX3 default in decompile.**
iff2lvl fills a default `(0,0,0)-(0,0,0)` bbox for non-geometry
objects that `expand_thin_bbox` widens to
`(-0.25,-0.25,-0.25)-(0,0,0)`.  The decompiled `.lev` carries that
synthesized bbox through, so Blender round-trip re-emits a BOX3
for CamShots that max2lev would never have written.  Fix in
`levcomp-rs::decompile`: recognise the default pattern and omit
BOX3.  Blender import/export gate then works naturally.

**e. ScriptLanguage OAD field — see separate plan.**
`docs/plans/2026-04-16-script-language-oad-field.md` already
tracks this.  Same gate.

**f. Drop NULL_Object (index 0) from room entry lists.**
Oracle's Room02 entries start with `[0, 1, 2, …]` — iff2lvl's
accidental inclusion of NULL_Object because its identity bbox
lands at the origin.  Engine skips null entries at load, so this
is cosmetic.  Reproduce for byte-identity; drop after.
