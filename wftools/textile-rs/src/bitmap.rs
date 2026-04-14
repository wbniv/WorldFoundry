// bitmap.rs — Bitmap data structure and image format readers/writers
// Port of bitmap.hp/cc, tga.cc, bmp.cc
//
// Internal pixel format: BGR555 with translucent bit at 15
//   bit 15 : translucent / alpha flag
//   bits 14:10 : Blue  (5 bits)
//   bits 9:5   : Green (5 bits)
//   bits 4:0   : Red   (5 bits)
//
// Image loading uses the `image` crate (TGA, BMP, PNG → RGBA8 → BGR555).
// SGI format (.rgb/.bw/.sgi) is not supported; use ImageMagick to convert.
// The atlas (out_bitmap) is always 16-bit: cb_row = width * 2.

use std::fs::File;
use std::io::{self, BufWriter, Write};
use std::path::Path;

use crate::allocmap::{AllocationMap, round};
use crate::config::{Config, TargetSystem};
use crate::profile;

const TRANSLUCENT_BIT: u16 = 1 << 15;

// ─── Colour conversion ───────────────────────────────────────────────────────

/// BGR_RGB_555: RGB bytes to BGR555 (no alpha). Used for palette conversion and col_transparent.
#[inline]
pub fn br_colour_rgb_555(r: u8, g: u8, b: u8) -> u16 {
    let rr = (r as u16) >> 3;
    let gg = (g as u16) >> 3;
    let bb = (b as u16) >> 3;
    (bb << 10) | (gg << 5) | rr
}

/// RGBA_555: converts 8-bit RGBA to BGR555.
/// alpha=0 if pixel should be fully transparent (bit 15 set only if a<85).
#[inline]
pub fn rgba_555(r: u8, g: u8, b: u8, a: u8) -> u16 {
    if a > 170 {
        return 0;
    }
    let rr = (r as u16) >> 3;
    let gg = (g as u16) >> 3;
    let bb = (b as u16) >> 3;
    let alpha: u16 = if (a as u16) < 85 { 1 } else { 0 };
    (alpha << 15) | (bb << 10) | (gg << 5) | rr
}

// ─── ColourCycle ─────────────────────────────────────────────────────────────

#[derive(Clone, Copy, PartialEq)]
pub struct ColourCycle {
    pub start: i32,
    pub end:   i32,
    pub speed: f32,
}

// ─── Bitmap ──────────────────────────────────────────────────────────────────

pub struct Bitmap {
    /// Raw pixel buffer.  16-bit: cb_row = width*2; 8-bit: cb_row = width; 4-bit: cb_row = width/2 (rounded up)
    pub pixels:             Vec<u8>,
    pub width:              i32,
    pub height:             i32,
    pub bitdepth:           i32,   // 4, 8, 15, or 16
    pub cb_row:             i32,   // bytes per row
    pub buf_width:          i32,
    pub buf_height:         i32,
    pub name:               String,
    /// Converted 16-bit palette for paletted images
    pub converted_palette:  Vec<u16>,
    pub cmap_start:         i32,
    pub cmap_length:        i32,
    pub start_colour:       i32,
    pub end_colour:         i32,
    /// Position within atlas (-1 = not placed yet)
    pub subx:               i32,
    pub suby:               i32,
    /// Palette position in palette atlas (-1 = none)
    pub xpal:               i32,
    pub ypal:               i32,
    pub idx_pal:            i32,
    pub colour_cycles:      Vec<ColourCycle>,
    pub has_transparent:    bool,
    pub power_of2:          bool,
}

impl Bitmap {
    // ── Constructors ────────────────────────────────────────────────────────

    /// Create a blank atlas bitmap of given dimensions, filled with `bg_byte`.
    pub fn new_blank(width: i32, height: i32, bg_byte: u8, power_of2: bool) -> Self {
        let cb_row = width * 2;
        let size = cb_row as usize * (height as usize + 1); // +1 as in C++
        Bitmap {
            pixels:            vec![bg_byte; size],
            width,
            height,
            bitdepth:          16,
            cb_row,
            buf_width:         width,
            buf_height:        height,
            name:              String::new(),
            converted_palette: Vec::new(),
            cmap_start:        0,
            cmap_length:       0,
            start_colour:      -1,
            end_colour:        -1,
            subx:              -1,
            suby:              -1,
            xpal:              -1,
            ypal:              -1,
            idx_pal:           -1,
            colour_cycles:     Vec::new(),
            has_transparent:   false,
            power_of2,
        }
    }

