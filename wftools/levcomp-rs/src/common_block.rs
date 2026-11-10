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

    /// Like [`add`](Self::add), but a run is reused only when **every** byte
    /// matches. `add` ignores the last byte (iff2lvl's `memcmp(.., size-1)`),
    /// so a string whose length is 3 mod 4 has no padding to compare and can
    /// alias a longer one: `"Cat\0"` matches the start of `"Cats…"` (R8).
    /// `add` keeps that behaviour for the iff2lvl oracle; new data uses this.
    pub fn add_exact(&mut self, bytes: &[u8]) -> i32 {
        debug_assert_eq!(bytes.len() % 4, 0);
        if !bytes.is_empty() && self.data.len() >= bytes.len() {
            let mut off = 0;
            while off + bytes.len() <= self.data.len() {
                if &self.data[off..off + bytes.len()] == bytes {
                    return off as i32;
                }
                off += 4;
            }
        }
        let new_off = self.data.len();
        self.data.extend_from_slice(bytes);
        new_off as i32
    }

    pub fn bytes(&self) -> &[u8] {
        &self.data
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// R8: `"Cat"` must not resolve to the start of `"Cats"`.
    #[test]
    fn exact_add_does_not_alias_a_longer_string() {
        let mut legacy = CommonBlockBuilder::new();
        let cats = legacy.add(b"Cats\0\0\0\0");
        assert_eq!(legacy.add(b"Cat\0"), cats, "the legacy add aliases (kept for iff2lvl parity)");

        let mut common = CommonBlockBuilder::new();
        let cats = common.add_exact(b"Cats\0\0\0\0");
        let cat = common.add_exact(b"Cat\0");
        assert_ne!(cat, cats);
        assert_eq!(&common.bytes()[cat as usize..cat as usize + 4], b"Cat\0");
        assert_eq!(common.add_exact(b"Cat\0"), cat, "an exact match is still shared");
        assert_eq!(common.add_exact(b"Cats\0\0\0\0"), cats);
    }
}
