//! Asset ID registry — assigns `packedAssetID` values to referenced assets
//! and produces an `asset.inc` file consumed by `iffcomp-rs` via `iff.prp`.
//!
//! # Packed asset ID layout (from `wfsource/source/streams/asset.hp`)
//!
//! ```text
//! bits [31:24]  type   (8 bits)  — file extension code
//! bits [23:12]  room   (12 bits) — 0xFFF = permanent; 0..N = room N
//! bits [11:0]   index  (12 bits) — sequential, 1-based per (room, type)
//! ```
//!
//! # Asset types (from `wfsource/source/streams/assets.inc`)
//!
//! ```text
//! 0  NUL
//! 1  TGA
//! 2  BMP
//! 3  IFF
//! 4  _
//! 5  RUV
//! 6  WAV
//! 7  CYC
//! 8  CHR
//! 9  MAP
//! ```
//!
//! # Strategy
//!
//! IFF mesh assets are placed in the room their containing object lives in.
//! Objects with `MovesBetweenRooms=True` (or not contained in any room) are
//! placed in the permanent room (room = -1 → 0xFFF).  Indices are assigned in
//! first-seen order, starting at 1, separately per (room, type) pair.

use std::collections::HashMap;

pub const ROOM_PERM: i32 = -1;  // stored as 0xFFF in packed ID
pub const TYPE_IFF: i32  = 3;

pub struct AssetRegistry {
    /// (filename_original, packed_id) in registration order.
    entries: Vec<(String, i32)>,
    /// (filename_lowercase, room) → packed asset ID.
    by_name: HashMap<(String, i32), i32>,
    /// Next index per (room, type).  Key = (room as i32, type).
    next_index: HashMap<(i32, i32), i32>,
}

impl AssetRegistry {
    pub fn new() -> Self {
        Self {
            entries: Vec::new(),
            by_name: HashMap::new(),
            next_index: HashMap::new(),
        }
    }

    /// Register or look up an IFF mesh asset in a specific room slot.
    /// Returns the packed asset ID.
    pub fn add_iff_room(&mut self, filename: &str, room: i32) -> i32 {
        let key = (filename.to_ascii_lowercase(), room);
        if let Some(&id) = self.by_name.get(&key) {
            return id;
        }
        let id = pack(room, TYPE_IFF, self.next_index(room, TYPE_IFF));
        self.by_name.insert(key, id);
        self.entries.push((filename.to_string(), id));
        id
    }

    /// Register or look up an IFF mesh asset in the permanent slot.
    pub fn add_iff(&mut self, filename: &str) -> i32 {
        self.add_iff_room(filename, ROOM_PERM)
    }

    fn next_index(&mut self, room: i32, typ: i32) -> i32 {
        let idx = self.next_index.entry((room, typ)).or_insert(0);
        *idx += 1;
        *idx
    }

    /// Generate the `asset.inc` text for this level.
    ///
    /// Outputs a ROOM_START(Permanents,PERM) block followed by one
    /// ROOM_START(rmN,RMN) block per room that has mesh assets.
    pub fn asset_inc(&self, level_name: &str) -> String {
        let mut out = String::new();
        out.push_str("@*============================================================================\n");
        out.push_str("@* asset.inc: asset list for use with prep, created by levcomp-rs\n");
        out.push_str("@*============================================================================\n");
        out.push_str(&format!("FILE_HEADER({level_name},1,levcomp-rs)\n"));

        // PERM section
        out.push_str("ROOM_START(Permanents,PERM)\n");
        for (name, id) in &self.entries {
            if room_from_id(*id) == ROOM_PERM {
                out.push_str(&format!("\tROOM_ENTRY({name},{id:x})\n"));
            }
        }
        out.push_str("ROOM_END\n");

        // Per-room sections (RM0, RM1, …), in room-index order.
        let mut room_indices: Vec<i32> = self.entries.iter()
            .map(|(_, id)| room_from_id(*id))
            .filter(|&r| r != ROOM_PERM)
            .collect();
        room_indices.sort();
        room_indices.dedup();

        for ri in room_indices {
            let room_upper = format!("RM{ri}");
            let room_lower = format!("rm{ri}");
            out.push_str(&format!("ROOM_START({room_lower},{room_upper})\n"));
            for (name, id) in &self.entries {
                if room_from_id(*id) == ri {
                    out.push_str(&format!("\tROOM_ENTRY({name},{id:x})\n"));
                }
            }
            out.push_str("ROOM_END\n");
        }

        out.push_str("FILE_FOOTER\n");
        out
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }
}

/// Extract the room field from a packed asset ID.
/// Returns `ROOM_PERM` (-1) when room bits == 0xFFF.
fn room_from_id(id: i32) -> i32 {
    let room_bits = ((id as u32) >> 12) & 0xFFF;
    if room_bits == 0xFFF { ROOM_PERM } else { room_bits as i32 }
}

/// Pack `(room, type, index)` into a 32-bit `packedAssetID` integer.
///
/// ```text
/// room:  -1 → 0xFFF (12-bit two's complement); 0..N as-is
/// type:  shifted to bits [31:24]
/// room:  shifted to bits [23:12]
/// index: bits [11:0]
/// ```
pub fn pack(room: i32, typ: i32, index: i32) -> i32 {
    let room_bits = (room as u32) & 0xFFF;
    let type_bits = (typ as u32) & 0xFF;
    let idx_bits  = (index as u32) & 0xFFF;
    ((type_bits << 24) | (room_bits << 12) | idx_bits) as i32
}