    /// Create a palette bitmap from another bitmap's colour table.
    /// Used in palette_fit() to pack palette data into the palette atlas.
    pub fn from_palette(src: &Bitmap) -> Self {
        let n = src.colours_used() as i32;
        let cb_row = n * 2;
        let mut pixels = vec![0u8; cb_row as usize];
        // copy converted palette as raw u16 LE bytes
        for (i, &colour) in src.converted_palette.iter().enumerate().take(n as usize) {
            let off = i * 2;
            let bytes = colour.to_le_bytes();
            pixels[off]     = bytes[0];
            pixels[off + 1] = bytes[1];
        }
        Bitmap {
            pixels,
            width:             n,
            height:            1,
            bitdepth:          16,
            cb_row,
            buf_width:         n,
            buf_height:        1,
            name:              src.name.clone(),
            converted_palette: Vec::new(),
            cmap_start:        0,
            cmap_length:       0,
            start_colour:      src.start_colour,
            end_colour:        src.end_colour,
            subx:              -1,
            suby:              -1,
            xpal:              -1,
            ypal:              -1,
            idx_pal:           -1,
            colour_cycles:     src.colour_cycles.clone(),
            has_transparent:   false,
            power_of2:         src.power_of2,
        }
    }

    /// Area metric used for sorting (largest first).
    pub fn area(&self) -> i32 {
        self.width * self.height * self.bitdepth / 16
    }

    /// Number of palette entries (0 for 16-bit images).
    pub fn colours_used(&self) -> usize {
        if self.bitdepth == 16 { 0 } else { self.cmap_length as usize }
    }

    // ── Pixel ops ───────────────────────────────────────────────────────────

    fn pixel_ref(&mut self, x: i32, y: i32) -> &mut u16 {
        let off = y as usize * (self.cb_row as usize / 2) + x as usize;
        let ptr = self.pixels.as_mut_ptr() as *mut u16;
        unsafe { &mut *ptr.add(off) }
    }

    fn pixel_at(&self, x: i32, y: i32) -> u16 {
        let off = (y as usize * self.buf_width as usize + x as usize) * 2;
        u16::from_le_bytes([self.pixels[off], self.pixels[off + 1]])
    }

    fn set_pixel(&mut self, x: i32, y: i32, val: u16) {
        let off = (y as usize * self.buf_width as usize + x as usize) * 2;
        let bytes = val.to_le_bytes();
        self.pixels[off]     = bytes[0];
        self.pixels[off + 1] = bytes[1];
    }

    fn foreach_pixel_16<F: FnMut(u16) -> u16>(&mut self, mut f: F) {
        assert_eq!(self.bitdepth, 16);
        let rows = self.height as usize;
        let cols = self.width as usize;
        for y in 0..rows {
            for x in 0..cols {
                let off = (y * self.buf_width as usize + x) * 2;
                let px = u16::from_le_bytes([self.pixels[off], self.pixels[off + 1]]);
                let result = f(px);
                let bytes = result.to_le_bytes();
                self.pixels[off]     = bytes[0];
                self.pixels[off + 1] = bytes[1];
            }
        }
    }

    fn transparent_remap(&mut self, col_transparent: u16) {
        self.foreach_pixel_16(|px| {
            if px == col_transparent {
                0 // replace transparent colour with pure black (alpha=0)
            } else if px == 0 {
                TRANSLUCENT_BIT // pure black → translucent marker
            } else {
                px
            }
        });
    }

    fn swap_rb(&mut self) {
        // Pixel_RGB_BRG: swap red and blue components for PlayStation
        self.foreach_pixel_16(|px| {
            let r = (px >> 0) & 0x1F;
            let g = (px >> 5) & 0x1F;
            let b = (px >> 10) & 0x1F;
            let a = (px >> 15) & 1;
            (a << 15) | (r << 10) | (g << 5) | b
        });
    }

    fn force_translucent_pixels(&mut self) {
        self.foreach_pixel_16(|px| px | TRANSLUCENT_BIT);
    }

    fn check_for_transparent(&self) -> bool {
        assert_eq!(self.bitdepth, 16);
        for y in 0..self.height as usize {
            for x in 0..self.width as usize {
                let off = (y * self.buf_width as usize + x) * 2;
                let px = u16::from_le_bytes([self.pixels[off], self.pixels[off + 1]]);
                if px & TRANSLUCENT_BIT != 0 {
                    return true;
                }
            }
        }
        false
    }

