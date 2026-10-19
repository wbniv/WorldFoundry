# Texture UV repeat broken: atlas-coord uint8 overflow in the render path

**Date:** 2026-05-18
**Discovered while:** implementing the unit-grid floor texture for the SMB W1-1 scrolling-camera verification screenshots ([`docs/plans/2026-05-17-smb-scrolling-camera.md`](../plans/2026-05-17-smb-scrolling-camera.md)).
**Status:** Open bug; TODO entry under `SCRIPTING ENGINES` (mis-categorised — should arguably be its own `RENDERER` section). Workaround in use for SMB.

---

## Symptom

A statplat mesh with an image-textured material and **mesh UVs larger than roughly 5–8** does not tile its texture correctly. Instead of GL_REPEAT producing visible repeating tiles, the entire textured face samples one apparently-random atlas region — typically a single solid colour.

Concrete: SMB W1-1 ground is a 73.5 m × 3 m statplat. Top face textured with a 32×32 `grid_tile.tga` (light brown with a darker line on the left + bottom edges). With mesh UVs going `0..73.5` on X (so the 32-pixel tile would repeat 73 times across the level), the ground rendered as a *uniform* brown — no grid lines visible at all.

A high-contrast diagnostic texture (red field with a green check in two quadrants) proved the texture pipeline itself works:
- **UVs in [0, 1]** (one tile spread across the whole top face) → clearly visible red + green stripes on screen. Texture sampling works.
- **UVs in [0, 73.5]** with the *same* texture → identical appearance to the [0,1] case (single visible stripe pair). Tiling does **not** happen.

If GL_REPEAT were working, the [0, 73.5] case should have shown ~73 tiny red/green tiles instead of the same big stripes as [0, 1].

## Root cause

Trace, in render order:

1. **Mesh load.** [`gfx/rendobj3.cc:179-181`](../../wfsource/source/gfx/rendobj3.cc) reads `tempVertex.u`/`.v` from the IFF VRTX chunk (fixed32, full 32-bit precision) into `vertexList[count].u/v` as `Scalar`s. ✓ UVs preserved at full precision here.

2. **Atlas coordinate conversion.** [`gfx/rendmatt.cc:69-79`](../../wfsource/source/gfx/rendmatt.cc) — the `CalcVRAMuv` macro:

   ```cpp
   #define CalcVRAMuv(uin,vin,resultu,resultv,texture) \
       { \
       Scalar u(uin); \
       Scalar v(vin); \
       Scalar vramU = (u * int(texture.w-1)) + Scalar(texture.u,0); \
       AssertMsg(vramU >= Scalar::zero, ...); \
       resultu = vramU.WholePart(); \
       Scalar vramV = (v * int(texture.h-1)) + Scalar(texture.v,0); \
       AssertMsg(vramV >= Scalar::zero, ...); \
       resultv = vramV.WholePart(); \
       }
   ```

   This transforms a normalised-ish mesh UV (`u`) into an **atlas pixel coordinate** (`resultu` = `u * (texW - 1) + atlasOriginU`). The assumption is `u ∈ [0, 1]`, in which case `vramU` lands inside `[atlasOriginU, atlasOriginU + texW - 1]` — i.e. somewhere inside this texture's slot in the room atlas. Mesh UVs outside [0, 1] *should* tile (atlas would need to loop back to the start), but the math just keeps multiplying, producing increasingly large `vramU`.

3. **Storage into PS1-legacy uint8.** `resultu` and `resultv` are then assigned into `POLY_GT3` fields whose declared types are **`unsigned char`**. Evidence:
   - [`gfx/glpipeline/rendgtp.cc:82`](../../wfsource/source/gfx/glpipeline/rendgtp.cc): `CalcUV(poly.tpage, poly.u0, poly.v0, *poly.pPixelMap, v[0].u, v[0].v);`
   - [`gfx/rendmatt.cc:81-95`](../../wfsource/source/gfx/rendmatt.cc): `static void CalcUV(unsigned char uin, unsigned char vin, const PixelMap& texturePixelMap, float& uOut, float& vOut)`

   So the atlas pixel coord is round-tripped through `unsigned char` — domain `[0, 255]`.

