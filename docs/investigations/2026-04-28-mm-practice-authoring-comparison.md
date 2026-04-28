# Level Authoring Comparison — Hand-crafted .lev vs Blender-driven

**Date:** 2026-04-28  
**Level:** `mm_practice` (Marble Madness tutorial stage)  
**Context:** First brand-new level to exercise the end-to-end pipeline.  
Both approaches produced a compilable `.lev` that successfully ran through
`build_level_binary.sh` (iffcomp → levcomp → textile → iffcomp) and emitted a
valid `mm_practice.iff`.

---

## Approach A — Hand-crafted `.lev` + Python generator

**Files:**
- `wflevels/mm_practice/gen_lev.py` — emits `mm_practice.lev` using helper functions
- `wflevels/mm_practice/gen_ramp.py` — emits `ramp.iff` (MODL binary)
- `wflevels/mm_practice/mm_practice.lev` — the produced text-IFF source

**Method:**
1. Read `snowgoons.lev` (the validated reference level) to understand every
   field for each object class (actboxor, room, light, camera, director,
   levelobj, matte, camshot, target, player, statplat).
2. Write `gen_lev.py`: Python helper functions that emit the verbose multi-line
   text-IFF format, reproducing the exact field ordering and value types the
   parser expects.
3. Write `gen_ramp.py`: packs a simple quad surface into the WF binary MODL
   format (`MODL { VRTX MATL FACE }`) using `struct.pack` with 1.15.16
   fixed-point encoding.
4. Run both scripts, copy `player.iff` and `G_SnowyGrass1.tga` from
   `snowgoons-blender/`, run `build_level_binary.sh mm_practice`.

**Key discoveries:**
- The text-IFF parser requires all embedded scripts to be on **one line** with
  `\n` and `\\` escape sequences — real newlines inside a `STR` value cause a
  parse error at the character after the newline.
- Field order within each OBJ block matters; using the same order as
  `snowgoons.lev` avoids any ordering ambiguity.
- `actboxor` class-specific fields (`MailBox`, `Object`, `Activated By`, etc.)
  must appear **after** the common tail (`Template Object`).
- `light` objects omit the `BOX3 "Global Bounding Box"` chunk entirely.
- The `director` and `player` classes include an `hp` field before
  `Number Of Local Mailboxes`; `statplat` and `actboxor` do not.
- `build_level_binary.sh` requires all three Rust tools to be pre-built
  (`cargo build --release` in `iffcomp-rs/`, `levcomp-rs/`, `textile-rs/`).

**Compile result:** ✓ 24 576 byte `mm_practice.iff` in ~2 s.

**Pro:** Fully scriptable, no GUI dependency, produces a minimal .lev with
only the fields that matter. The generator (`gen_lev.py`) doubles as readable
documentation of object structure.

**Con:** Requires reading the reference level in detail before writing a new
one; getting field order/types wrong produces silent semantic bugs or hard-to-
diagnose parse errors. MODL binary generation requires understanding the exact
struct layout.

---

## Approach B — Blender-driven (`blender --background --python`)

**Files:**
- `wflevels/mm_practice/blender_create_mm_practice.py` — headless Blender script
- `wflevels/mm_practice/mm_practice_blender.lev` — produced by Blender exporter

**Method:**
1. `blender --background --python blender_create_mm_practice.py`
2. Script calls `bpy.ops.wm.read_factory_settings(use_empty=True)`, then
   `addon_utils.enable("wf_blender")` (enabling **after** factory reset is
   required — factory reset clears addon state).
3. Import `snowgoons-blender.lev` via `bpy.ops.wf.import_level` — this
   reconstructs all objects with OAD schemas attached as custom properties.
4. Class identity is read from `wf_schema_path`: `os.path.basename(path).replace('.oad','')`.
5. Delete gameplay objects (`statplat`, `enemy`, etc.); keep one of each
   infrastructure class; reposition to fit the ramp layout.
6. Add a new Ramp mesh via `bpy.data.meshes.new` / `from_pydata`, attach the
   `statplat.oad` schema path, set `wf_Mesh Name = 'ramp.iff'`.
7. Export via `bpy.ops.wf.export_level(filepath=...)`.

**Key discoveries:**
- `addon_utils.enable("wf_blender")` must be called **after** `read_factory_settings`,
  not before.
- Class name is not stored as a string property; it is encoded in
  `wf_schema_path` as the OAD filename stem (`actboxor.oad` → `"actboxor"`).
- The Blender exporter writes a denser, single-line format (all fields on one
  line per entry) compared to the verbose multi-line format of the handwritten
  .lev. Both are valid.
- The exporter writes **all** OAD fields (including defaults), producing a
  larger file (1 084 lines vs ~600 for the hand-crafted version for the same
  12 objects).
- Duplicate infrastructure objects from the imported level must be
  explicitly deleted; the importer recreates all 36 original objects.
- The imported actboxor retained the original (snowgoons) bounding box — for
  mm_practice, this needs to be corrected by resizing the object.

**Compile result:** ✓ `mm_practice_blender.iff` (24 576 bytes) produced by full
pipeline (iffcomp → levcomp → textile → iffcomp).

