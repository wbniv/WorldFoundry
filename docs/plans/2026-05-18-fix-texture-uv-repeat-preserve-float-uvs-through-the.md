# Fix texture UV repeat — preserve float UVs through the GL path

## Context

[docs/investigations/2026-05-18-texture-uv-uint8-overflow.md](../../WorldFoundry.2026-new-level/docs/investigations/2026-05-18-texture-uv-uint8-overflow.md) documents the root cause: mesh UVs (full-precision `Scalar`s in `vertexList[i].u/v`) get truncated to `unsigned char` when `material.cc` builds a `POLY_GT3`/`POLY_FT3` primitive (`CalcVRAMuv` macro at [rendmatt.cc:69-79](../../WorldFoundry.2026-new-level/wfsource/source/gfx/rendmatt.cc)). On the GL backend the truncated uchar is later divided back to float `[0,1]` of the atlas *page* — losing both the original UV precision and the wrap-modulo semantics the PS1 GPU used to provide. `GL_REPEAT` on the texture object is set but useless: by the time the shader sees `v_uv`, it has already been hammered into `[0,1]`.

Symptom in the wild: SMB W1-1 ground (statplat with mesh UVs `0..73.5`, 32×32 tile) renders as one solid colour instead of a tiled grid. Workaround is to pre-tile the texture; engine fix unblocks any future statplat that wants `>~5` UV repeats with a small tile.

The investigation's preferred fix (verbatim): "replumb `gfx/glpipeline/rend*tp.cc` and the GL backend so that mesh `vertexList[i].u, .v` (already full-precision `Scalar`s) flow directly into the GL `Vert.u, .v` floats, with the atlas offset applied as a separate scale-and-bias on the final float UV." That is what this plan implements.

## Architectural approach

The right place to do `fract(uv)` is the fragment shader — vertex-side `fract` would interpolate linearly across a triangle and collapse all tiles back into one. So:

