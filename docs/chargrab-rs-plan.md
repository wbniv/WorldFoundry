# Plan: Port chargrab to Rust (chargrab-rs)

## Context

`chargrab` is a World Foundry game engine tool that extracts and deduplicates 16×16 pixel tiles from a source image, producing a compact tile atlas (TGA) and a binary tile-index map. It is the companion to `textile` (texture atlas packer), which has already been ported to Rust as `textile-rs`. This port uses the `image` crate for format reading, and `textile-rs` will be refactored to do the same — removing ~500 lines of hand-rolled TGA/BMP/SGI readers from both tools.

## Recommended approach

Create `wftools/chargrab-rs/` as an independent Rust binary crate (no shared library with textile-rs). Reuse the image format reading/writing patterns from `textile-rs/src/bitmap.rs` but with a stripped-down `Bitmap` struct — chargrab only needs `pixels`, `width`, `height`.

## Directory layout

```
wftools/chargrab-rs/
├── Cargo.toml
└── src/
    ├── main.rs       — CLI parsing, orchestration, entry point
    ├── bitmap.rs     — Bitmap struct, image loading (via `image` crate), TGA writer
    └── tile.rs       — TileMap struct, tile extraction & dedup algorithm
```

No `config.rs` needed — only two CLI flags (`-x`, `-y`). No `allocmap.rs` — tiles are placed sequentially, no 2D bin-packing.

## Critical files to read during implementation

The C++ `wftools/chargrab/` source has been deleted — it was never used in production (World Foundry was a 3D engine; tile extraction only applied to speculative 2D/Genesis work). The algorithm was fully documented in this plan before deletion.

- `wftools/textile-rs/src/bitmap.rs` — Rust colour conversion patterns to reuse (`rgba_555`, `rgb_555`, etc.)
- `wftools/textile-rs/Cargo.toml` — build config to mirror

## Cargo.toml

```toml
[package]
name = "chargrab-rs"
version = "0.1.0"
edition = "2021"
description = "World Foundry tile extractor and deduplicator (Rust port of wftools/chargrab)"

[[bin]]
name = "chargrab"
path = "src/main.rs"

[dependencies]
image = { version = "0.25", default-features = false, features = ["tga", "bmp", "png"] }

[profile.release]
opt-level = 3
lto = "thin"
strip = true
```

The `image` crate handles TGA, BMP, and PNG loading, replacing `tga.cc` and `bmp.cc`. SGI format is dropped — use `convert` (ImageMagick) to pre-convert `.sgi`/`.rgb`/`.bw` files. We decode to `Rgba8` then convert to BGR555 ourselves.

## Key types

**bitmap.rs**
```rust
pub struct Bitmap {
    pub pixels: Vec<u8>,   // 16-bit BGR555, cb_row = width * 2
    pub width:  usize,
    pub height: usize,
}
```

Image loading: `image::open(path)` → decoded as `Rgba8` → converted pixel-by-pixel to BGR555 using `rgba_555`. TGA and BMP handled by `image` crate. SGI dropped (use ImageMagick to convert). Colour conversion functions from textile-rs: `rgba_555`, `rgb_555`, `greyscale_rgb555`.

**tile.rs**
```rust
pub struct TileMap {
    pub entries: Vec<u8>,   // row-major, one u8 per tile
    pub x_tiles: usize,
    pub y_tiles: usize,
}
```

## Core algorithm (tile.rs: `extract_tiles`)

Direct translation of `main.cc` lines 321–358:

```rust
const TRANSPARENT_INDEX: u8 = 255;

pub fn extract_tiles(src: &Bitmap, out_xsize: usize, out_ysize: usize, tile_size: usize)
    -> Result<(Bitmap, TileMap), String>
{
    let ts = tile_size; // CLI -t flag, default 8
    let x_tiles = src.width / ts;
    let y_tiles = src.height / ts;
    let cols = out_xsize / ts;
    let max_tiles = cols * (out_ysize / ts);
    let mut out = Bitmap::new_blank(out_xsize, out_ysize);
    let mut map = TileMap::new(x_tiles, y_tiles);
    let mut n_tiles = 0usize;

    for y_off in (0..src.height).step_by(ts) {
        for x_off in (0..src.width).step_by(ts) {
            let idx = if tile_is_transparent(src, x_off, y_off, ts) {
                TRANSPARENT_INDEX
            } else {
                let found = (0..n_tiles).find(|&i| {
                    tiles_match(&out, (i % cols) * ts, (i / cols) * ts,
                                src, x_off, y_off, ts)
                });
                match found {
                    Some(i) => i as u8,
                    None => {
                        if n_tiles >= max_tiles {
                            // save partial atlas, exit 1 (mirrors C++)
                            return Err("ran out of tiles".into());
                        }
                        copy_tile(&mut out, (n_tiles % cols)*ts, (n_tiles / cols)*ts,
                                  src, x_off, y_off, ts);
                        let i = n_tiles;
                        n_tiles += 1;
                        i as u8
                    }
                }
            };
            map.set(x_off / ts, y_off / ts, idx);
        }
    }
    Ok((out, map))
}
```

