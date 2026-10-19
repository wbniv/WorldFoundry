# Use Blender's face-normal convention engine-wide

16 October 2026 · **Implemented in the dedicated worktree; release validation pending.**
Will prefers converting previously generated meshes over keeping legacy
face-order handling in the engine.

Will explicitly authorized the engine changes with “implement” after reviewing
this proposal. The worktree is `.worktrees/blender-normal-convention`, branch
`blender-normal-convention`, starting at `0a1289295f177b59525fe1018b8cd58672036bbf`.
The [inventory and per-hash decisions](../diagnostics/blender-normal-convention/)
cover 528 original model hashes and 4,849 occurrences. The offline conversion
changed 702 regular IFF files; tracked symlinks remain links. Byte verification
checks every file against the reviewed `FACE` swaps. Desktop build, exporter,
deformer and converter checks pass; the Android release APK builds for both ARM
ABIs and contains the migrated assets. [Validation results and gaps](../diagnostics/blender-normal-convention/README.md)
record both unavailable Chromecasts, pending Metal rendering and the shipped
dome's existing script compile failure. Those are not passing render checks.

## Decision

Define the engine's in-memory triangle `(v0, v1, v2)` as front-facing where
`(v1−v0) × (v2−v0)` points toward the intended visible side. This is Blender's
face order. Exterior surfaces point outward, interior surfaces point into the
space viewed from inside, and intentionally two-sided materials remain exempt
from face culling. This is a convention change, not a request to enable
hardware culling for every world mesh. The [GPU skinning experiment](2026-10-16-gpu-skinning-chromecast-experiment.md)
still audits each rig and measures hardware culling separately.

## Execution worktree

Perform the implementation, mesh audit, conversions, regeneration, builds and
validation in a **dedicated Git worktree and branch** under `.worktrees/`.
Record its starting commit and explicitly bring in any reviewed prerequisite
changes, including the recent matte winding cleanup. The current checkout has
other in-progress level and engine edits; do not build migration artifacts into
it or treat its uncommitted state as the migration baseline. Keep the reviewed
manifest and before/after evidence with the migration worktree. Use the shared
Chromecast coordinator for device sessions from that worktree; do not create a
separate device lock or control a device directly.

## Why the change needs a migration

Before this migration [`CalculateNormal`](../../wfsource/source/gfx/face.hpi) used
`(v2−v0) × (v1−v0)`. The [Blender exporter](../../wftools/wf_blender/export_level.py)
reversed each triangle on export, and its importer reversed it back. Loaded
`FACE` chunks contain indices, not stored normals:
[`RenderObject3D`](../../wfsource/source/gfx/rendobj3.cc) derives normals at load.
Changing only `CalculateNormal` would therefore invert lighting and software
back-face culling for every existing one-sided mesh. The source survey found
819 tracked `.iff` files across the repository, including 773 under
`wflevels/`, 42 standalone bundles there, Android packages, test fixtures and
historical tool data. There are 40 tracked `.lev` files. These are file counts,
not counts of distinct meshes or Blender scenes. Hand-written `FACE` generators
and built-in `TriFace` lists may contain old-hand, Blender-hand or intentionally
opposing faces. File age and current rendering do not establish intent.

## Level scenes to review

These are the **six checked-in level `.blend` files**. The condo scenes are
assembled from the separate source `~/docs/aircon/units-639-640.blend`, which
exists locally but is outside this repository. `baseline` and `pilot_demo` have
no tracked `.lev` output; their saved scenes still need review because they can
be exported again.

| Level | Saved Blender scene |
|---|---|
| `baseline` | [`wflevels/baseline/baseline.blend`](../../wflevels/baseline/baseline.blend) |
| `condo_639_640` | [`wflevels/condo_639_640/condo_639_640.blend`](../../wflevels/condo_639_640/condo_639_640.blend) |
| `condo_639_640_touch` | [`wflevels/condo_639_640_touch/condo_639_640_touch.blend`](../../wflevels/condo_639_640_touch/condo_639_640_touch.blend) |
| `condo_639_640_tour` | [`wflevels/condo_639_640_tour/condo_639_640_tour.blend`](../../wflevels/condo_639_640_tour/condo_639_640_tour.blend) |
| `pilot_demo` | [`wflevels/pilot_demo/pilot_demo.blend`](../../wflevels/pilot_demo/pilot_demo.blend) |
| `qbert_practice` | [`wflevels/qbert_practice/qbert_practice.blend`](../../wflevels/qbert_practice/qbert_practice.blend) |

Two more local baseline variants exist but are ignored build outputs, not
checked-in sources: [`diagnostics.blend`](../../wflevels/baseline/build/diagnostics.blend)
and [`settings-gallery.blend`](../../wflevels/baseline/build/settings-gallery.blend).
Regenerate and review them if those presets are included in the release.