1. **Vertex pipeline** carries the raw (potentially-large) mesh UV all the way to the fragment shader as a varying.
2. **Atlas slot** (origin + scale in page-normalised coords) travels alongside the UV. A single mesh can use multiple atlas slots in one `PixelMap`, so this needs to be per-primitive — implemented as 4 extra floats on each `RBVertex` (flat-interpolated through to the fragment shader since they're constant across the triangle).
3. **Fragment shader** does `vec2 sample_uv = v_atlas_origin + fract(v_uv) * v_atlas_scale; texture(u_tex, sample_uv);`. `fract` makes the wrap happen at the fragment level (the seam between tiles falls on a fragment boundary, not a vertex); the atlas scale/bias then maps the unit-tile coord into this slot's pixels.
4. **Atlas wrap mode** on the texture object changes from `GL_REPEAT` to `GL_CLAMP_TO_EDGE` — wrap is now handled in the shader, against the atlas slot rather than the whole page. The slot-bleed problem (bilinear sampling at exactly `fract==0`) is a known atlas-packing issue and out of scope here; punt to a follow-up if it surfaces.

The PS1-legacy uchar `poly.u0/v0/u1/v1/u2/v2` fields stay where they are — the few remaining PS1-target callers (if any) keep working. New parallel float fields are added to `POLY_GT3`/`POLY_FT3` and populated by `material.cc`.

## Files modified

| File | Change |
|---|---|
| [wfsource/source/gfx/gl/wfprim.h](../../WorldFoundry.2026-new-level/wfsource/source/gfx/gl/wfprim.h) | Add 6 raw-UV floats (`u0_f,v0_f,u1_f,v1_f,u2_f,v2_f`) and 4 atlas params (`atlasOriginU/V`, `atlasScaleU/V`) to `POLY_GT3` and `POLY_FT3`. |
| [wfsource/source/gfx/material.cc](../../WorldFoundry.2026-new-level/wfsource/source/gfx/material.cc) | In the `TEXTURE_MAPPED` (~line 280) and `GOURAUD_SHADED\|TEXTURE_MAPPED` (~line 349) cases, populate the new float UV fields with `(vertex.u - offsetU).AsFloat()` (no `*int(tex.w-1)` scaling — that's now the shader's job). Compute atlas params once: `atlasOriginU = float(_texture.u) / pageW`, `atlasScaleU = float(_texture.w) / pageW`, same for V. |
| [wfsource/source/gfx/renderer_backend.hp](../../WorldFoundry.2026-new-level/wfsource/source/gfx/renderer_backend.hp) | Add `float atlasOriginU, atlasOriginV, atlasScaleU, atlasScaleV` to `RBVertex` (default 0,0,1,1 so untextured paths sample directly). |
| [wfsource/source/gfx/glpipeline/rendgtp.cc](../../WorldFoundry.2026-new-level/wfsource/source/gfx/glpipeline/rendgtp.cc) | Replace the `CalcUV(poly.tpage, poly.uN, poly.vN, …, v[N].u, v[N].v)` calls with direct copies of `poly.uN_f → v[N].u`, `poly.vN_f → v[N].v`, plus copies of `poly.atlas*` into the corresponding `RBVertex` fields. `CalcUV` becomes dead code in this file (delete the static helper). |
| [wfsource/source/gfx/glpipeline/rendftp.cc](../../WorldFoundry.2026-new-level/wfsource/source/gfx/glpipeline/rendftp.cc) | Same as `rendgtp.cc`. |
| [wfsource/source/gfx/glpipeline/rendgtl.cc](../../WorldFoundry.2026-new-level/wfsource/source/gfx/glpipeline/rendgtl.cc) | Same — verify same `CalcUV` pattern; replace if present. |
| [wfsource/source/gfx/glpipeline/rendftl.cc](../../WorldFoundry.2026-new-level/wfsource/source/gfx/glpipeline/rendftl.cc) | Same — verify same `CalcUV` pattern; replace if present. |
| [wfsource/source/gfx/glpipeline/backend_modern.cc](../../WorldFoundry.2026-new-level/wfsource/source/gfx/glpipeline/backend_modern.cc) | Extend `Vert` struct with 4 atlas floats. Add `layout(location=4) in vec4 a_atlas;` to vertex shader, `flat out vec4 v_atlas;`. Fragment shader: `flat in vec4 v_atlas; vec2 sample_uv = v_atlas.xy + fract(v_uv) * v_atlas.zw; texture(u_tex, sample_uv);`. Add `glEnableVertexAttribArray(4)` + `glVertexAttribPointer(4, 4, GL_FLOAT, GL_FALSE, stride, (void*)offsetof(Vert, atlasOriginU))` in `LazyInit()`. Update `Pack()` to copy the 4 atlas fields. |
| [wfsource/source/gfx/pixelmap.cc](../../WorldFoundry.2026-new-level/wfsource/source/gfx/pixelmap.cc) (lines 208/210) | `GL_TEXTURE_WRAP_S/T = GL_CLAMP_TO_EDGE` instead of `GL_REPEAT`. Wrap is now handled in the shader against the atlas slot, not the page. |

Out of scope for this PR: `rendmatt.cc` (`ScrollingMatte` — pre-divides UVs into `[0,1]` before `CalcVRAMuv`; works today). Atlas-slot bilinear bleed (separate concern; texture-packing-side fix).

## Verification

1. **Compile** — `task build` on Linux. Watch for unused-variable warnings on the now-dead `CalcUV` static in the rend*tp/tl files; remove cleanly.

2. **Visual parity smoke test on snowgoons** — `cd wfsource/source/game && ./wf_game` (snowgoons is the hardcoded default). All meshes with UVs in `[0,1]` should render identical to HEAD. Capture a screenshot, diff against the last known-good snowgoons screenshot.

3. **Tile-repeat regression test (the actual bug)** — rebuild SMB W1-1 (`bash wftools/wf_blender/build_level_binary.sh smb_w1_1`) with the diagnostic grid texture (red + green checker) and ground UVs `0..73.5`. Expect ~73 visible tiles across the ground instead of one large pattern. Capture in-game screenshot per `feedback_screenshots_for_proof.md`.

4. **Add a permanent regression test** (per the investigation §"Suggested test coverage after the fix"): `tests/test_renderer_tiling.py` builds a minimal level with one 16 m statplat, top-textured with a 32×32 two-colour tile, mesh UV `(0..16, 0..1)`; boots `wf_game` via the debug bridge; captures a screenshot; asserts ≥8 colour transitions across the visible ground span.

5. **Atlas slot mapping sanity check** — qbert_practice uses a multi-slot atlas (cube top/lit/shadow + player + several enemies in one page). Walk Q\*bert across the pyramid and confirm cube colours are unchanged from HEAD; that exercises the `atlasOriginU/V + atlasScaleU/V` math against a non-zero slot origin (the snowgoons case may have everything at origin 0,0).

## Risks / things to watch

- **Atlas slot bleed at `fract==0`** — bilinear sampling can pull from the adjacent slot at the seam. Snowgoons probably uses `GL_NEAREST` magnification (PSX-look pixelation); confirm at [pixelmap.cc](../../WorldFoundry.2026-new-level/wfsource/source/gfx/pixelmap.cc). If linear, defer; SMB grid test will reveal whether it's actually visible.
- **`flat` qualifier on `v_atlas`** — GLSL `flat out` takes the value from the *provoking* vertex (last vertex of the triangle by default in GL 3.3 core). All three of a triangle's vertices in the same draw call carry the same atlas params (set per-primitive in `material.cc`), so this is fine — but worth confirming via the qbert visual check rather than asserting blind.
- **`pPixelMap` may differ from page bounds used in `DecodeTPageX/Y`** — current `CalcUV` divides by `texturePixelMap.GetBaseXSize()` (the *page* width); `material.cc` already uses `_texturePixelMap` and `_texture.u/_texture.v/_texture.w/_texture.h`. Confirm `GetBaseXSize()` matches whatever page width is implicit in `getTPage()` encoding — should be the same atlas page, but if it isn't the atlas params will be wrong. Spot-check by printing both at runtime if anything looks off.
- **Mid-tile fragments at the seam** — when a triangle vertex has `u = 73.0` and the next has `u = 73.5`, GL interpolates `v_uv` linearly. `fract(73.0) = 0.0, fract(73.5) = 0.5`, but at fragments *between* the vertices `v_uv` linearly traverses `73.0 → 73.5` so `fract` produces `0 → 0.5` cleanly. The only artefact is the implicit `fract` discontinuity at integer boundaries — which is exactly where the tile seam should be, so it's correct. Just noting for completeness.

## Implementation sequence

1. `wfprim.h` — extend `POLY_GT3`/`POLY_FT3` structs. Compile-check (everything else still compiles even though fields are unread).
2. `material.cc` — populate the new float fields in both texture-mapped branches. Compile-check.
3. `renderer_backend.hp` — extend `RBVertex`. Compile-check.
4. `rendgtp.cc` first (the simpler/canonical example), then `rendftp.cc`, then `rendgtl.cc`/`rendftl.cc` if they have the same `CalcUV` pattern. After each, run on snowgoons to confirm no regression.
5. `backend_modern.cc` — extend `Vert`, shader (vs + fs), attribute pointers, `Pack`. Confirm snowgoons still renders correctly with `GL_REPEAT` still set on the texture (the shader's `fract` should give the same result as the old path for `uv ∈ [0,1]`).
6. `pixelmap.cc` — switch to `GL_CLAMP_TO_EDGE`. Confirm snowgoons unchanged.
7. Build SMB W1-1 with the grid texture + large-UV ground; verify tiling appears; capture proof screenshot.
8. Commit per phase (per `feedback_commit_after_each_phase.md`); update [TODO.md](../../WorldFoundry.2026-new-level/TODO.md) entry to move the "Bug: texture UV repeat broken …" line to DONE; update [docs/investigations/2026-05-18-texture-uv-uint8-overflow.md](../../WorldFoundry.2026-new-level/docs/investigations/2026-05-18-texture-uv-uint8-overflow.md) status from "Open bug" to "Fixed 2026-05-18 — see commits …".

This plan will also be copied to `docs/plans/2026-05-18-uv-float-passthrough.md` for the project-side record (per `feedback_plans_in_project.md`).
