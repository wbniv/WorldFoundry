//! Write a flat binary `.lvl` file (_LevelOnDisk + object array).
//!
//! File layout (matches what `wftools/iff2lvl` produces and what
//! `wftools/lvldump-rs` expects):
//!
//! ```text
//! _LevelOnDisk header            52 bytes
//! int32 objectsOffsets[N]        4·N bytes
//! _ObjectOnDisk + OAD data       variable per object, 4-byte aligned
//! int32 pathsOffsets[P]          (MVP: empty)
//! int32 channelsOffsets[C]       (MVP: empty)
//! int32 roomsOffsets[R]          (MVP: empty)
//! common data block              (MVP: empty)
//! ```
//!
//! MVP: objects only (no paths/channels/rooms/common block), OADSize = 0.

use crate::common_block::CommonBlockBuilder;
use crate::lc_parser::ClassMap;
use crate::lev_parser::LevObject;
use crate::oad_loader::{per_object_size, serialize_oad_data, OadSchemas};
use crate::rooms;

pub const LEVEL_VERSION: i32 = 28;

/// `_ObjectOnDisk` header size with natural field alignment (GNUALIGN).
///
/// Verified against snowgoons.iff's LVL chunk extracted from cd.iff:
/// obj[1]→obj[2] spacing is 96 bytes with OADSize=28, i.e. 68 + align4(28) = 96.
///
///   0: type (i16)
///   2: pad  (2 bytes so next i32 aligns)
///   4: x, y, z (i32×3)                         — 12 bytes
///  16: x_scale, y_scale, z_scale (i32×3)       — 12 bytes
///  28: rotation a, b, c (u16×3), order (u8), pad  — 8 bytes (wf_euler aligned(4))
///  36: bbox minX..maxZ (i32×6)                 — 24 bytes
///  60: oadFlags (i32)
///  64: pathIndex (i16)
///  66: OADSize  (i16)
///  68: — end of header —
const OBJ_HEADER_SIZE: usize = 68;

#[inline]
fn align4(n: usize) -> usize { (n + 3) & !3 }

pub struct LevelPlan<'a> {
    pub objects: &'a [LevObject],
    pub classes: &'a ClassMap,
    pub schemas: &'a OadSchemas,
}

pub fn write(plan: &LevelPlan) -> Result<Vec<u8>, String> {
    // Object count includes the NULL_Object placeholder at index 0.
    let total_objects = plan.objects.len() + 1;

    // Per-object size = align4(OBJ_HEADER_SIZE + oad_size).  NULL_Object always
    // has oad_size=0; real objects look their size up from the OAD schema.
    let mut obj_sizes = Vec::with_capacity(total_objects);
    let mut obj_oad_sizes = Vec::with_capacity(total_objects);
    obj_sizes.push(align4(OBJ_HEADER_SIZE));
    obj_oad_sizes.push(0usize);
    for obj in plan.objects {
        let oad_size = plan
            .schemas
            .get(&obj.class_name)
            .map(per_object_size)
            .unwrap_or(0);
        obj_oad_sizes.push(oad_size);
        obj_sizes.push(align4(OBJ_HEADER_SIZE + oad_size));
    }
    let objects_total: usize = obj_sizes.iter().sum();

    // Pre-build the per-object OAD payloads so we know the final common data
    // length before writing the header (the header carries commonDataOffset
    // and commonDataLength).  Building in-order mirrors iff2lvl's Save flow.
    let mut common = CommonBlockBuilder::new();
    let mut oad_payloads: Vec<Vec<u8>> = Vec::with_capacity(total_objects);
    oad_payloads.push(Vec::new());  // NULL_Object: empty payload
    for obj in plan.objects {
        let payload = plan
            .schemas
            .get(&obj.class_name)
            .map(|s| serialize_oad_data(s, obj, &mut common))
            .unwrap_or_default();
        oad_payloads.push(payload);
    }

    // Rooms: sort non-room objects into rooms by bbox-center containment.
    let room_list = rooms::sort(plan.objects, plan.schemas);
    let room_sizes: Vec<usize> = room_list.iter().map(|r| r.byte_size()).collect();
    let rooms_total: usize = room_sizes.iter().sum();

    let header_size   = 52;
    let objects_off   = header_size;
    let array_bytes   = 4 * total_objects;

    let paths_off    = objects_off + array_bytes + objects_total;
    let channels_off = paths_off;    // empty paths section
    let rooms_off    = channels_off; // empty channels section
    let rooms_array  = 4 * room_list.len();
    let common_off   = rooms_off + rooms_array + rooms_total;
    let common_len   = common.bytes().len();

    let mut out = Vec::with_capacity(common_off + common_len);

    // ── header ───────────────────────────────────────────────────────────────
    push_i32(&mut out, LEVEL_VERSION);
    push_i32(&mut out, total_objects as i32);
    push_i32(&mut out, objects_off as i32);
    push_i32(&mut out, 0);                     // pathCount
    push_i32(&mut out, paths_off as i32);
    push_i32(&mut out, 0);                     // channelCount
    push_i32(&mut out, channels_off as i32);
    push_i32(&mut out, 0);                     // lightCount
    push_i32(&mut out, 0);                     // lightsOffset
    push_i32(&mut out, room_list.len() as i32);
    push_i32(&mut out, rooms_off as i32);
    push_i32(&mut out, common_len as i32);
    push_i32(&mut out, common_off as i32);
    debug_assert_eq!(out.len(), header_size);

    // ── object offset array ──────────────────────────────────────────────────
    let mut cursor = objects_off + array_bytes;
    for sz in &obj_sizes {
        push_i32(&mut out, cursor as i32);
        cursor += sz;
    }

    // ── objects ──────────────────────────────────────────────────────────────
    // index 0: NULL_Object (type=1, scale=0, unit-cube bbox, pathIndex=-1).
    // iff2lvl's QLevel constructor passes scale=Point3(0,0,0) and
    // collision=QColBox(Point3(0,0,0), Point3(1,1,1)).
    const ONE: i32 = 0x10000;
    let start = out.len();
    write_obj_header(
        &mut out, 1,
        (0, 0, 0), (0, 0, 0), (0, 0, 0),
        &[0, 0, 0, ONE, ONE, ONE],
        0, -1, 0,
    );
    pad_section(&mut out, start, obj_sizes[0]);

    for (i, obj) in plan.objects.iter().enumerate() {
        let type_idx = plan
            .classes
            .index_of(&obj.class_name)
            .ok_or_else(|| format!("object '{}': unknown class '{}'", obj.name, obj.class_name))?
            as i16;
        let oad_size = obj_oad_sizes[i + 1] as i16;

        // .lev rotations are fixed32 radians; iff2lvl stores them divided by 2π
        // (i.e. in revolutions) as the low 16 bits of the resulting fixed32.
        // Ref: wftools/iff2lvl/object.cc:109 — `WF_FLOAT_TO_SCALAR(rot.a / (2*PI))`.
        let rot = (radians_fx_to_u16_revs(obj.rotation.a),
                   radians_fx_to_u16_revs(obj.rotation.b),
                   radians_fx_to_u16_revs(obj.rotation.c));
        let bbox = [
            obj.bbox.min[0], obj.bbox.min[1], obj.bbox.min[2],
            obj.bbox.max[0], obj.bbox.max[1], obj.bbox.max[2],
        ];

        let start = out.len();
        write_obj_header(
            &mut out,
            type_idx,
            (obj.position.x, obj.position.y, obj.position.z),
            (ONE, ONE, ONE),
            rot,
            &bbox,
            /* oad_flags  */ 0,
            /* path_index */ -1,
            oad_size,
        );
        // Per-object OAD payload: fields outside any COMMONBLOCK carry real
        // values from the .lev sub-chunks; COMMONBLOCK markers carry the
        // offset returned by the CommonBlockBuilder for the section's bytes.
        let payload = &oad_payloads[i + 1];
        debug_assert_eq!(payload.len(), oad_size as usize,
            "serialized OAD payload ({}) != computed size ({})",
            payload.len(), oad_size);
        out.extend_from_slice(payload);
        pad_section(&mut out, start, obj_sizes[i + 1]);
    }

    // No paths or channels in MVP (offsets point at empty regions).

    // Rooms: offset array, then packed records.
    debug_assert_eq!(out.len(), rooms_off);
    let mut room_cursor = rooms_off + rooms_array;
    for sz in &room_sizes {
        push_i32(&mut out, room_cursor as i32);
        room_cursor += sz;
    }
    for room in &room_list {
        let start = out.len();
        room.write(&mut out);
        debug_assert_eq!(out.len() - start, room.byte_size());
    }

    // Common data area sits at the end.
    debug_assert_eq!(out.len(), common_off);
    out.extend_from_slice(common.bytes());
    debug_assert_eq!(out.len(), common_off + common_len);
    Ok(out)
}