**Pro:** Inherits correct OAD field ordering and default values automatically.
Perfect for iterating on layout, positioning, and property tweaks in a visual
environment. The wf_blender addon validates fields in real time.

**Con:** Requires Blender 4.0 installed. Headless scripting is less intuitive
than interactive use — the more natural workflow is to do the import+edit
interactively in the Blender GUI, then export. The Blender script needs
careful ordering (factory reset → addon enable → import) and the class
detection requires understanding the `wf_schema_path` convention.

---

## Summary comparison

| Dimension | Hand-crafted (A) | Blender-driven (B) |
|-----------|------------------|-------------------|
| **GUI required** | No | Optional (headless works) |
| **Pipeline steps** | gen_lev.py → gen_ramp.py → build script | blender script → build script |
| **Format written** | Verbose multi-line | Compact single-line |
| **Field coverage** | Minimal (only used fields) | All OAD fields with defaults |
| **Class name source** | Hard-coded in generator | OAD path stem |
| **Mesh authoring** | Struct-pack Python script | Blender mesh + exporter |
| **Compile time** | ~2 s (no Blender startup) | ~10 s (includes Blender startup) |
| **Error surface** | Field order, escape sequences | Addon enable ordering, property key names |
| **Best for** | Scripted/procedural level gen | Interactive layout editing |

**Recommendation:** Use Blender interactively for layout and positioning
(the GUI provides immediate visual feedback and schema validation). Use the
hand-crafted generator for procedural/bulk level generation or when Blender is
not available. The `gen_lev.py` pattern also serves as a readable ground-truth
reference for the .lev schema.

---

## Smoke test — 2026-04-28

**Status:** PASSING. `wf_game -L mm_practice-standalone.iff` boots, player
grounds on the ramp at feet_z=4.0, camera activates by frame 3,
RenderScene fires every frame thereafter. Not black.

**Root cause of the initial black screen** (and how to avoid it in future levels):
Every actor is assigned to a room by levcomp based on whether its world-space
position lies within the room's bounding box. Actors outside all room bounds
are placed in the PERM section. `updateRoomContents()` only iterates the active
room list (RM0 and adjacent rooms); PERM objects are NOT updated. The Camera
actor's `update()` must run every frame for `DelayCameraHandler` to read
mailbox 1021 and switch to `NormalCameraHandler`, which sets `ValidView()=true`
and enables `RenderScene()`. If the Camera is in PERM it is never updated →
`ValidView()` is always false → black screen.

The same pattern applies to the Light actor: if the light is outside room bounds
it goes to PERM and will not appear in `ROOM_OBJECT_LIST_LIGHT` during
`RenderScene`, so the room renders unlit.

**Rule:** Place Camera, CamShot, and all Lights inside the world bounds of at
least one room. The world bounds of a room = room.Position + room.BOX3 min/max.
For `mm_practice`, Room01 at position (0,10,3) with BOX3 (-12,-14,-6, 12,14,5)
gives world bounds X:[-12,12], Y:[-4,24], Z:[-3,8]. The original Camera and
CamShot positions (20,-10,15) and the Light position (0,10,20) were all outside
these bounds; moving them to (0,-2,7) and (0,10,6) respectively fixed the issue.

This is documented in the levcomp-rs reverse engineering investigation
(`2026-04-16-levcomp-rs-reverse-engineering.md`, section 15 "Adjacent rooms
drive the active-room system") where the same failure mode was found for snowgoons
when rooms had no adjacency declarations.

## Next steps for mm_practice

- [x] Smoke test: `wf_game -L mm_practice-standalone.iff` boots and renders (2026-04-28).
- [x] Smoke test: `wf_game -L mm_practice_blender-standalone.iff` boots, player
      grounds at feet_z=3.998 by frame 14, no crash (2026-04-28).
- [ ] Add bounding-box correction to the Blender script (actboxor bbox still
      references the snowgoons field size: -81.38 to 81.38).
- [ ] Author a proper marble mesh (sphere.iff) — currently using player.iff
      (snowman model) as a placeholder.
- [ ] Add the director script timer logic for the 90 s practice countdown.
- [ ] Tune player physics for marble rolling (Vertical Elasticity 0.3,
      Horizontal Elasticity 0.7, Running Acceleration 5 N).

## Blender variant fixes (2026-04-28)

Three issues were found and fixed during the blender smoke test:

1. **Room BOX3 not updated** — the exporter reads BOX3 from `wf_original_bbox` custom
   property (set at import from source .lev), not from mesh geometry. Fix: set
   `room["wf_original_bbox"] = (-12.0, -14.0, -6.0, 12.0, 14.0, 5.0)` directly.

2. **Target02 missing** — snowgoons has one target (GMACamTar); after dedup only
   Target01 exists. BungeeCameraHandler dereferences Target02 (null) → crash. Fix:
   duplicate Target01 to create Target02 in the blender script.

3. **Ramp Z too high** — ramp at position (0,10,4) puts the high end at world Z=6,
   above the player spawn Z=5. Player starts below the ramp and falls through the level.
   Fix: `ramp_obj.location = (0, 10, 2)`. With the room BOX3 now correctly set to
   (-12,-14,-6,12,14,5), world Z=[-3,8], the ramp at world Z=[0,4] is inside the room
   so levcomp assigns it to RM0 (no TOC assertion).
