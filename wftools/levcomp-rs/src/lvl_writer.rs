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

use crate::asset_registry::{AssetRegistry, ROOM_PERM};
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
    /// Pre-computed mesh bboxes, parallel to `objects`.  `None` means no mesh
    /// file was found for that object (no Mesh Name field or file absent).
    pub mesh_bboxes: &'a [Option<[i32; 6]>],
    /// Asset registry — populated during OAD serialization; caller reads it
    /// after `write()` to emit `asset.inc`.
    pub assets: &'a mut AssetRegistry,
}

pub fn write(plan: &mut LevelPlan) -> Result<Vec<u8>, String> {
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

    // Rooms first — needed to determine per-object asset room assignment
    // before OAD serialization.
    let room_list = rooms::sort(plan.objects, plan.schemas);

    // Per-object asset room: PERM for objects with MovesBetweenRooms=True (or
    // not contained in any room); room index N for others.
    let obj_asset_room: Vec<i32> = {
        let mut obj_to_room = vec![-1i32; plan.objects.len()];
        for (ri, room) in room_list.iter().enumerate() {
            for &oi in &room.entries {
                obj_to_room[(oi as usize) - 1] = ri as i32;
            }
        }
        plan.objects.iter().enumerate().map(|(i, obj)| {
            if moves_between_rooms(obj) || obj_to_room[i] < 0 {
                ROOM_PERM
            } else {
                obj_to_room[i]
            }
        }).collect()
    };

    // Pre-build the per-object OAD payloads so we know the final common data
    // length before writing the header (the header carries commonDataOffset
    // and commonDataLength).  Building in-order mirrors iff2lvl's Save flow.
    let mut common = CommonBlockBuilder::new();
    let name_to_idx = crate::lev_parser::name_to_index(plan.objects);
    let mut oad_payloads: Vec<Vec<u8>> = Vec::with_capacity(total_objects);
    oad_payloads.push(Vec::new());  // NULL_Object: empty payload
    for (i, obj) in plan.objects.iter().enumerate() {
        let payload = plan
            .schemas
            .get(&obj.class_name)
            .map(|s| serialize_oad_data(s, obj, &mut common, &name_to_idx, plan.assets, obj_asset_room[i]))
            .unwrap_or_default();
        oad_payloads.push(payload);
    }
    let room_sizes: Vec<usize> = room_list.iter().map(|r| r.byte_size()).collect();
    let rooms_total: usize = room_sizes.iter().sum();

    // Template objects — the engine's oas/objects.c dispatcher skips
    // construction for any class whose oadFlags bit 0
    // (OADFLAG_TEMPLATE_OBJECT) is set.  Objects carry a "Template Object"
    // INT32 field in their per-class OAD; when its .lev value is "1"
    // ("True" in the False|True enum) the flag must propagate into the
    // _ObjectOnDisk.oadFlags field or level.cc:188 asserts.
    let is_template_object: Vec<bool> = plan.objects.iter()
        .map(|obj| obj.find_field("Template Object")
            .map(|c| {
                let d = crate::lev_parser::field_data(c);
                d.len() >= 4 && i32::from_le_bytes(d[..4].try_into().unwrap()) != 0
            })
            .unwrap_or(false))
        .collect();

    // Paths + channels — extract per-object PATH blocks from the `.lev`.
    // Every object with Mobility=Path must point at a valid path record
    // (the engine's MovementObject ctor asserts on NULL).  If such an
    // object has no authored PATH we fall back to a dummy all-zero path
    // sharing a single constant-zero channel, to keep the ctor alive
    // while still loading.
    let needs_any_path: Vec<bool> = plan.objects.iter()
        .map(|obj| obj.find_field("Mobility")
            .map(|c| crate::lev_parser::field_str_value(c))
            .as_deref() == Some("Path"))
        .collect();

    // Plan the path + channel tables.  Per-object path index is assigned
    // in the order we emit them.  Channels are owned by the path that
    // owns them (no deduplication) — simpler and matches iff2lvl output.
    // Falls back to one shared dummy path (index 0) + one dummy channel
    // (index 0) for Mobility=Path objects with no authored PATH block.
    let mut path_index_for_obj: Vec<i16> = vec![-1; plan.objects.len()];
    let mut real_paths: Vec<&crate::lev_parser::PathBlock> = Vec::new();
    let mut real_path_owners: Vec<usize> = Vec::new();
    let mut any_needs_fallback = false;
    for (i, obj) in plan.objects.iter().enumerate() {
        if let Some(pb) = &obj.path {
            path_index_for_obj[i] = real_paths.len() as i16;
            real_paths.push(pb);
            real_path_owners.push(i);
        } else if needs_any_path[i] {
            any_needs_fallback = true;
        }
    }
    let fallback_path_index: i16 = if any_needs_fallback {
        real_paths.len() as i16
    } else { -1 };
    if any_needs_fallback {
        for (i, _) in plan.objects.iter().enumerate() {
            if needs_any_path[i] && path_index_for_obj[i] < 0 {
                path_index_for_obj[i] = fallback_path_index;
            }
        }
    }

    // Channel index assignment: 6 channels per real path, in the order
    // x, y, z, a, b, c.  Fallback path reuses one trailing constant-zero
    // channel for all six slots.
    let path_count = real_paths.len() + if any_needs_fallback { 1 } else { 0 };
    let channel_count = real_paths.len() * 6 + if any_needs_fallback { 1 } else { 0 };
    let path_record_size = 44;  // fx32×3 + u16×3 + u8 + 1 pad + i32×6

    // Per-channel byte size varies with numKeys; compute each up front so
    // we can lay out offsets.
    let mut channel_sizes: Vec<usize> = Vec::with_capacity(channel_count);
    for pb in &real_paths {
        for ch in &pb.channels {
            channel_sizes.push(12 + 8 * ch.entries.len().max(1));
        }
    }
    if any_needs_fallback {
        channel_sizes.push(12 + 8);  // CONSTANT channel, one zero key
    }

    let header_size   = 52;
    let objects_off   = header_size;
    let array_bytes   = 4 * total_objects;

    let paths_off    = objects_off + array_bytes + objects_total;
    let paths_array  = 4 * path_count;
    let paths_total  = path_record_size * path_count;
    let channels_off = paths_off + paths_array + paths_total;
    let channels_array = 4 * channel_count;
    let channels_total: usize = channel_sizes.iter().sum();
    let rooms_off    = channels_off + channels_array + channels_total;
    let rooms_array  = 4 * room_list.len();
    let common_off   = rooms_off + rooms_array + rooms_total;
    let common_len   = common.bytes().len();

    let mut out = Vec::with_capacity(common_off + common_len);

    // ── header ───────────────────────────────────────────────────────────────
    push_i32(&mut out, LEVEL_VERSION);
    push_i32(&mut out, total_objects as i32);
    push_i32(&mut out, objects_off as i32);
    push_i32(&mut out, path_count as i32);
    push_i32(&mut out, paths_off as i32);
    push_i32(&mut out, channel_count as i32);
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
        // Use the authoring-tool bbox from the `.lev` verbatim.  Original
        // iff2lvl output preserves the authored collision box (which is
        // intentionally wider than the mesh extent for many objects — see
        // the 2026-04-19 investigation).  Mesh-bbox extension is only
        // meaningful for freshly-authored Blender levels with no authored
        // bbox at all; if we re-enable it, gate it on `base_bbox` being a
        // trivial placeholder rather than always overriding the author.
        let base_bbox = [
            obj.bbox.min[0], obj.bbox.min[1], obj.bbox.min[2],
            obj.bbox.max[0], obj.bbox.max[1], obj.bbox.max[2],
        ];
        let _mesh_bb_unused = plan.mesh_bboxes.get(i).and_then(|b| *b);
        let bbox = expand_thin_bbox(base_bbox);

        let path_index: i16 = path_index_for_obj[i];
        // oadFlags bitset from wfsource/source/oas/oad.h:
        //   bit 0 = OADFLAG_TEMPLATE_OBJECT       ("Template Object")
        //   bit 1 = OADFLAG_PERMANENT_TEXTURE     ("Moves Between Rooms")
        //   bit 2 = OADFLAG_NOMESH_OBJECT
        // The engine tests these in oas/objects.c (template skip) and in the
        // asset manager (PERMANENT_TEXTURE keeps a room's assets resident).
        const OADFLAG_TEMPLATE_OBJECT:   i32 = 1 << 0;
        const OADFLAG_PERMANENT_TEXTURE: i32 = 1 << 1;
        let mut oad_flags: i32 = 0;
        if is_template_object[i]    { oad_flags |= OADFLAG_TEMPLATE_OBJECT; }
        if moves_between_rooms(obj) { oad_flags |= OADFLAG_PERMANENT_TEXTURE; }
        let start = out.len();
        write_obj_header(
            &mut out,
            type_idx,
            (obj.position.x, obj.position.y, obj.position.z),
            (ONE, ONE, ONE),
            rot,
            &bbox,
            oad_flags,
            path_index,
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

    // Paths: offset array + per-path records.
    debug_assert_eq!(out.len(), paths_off);
    let paths_data_start = paths_off + paths_array;
    for i in 0..path_count {
        push_i32(&mut out, (paths_data_start + i * path_record_size) as i32);
    }
    for (pi, pb) in real_paths.iter().enumerate() {
        let path_start = out.len();
        push_i32(&mut out, pb.base_pos.0);
        push_i32(&mut out, pb.base_pos.1);
        push_i32(&mut out, pb.base_pos.2);
        // iff2lvl always writes Euler base rotation as zeros (path.cc:281);
        // real rotation lives per-channel.  Emit matching layout: u16×3
        // + order (0xFE default, wf_euler) + 1 pad byte.
        out.extend_from_slice(&0u16.to_le_bytes());
        out.extend_from_slice(&0u16.to_le_bytes());
        out.extend_from_slice(&0u16.to_le_bytes());
        out.push(0xFEu8);
        out.push(0u8);
        // Channels for this path occupy indices [pi*6 .. pi*6+6) in the
        // compiled channel table.
        for slot in 0..6 {
            push_i32(&mut out, (pi * 6 + slot) as i32);
        }
        debug_assert_eq!(out.len() - path_start, path_record_size);
        let _ = pb;  // touch to silence unused if future refactor drops it
    }
    if any_needs_fallback {
        let path_start = out.len();
        push_i32(&mut out, 0); push_i32(&mut out, 0); push_i32(&mut out, 0);
        out.extend_from_slice(&0u16.to_le_bytes());
        out.extend_from_slice(&0u16.to_le_bytes());
        out.extend_from_slice(&0u16.to_le_bytes());
        out.push(0xFEu8);
        out.push(0u8);
        // Fallback path references the fallback channel (last in table).
        let fallback_ch = (channel_count - 1) as i32;
        for _ in 0..6 { push_i32(&mut out, fallback_ch); }
        debug_assert_eq!(out.len() - path_start, path_record_size);
    }

    // Channels: offset array + per-channel records.
    debug_assert_eq!(out.len(), channels_off);
    let mut ch_cursor = channels_off + channels_array;
    for sz in &channel_sizes {
        push_i32(&mut out, ch_cursor as i32);
        ch_cursor += sz;
    }
    let mut ch_slot = 0;
    for pb in &real_paths {
        for ch in &pb.channels {
            let ch_start = out.len();
            push_i32(&mut out, ch.compressor);
            push_i32(&mut out, ch.end_time);
            let num_keys = ch.entries.len().max(1);
            push_i32(&mut out, num_keys as i32);
            if ch.entries.is_empty() {
                // Safety net: constant-zero key so the runtime sees a valid
                // first entry with time=0.
                push_i32(&mut out, 0);
                push_i32(&mut out, 0);
            } else {
                for (t, v) in &ch.entries {
                    push_i32(&mut out, *t);
                    push_i32(&mut out, *v);
                }
            }
            debug_assert_eq!(out.len() - ch_start, channel_sizes[ch_slot]);
            ch_slot += 1;
        }
    }
    if any_needs_fallback {
        let ch_start = out.len();
        push_i32(&mut out, 1);   // CONSTANT_COMPRESSION
        push_i32(&mut out, 0);   // endTime
        push_i32(&mut out, 1);   // numKeys
        push_i32(&mut out, 0);   // time
        push_i32(&mut out, 0);   // value
        debug_assert_eq!(out.len() - ch_start, channel_sizes[ch_slot]);
    }

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

/// Ensure every bbox axis has `max - min >= 0.25` (fixed32 `0x4000`).
///
/// iff2lvl/level.cc:573-598 applies this to every object's collision box:
/// where an axis's span is below 0.25, it pushes min down by 0.25 (keeping
/// max where it was).  The engine's colbox constructor asserts `max > min`
/// per-axis and would otherwise fire on lights / matte objects / zero-mesh
/// actors whose `.lev` carries no BOX3 (they'd default to zeros here).
fn expand_thin_bbox(mut bbox: [i32; 6]) -> [i32; 6] {
    const QUARTER: i32 = 0x4000;  // 0.25 in fixed32
    for axis in 0..3 {
        let min = bbox[axis];
        let max = bbox[axis + 3];
        let span = (max - min).abs();
        if span < QUARTER {
            bbox[axis] = max - QUARTER;
        }
    }
    bbox
}

/// Extend `base` bbox to also encompass `mesh` bbox.
///
/// The mesh bbox is in local (object) space; the .lev BOX3 is also local
/// space (iff2lvl reads vertices directly and updates the colbox in-place).
fn extend_bbox(mut base: [i32; 6], mesh: [i32; 6]) -> [i32; 6] {
    for axis in 0..3 {
        if mesh[axis] < base[axis] { base[axis] = mesh[axis]; }
        if mesh[axis + 3] > base[axis + 3] { base[axis + 3] = mesh[axis + 3]; }
    }
    base
}

/// Pad `out` with zeros until it reaches `start + target_len`.
fn pad_section(out: &mut Vec<u8>, start: usize, target_len: usize) {
    while out.len() < start + target_len {
        out.push(0);
    }
}

/// Return true if this object's mesh should live in the PERM asset slot.
///
/// "Moves Between Rooms" = 1 (True) means the object travels between rooms,
/// so its assets must be permanently resident.  Default 0 (False) means the
/// object stays in one room and can use a room-specific asset slot.
fn moves_between_rooms(obj: &crate::lev_parser::LevObject) -> bool {
    obj.find_field("Moves Between Rooms")
        .and_then(|chunk| {
            let data = crate::lev_parser::field_data(chunk);
            if data.len() >= 4 {
                Some(i32::from_le_bytes(data[..4].try_into().unwrap()) != 0)
            } else {
                None
            }
        })
        .unwrap_or(false)
}
