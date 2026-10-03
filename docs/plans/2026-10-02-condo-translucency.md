# Condo shade and glass: translucency investigation and implementation plan

**Date:** 2026-10-02. **Status:** investigation complete; awaiting Will’s review and approval. No renderer, exporter, model or level implementation has started. The SVGs below are illustrative planning assets, not engine screenshots.

## Intended result

The lowered balcony shade should let Will see the outside scene through a lightly tinted sheet. The telescoping glass doors should look like glass rather than a solid coloured wall: a faint tint, visible edges and opaque handles, with the patio and lowered shade visible beyond them. Raising the shade and opening the doors retain their existing motion and collision behaviour.

Start with adjustable material opacity and correctly ordered compositing across desktop GL, Android GLES, WebGL and Metal. Opacity here means how strongly the surface contributes to the image: zero is invisible, one is opaque. This first phase keeps the scene sharp through the material. Optical blur, refraction and physically based reflection would be separate work if later needed; alpha blending alone cannot produce those effects.

## Appearance mockups

![Six illustrative studies: opaque shade, translucent shade, glass, both layers, stacked doors and a strip-overlap failure](2026-10-02-condo-translucency/appearance-mockups.svg)

The mockups use shade opacity **0.32** and glass opacity **0.12** as starting points for review, not measured properties of the eventual purchased fabric or existing doors. Suggested tuning ranges: shade 0.20–0.45; glass 0.06–0.18. Keep cassette, solar strip, guides, bottom bar, door handles and locks opaque. The glass highlights shown are an appearance cue; the first phase does not promise a dynamic reflection system.

True stacked door panes should accumulate a little tint. Accidental double surfaces on one pane, or the existing shade-strip overlap, must not create the same effect. At opacity 0.32, drawing the same sheet twice gives effective opacity approximately 0.54; lowering one material’s alpha without addressing its geometry would therefore be misleading.

[Open the visual preview](2026-10-02-condo-translucency/preview.html). [Combined PNG preview](2026-10-02-condo-translucency/preview.png).

## Findings from the current source

| Stage | Evidence | Consequence |
|---|---|---|
| Condo material authoring | `wflevels/condo_639_640/blender_create_condo.py`: `make_flat_material()` sets Base Color and diffuse alpha to 1.0. `SHADE_RGB['fabric']` is beige RGB. Doors reuse the imported `glass` material. | Changing only the shade colour cannot make it see-through. The source glass material’s actual alpha/node setup still needs a read-only Blender probe before implementation. |
| Shade geometry | Same generator: `SLAT_T = 0.003`, `SLAT_DY = 0.001`, `SLAT_OVERLAP = 0.002`; slats have front/back surfaces, with top/bottom faces removed. | Thin-box surfaces and overlapping neighbours need deliberate handling to prevent doubled tint and dark horizontal bands. |
| Door geometry | Same generator: `_door_panel()` builds solid panels with hardware material slots. | Make glass surfaces transparent without making the handles transparent or altering collision boxes. |
| Blender model export/import | `wftools/wf_blender/export_level.py`: `_extract_mat_info()` exports RGB, texture name and flags; it does not export Principled Alpha, Base Color alpha or transmission. `_make_blender_material()` imports Base Color alpha as 1.0. | Opacity currently disappears during export and round trip. |
| Model format | `wfsource/source/gfx/material.hp`: `_MaterialOnDisk` contains flags, `Color` and a 256-byte texture name; the historical `_opacity` field is commented out. The exporter assumes a 264-byte MATL record. | Adding a field directly would break existing asset layout. Preserve MATL size. |
| Legacy texture transparency | `material.cc` picks up `bTranslucent` and historical texture blend flags. `pixelmap.cc` decodes texture pixels to alpha 0, 128 or 255. `textile-rs/src/bitmap.rs` quantizes input alpha into a legacy bit. | Existing flags are not continuous material opacity. Enabling all texture alpha could also expose old colour-key/black-pixel artefacts; audit separately. |
| Shared draw interface | `wfsource/source/gfx/renderer_backend.hp`: `RBVertex` contains RGB; `DrawTriangle()` passes texture, culling exemption and prelit state, but no opacity or blend mode. | New material state must reach every flat/textured and lit/prelit submission path. |
| GL/GLES/WebGL shader | `glpipeline/backend_modern.cc`: both flat and textured fragment paths output alpha 1.0; texture sampling uses only `.rgb`. Texture creation also enables blending as a global side effect. | There is no usable material-opacity path even though blending is sometimes enabled. Blend/depth policy must belong to drawing, not texture creation. |
| Metal shader/pipeline | `metal/backend_metal.mm`: fragment alpha is also 1.0; the inspected pipeline has no blend configuration and uses depth writes. | Metal needs a corresponding blend pipeline and read-only depth state. |
| Ordering | `rendobj3.cc` groups faces by material; `glpipeline/rendobj3.cc` submits them under each actor’s transform. Current batches key texture/prelit and flush on state changes. | Material order and per-actor sorting cannot correctly composite shade strips, glass leaves and the world behind them. Deferred draws must retain their own transforms and lighting state. |