4. **Float-back-to-[0, 1] for GL.** `CalcUV` then divides `uin / texturePixelMap.GetBaseXSize()` to produce a float in roughly `[0, 1]` of the *page* (the full atlas TGA). That float is what `backend_modern.cc` uses in its fragment shader's `texture(u_tex, v_uv)`.

5. **GL_REPEAT applied here is useless.** The texture object DOES have `GL_TEXTURE_WRAP_S/T = GL_REPEAT` set at [`gfx/pixelmap.cc:208/210`](../../wfsource/source/gfx/pixelmap.cc), and the shader does `texture(u_tex, v_uv)` (which GL_REPEAT covers when `v_uv` is outside `[0, 1]`). But by the time we get to GL, `v_uv` has already been hammered into `[0, 1]` by the uint8 truncation in step 3 — the wrap mode has nothing to do.

### Where it truncates

With `u = 73.5` (mesh UV for the right edge of the SMB ground when 1 UV unit = 1 metre) and `texture.w = 32`:

```
vramU = 73.5 × 31 + atlasOriginU
      = 2278.5 + atlasOriginU
```

Stored into `unsigned char` → `2278 mod 256 = 230` (plus whatever `atlasOriginU` was). The renderer then samples atlas-pixel 230, which is somewhere in a different texture's slot — or off the end entirely.

### When it doesn't bite

`vramU < 256` works correctly (no truncation). With `texW = 32`, that's `u < (255 - atlasOriginU) / 31`. With `atlasOriginU = 0`, the safe range is `u ∈ [0, ~8.2]`. With a 16-wide texture, `[0, ~17]`. So **small UVs and small textures get away clean**.

## Why this is a regression, not a planned limitation

The user reports that texture-map tiling *used to* work in WF. The PS1-legacy path going through `POLY_GT3` with `unsigned char u`/`v` was correct in the PS1 era — there, `u, v` named PS1 texture-page atlas coords directly, and the PS1 GPU's GS register interpreted them with wrap modulo. The PSX HW essentially treated `u, v` as `uint8 mod texW` — i.e. wrap was native.

On the OpenGL backend, the design pretends to preserve that "uint8 atlas coord" interface but converts to float UV for GL just-in-time. The conversion divides by the *page* width, losing the wrap-modulo semantics. So a UV `2278 mod 256 = 230` becomes `230 / pageWidth ≈ 0.45` instead of the intended `(73.5 mod 1.0) = 0.5`. The two values *happen to be similar* (because both modulo into a tile-relative coord), but they aren't the same — and once `atlasOriginU > 0`, they diverge wildly.

Net: the OpenGL port preserved the legacy data path without preserving the legacy wrap semantics.

## Reproduction

1. Make a 32×32 high-contrast TGA (`(255,0,0)` background; `(0,255,0)` checker in two quadrants).
2. Apply to the top face of any statplat that is >8 m on its longer dimension.
3. Set mesh UVs so 1 UV unit = 1 world metre on that face.
4. Build the level pipeline and run `wf_game` on it.

**Expected:** visible 1-metre tiles of red/green across the face.
**Actual:** the entire face renders as one big red/green pattern (UV truncated to a single sub-1.0 value).

A control test with mesh UVs in `[0, 1]` shows the texture *is* being sampled — it's only tiling that's broken.

## Workarounds (no engine fix required)

1. **Pre-tile the texture asset.** Bake the grid pattern into one wide texture so mesh UV stays in `[0, 1]`. Limit: textile-rs requires both width *and* height to be powers of two from `{16, 32, 64, 128, 256, 512, 1024}` ([`textile-rs/src/bitmap.rs:507-510`](../../wftools/textile-rs/src/bitmap.rs)), and the default atlas page is 256×256 (per `build_level_binary.sh`). So you have at most a 256×N texture, which constrains how many grid cells fit. For a 73-metre level, even a 256-wide texture only buys ~3.5 pixels per metre — fine for a coarse grid, mediocre for fine detail.
2. **Subdivide the mesh.** Break the textured face into N quads, each with UV in `[0, 1]` on the same small tile. N quads = N grid cells. Same visual as tiling but increases vertex/face count linearly.
3. **Limit UV range.** Use UV up to ~5 with a 32-px texture (or up to ~17 with a 16-px texture). The renderer still tiles for small ranges. Useful when only a small portion of a large mesh needs the texture.