The **other 36 tracked `.lev` files have no checked-in level `.blend`**. Review
their generating scripts and cooked meshes; do not assume that a similarly
named `.blend` exists. Names below are the `.lev` basenames, with directory
where it disambiguates the file:

| Family | Level source names without a checked-in `.blend` |
|---|---|
| Aquarium | `aquarium`, `aquarium_arowana`, `aquarium_betta`, `aquarium_blue_shrimp`, `aquarium_idle`, `aquarium_jellyfish`, `aquarium_lionfish`, `aquarium_plants`, `aquarium_tiger_barbs` |
| Marble Madness | `marble-madness-2`, `marble-madness/marble-madness`, `marble-madness/mm_fromscratch`, `marble-madness/mm_intermediate`, `marble-madness/mm_practice_rom`, `mm_practice/mm_practice`, `mm_practice/mm_practice_blender`, `mm_practice_blender/mm_practice_blender`, `mm_practice_blender/mm_practice_blender_rt`, `mm_practice_blender_rt/mm_practice_blender_rt` |
| SMB | `smb_w1_1`, `smb_w1_2`, `smb_w1_3`, `smb_w1_4` |
| Snowgoons | `snowgoons-blender/snowgoons-blender`, `snowgoons-blender/snowgoons` |
| Other | `basic`, `cube`, `cyber`, `dome`, `filelight`, `filesys`, `main_game`, `moon_site01`, `primitives`, `treemap`, `whitestar` |

The `.blend` files under `docs/plans/` and `docs/reference/` are asset studies,
not saved level scenes. Include their exported models if those models are
shipped in a level.

## Verify direction before conversion

Build a review manifest for **each distinct mesh source and face group** before
editing any generated file or direct geometry. Link all copies of that source
in level, standalone, CD, Android and fixture bundles. For every group record:

- the source file, cooked model hash, material and whether it is one-sided,
  two-sided, prelit or explicitly normaled;
- its current face indices and normals under both the old and proposed cross
  products, including negative-scale or mirrored instances;
- the intended visible side, supported by Blender face orientation, source
  comments, exterior/interior geometry, level camera views and screenshots;
- a reviewed decision: **reverse**, **keep**, **repair source geometry**, or
  **unresolved**, with the expected new normal and reviewer evidence.

For closed exterior shells, check signed volume and normals against the shell
centre; for interior rooms, check the viewer-facing side. These automatic
checks are clues, not authority for an open sheet, a mixed mesh or a two-sided
surface. A mesh may need different decisions for different face groups. For
example, `mm_practice/gen_ramp.py` deliberately emits both sides of a ramp;
`qbert_practice/gen_cube.py` documents a historical old-hand correction.
Neither example licenses a rule for other files. If intent remains unresolved,
leave that model unconverted and do not release a new engine with it.

| Existing stored face under the proposed Blender cross product | Action |
|---|---|
| Normal already points to the reviewed visible side | Keep its indices. |
| Normal points away from that side | Reverse the two indices needed to correct that face. |
| Intended side is ambiguous or faces in a group disagree | Resolve from source and scene evidence before conversion. |

## Proposed implementation

1. **Use one rule in the engine and on disk.** Change `CalculateNormal` to
   `(v1−v0) × (v2−v0)`. Keep the software culling test and two-sided exemptions.
   The loader reads `FACE` indices directly, with no legacy conversion branch
   or face-hand marker.
2. **Remove the exporter and importer reversals.** Write Blender's triangulated
   loop order directly; import it directly. Update the exporter golden and its
   normal-direction test. Review each `.blend` scene before re-export. If its
   source winding was hand-compensated or already wrong, repair the source
   according to the manifest rather than assuming all its faces should change.
3. **Migrate reviewed generated mesh data.** Inventory every tracked
   `MODL/FACE` payload, including level meshes, nested standalone/CD bundles,
   Android asset copies and loadable fixtures. Re-export models from reviewed
   Blender scenes and generation scripts where reproducible. For remaining
   historical or hand-built model files, use a strict one-time offline IFF
   converter that applies **only manifest-approved face changes**; `keep` is a
   valid result. The converter must parse chunk boundaries, require `FACE`
   sizes divisible by eight, preserve material indices/UVs and record hashes;
   it must never search raw bytes for the string `FACE` or flip every face by
   default. Rebuild containing level and app bundles from the reviewed models.
   Run the inventory again afterward and account for every tracked loadable
   mesh and copy.
4. **Migrate reviewed direct geometry at its source.** Check each runtime face
   list, including the cube in `rendacto.cc` and scarecrow in `rendcrow.cc`,
   against its intended visible side under the proposed cross product. Reverse
   only groups whose reviewed new normal would be wrong; keep groups already in
   the desired Blender order. Check the tiled matte's draw order against its
   explicit +Z normal; it remains two-sided.
   Audit runtime plant faces and normals together; its current explicit cross
   product already uses Blender's order. Update hand-written `.iff` generators
   to reproduce their manifest-approved order. Include test-only face lists in
   the source survey.
