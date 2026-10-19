//! The level's shared common data area.
//!
//! Each per-object OAD COMMONBLOCK marker stores a 4-byte offset into this
//! area.  Multiple objects that serialize identical field values share the
//! same bytes — `add()` does a linear scan-and-dedupe on every insert, matching
//! `wftools/iff2lvl/level4.cc::AddCommonBlockData`.

pub struct CommonBlockBuilder {
    data: Vec<u8>,
}

impl CommonBlockBuilder {
    pub fn new() -> Self {
        Self { data: Vec::new() }
    }

    /// Append `bytes` to the common data area, or return the offset of an
    /// existing matching run if present.
    ///
    /// Matches iff2lvl's algorithm: step through `data` in 4-byte strides,
    /// compare the first `size - 1` bytes (last byte ignored, consistent with
    /// the C++ `memcmp(..., data, size-1)` call).  Returns the matching offset
    /// if found; otherwise appends and returns the old end-of-data.
    pub fn add(&mut self, bytes: &[u8]) -> i32 {
        if bytes.is_empty() {
            return self.data.len() as i32;
        }
        if bytes.len() >= 2 && self.data.len() >= bytes.len() {
            let stop = self.data.len() - bytes.len();
            let cmp_len = bytes.len() - 1;
            let mut off = 0;
            while off <= stop {
                if &self.data[off..off + cmp_len] == &bytes[..cmp_len] {
                    return off as i32;
                }
                off += 4;
            }
        }
        let new_off = self.data.len();
        self.data.extend_from_slice(bytes);
        // iff2lvl keeps the area 4-byte aligned implicitly because every
        // block added is itself 4-byte aligned.
        debug_assert_eq!(self.data.len() % 4, 0);
        new_off as i32
    }

    pub fn bytes(&self) -> &[u8] {
        &self.data
    }
}
