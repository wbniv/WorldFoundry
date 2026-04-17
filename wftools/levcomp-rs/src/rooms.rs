//! Room section: identifies "room" objects in the level and sorts every
//! other object into a room by bbox-center containment.  Port of
//! `wftools/iff2lvl/level3.cc::SortIntoRooms` + `wftools/iff2lvl/room.cc`.
//!
//! Binary layout of each `_RoomOnDisk` (from `wfsource/source/oas/levelcon.h`):
//!
//! ```text
//!  0: int32  count                     — number of objects in this room
//!  4: i32×6  boundingBox (fixed32)     — room's world-space AABB
//! 28: i16×2  adjacentRooms             — ADJACENT_ROOM_NULL (-1) in MVP
//! 32: i16    roomObjectIndex           — index of the room object in the
//!                                        level's object list
//! 34: i16 * count                      — object indices (one per entry)
//! --  padding to 4-byte boundary
//! ```

use wf_oad::ButtonType;

use crate::lev_parser::LevObject;
use crate::oad_loader::OadSchemas;

pub const ADJACENT_ROOM_NULL: i16 = -1;
pub const ROOM_HEADER_SIZE: usize = 34;

/// A room: the room object's index in the level list + an ordered list of
/// contained object indices.
pub struct Room {
    /// Bounding box in world space: (minX, minY, minZ, maxX, maxY, maxZ).
    pub bbox: [i32; 6],
    /// Index of the room object itself in the level's object list (1-based
    /// because slot 0 is NULL_Object).
    pub room_object_index: i16,
    /// Indices of contained objects (excluding the room object itself).
    pub entries: Vec<i16>,
    /// Resolved adjacent-room indices (into the rooms array), or
    /// `ADJACENT_ROOM_NULL` when absent.
    pub adjacent_rooms: [i16; 2],
}

impl Room {
    pub fn byte_size(&self) -> usize {
        let raw = ROOM_HEADER_SIZE + 2 * self.entries.len();
        (raw + 3) & !3  // pad to 4-byte boundary
    }

    pub fn write(&self, out: &mut Vec<u8>) {
        let start = out.len();
        out.extend_from_slice(&(self.entries.len() as i32).to_le_bytes());
        for &v in &self.bbox { out.extend_from_slice(&v.to_le_bytes()); }
        out.extend_from_slice(&self.adjacent_rooms[0].to_le_bytes());
        out.extend_from_slice(&self.adjacent_rooms[1].to_le_bytes());
        out.extend_from_slice(&self.room_object_index.to_le_bytes());
        for &e in &self.entries {
            out.extend_from_slice(&e.to_le_bytes());
        }
        while (out.len() - start) % 4 != 0 { out.push(0); }
    }
}

/// Return true if `class_name` is a "room" class — its OAD schema has a
/// `LEVELCONFLAG_ROOM` entry.  Falls back to a name match when no schema is
/// available (snowgoons always has the schema loaded).
pub fn is_room_class(class_name: &str, schemas: &OadSchemas) -> bool {
    if let Some(schema) = schemas.get(class_name) {
        schema.entries.iter().any(|e| e.button_type == ButtonType::Room)
    } else {
        class_name.eq_ignore_ascii_case("room")
    }
}

