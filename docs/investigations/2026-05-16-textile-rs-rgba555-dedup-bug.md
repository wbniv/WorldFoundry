# Investigation — textile-rs RGBA→BGR555 alpha-inversion + false deduplication

**Date:** 2026-05-16  
**Status:** Root cause confirmed; workaround in place  
**Fixed in:** `blender_create_qbert.py` (use 24-bit RGB TGA, not RGBA)

## Symptom

`Room0.tga` was only 146 bytes (4×16 pixels) after a textile-rs run that should have packed a 128×64 texture. The engine loaded the level normally but the curse-bubble mesh rendered as solid colour (no text visible).

## Root Cause: Two Bugs Acting Together

### Bug 1 — `rgba_555()` maps fully-opaque pixels to transparent

`wftools/textile-rs/src/bitmap.rs:rgba_555()` (line 38):

```rust
fn rgba_555(r: u8, g: u8, b: u8, a: u8) -> u16 {
    if a > 170 {
        return 0;          // <-- returns TRANSPARENT for opaque pixels
    }
    br_colour_rgb_555(r, g, b)
}
```

The convention is inverted: the function returns 0 (the BGR555 transparent key) when alpha > 170, i.e. when the pixel is **fully opaque**. Every pixel in a standard RGBA texture with alpha=255 becomes 0x0000.

### Bug 2 — `find_existing()` false deduplication against an all-zero atlas

After bug 1 turns the entire texture into 0x0000 pixels, `find_existing()` (`bitmap.rs:405`) compares the texture's pixel data byte-by-byte against the atlas, which is also initialized to zeros. Every pixel matches — the texture is falsely considered "already present" at offset (0,0).

The blit is skipped, the allocation map records no usage, and when the atlas is cropped to its minimum non-empty bounding box it produces a 4×16 placeholder (the internal no-data floor, not even the texture region).

`Room0.ruv` is still written with the correct texture name and nominal dimensions (128×64, u=0, v=0) because that metadata comes from the deduplication-match path, not the blit path — so no error is raised.

## Fast Path: `try_load_tga_bgr555()`

`bitmap.rs:595` has a separate fast path for 16-bit and 24-bit TGA files. For 24-bit:

```rust
// bpp == 24: three bytes per pixel, no alpha channel
let col = br_colour_rgb_555(r, g, b);
```

`br_colour_rgb_555()` truncates each channel to 5 bits and packs them — it has no alpha logic and therefore no alpha-inversion bug.

## Fix

Generate the texture as **24-bit RGB** (PIL `Image.new('RGB', ...)`):

```python
img = Image.new('RGB', (W, H), (255, 255, 255))
```

PIL saves a 24-bit TGA when the mode is `'RGB'`. `textile-rs` detects `bpp=24` and takes the `try_load_tga_bgr555()` fast path, bypassing `rgba_555()` entirely.

## Second Issue: BGR555 Transparent Key = 0x0000

The engine uses `0x0000` as the transparent pixel value. Dark colours round to (0,0,0) = 0x0000 and become transparent in-game even if they were opaque in the source TGA.

Original text colour: `(20, 20, 20)` → `br_colour_rgb_555(20,20,20)` = `(0, 0, 0)` = 0x0000 → invisible text.

Fix: use `(40, 40, 40)` → `br_colour_rgb_555(40,40,40)` = `(1, 1, 1)` = 0x0421 (non-zero, clearly visible).

**Rule:** any colour with all RGB channels below 8 will round to 0x0000 in BGR555 and be treated as transparent. Minimum safe values: each channel ≥ 8.

## Affected Code Paths

| Path | Condition |
|------|-----------|
| `rgba_555()` (RGBA TGA, bpp=32) | **Buggy** — alpha > 170 → 0x0000 for every opaque pixel |
| `try_load_tga_bgr555()` bpp=24 | **Correct** — no alpha channel, `br_colour_rgb_555` only |
| `try_load_tga_bgr555()` bpp=16 | **Correct** — already BGR555, verbatim copy |

## How to Detect the Bug at Build Time

After textile-rs runs, check:

```bash
ls -lh Room0.tga     # must be > 1 KB for any real texture
xxd Room0.tga | head  # first pixels should NOT all be 0x0000
```

`Room0.ruv` having a correct texture entry does NOT mean the texture was actually blitted — the false-deduplication path writes the RMUV entry before blitting.

## Status of the textile-rs Bugs

Both bugs (`rgba_555` alpha inversion, `find_existing` false dedup against empty atlas) remain in `wftools/textile-rs/src/bitmap.rs`. They are worked around by generating 24-bit RGB TGA inputs. A proper fix would require inverting the alpha condition in `rgba_555()` and adding a guard in `find_existing()` to skip comparison when the atlas is empty.

## Related

- [Plan — curse bubble texture](../plans/2026-05-16-curse-bubble-texture.md)
- [Investigation — curse bubble non-bugs](2026-05-12-curse-bubble-non-bugs.md)