fn write_obj_header(
    out: &mut Vec<u8>,
    type_idx: i16,
    pos: (i32, i32, i32),
    scale: (i32, i32, i32),
    rot: (u16, u16, u16),
    bbox: &[i32; 6],
    oad_flags: i32,
    path_index: i16,
    oad_size: i16,
) {
    out.extend_from_slice(&type_idx.to_le_bytes());
    out.extend_from_slice(&[0u8; 2]);                    // pad for i32 alignment
    push_i32(out, pos.0);
    push_i32(out, pos.1);
    push_i32(out, pos.2);
    push_i32(out, scale.0);
    push_i32(out, scale.1);
    push_i32(out, scale.2);
    // rotation: a, b, c (u16 each), order (u8) + 1 byte pad = 8 bytes total.
    // iff2lvl's Euler default constructor sets order = 0xFE (see euler.hp).
    out.extend_from_slice(&rot.0.to_le_bytes());
    out.extend_from_slice(&rot.1.to_le_bytes());
    out.extend_from_slice(&rot.2.to_le_bytes());
    out.push(0xFEu8);                                    // order
    out.push(0u8);                                       // pad (wf_euler aligned(4))
    // coarse bbox
    for v in bbox { push_i32(out, *v); }
    push_i32(out, oad_flags);
    out.extend_from_slice(&path_index.to_le_bytes());
    out.extend_from_slice(&oad_size.to_le_bytes());
}

fn push_i32(out: &mut Vec<u8>, v: i32) {
    out.extend_from_slice(&v.to_le_bytes());
}

/// Convert fixed32 radians (as stored in a `.lev` EULR DATA) to the u16
/// representation iff2lvl writes: the low 16 bits of `fixed32(radians / 2π)`.
///
/// iff2lvl uses `WF_FLOAT_TO_SCALAR` which truncates toward zero (C cast from
/// float to int32), so match that rather than rounding.
fn radians_fx_to_u16_revs(fx: i32) -> u16 {
    const TWO_PI: f64 = std::f64::consts::TAU;
    let revs = (fx as f64 / 65536.0) / TWO_PI;  // radians → revolutions (float)
    let revs_fx = (revs * 65536.0) as i32;      // truncate toward zero
    (revs_fx as u32 & 0xffff) as u16
}

/// Pad `out` with zeros until it reaches `start + target_len`.
fn pad_section(out: &mut Vec<u8>, start: usize, target_len: usize) {
    while out.len() < start + target_len {
        out.push(0);
    }
}
