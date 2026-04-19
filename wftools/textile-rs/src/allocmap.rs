// allocmap.rs — 2D texture atlas bin-packing (port of allocmap.cc / allocmap.hp)

use std::io::Write;

use crate::bitmap::Bitmap;

pub struct AllocationRestrictions {
    pub width:                  i32,
    pub height:                 i32,
    pub x_align:                i32,
    pub y_align:                i32,
    pub align_to_size_multiple: bool,
    pub k:                      i32,
}

const UNALLOCATED: i32 = -1;

pub struct AllocationMap {
    table:                  Vec<i32>,  // x_slots * y_slots grid of allocation IDs
    x_slots:                i32,
    y_slots:                i32,
    x_align:                i32,
    y_align:                i32,
    align_to_size_multiple: bool,
    k:                      i32,
    x_max_allocated:        i32,
    y_max_allocated:        i32,
}

impl AllocationMap {
    pub fn new(ar: &AllocationRestrictions) -> Self {
        assert!(ar.width > 0);
        assert!(ar.height > 0);
        let size = (ar.width * ar.height) as usize;
        let mut am = AllocationMap {
            table:                  vec![UNALLOCATED; size],
            x_slots:                ar.width,
            y_slots:                ar.height,
            x_align:                ar.x_align,
            y_align:                ar.y_align,
            align_to_size_multiple: ar.align_to_size_multiple,
            k:                      ar.k,
            x_max_allocated:        0,
            y_max_allocated:        0,
        };
        am.reset();
        am
    }

    pub fn reset(&mut self) {
        for v in self.table.iter_mut() {
            *v = UNALLOCATED;
        }
        self.x_max_allocated = 0;
        self.y_max_allocated = 0;
    }

    pub fn x_extent(&self) -> i32 { self.x_max_allocated + 1 }
    pub fn y_extent(&self) -> i32 { self.y_max_allocated + 1 }
    pub fn x_align(&self) -> i32  { self.x_align }
    pub fn y_align(&self) -> i32  { self.y_align }
    pub fn k(&self) -> i32        { self.k }

    fn check_if_fits(&self, x: i32, y: i32, src_w: i32, src_h: i32, src_bm: &Bitmap) -> bool {
        if src_w + x > self.x_slots { return false; }
        if src_h + y > self.y_slots { return false; }

        // align-to-size wants the placement origin to land on texture-sized
        // boundaries. `x` / `y` are in SLOTS (x_align_slots wide, y_align
        // tall), so the modulus must use the slot-space width/height
        // (src_w / src_h) — NOT src_bm.width/height, which are pixel
        // counts. That unit-mismatch rejected most placements and caused
        // "couldn't fit" errors for textures that had plenty of room.
        let _ = src_bm; // kept on the signature for future bpp-aware checks
        if self.align_to_size_multiple && (x % src_w != 0) { return false; }
        if self.align_to_size_multiple && (y % src_h != 0) { return false; }

        for yy in y..y + src_h {
            for xx in x..x + src_w {
                if self.table[(yy * self.x_slots + xx) as usize] != UNALLOCATED {
                    return false;
                }
            }
        }
        true
    }

    fn mark(&mut self, x: i32, y: i32, src_w: i32, src_h: i32, id: i32) {
        for ya in 0..src_h {
            for xa in 0..src_w {
                let xx = x + xa;
                let yy = y + ya;
                assert!(xx < self.x_slots);
                assert!(yy < self.y_slots);
                self.table[(yy * self.x_slots + xx) as usize] = id;
                if xx > self.x_max_allocated { self.x_max_allocated = xx; }
                if yy > self.y_max_allocated { self.y_max_allocated = yy; }
            }
        }
    }

    /// Find a free slot for `src_bm` and mark it.  Returns (x_slot, y_slot) or None.
    pub fn find(&mut self, src_bm: &Bitmap, id: i32) -> Option<(i32, i32)> {
        let x_adj = round(src_bm.width, self.x_align);
        let y_adj = round(src_bm.height, self.y_align);

        // slots needed: bitdepth/4 slots per x_align-sized x unit; 1 slot per y_align-sized y unit
        let src_w = (x_adj / self.x_align) * (src_bm.bitdepth / (16 / 4));
        let src_h = y_adj / self.y_align;

        let x_step = 16 / src_bm.bitdepth; // 1 for 16-bit, 2 for 8-bit, 4 for 4-bit

        for y in 0..self.y_slots {
            let mut x = 0;
            while x < self.x_slots {
                if self.check_if_fits(x, y, src_w, src_h, src_bm) {
                    self.mark(x, y, src_w, src_h, id);
                    return Some((x, y));
                }
                x += x_step;
            }
        }
        None
    }

    pub fn print_to(&self, out: &mut dyn Write) {
        let _ = writeln!(out, "<pre>");
        for y in 0..self.y_extent() {
            for x in 0..self.x_extent() {
                let v = self.table[(y * self.x_slots + x) as usize];
                if v == UNALLOCATED {
                    let _ = write!(out, ".");
                } else if v & 0x8000 != 0 {
                    let _ = write!(out, "*");
                } else {
                    let _ = write!(out, "{}", char::from_digit((v as u32) % 36, 36).unwrap_or('?'));
                }
            }
            let _ = writeln!(out);
        }
        let _ = writeln!(out, "</pre>");
    }
}

pub fn round(n: i32, align: i32) -> i32 {
    ((n + align - 1) / align) * align
}