## Proper fix (engine work)

Two paths, in order of preference:

1. **Preserve float UVs all the way through the GL path.** The PS1-legacy `POLY_GT3` `u`/`v` fields were correct for the PS1 GPU; on the GL path they're a vestigial precision bottleneck. The cleanest fix is to replumb `gfx/glpipeline/rend*tp.cc` and the GL backend so that mesh `vertexList[i].u, .v` (already full-precision `Scalar`s) flow directly into the GL `Vert.u, .v` floats, with the atlas offset applied as a separate scale-and-bias on the final float UV. That preserves both the atlas indirection *and* GL_REPEAT semantics for large UVs.
2. **Widen `poly.u`/`poly.v` to int16 or int32.** Cheaper local fix; doesn't fix the underlying "atlas wrap doesn't compose with GL_REPEAT" issue but lets large UVs survive without bit-rot. Still leaves a worse-than-necessary precision floor in the PS1-legacy intermediate format.

Either fix needs a regression test that draws a textured statplat with UV ≥ 10 and verifies tiling.

## Suggested test coverage after the fix

A `tests/test_renderer_tiling.py` (or similar) that:

1. Builds a minimal level with one 16 m × 1 m × 0 m statplat, top-textured with a 32×32 two-colour tile, mesh UV `(0..16, 0..1)`.
2. Runs `wf_game -L<level>` with the debug bridge.
3. Captures a screenshot.
4. Asserts that the pixel-row immediately above the front edge of the statplat contains *at least* 8 distinct two-colour transitions across the visible portion of the ground.

That's the simplest visible-evidence that tiling is alive.

## Cross-references

- TODO entry: [`TODO.md`](../../TODO.md) § `SCRIPTING ENGINES` — "Bug: texture UV repeat broken for mesh UVs outside [0, ~5]".
- Discovered while implementing: [`docs/plans/2026-05-17-smb-scrolling-camera.md`](../plans/2026-05-17-smb-scrolling-camera.md) — see the verification-screenshots subsection.
- Related render code:
  - [`wfsource/source/gfx/rendobj3.cc:179-181`](../../wfsource/source/gfx/rendobj3.cc) — mesh UV load (correct, full precision).
  - [`wfsource/source/gfx/rendmatt.cc:69-79`](../../wfsource/source/gfx/rendmatt.cc) — `CalcVRAMuv` macro (introduces the atlas-pixel-coord intermediate that gets truncated).
  - [`wfsource/source/gfx/rendmatt.cc:81-95`](../../wfsource/source/gfx/rendmatt.cc) — `CalcUV` (signature takes `unsigned char` — the truncation site).
  - [`wfsource/source/gfx/glpipeline/rendgtp.cc:82,90,98`](../../wfsource/source/gfx/glpipeline/rendgtp.cc) — modern GL path that calls `CalcUV` with `poly.u`/`poly.v` already truncated.
  - [`wfsource/source/gfx/glpipeline/backend_modern.cc:114`](../../wfsource/source/gfx/glpipeline/backend_modern.cc) — fragment shader `texture(u_tex, v_uv)`.
  - [`wfsource/source/gfx/pixelmap.cc:208,210`](../../wfsource/source/gfx/pixelmap.cc) — `GL_REPEAT` set on the texture (correctly, but ineffective due to upstream truncation).
- textile-rs constraint: [`wftools/textile-rs/src/bitmap.rs:507-532`](../../wftools/textile-rs/src/bitmap.rs) — `is_pow2` check forces texture dims into `{16, 32, 64, 128, 256, 512, 1024}`.
