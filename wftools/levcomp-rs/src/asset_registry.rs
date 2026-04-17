//! Asset ID packing — port of `wftools/iff2lvl/asset.cc::AssignUniqueAssetID`.
//!
//! `packedAssetID` layout (32 bits, from `wfsource/source/streams/asset.hp`):
//!
//!   bits 31–24  type  (8 bits)  — extension index from `assets.inc`
//!   bits 23–12  room  (12 bits) — 0xFFF (-1) for permanents, 0..n for rooms
//!   bits 11–0   index (12 bits) — per-(room, type) counter, starts at 1
//!
//! Two-pass algorithm (mirrors iff2lvl `CreateAssetLST` + `PatchAssetIDsIntoOADs`):
//!
//!   Pass 1: walk all objects; for those with `MovesBetweenRooms=True` (or no
//!           field at all), register every Filename/MeshName asset as permanent
//!           (room = -1 / 0xFFF).
//!   Pass 2: walk rooms in order; for objects in each room with
//!           `MovesBetweenRooms=False`, register per-room assets.
//!
//! `asset.inc` output format (consumed by `wfsource/levels.src/iff.prp`):
//!
//!   FILE_HEADER(level, rooms, version)
//!   ROOM_START(Permanents, PERM)
//!       ROOM_ENTRY(house.iff, 03fff001)
//!   ROOM_END
//!   ROOM_START(Room0, RM0)
//!       ROOM_ENTRY(player.iff, 03000001)
//!   ROOM_END
//!   FILE_FOOTER

use std::collections::HashMap;

use crate::lev_parser::{field_data, LevObject};
use crate::rooms::Room;

/// Extension type index — must match `wfsource/source/streams/assets.inc` order.
fn ext_type(name: &str) -> Option<i32> {
    let ext = name.to_lowercase();
    let ext = ext.rsplit('.').next().unwrap_or("");
    match ext {
        "tga" => Some(1),
        "bmp" => Some(2),
        "iff" => Some(3),
        "ruv" => Some(5),
        "wav" => Some(6),
        "cyc" => Some(7),
        "chr" => Some(8),
        "map" => Some(9),
        _     => None,
    }
}

fn pack_asset_id(room: i32, typ: i32, index: i32) -> i32 {
    // type:8 at bits [31:24], room:12 at bits [23:12], index:12 at bits [11:0]
    (((room  as u32) << 12) & 0x00FFF000) as i32
        | (((typ   as u32) << 24) & 0xFF000000_u32) as i32
        | ((index  as u32)         & 0x00000FFF) as i32
}

pub struct AssetRegistry {
    /// Fast lookup: (room, lowercase_name) → packed_id.  room = -1 for permanents.
    lookup: HashMap<(i32, String), i32>,
    /// Ordered entries for asset.inc: first permanents, then room 0, room 1, …
    perm_entries: Vec<(String, i32)>,
    room_entries: Vec<Vec<(String, i32)>>,
    num_rooms: usize,
}

impl AssetRegistry {
    /// Build the registry for `objects` sorted into `rooms`.
    /// `room_of_obj[i]` = index into `rooms` for objects[i], or None if that
    /// object is a room object itself.
    pub fn build(objects: &[LevObject], rooms: &[Room]) -> Self {
        let num_rooms = rooms.len();
        let mut lookup: HashMap<(i32, String), i32> = HashMap::new();
        let mut perm_counters: HashMap<i32, i32> = HashMap::new();
        let mut room_counters: HashMap<(usize, i32), i32> = HashMap::new();
        let mut perm_entries: Vec<(String, i32)> = Vec::new();
        let mut room_entries: Vec<Vec<(String, i32)>> = vec![Vec::new(); num_rooms];

        // Pass 1: permanent objects (MovesBetweenRooms = True or field absent).
        for obj in objects {
            if !moves_between_rooms(obj) {
                continue;  // room-specific; handled in pass 2
            }
            for name in mesh_asset_names(obj) {
                let key = (-1_i32, name.clone());
                if lookup.contains_key(&key) { continue; }
                let Some(typ) = ext_type(&name) else { continue };
                let idx = perm_counters.entry(typ).or_insert(0);
                *idx += 1;
                let id = pack_asset_id(-1, typ, *idx);
                lookup.insert(key, id);
                perm_entries.push((name, id));
            }
        }

        // Pass 2: room-specific objects (MovesBetweenRooms = False), in room order.
        for (ri, room) in rooms.iter().enumerate() {
            for &obj_slot in &room.entries {
                let obj_idx = (obj_slot as usize) - 1;  // slot is 1-based
                let obj = &objects[obj_idx];
                if moves_between_rooms(obj) { continue; }
                for name in mesh_asset_names(obj) {
                    // Already registered as permanent?
                    if lookup.contains_key(&(-1, name.clone())) { continue; }
                    let key = (ri as i32, name.clone());
                    if lookup.contains_key(&key) { continue; }
                    let Some(typ) = ext_type(&name) else { continue };
                    let idx = room_counters.entry((ri, typ)).or_insert(0);
                    *idx += 1;
                    let id = pack_asset_id(ri as i32, typ, *idx);
                    lookup.insert(key, id);
                    room_entries[ri].push((name, id));
                }
            }
        }

        // Also scan objects not in any room (room_of_obj[i] = None means room object;
        // room_of_obj[i] = Some(r) means it's in room r — handled above).
        // Objects that are room objects themselves have no Filename assets to register.

        Self { lookup, perm_entries, room_entries, num_rooms }
    }