These are source-inspection findings. No new engine captures, runtime benchmarks or regenerated condo assets were produced during this investigation.

## Proposed design

![Material export path and opaque-first, back-to-front compositing diagram](2026-10-02-condo-translucency/rendering-flow.svg)

### 1. Explicit, compatible material opacity

- [ ] Probe the existing `glass` material and exact face layout read-only; record whether the source uses Alpha, Base Color alpha or transmission. Do not equate transmission automatically with alpha: they describe different rendering effects.
- [ ] Add explicit authoring properties for blend mode (`opaque` or `blend`) and opacity. Default existing materials to opaque. For these condo materials, set the properties deliberately and mirror the approved appearance in Blender’s preview. Import restores the same properties.
- [ ] Add an optional `OPAC` model chunk, leaving MATL unchanged. Proposed payload: a version followed by one fixed-width mode/opacity record per MATL slot, with opacity represented as a bounded fixed-point value. Write it only when a material opts into blending. Final binary field widths are to be documented before coding.
- [ ] Read the chunk without relying on chunk order; validate version, count and opacity range. Missing chunk means fully opaque. The current model loader’s default branch ignores unknown chunks, so older engines are expected to show these assets opaque; verify that complete fallback, including packaging tools, rather than assuming it.
- [ ] Preserve the chunk through Blender import/export, model packaging, editor save and round trip. Audit other model writers/loaders before selecting the final format. Do not repurpose the high byte of `Color`, which is also used by existing primitive conventions.
- [ ] Add runtime opacity/blend accessors independently of legacy texture blend flags. Keep ordinary RGB updates from resetting opacity.

### 2. Shared ordering and backend state

- [ ] Pass material opacity and blend mode through every triangle submission variant. Prefer a small explicit draw-state structure over another growing list of boolean arguments.
- [ ] Introduce a common translucent queue so GL and Metal use the same deterministic order. Keep the opaque batching path intact. Queue only blended world triangles; capture vertices, current model/view/projection transforms, normals, texture handle, fog, lighting, prelit and culling policy by value or stable ownership.
- [ ] Render opaque world geometry first, with depth test and writes. Then sort blended triangles back to front in camera space, with a stable tie-breaker, depth testing against the opaque scene, and depth writes disabled. Triangles across different actors must share this ordering; texture batching may combine only adjacent compatible draws after sorting.
- [ ] Partition the queue by camera/render pass. Flush world translucency before matte/HUD/overlay drawing and before frame capture; clear it at the actual frame boundary. Do not let deferred draws inherit the last actor’s transform or leak into another camera’s pass.
- [ ] Use straight-alpha source-over compositing for explicitly opted-in materials. For initial flat glass/shade, alpha is material opacity. Ordinary textured materials retain their present opaque behaviour. Texture-alpha cutouts and continuous texture-alpha preservation remain a separately audited extension; the first phase must not make legacy black texels into unintended holes.
- [ ] GL/GLES/WebGL: explicit per-pass blend/depth state and shader opacity. Metal: equivalent blend factors and write-disabled depth state; preserve the ordinary opaque pipeline. Restore state for overlays and the following frame, including opaque framebuffer alpha.

Centroid triangle sorting is adequate as the initial approach for these mostly parallel surfaces, but is not a general solution for intersecting/cyclic transparent geometry. Test oblique views and gathered door leaves before accepting it. If this geometry produces visible sorting errors, split the affected surfaces or reconsider the technique; do not claim order-independent transparency.

### 3. Condo material and geometry treatment