/// Sort level objects into rooms.  Follows iff2lvl's SortIntoRooms +
/// QRoom::Save's adjacent-room resolution.
///
/// - For each object whose class has LEVELCONFLAG_ROOM, create a room with
///   its world-space bounding box (object.position + object.bbox).
/// - For every other object (not itself a room), add it to the first room
///   whose bbox contains its world-space *center*.
/// - Resolve each room's "Adjacent Room 1/2" OAD fields: look up the named
///   room object, translate its *object index* into a *room index* (index
///   into the rooms vector), store in adjacentRooms[0/1].  This is load-
///   bearing: the active-room system keeps adjacent rooms' objects on the
///   update list even while the player is elsewhere — without it, the camera
///   in one room stops ticking when the player is in another.
/// - If no rooms are found, create one giant fallback room containing every
///   object (mirrors iff2lvl's default-room path).
pub fn sort(objects: &[LevObject], schemas: &OadSchemas) -> Vec<Room> {
    let mut rooms: Vec<Room> = Vec::new();
    let mut room_of_obj: Vec<i16> = Vec::new();  // parallel to objects: which room slot

    // Pass 1 — identify rooms and compute their world-space bboxes.
    // Index i in `objects` corresponds to obj[i+1] in the level (slot 0 is NULL).
    for (i, obj) in objects.iter().enumerate() {
        if is_room_class(&obj.class_name, schemas) {
            let wb = world_bbox(obj);
            rooms.push(Room {
                bbox: wb,
                room_object_index: (i + 1) as i16,
                entries: Vec::new(),
                adjacent_rooms: [ADJACENT_ROOM_NULL; 2],
            });
            room_of_obj.push(-1);  // rooms themselves are not entries
        } else {
            room_of_obj.push(-2);  // unassigned marker
        }
    }

    // Pass 1.5 — resolve adjacent-room references for each room object.
    let mut adjacencies: Vec<[i16; 2]> = vec![[ADJACENT_ROOM_NULL; 2]; rooms.len()];
    for (ri, room) in rooms.iter().enumerate() {
        let room_obj = &objects[(room.room_object_index as usize) - 1];
        for (slot, field_name) in ["Adjacent Room 1", "Adjacent Room 2"].iter().enumerate() {
            let Some(chunk) = room_obj.find_field(field_name) else { continue };
            let target_name = crate::lev_parser::field_str_value(chunk);
            if target_name.is_empty() { continue; }
            // Find the target object by name, then find the room whose
            // room_object_index points at that object.
            if let Some((target_obj_i, _)) =
                objects.iter().enumerate().find(|(_, o)| o.name == target_name)
            {
                let target_obj_idx = (target_obj_i + 1) as i16;
                if let Some((target_room_idx, _)) = rooms.iter().enumerate()
                    .find(|(_, r)| r.room_object_index == target_obj_idx)
                {
                    adjacencies[ri][slot] = target_room_idx as i16;
                }
            }
        }
    }
    for (ri, room) in rooms.iter_mut().enumerate() {
        // Stash the resolved adjacencies; the Room struct currently has no
        // field for them, so emit via adjacentRooms in `write()` below.  We
        // extend Room to carry them explicitly.
        room.adjacent_rooms = adjacencies[ri];
    }

    // Pass 2 — sort every non-room object into the first room containing its
    // world-space center point.
    for (i, obj) in objects.iter().enumerate() {
        if room_of_obj[i] != -2 { continue; }  // already a room

        let center = obj_center(obj);
        for (r, room) in rooms.iter_mut().enumerate() {
            if point_in_box(center, room.bbox) {
                room.entries.push((i + 1) as i16);
                room_of_obj[i] = r as i16;
                break;
            }
        }
    }

    // Fallback — if no rooms were found in the .lev, emit one giant room
    // holding every object (matches iff2lvl's default-room behaviour).
    if rooms.is_empty() {
        let huge: i32 = 32767 * 65536;  // Point3(32767,...) in fixed32
        let mut fallback = Room {
            bbox: [-huge, -huge, -huge, huge, huge, huge],
            room_object_index: 0,
            entries: Vec::new(),
            adjacent_rooms: [ADJACENT_ROOM_NULL; 2],
        };
        for i in 0..objects.len() {
            fallback.entries.push((i + 1) as i16);
        }
        rooms.push(fallback);
    }

    rooms
}

/// Object world-space bbox = position + local bbox.
fn world_bbox(obj: &LevObject) -> [i32; 6] {
    [
        obj.position.x + obj.bbox.min[0],
        obj.position.y + obj.bbox.min[1],
        obj.position.z + obj.bbox.min[2],
        obj.position.x + obj.bbox.max[0],
        obj.position.y + obj.bbox.max[1],
        obj.position.z + obj.bbox.max[2],
    ]
}

/// Object world-space center — matches `QRoom::InsideCheck` in iff2lvl:
/// center = position + (bbox.min + bbox.max) / 2
fn obj_center(obj: &LevObject) -> [i32; 3] {
    [
        obj.position.x + (obj.bbox.min[0] + obj.bbox.max[0]) / 2,
        obj.position.y + (obj.bbox.min[1] + obj.bbox.max[1]) / 2,
        obj.position.z + (obj.bbox.min[2] + obj.bbox.max[2]) / 2,
    ]
}

/// AABB containment test: `[min.x, min.y, min.z, max.x, max.y, max.z]`.
fn point_in_box(p: [i32; 3], b: [i32; 6]) -> bool {
    p[0] >= b[0] && p[0] <= b[3]
        && p[1] >= b[1] && p[1] <= b[4]
        && p[2] >= b[2] && p[2] <= b[5]
}