    fn calculate_palette_info(&mut self, palette: Option<&[[u8; 4]]>, n_entries: usize, col_transparent: u16) {
        // n_entries: 0 for no palette, 16 or 256 for paletted
        if n_entries > 0 {
            let pal = palette.unwrap();
            if n_entries == 16 {
                self.start_colour = 0;
                self.end_colour = 15;
            } else {
                // 256: find actual used range
                let mut histogram = [0u32; 256];
                for &b in &self.pixels[..self.cb_row as usize * self.height as usize] {
                    histogram[b as usize] += 1;
                }
                self.start_colour = -1;
                self.end_colour = -1;
                for i in (0..n_entries as i32).rev() {
                    if histogram[i as usize] > 0 {
                        if self.end_colour == -1 { self.end_colour = i; }
                        self.start_colour = i;
                    }
                }
            }

            self.cmap_length = self.end_colour + 1;

            // Convert palette to BGR555
            self.converted_palette.clear();
            for i in 0..self.cmap_length as usize {
                let r = pal[i][0];
                let g = pal[i][1];
                let b = pal[i][2];
                let mut colour = br_colour_rgb_555(r, g, b);
                if col_transparent != 0 {
                    if colour == col_transparent {
                        colour = 0;
                    } else if colour == 0 {
                        colour = TRANSLUCENT_BIT;
                    }
                }
                self.converted_palette.push(colour);
            }
        } else {
            self.has_transparent = self.check_for_transparent();
        }
    }

    // ── Frame drawing ───────────────────────────────────────────────────────

    pub fn hline(&mut self, x: i32, y: i32, width: i32) {
        if width == 0 { return; }
        let row_off = y as usize * self.cb_row as usize + x as usize * 2;
        for i in 0..width as usize {
            self.pixels[row_off + i * 2]     = 0xFF;
            self.pixels[row_off + i * 2 + 1] = 0xFF;
        }
    }

    pub fn vline(&mut self, x: i32, y: i32, height: i32) {
        for yy in 0..height {
            let off = (y + yy) as usize * self.cb_row as usize + x as usize * 2;
            self.pixels[off]     = 0xFF;
            self.pixels[off + 1] = 0xFF;
        }
    }

    pub fn box_fill(&mut self, x: i32, y: i32, width: i32, height: i32) {
        for yy in 0..height {
            self.hline(x, y + yy, width);
        }
    }

    pub fn frame(&mut self, x1: i32, y1: i32, width: i32, height: i32) {
        let x2 = x1 + width - 1;
        let y2 = y1 + height - 1;
        self.hline(x1, y1, width);
        self.vline(x1, y1, height);
        self.hline(x1, y2, width);
        self.vline(x2, y1, height);
    }

    // ── Save TGA ────────────────────────────────────────────────────────────

    /// Write a 16-bit TGA file to `dir/filename`, optionally flipping vertically.
    /// After the pixel data, colour cycle data is appended (12 bytes each).
    pub fn save_tga(&self, dir: &str, filename: &str, flip_y: bool) {
        let path = format!("{}/{}", dir, filename);
        let f = match File::create(&path) {
            Ok(f) => f,
            Err(e) => {
                eprintln!("textile: error opening \"{}\": {}", path, e);
                std::process::exit(1);
            }
        };
        let mut w = BufWriter::new(f);

        // TGA header (18 bytes, pack-1)
        let header: [u8; 18] = [
            0,               // IDLength
            0,               // ColorMapType
            2,               // ImageType = uncompressed true-colour
            0, 0,            // CMapStart
            0, 0,            // CMapLength
            0,               // CMapDepth
            0, 0,            // XOffset
            0, 0,            // YOffset
            (self.width & 0xFF) as u8, ((self.width >> 8) & 0xFF) as u8,    // Width
            (self.height & 0xFF) as u8, ((self.height >> 8) & 0xFF) as u8,  // Height
            self.bitdepth as u8, // PixelDepth
            0,               // ImageDescriptor
        ];
        w.write_all(&header).unwrap();

        if flip_y {
            for y in 0..self.height as usize {
                let row_start = y * self.buf_width as usize * 2;
                let row_end   = row_start + self.width as usize * 2;
                w.write_all(&self.pixels[row_start..row_end]).unwrap();
            }
        } else {
            for y in (0..self.height as usize).rev() {
                let row_start = y * self.buf_width as usize * 2;
                let row_end   = row_start + self.width as usize * 2;
                w.write_all(&self.pixels[row_start..row_end]).unwrap();
            }
        }

        // Append colour cycle data (matches Bitmap::save in C++)
        for cc in &self.colour_cycles {
            let start = cc.start as i32;
            let end   = cc.end as i32;
            let speed = (cc.speed * 65536.0) as i32;
            w.write_all(&start.to_le_bytes()).unwrap();
            w.write_all(&end.to_le_bytes()).unwrap();
            w.write_all(&speed.to_le_bytes()).unwrap();
        }
    }