- [ ] Give the moving door panes a dedicated glass material copy, so tuning does not silently change unrelated condo windows. Keep hardware material slots opaque.
- [ ] Make each pane contribute one visible optical surface from either side. Options to assess during implementation: a two-sided render sheet with unchanged collision geometry, or outward-wound thin boxes with back-face culling that admits one broad face per view. Avoid drawing front and back together for the same pane. Verify side-edge appearance and both camera directions.
- [ ] Apply the same principle to shade strips. Retain actor count, export order, indices, collision and existing motion. Separate render geometry from collision geometry where necessary rather than collapsing moving actors and invalidating Forth indices.
- [ ] Eliminate double coverage at the slat joins while retaining the gap-free visual invariant through the full travel. A simple alpha change or equal tint on every existing box is insufficient. Check front, back and oblique views; crop/split visible strips or use a dedicated visual sheet if the motion representation requires it. The chosen solution must also cover intermediate motion states and raised parking inside the cassette.
- [ ] Tune approved shade/glass opacity with fixed cameras in the actual condo. Lighting and fog affect RGB, not the material’s opacity. Inspect back-facing sheet lighting so the material does not turn black from one side.

## Implementation sequence after approval

1. **Baseline and format:** read-only glass probe, reproducible captures, material contract and OPAC round-trip tests. Deliver material values to a small test scene before rebuilding condo content.
2. **Renderer:** shared queue, state lifetime and ordering; GL/GLES/WebGL and Metal parity. Prove synthetic layered scenes first.
3. **Condo:** glass/shade material copies and geometry treatment; preserve interaction/collision/motion invariants; rebuild only the affected variants.
4. **Review evidence:** matched before/after captures and timing results, including Android/Chromecast. Tune from the visual review before rollout.

## Verification and review gates

| Case | Required evidence |
|---|---|
| Legacy assets | Existing assets without OPAC render as before; exporter emits no new chunk for fully opaque models. Include coloured-but-textured, prelit, sky/matte and HUD examples. |
| Export/import | Two material slots with different opacity; opaque old model; malformed/count-mismatched chunk; round trip retains values and MATL layout. |
| Compositing | Known flat colours over a fixed background at opacity 0, 0.25, 0.5 and 1; two layers in reversed submission order; opaque object in front; late-submitted opaque object behind. Check numeric pixel results within documented tolerances. |
| Transforms/state | Two differently transformed actors and differing fog/lighting states in one queue, multiple camera passes, overlay after translucency, and the next frame. |
| Glass | Closed, partial and fully gathered doors viewed from both sides and obliquely; real stacked panes tint naturally; single panes are not double tinted; handles stay opaque; player cannot pass closed glass. |
| Shade | Raised, half-lowered and closed; seam close-up plus balcony-wide view; no dark bands, gaps, bright seams or leaked parked fabric. Cassette/guides/bar stay opaque. |
| Both | Camera inside looking through closed doors and lowered shade; camera outside looking inward; sort order follows the camera, not actor creation order. |
| Platforms and cost | Matched captures on desktop GL, WebGL, Android GLES/Chromecast and Metal where hardware/build access exists. Record queued triangles, draws, queue memory and CPU/GPU frame time; compare with the same camera/state baseline. Mark unavailable platform evidence explicitly. |

Use the existing condo shade/door geometry and interaction verification scripts, plus renderer capture infrastructure such as `tests/compare_renderer_frames.py`. Add targeted opacity/order/round-trip tests at the layers that own those behaviours. Existing tests passing is necessary but does not establish the visual result; the matched captures above are required.

## Scope to approve

Recommended first phase: explicit flat-material opacity, optional model metadata, shared sorted compositing, corresponding GL/GLES/WebGL/Metal support, and corrected condo render surfaces. The mockup values are provisional. Continuous RGBA texture export, frosted blur, refraction, dynamic reflection and order-independent transparency are possible later phases, each with additional format/performance implications.

- [x] Inspect the authoring, model format, draw interface and both active backends.
- [x] Identify strip-overlap, double-surface and legacy-texture compatibility risks.
- [x] Prepare appearance mockups and a rendering-flow diagram.
- [ ] Will reviews and approves this plan.
- [ ] Begin implementation only after that approval.

Related plans: [balcony shade](2026-09-30-condo-balcony-shade.md), [telescoping glass doors](2026-09-20-condo-project-room-telescoping-doors.md), [Metal renderer](2026-09-20-macos-metal-renderer.md).

Primary API references for implementation: [Khronos glBlendFunc](https://registry.khronos.org/OpenGL-Refpages/gl4/html/glBlendFunc.xhtml), [Khronos glDepthMask](https://registry.khronos.org/OpenGL-Refpages/gl4/html/glDepthMask.xhtml), [Apple Metal blend configuration](https://developer.apple.com/documentation/metal/mtlrenderpipelinecolorattachmentdescriptor). Repository findings above come from local source inspection; these references are implementation reading, not runtime validation.