`tiles_match` does row-by-row slice comparison (mirrors `sameBitmap` memcmp).

## TileMap binary format (matches `TileMap::Save` in main.cc)

```
[x_tiles as u32 LE] [y_tiles as u32 LE] [entries: u8 × (x_tiles × y_tiles)]
```

Note: `output.write((char*)&_xSize, 8)` in C++ writes `_xSize` (4 bytes) + `_ySize` (4 bytes) since the struct fields are adjacent `int` members on a 32-bit layout. Both are written as `u32` LE in Rust.

## TGA output format (matches `Bitmap::save` in bitmap.cc)

18-byte header: `ImageType=2` (uncompressed true-colour), `PixelDepth=16`, everything else zero except `Width` and `Height`. Rows written **bottom-to-top** by default (standard TGA convention). The C++ `bFlipYOut` flag reverses this; omit it unless `-flipyout` is added to the CLI.

## CLI

```
chargrab {-x<N>} {-y<N>} {-t<N>} <infile> <charfile> <mapfile>
```

- `-x<N>` — output atlas width in pixels (default 128; must be a multiple of tile size)
- `-y<N>` — output atlas height in pixels (default 512; must be a multiple of tile size)
- `-t<N>` — tile size in pixels (default **8**; common values: 8 for Genesis/SNES, 16 for other targets)

The C++ hardcoded `TILE_SIZE = 16` with no CLI flag; the Rust port makes it configurable and defaults to 8. Format dispatch: `.tga`, `.bmp`, and `.png` loaded via `image::open()`; `.sgi`/`.rgb`/`.bw` print an error message directing the user to convert with ImageMagick and exit 1.

Output paths are used exactly as given on the command line (no `szOutDir` prefix logic from C++).

## Implementation steps

### Phase A — Refactor textile-rs to use `image` crate

1. Add `image = { version = "0.25", default-features = false, features = ["tga", "bmp", "png"] }` to `wftools/textile-rs/Cargo.toml`
2. In `textile-rs/src/bitmap.rs`: replace `load_tga`, `load_bmp`, `load_sgi` with a single `load(path)` using `image::open()` → `to_rgba8()` → convert to BGR555 via existing `rgba_555`. Remove the hand-rolled format reader code (~500 lines). Keep colour conversion functions and everything else.
3. Verify `cargo build --release` for textile-rs still succeeds.

### Phase B — Build chargrab-rs

4. **Scaffold** — Create `wftools/chargrab-rs/Cargo.toml` + stub `main.rs`; verify `cargo build`
5. **bitmap.rs** — `Bitmap` struct, `new_blank`, pixel helpers, colour conversion (`rgba_555` etc. from textile-rs); `load(path)` using `image::open()` for `.tga`/`.bmp`/`.png` → decode to `Rgba8` → BGR555. Error on `.sgi`/`.rgb`/`.bw` with a message to use ImageMagick.
6. **TGA writer** — `save_tga(&Bitmap, path)`: 18-byte header + rows bottom-to-top using `BufWriter`
7. **tile.rs** — `TileMap`, `extract_tiles` (core dedup algorithm), `save_tilemap` (binary output)
8. **main.rs** — `parse_args`, call `load`, `extract_tiles`, handle out-of-tiles error (save partial atlas + exit 1), `save_tga`, `save_tilemap`
9. **Verify** — Run against a test image; diff tilemap output and inspect TGA

## Verification

The C++ chargrab was likely never used in production (World Foundry was a 3D engine; tile extraction was only relevant for speculative 2D/Genesis work). No real-world asset corpus exists to diff against. Verification is functional rather than byte-for-byte:

```sh
cd wftools/chargrab-rs
cargo build --release
# Synthesize a test image (e.g. with ImageMagick) or use any tiled sprite sheet:
convert -size 64x64 xc:black test.png   # trivial all-black test
./target/release/chargrab test.png out_atlas.tga out_map.bin
```

Check:
- Tilemap file is `8 + (x_tiles * y_tiles)` bytes; header is two u32 LE (x_tiles, y_tiles)
- Transparent (all-zero) tiles map to index 255
- Output TGA opens correctly in an image viewer (GIMP, `eog`, etc.)
- Tile count printed to stdout is plausible
- Duplicate tiles in input produce the same index in the map