    // ── Atlas operations ────────────────────────────────────────────────────

    /// Check if `check_bm` (placed at x,y in self) matches the pixels there.
    fn same_bitmap(&self, x: i32, y: i32, check_bm: &Bitmap) -> bool {
        if self.colour_cycles.len() != check_bm.colour_cycles.len() {
            return false;
        }
        for (a, b) in self.colour_cycles.iter().zip(check_bm.colour_cycles.iter()) {
            if a != b { return false; }
        }

        assert_eq!(check_bm.bitdepth, 16);
        for yy in 0..check_bm.height as usize {
            let src_row = yy * check_bm.buf_width as usize * 2;
            let dst_row = (y as usize + yy) * self.buf_width as usize * 2 + x as usize * 2;
            let src = &check_bm.pixels[src_row..src_row + check_bm.width as usize * 2];
            let dst = &self.pixels[dst_row..dst_row + check_bm.width as usize * 2];
            if src != dst { return false; }
        }
        true
    }

    /// Search atlas for an existing copy of `bm`.  Returns (x,y) in pixel coords if found.
    pub fn find_existing(&self, bm: &Bitmap, am: &AllocationMap) -> Option<(i32, i32)> {
        let mut y = 0;
        while y <= self.height - bm.height {
            let mut x = 0;
            while x <= self.width - bm.width {
                if self.same_bitmap(x, y, bm) {
                    return Some((x, y));
                }
                x += am.x_align();
            }
            y += am.y_align();
        }
        None
    }

    /// Blit `src` into self at pixel position `(x_dest, y_dest)`.
    /// Handles both 16-bit and paletted (4/8-bit) source bitmaps.
    pub fn blit(&mut self, src: &Bitmap, x_dest: i32, y_dest: i32) {
        // Accumulate colour cycles from src
        for cc in &src.colour_cycles {
            self.colour_cycles.push(*cc);
        }

        for y in 0..src.height as usize {
            let dst_off = (y + y_dest as usize) * self.cb_row as usize + x_dest as usize * 2;
            let src_off = y * src.cb_row as usize;
            let nbytes  = src.cb_row as usize;
            self.pixels[dst_off..dst_off + nbytes]
                .copy_from_slice(&src.pixels[src_off..src_off + nbytes]);
        }
    }

    /// Pack `bm` into the atlas.  Tries deduplication first, then allocation.
    /// On success sets `bm.subx` / `bm.suby` and returns true.
    pub fn texture_fit(
        &mut self,
        bm: &mut Bitmap,
        am: &mut AllocationMap,
        room_name: &str,
        tex_type: &str,
        id: i32,
        cfg: &Config,
        log: &mut dyn io::Write,
        global_error: &mut bool,
    ) -> bool {
        // Deduplication: check if this texture already exists in the atlas
        if let Some((x, y)) = self.find_existing(bm, am) {
            bm.subx = x;
            bm.suby = y;
            return true;
        }

        match am.find(bm, id) {
            None => {
                let _ = write!(log,
                    "<p>TEXTILE error: couldn't fit {} &quot;{}&quot; in room &quot;{}&quot;</p>\n",
                    tex_type, bm.name, room_name);
                eprintln!("TEXTILE error: couldn't fit {} \"{}\" in room \"{}\"",
                    tex_type, bm.name, room_name);
                *global_error = true;
                false
            }
            Some((x_slot, y_slot)) => {
                let x_pix = x_slot * am.x_align() / am.k();
                let y_pix = y_slot * am.y_align();
                self.blit(bm, x_pix, y_pix);

                if cfg.frame || cfg.show_align {
                    let x1 = x_slot * am.x_align();
                    let y1 = y_slot * am.y_align();
                    if cfg.frame {
                        self.frame(x1, y1, bm.width, bm.height);
                    }
                    if cfg.show_align {
                        self.box_fill(
                            x1 + bm.width, y1,
                            round(bm.width, am.x_align()) - bm.width,
                            round(bm.height, am.y_align()) - bm.height,
                        );
                    }
                }

                bm.subx = x_slot * am.x_align() / (16 / 4);
                bm.suby = y_slot * am.y_align();
                true
            }
        }
    }

