# Marble Madness: correction to the earlier terrain reconstruction

**Date:** 2026-09-22

**Status:** Earlier terrain interpretation superseded; Astra Practice reconstruction delivered

The earlier ROM conversion read real bytes but assigned them the wrong meanings. It treated object-spawn records as terrain cross-sections, then generated a track from invented headings, lengths and widths. The result used real 3D meshes and physics, but its course shape did not reproduce the arcade terrain. The separate hand-authored `marble-madness` / `marble-madness-2` prototypes were also approximations.

Astra benefited from **Marble Love's existing reverse engineering**. Its contribution was adapting that research into a terrain extractor and World Foundry geometry/collision pipeline, then validating the result. It did not independently discover the ROM format. The earlier attempt apparently did not use the same reference; whether that reference was publicly available in May has not been established.

The current delivered course is **Astra Practice**, bundled at index 6. Launch it from the main checkout with `task run-marble-3d-astra` or `task run -- 6`. See the [bundle guide](../../wflevels/marble-madness-3d-astra.md) and [integration verification](../plans/2026-09-21-add-marble-astra-to-cd-iff.md).

## Reference access and attribution

The source/history review on September 22 found:

- The May investigation cited MAME's `atarisy1.cpp` driver, Ben Ryves's research and its own MAME runtime memory dumps. It also recorded an attempted RomHacking.net forum lookup that returned HTTP 403. Its recorded sources did not include Marble Love.
- Searches of the earlier implementation, documentation and saved transcripts found no Marble Love or `magno73` citation. In the available Git history, the first reference in `docs/` or `wflevels/` appears in Astra's September 21 commit `13c96e2e`.
- Astra explicitly used Marble Love's instruction-level reconstruction at `113cf5de969ff62cb1d7b901340206f30122f658` to identify the spawn table and implement the terrain semantics, then compared its output with MAME and the reference implementation.

This supports “the earlier attempt apparently did not use the same reference,” not a categorical claim that its author never saw it. The review did not establish when the relevant Marble Love research became publicly available. It would therefore be unsupported to say the earlier attempt ignored an available solution.

The successful result benefited from a different information base. It does not demonstrate that Astra independently solved the reverse-engineering problem the earlier attempt struggled with. The earlier work's documented methodological failure remains the promotion of unverified field meanings to confirmed facts; the comparison must also credit the later attempt's outside source.

## What was wrong

| Earlier interpretation | Correction | Consequence |
| --- | --- | --- |
| `0x1DEC0` points to terrain descriptors. | It selects object-spawn rectangle lists consumed by routine `0x12DFA`. | These lists cannot supply the course surface. |
| Each six-byte entry is `[type:u16][segment_ptr:u32]`. | The first two bytes are signed region bounds; the long is a script pointer, or zero for random-group selection. | Turning the low byte into a compass heading has no basis in the consumer. |
| Referenced records contain `h_left`, `h_right`, `h_center`. | The supposed heights include object coordinates and script arguments. | Their numeric patterns do not establish elevations, banks or walls. |
| `h_center <= 5` identifies a start/goal platform. | This was a heuristic over misidentified fields. | Replacing those records with flat platforms conceals the decoding error. |
| Fixed segment length and width reconstruct the layout. | `SEG_LEN=2.5` and `PATH_HALF=2.0` were converter choices. | Accumulating positions along invented angles produces a ribbon, not the arcade topology. |

The old [decoder](../../wflevels/marble-madness/decode_levels.py) and [Blender converter](../../wflevels/marble-madness/rom_to_blender.py) remain as historical implementation artifacts. Their field names and “confirmed” comments are invalid as terrain documentation. `levels.json` is output from that interpretation, not ground-truth course geometry. This documentation correction does not alter or regenerate the old assets.

The converter also forced floor edges to the assumed center height, used other values as vertical walls, and added platforms and containment walls. Those changes could make its invented track easier to traverse; they could not recover the missing terrain semantics. Winding, lighting and duplicate-face fixes addressed rendering defects independently of this decoding error.

## Why validation failed