5. **Update all authoring guides and current docs, including renderer references.** Search all
   current authoring, level-building, troubleshooting, exporter, investigation and
   implementation docs for the old
   reversed cross product, automatic exporter/importer loop reversal and
   hand-authored IFF exceptions. Replace current advice with the Blender rule:
   engine normals and stored `FACE` order agree with the Blender viewport.
   Keep historical plans as dated records, but point their readers to the new
   convention where their advice would otherwise be mistaken for current
   instructions. Existing external `.iff` models built for the old engine must
   be converted offline before use with this release. Do not switch ordinary
   world draws to `GL_CULL_FACE` as part of this change.

The proposed engine edit surface is `gfx/face.hpi`, the runtime face sources
above, and renderer comments in `gfx/glpipeline/backend_modern.cc`. The loader
does not need a format branch. The normal rule applies to both GL and Metal.
Exporter/importer, generators, one-time conversion and tests are tooling and
asset changes. If the source audit finds another engine-generated face path,
add it to the reviewed diff before editing it.

## Evidence and acceptance

Implementation evidence includes the [per-model manifest](../diagnostics/blender-normal-convention/model-decisions.json),
[shell review](../diagnostics/blender-normal-convention/original-components.json),
[direct geometry review](../diagnostics/blender-normal-convention/direct-geometry.md)
and [saved Blender scene export comparison](../diagnostics/blender-normal-convention/blender-source-review.json).
The source comparison covers all six tracked level scenes: 303 of 313 exported
mesh records match migrated face geometry/direction. Nine older baseline source
meshes have no current geometry match; Qbert's saved cube is a placeholder whose
shipped override regenerates exactly from `gen_cube.py`. They are accounted for
as separate sources rather than overwriting the current assets from stale scenes.

**Correction (2026‑10‑17).** One `keep` was wrong. The snowgoons arena
(`quadpatch01` and its classic twin) was kept on exterior-shell clues, which
this plan rules out as authority for an open sheet. Its floor then pointed down,
and GL and Metal both culled it. It is now `reverse_all`, and a render audit of
the other kept models found no further inversion. See the
[investigation](../diagnostics/metal-snowgoons-cull-2026-10-17/README.md).

All authoring guides and current docs with winding guidance are updated,
including the GPU experiment and rig investigation. Historical plans carry
current-convention notices; transcripts retain their recorded statements.

- Before conversion, the manifest must cover every distinct loadable model and
  direct face group, including reviewed `keep` decisions and no unresolved
  groups in the release set. A built-in cube, intentional inward room, open
  sheet and two-sided ramp must have documented expected normals.
- After conversion, each reviewed face group's normal must match its expected
  direction. Preserve current culling and lighting where that appearance was
  correct; document intentional changes where the old asset was wrong.
- Before/after model checks must preserve positions, UVs, materials and
  triangle count; only manifest-approved face order changes. Import→export
  of migrated Blender-order models remains deterministic.
- Source checks cover the built-in cube, scarecrow, matte and runtime plant
  geometry. Existing culling and prelit guards must still pass.
- Search all current docs and authoring guides afterward; none
  may instruct authors to use the old engine hand or rely on an exporter flip.
- Capture a representative desktop GL set (exterior, interior, procedural,
  translucent and two-sided) before and after the change. Run the shipped-level
  culling sweep, treating its two skipped dynamic levels as unverified rather
  than passing. Exercise the affected paths on both Chromecasts through the
  coordinator; obtain a Metal render for the same examples.
- Preserve current model appearance unless a specific existing winding defect
  is separately identified and documented. Rebuild packaged copies from the
  migrated assets; check for stale old-order meshes before any release.

## Permission boundary

This file was the concrete proposal required by `AGENTS.md`. Will authorized
the engine edit surface before implementation. That authorization is separate
from permission for GPU skinning.

### Integration with seahorse Phase 3

Merged with `2026-new-level` through `66d03efd`. Reviewed the six newly added
seahorse/post models against a fresh Blender export before reversing their
legacy FACE order. Preserved all non-FACE bytes and the newer planted-tank
bundles. The extended inventory and exact verification cover 825 IFF paths,
534 original model hashes and 468,277 selected triangles; see the
[integration evidence](../diagnostics/blender-normal-convention/README.md#integration-with-the-newer-seahorse-work).
The Android selector still has its previously retained older planted-tank
variant; rebuilding it with the seahorses remains deferred with the pending
Aquarium bundle work. Device verification remains blocked by the unavailable
shared network.