    /// Remove all colour cycle data (called before saving the texture atlas).
    pub fn remove_colour_cycles(&mut self) {
        self.colour_cycles.clear();
    }

    /// Shrink logical width/height (does not reallocate pixel buffer).
    pub fn crop(&mut self, width: i32, height: i32) {
        self.width  = width;
        self.height = height;
    }

    // ── Power-of-two validation ─────────────────────────────────────────────

    pub fn check_power_of2(&self, log: &mut dyn io::Write, global_error: &mut bool) -> bool {
        fn is_pow2(n: i32) -> bool {
            matches!(n, 16|32|64|128|256|512|1024)
        }
        let mut ok = true;
        let w_adj = self.width / (16 / self.bitdepth);
        if !is_pow2(w_adj) {
            let msg = format!(
                "TEXTILE error: Texture {}'s width is not an acceptable power of two ({}x{}x{}bit)",
                self.name, self.width, self.height, self.bitdepth);
            eprintln!("{}", msg);
            let _ = writeln!(log, "<p>{}</p>", msg);
            ok = false;
            *global_error = true;
        }
        if !is_pow2(self.height) {
            let msg = format!(
                "TEXTILE error: Texture {}'s height is not an acceptable power of two ({}x{}x{}bit)",
                self.name, self.width, self.height, self.bitdepth);
            eprintln!("{}", msg);
            let _ = writeln!(log, "<p>{}</p>", msg);
            ok = false;
            *global_error = true;
        }
        ok
    }

    // ── Load image (TGA / BMP / PNG via `image` crate) ──────────────────────

    pub fn load(path: &Path, cfg: &Config) -> Option<Self> {
        let name = path.to_string_lossy().into_owned();
        let img = image::open(path).map_err(|e| {
            eprintln!("textile: couldn't open \"{}\": {}", name, e);
        }).ok()?;
        let rgba = img.to_rgba8();
        let width  = rgba.width()  as i32;
        let height = rgba.height() as i32;
        let cb_row = width * 2;

        let mut pixels = Vec::with_capacity((height * cb_row) as usize);
        for pixel in rgba.pixels() {
            let [r, g, b, a] = pixel.0;
            pixels.extend_from_slice(&rgba_555(r, g, b, a).to_le_bytes());
        }

        let mut bm = Bitmap {
            pixels,
            width, height,
            bitdepth: 16,
            cb_row,
            buf_width: width, buf_height: height,
            name,
            converted_palette: Vec::new(),
            cmap_start: 0, cmap_length: 0,
            start_colour: 0, end_colour: 0,
            subx: -1, suby: -1,
            xpal: -1, ypal: -1, idx_pal: -1,
            colour_cycles: Vec::new(),
            has_transparent: false,
            power_of2: cfg.power_of2,
        };

        bm.transparent_remap(cfg.col_transparent);
        if cfg.target == TargetSystem::PlayStation { bm.swap_rb(); }
        bm.load_colour_cycles(cfg);
        if cfg.force_translucent { bm.force_translucent_pixels(); }

        Some(bm)
    }

    fn load_colour_cycles(&mut self, cfg: &Config) {
        if cfg.colour_cycle_file.is_empty() || self.name.is_empty() {
            return;
        }
        let ccf = &cfg.colour_cycle_file;
        let stem = crate::locfile::file_stem(&self.name).to_string();
        let n_cycles = profile::get_int(&stem, "nCycles", 0, ccf);
        for i in 0..n_cycles {
            let section = format!("{}:{}", stem, i);
            let start = profile::get_int(&section, "StartColour", -1, ccf);
            let end   = profile::get_int(&section, "EndColour",   -1, ccf);
            let speed_s = profile::get_string(&section, "Speed", "0.0", ccf);
            let speed: f32 = speed_s.trim().parse().unwrap_or(0.0);
            if start == -1 || end == -1 || speed == 0.0 {
                eprintln!("textile: incomplete colour cycle specification for {}", section);
                return;
            }
            self.colour_cycles.push(ColourCycle { start, end, speed });
        }
    }
}