The [May investigation](2026-05-01-marble-madness-rom-level-data.md) promoted a pattern-based hypothesis to “confirmed” without establishing how the arcade code used the fields. Upward face normals validate the generated mesh's orientation, not the source interpretation. A level running without crashing establishes runtime viability, not course fidelity.

The investigation also explained missing sharp turns as an isometric illusion and treated unexpectedly small record counts as open questions. Those discrepancies should have triggered a new search for the terrain data. Adjusting scale, adding walls and broadening the same converter to six named levels did not provide an independent check.

## What the successful reconstruction uses

The actual six-level header pointer table is `0x2BE00`; Practice's header is `0x2BEE2`. Astra's extractor follows terrain routine `0x1CABA`: packed playfield collision data selects terrain codes, row bases provide elevations, and direct or encoded/indirect records supply height and void samples. It resolves the protected ROM bank and captured runtime indirect table. Routine `0x1CC62` establishes the split-triangle interpolation and corner order.

The generated Practice surface preserves cell heights, triangle divisions, gaps and height discontinuities. Renderer and Jolt use the same mesh. It contains 1,823 nonempty cells and 3,502 top triangles; authored skirts bring the total to 4,818 triangles.

Authoring sources live on the separate `marble-madness-3d-astra` branch. These links pin the delivered implementation to commit `13c96e2ea5a5ec9f823fa8eda94237f9bdbf9c45`, so they also work from this checkout, where only its packaged course is present:

- [Implementation, provenance and fidelity limits](https://github.com/wbniv/WorldFoundry/blob/13c96e2ea5a5ec9f823fa8eda94237f9bdbf9c45/wflevels/marble-madness-3d/README.md)
- [Terrain extractor](https://github.com/wbniv/WorldFoundry/blob/13c96e2ea5a5ec9f823fa8eda94237f9bdbf9c45/wflevels/marble-madness-3d/extract.py)
- [Geometry checks](https://github.com/wbniv/WorldFoundry/blob/13c96e2ea5a5ec9f823fa8eda94237f9bdbf9c45/wflevels/marble-madness-3d/verify_geometry.py)
- [Recorded standalone verification](https://github.com/wbniv/WorldFoundry/blob/13c96e2ea5a5ec9f823fa8eda94237f9bdbf9c45/docs/plans/2026-09-21-marble-madness-true-3d-reimplementation.md)

The correction draws on Marble Love's instruction-level reconstruction at commit `113cf5de969ff62cb1d7b901340206f30122f658`: [spawn dispatch](https://github.com/magno73/marble-love/blob/113cf5de969ff62cb1d7b901340206f30122f658/packages/engine/src/script-rect-dispatch-12dfa.ts), [level header](https://github.com/magno73/marble-love/blob/113cf5de969ff62cb1d7b901340206f30122f658/docs/level-header-format.md), [terrain sampler](https://github.com/magno73/marble-love/blob/113cf5de969ff62cb1d7b901340206f30122f658/packages/engine/src/sub-1caba-tile-redraw.ts), and [interpolation](https://github.com/magno73/marble-love/blob/113cf5de969ff62cb1d7b901340206f30122f658/packages/engine/src/sprite-project-1cc62.ts).

## Evidence and limits

The September 21 verification recorded 251 matching live MAME terrain queries, mostly near the start. Separately, 2,675 legal neighborhoods matched Marble Love's instruction-level reference with zero mismatches; another comparison covered all 1,823 retained cells. Geometry tests include solid/void interpolation fixtures from that reference. This is a separate implementation used for comparison, but it is also the research source for Astra's decoder, not a second independently discovered interpretation of the ROM. Runtime verification completed Practice using directional input only and exercised falling, restart and timeout. These are prior recorded results, not new runs performed for this documentation correction.

Only Practice is delivered by this reconstruction. The other five courses are not converted. Artwork, perspective projection, authored skirt depth, motion tuning, frozen dynamic terrain, scoring and respawn remain approximations. The marble uses the existing Jolt `CharacterVirtual` sphere and `MarbleHandler`, not an angular rigid-body simulation.

For future course conversions, establish field meanings from their consumer routines, compare sampled heights and voids against an independent reference, then verify the mesh and an input-driven traversal. Keep decoder parity, mesh validity, visual resemblance and gameplay completeness as separate claims.