    /// Look up the packed asset ID for `name` on an object.
    ///
    /// `is_perm`: object has MovesBetweenRooms=True (or field absent).
    /// `room`: room index (0-based) for non-permanent objects.
    ///
    /// Returns 0 if not found (matches iff2lvl behaviour for unresolvable assets).
    pub fn lookup(&self, name: &str, is_perm: bool, room: Option<usize>) -> i32 {
        let lower = name.to_lowercase();
        // Always check permanents first (mirrors PatchAssetIDsIntoOADs).
        if let Some(&id) = self.lookup.get(&(-1, lower.clone())) {
            return id;
        }
        if !is_perm {
            if let Some(r) = room {
                if let Some(&id) = self.lookup.get(&(r as i32, lower)) {
                    return id;
                }
            }
        }
        0
    }

    /// Emit `asset.inc` content for use with `wfsource/levels.src/iff.prp`.
    pub fn write_asset_inc(&self, level_name: &str, version: i32) -> String {
        let mut out = String::new();
        out.push_str(&format!(
            "@*============================================================================\n\
             @* asset.inc: asset list for use with prep, created by levcomp v{version}, DO NOT MODIFY\n\
             @*============================================================================\n\
             FILE_HEADER({level_name},{},{version})\n",
            self.num_rooms,
        ));
        out.push_str("ROOM_START(Permanents,PERM)\n");
        for (name, id) in &self.perm_entries {
            out.push_str(&format!("\tROOM_ENTRY({name},{id:07x})\n"));
        }
        out.push_str("ROOM_END\n");
        for (ri, entries) in self.room_entries.iter().enumerate() {
            out.push_str(&format!("ROOM_START(Room{ri},RM{ri})\n"));
            for (name, id) in entries {
                out.push_str(&format!("\tROOM_ENTRY({name},{id:07x})\n"));
            }
            out.push_str("ROOM_END\n");
        }
        out.push_str("FILE_FOOTER\n");
        out
    }
}

/// Return true if the object's assets go into PERM (i.e. MovesBetweenRooms=True
/// or the field is absent — same logic as iff2lvl `CreateAssetLST`).
pub fn moves_between_rooms(obj: &LevObject) -> bool {
    let Some(chunk) = obj.find_field("Moves Between Rooms") else {
        return true;  // field absent → treat as permanent
    };
    let data = field_data(chunk);
    if data.len() >= 4 {
        i32::from_le_bytes(data[..4].try_into().unwrap()) != 0
    } else if data.len() >= 2 {
        i16::from_le_bytes(data[..2].try_into().unwrap()) != 0
    } else {
        true  // no data → treat as permanent
    }
}

/// Collect all Filename/MeshName field values from an object (lowercased).
/// Identifies asset fields by scanning for string values with known extensions.
fn mesh_asset_names(obj: &LevObject) -> Vec<String> {
    let mut names = Vec::new();
    for chunk in &obj.fields {
        let value = crate::lev_parser::field_str_value(chunk);
        if !value.is_empty() && ext_type(&value).is_some() {
            let lower = value.to_lowercase();
            if !names.contains(&lower) {
                names.push(lower);
            }
        }
    }
    names
}
