// level.rs — level binary parsing and dump functions
// Port of wftools/lvldump/level.cc

use std::io::{self, Write};

// wf_hdump::hdump requires impl Write (Sized); wrap &mut dyn Write to satisfy that.
fn hdump(data: &[u8], indent: usize, out: &mut dyn Write) -> io::Result<()> {
    struct W<'a>(&'a mut dyn Write);
    impl Write for W<'_> {
        fn write(&mut self, buf: &[u8]) -> io::Result<usize> { self.0.write(buf) }
        fn flush(&mut self) -> io::Result<()> { self.0.flush() }
    }
    wf_hdump::hdump(data, indent, 16, &mut W(out))
}

use crate::oad::{self, OadContext};

// ── constants ────────────────────────────────────────────────────────────────

const LEVEL_VERSION: i32 = 28;
const MAX_ADJACENT_ROOMS: usize = 2;
const SEP: &str = "================================================================================";
const OBJ_SEP: &str = "--------------------------------------------------------------------------------";

// ── fixed-point conversion ───────────────────────────────────────────────────

#[inline]
fn ftf(v: i32) -> f32 {
    v as f32 / 65536.0
}

// ── byte reading helpers ─────────────────────────────────────────────────────

fn ri32(data: &[u8], off: usize) -> i32 {
    i32::from_le_bytes(data[off..off + 4].try_into().unwrap())
}

fn ri16(data: &[u8], off: usize) -> i16 {
    i16::from_le_bytes(data[off..off + 2].try_into().unwrap())
}

// ── _LevelOnDisk offsets (13 × i32, each 4 bytes) ───────────────────────────
// Byte layout:
//   0: versionNum
//   4: objectCount,   8: objectsOffset
//  12: pathCount,    16: pathsOffset
//  20: channelCount, 24: channelsOffset
//  28: lightCount,   32: lightsOffset
//  36: roomCount,    40: roomsOffset
//  44: commonDataLength, 48: commonDataOffset

struct Level<'a> {
    data: &'a [u8],
}

impl<'a> Level<'a> {
    fn version_num(&self)        -> i32 { ri32(self.data,  0) }
    fn object_count(&self)       -> i32 { ri32(self.data,  4) }
    fn objects_offset(&self)     -> i32 { ri32(self.data,  8) }
    fn path_count(&self)         -> i32 { ri32(self.data, 12) }
    fn paths_offset(&self)       -> i32 { ri32(self.data, 16) }
    fn channel_count(&self)      -> i32 { ri32(self.data, 20) }
    fn channels_offset(&self)    -> i32 { ri32(self.data, 24) }
    fn _light_count(&self)       -> i32 { ri32(self.data, 28) }
    fn _lights_offset(&self)     -> i32 { ri32(self.data, 32) }
    fn room_count(&self)         -> i32 { ri32(self.data, 36) }
    fn rooms_offset(&self)       -> i32 { ri32(self.data, 40) }
    fn common_data_length(&self) -> i32 { ri32(self.data, 44) }
    fn common_data_offset(&self) -> i32 { ri32(self.data, 48) }

    /// Array of i32 offsets at `objects_offset`.
    fn obj_array(&self) -> &[u8] {
        &self.data[self.objects_offset() as usize..]
    }
    fn path_array(&self) -> &[u8] {
        &self.data[self.paths_offset() as usize..]
    }
    fn channel_array(&self) -> &[u8] {
        &self.data[self.channels_offset() as usize..]
    }
    fn room_array(&self) -> &[u8] {
        &self.data[self.rooms_offset() as usize..]
    }
    fn common_block(&self) -> &[u8] {
        let off = self.common_data_offset() as usize;
        let len = self.common_data_length() as usize;
        &self.data[off..off + len]
    }
}

// ── _ObjectOnDisk field offsets (natural alignment, NOT pack(1)) ────────────
//   0: type (i16)
//   2: pad                                   (2 bytes for i32 alignment)
//   4: x,y,z (i32×3 = 12)
//  16: x_scale,y_scale,z_scale (i32×3 = 12)
//  28: rotation: a(u16),b(u16),c(u16),order(u8) = 7  (aligned(4), 8 bytes total)
//  36: coarse: minX,minY,minZ,maxX,maxY,maxZ (i32×6 = 24)
//  60: oadFlags (i32)
//  64: pathIndex (i16)
//  66: OADSize (i16)
//  68: [OADSize bytes of OAD data, padded to 4-byte alignment]

const OBJ_TYPE_OFF:      usize = 0;
const OBJ_X_OFF:         usize = 4;
const OBJ_Y_OFF:         usize = 8;
const OBJ_Z_OFF:         usize = 12;
const OBJ_COARSE_OFF:    usize = 36;  // minX
const OBJ_OFLAGS_OFF:    usize = 60;
const OBJ_PATHIDX_OFF:   usize = 64;
const OBJ_OADSIZE_OFF:   usize = 66;
const OBJ_HEADER_SIZE:   usize = 68;

// ── _PathOnDisk field offsets ────────────────────────────────────────────────
//   0: base.x,y,z (i32×3=12), base.rot a,b,c,order (7) → 19 bytes
//  19: PositionXChannel,PositionYChannel,PositionZChannel (i32×3=12)
//  31: RotationAChannel,RotationBChannel,RotationCChannel (i32×3=12)
//  43: end

const PATH_BASE_X:    usize = 0;
const PATH_BASE_Y:    usize = 4;
const PATH_BASE_Z:    usize = 8;
const PATH_ROT_A:     usize = 12;
const PATH_ROT_B:     usize = 14;
const PATH_ROT_C:     usize = 16;
const PATH_POS_X_CH:  usize = 19;
const PATH_POS_Y_CH:  usize = 23;
const PATH_POS_Z_CH:  usize = 27;
const PATH_ROT_A_CH:  usize = 31;
const PATH_ROT_B_CH:  usize = 35;
const PATH_ROT_C_CH:  usize = 39;

// ── _ChannelOnDisk offsets ───────────────────────────────────────────────────
//   0: compressorType (i32)
//   4: endTime (i32/fixed32)
//   8: numKeys (i32)
//  12: [numKeys × 8 bytes: time(i32), value(i32)]

const CH_COMPRESSOR:  usize = 0;
const CH_ENDTIME:     usize = 4;
const CH_NUMKEYS:     usize = 8;
const CH_HEADER_SIZE: usize = 12;
const CH_ENTRY_SIZE:  usize = 8;

// ── _RoomOnDisk offsets ──────────────────────────────────────────────────────
//   0: count (i32)
//   4: boundingBox (i32×6 = 24)
//  28: adjacentRooms (i16×2 = 4)
//  32: roomObjectIndex (i16)
//  34: [count × i16]

const ROOM_COUNT:       usize = 0;
const ROOM_BBOX_OFF:    usize = 4;
const ROOM_ADJ_OFF:     usize = 28;
const ROOM_OBJ_IDX:     usize = 32;
const ROOM_HEADER_SIZE: usize = 34;

// ── dump functions ───────────────────────────────────────────────────────────

fn dump_lc_file(ctx: &OadContext, out: &mut dyn Write) -> io::Result<()> {
    writeln!(out, "Game Object Enumeration")?;
    for (i, name) in ctx.object_types.iter().enumerate() {
        writeln!(out, "Object Index <{}>, Name <{}>", i, name)?;
    }
    Ok(())
}

fn dump_objects(lv: &Level, ctx: &OadContext, out: &mut dyn Write) -> io::Result<()> {
    writeln!(out, "  Object Dump:")?;

    let obj_count = lv.object_count() as usize;
    let obj_arr = lv.obj_array();
    let common = lv.common_block();

    // Start at 1 — object 0 is the null/invalid object
    for index in 1..obj_count {
        writeln!(out, "{}", OBJ_SEP)?;

        let obj_offset = ri32(obj_arr, index * 4) as usize;
        writeln!(out, "  Object {} is at offset  {}", index, obj_offset)?;

        let obj = &lv.data[obj_offset..];
        let obj_type = ri16(obj, OBJ_TYPE_OFF) as usize;
        let path_idx = ri16(obj, OBJ_PATHIDX_OFF);
        let oad_size = ri16(obj, OBJ_OADSIZE_OFF) as usize;

        if ctx.has_lc() {
            if let Some(name) = ctx.type_name(obj_type) {
                writeln!(out, "    Type = {} ({})", name, obj_type)?;
            } else {
                writeln!(out, "    Type = {}", obj_type)?;
            }
        } else {
            writeln!(out, "    Type = {}", obj_type)?;
        }

        writeln!(out, "    PathIndex = {}", path_idx)?;
        writeln!(out)?;

        let x = ri32(obj, OBJ_X_OFF);
        let y = ri32(obj, OBJ_Y_OFF);
        let z = ri32(obj, OBJ_Z_OFF);
        writeln!(out, "    Position: X:{} Y:{} Z:{}", ftf(x), ftf(y), ftf(z))?;
        writeln!(out, "    Coarse collision rect: ")?;

        let min_x = ri32(obj, OBJ_COARSE_OFF);
        let min_y = ri32(obj, OBJ_COARSE_OFF + 4);
        let min_z = ri32(obj, OBJ_COARSE_OFF + 8);
        let max_x = ri32(obj, OBJ_COARSE_OFF + 12);
        let max_y = ri32(obj, OBJ_COARSE_OFF + 16);
        let max_z = ri32(obj, OBJ_COARSE_OFF + 20);

        writeln!(out, "    MinX:{} MinY:{} MinZ:{}", ftf(min_x), ftf(min_y), ftf(min_z))?;
        writeln!(out, "    MaxX:{} MaxY:{} MaxZ:{}", ftf(max_x), ftf(max_y), ftf(max_z))?;

        writeln!(out, "    Collision rect offset by position: ")?;
        writeln!(out, "      MinX:{} MinY:{} MinZ:{}",
            ftf(min_x + x), ftf(min_y + y), ftf(min_z + z))?;
        writeln!(out, "      MaxX:{} MaxY:{} MaxZ:{}",
            ftf(max_x + x), ftf(max_y + y), ftf(max_z + z))?;

        let oad_flags = ri32(obj, OBJ_OFLAGS_OFF);
        writeln!(out, "    OadFlags: {}", oad_flags)?;
        writeln!(out, "    OADSize: {}", oad_size)?;

        let oad_data = &obj[OBJ_HEADER_SIZE..OBJ_HEADER_SIZE + oad_size];

        if !ctx.object_oads.is_empty() {
            // Full OAD display
            if let Some(Some(schema)) = ctx.object_oads.get(obj_type) {
                oad::dump_oad_struct(schema, oad_data, common, out)?;
            } else {
                // No schema for this type — hex dump
                hdump(oad_data, 4, out)?;
            }
        } else {
            // No OADs loaded — hex dump
            hdump(oad_data, 4, out)?;
        }
    }

    Ok(())
}

fn dump_paths(lv: &Level, out: &mut dyn Write) -> io::Result<()> {
    writeln!(out, "Paths Dump:")?;

    let path_arr = lv.path_array();
    for index in 0..lv.path_count() as usize {
        let path_offset = ri32(path_arr, index * 4) as usize;
        writeln!(out, "  Path # {} is at offset  {}", index, path_offset)?;

        let p = &lv.data[path_offset..];
        let bx = ri32(p, PATH_BASE_X);
        let by = ri32(p, PATH_BASE_Y);
        let bz = ri32(p, PATH_BASE_Z);
        let ra = ri16(p, PATH_ROT_A) as i32;
        let rb = ri16(p, PATH_ROT_B) as i32;
        let rc = ri16(p, PATH_ROT_C) as i32;

        writeln!(out, "    Path base at position: {},{},{}", ftf(bx), ftf(by), ftf(bz))?;
        writeln!(out, "    Rotation base: {},{},{}", ftf(ra), ftf(rb), ftf(rc))?;
        writeln!(out, "    X position using channel #: {}", ri32(p, PATH_POS_X_CH))?;
        writeln!(out, "    Y position using channel #: {}", ri32(p, PATH_POS_Y_CH))?;
        writeln!(out, "    Z position using channel #: {}", ri32(p, PATH_POS_Z_CH))?;
        writeln!(out, "    A rotation using channel #: {}", ri32(p, PATH_ROT_A_CH))?;
        writeln!(out, "    B rotation using channel #: {}", ri32(p, PATH_ROT_B_CH))?;
        writeln!(out, "    C rotation using channel #: {}", ri32(p, PATH_ROT_C_CH))?;
    }

    Ok(())
}

fn dump_channels(lv: &Level, out: &mut dyn Write) -> io::Result<()> {
    writeln!(out, "Channels Dump:")?;

    let ch_arr = lv.channel_array();
    for index in 0..lv.channel_count() as usize {
        let ch_offset = ri32(ch_arr, index * 4) as usize;
        writeln!(out, "  Channel # {} is at offset  {}", index, ch_offset)?;

        let c = &lv.data[ch_offset..];
        let compressor = ri32(c, CH_COMPRESSOR);
        let end_time   = ri32(c, CH_ENDTIME);
        let num_keys   = ri32(c, CH_NUMKEYS) as usize;

        writeln!(out, "    Compressor Type = {}", compressor)?;
        writeln!(out, "    End Time = {}", ftf(end_time))?;
        writeln!(out, "    Number of Keys = {}", num_keys)?;

        for ki in 0..num_keys {
            let entry_off = CH_HEADER_SIZE + ki * CH_ENTRY_SIZE;
            let time  = ri32(c, entry_off);
            let value = ri32(c, entry_off + 4);
            writeln!(out, "    Key #{}: Time = {}, Value = {}", ki, ftf(time), value)?;
        }
    }

    Ok(())
}

fn dump_rooms(lv: &Level, out: &mut dyn Write) -> io::Result<()> {
    writeln!(out, "Rooms Dump:")?;

    let room_arr = lv.room_array();
    for index in 0..lv.room_count() as usize {
        let room_offset = ri32(room_arr, index * 4) as usize;
        writeln!(out, "  Room # {} is at offset  {}", index, room_offset)?;

        let r = &lv.data[room_offset..];
        let count    = ri32(r, ROOM_COUNT) as usize;
        let room_obj = ri16(r, ROOM_OBJ_IDX);

        writeln!(out, "Room #{}, contains {} entries", index, count)?;
        writeln!(out, "  And is object #{}", room_obj)?;

        let min_x = ri32(r, ROOM_BBOX_OFF);
        let min_y = ri32(r, ROOM_BBOX_OFF + 4);
        let min_z = ri32(r, ROOM_BBOX_OFF + 8);
        let max_x = ri32(r, ROOM_BBOX_OFF + 12);
        let max_y = ri32(r, ROOM_BBOX_OFF + 16);
        let max_z = ri32(r, ROOM_BBOX_OFF + 20);

        writeln!(out, " MinX:{} MinY:{} MinZ:{}", ftf(min_x), ftf(min_y), ftf(min_z))?;
        writeln!(out, " MaxX:{} MaxY:{} MaxZ:{}", ftf(max_x), ftf(max_y), ftf(max_z))?;

        for adj in 0..MAX_ADJACENT_ROOMS {
            let adj_room = ri16(r, ROOM_ADJ_OFF + adj * 2);
            writeln!(out, "  Room Reference #{}: {}", adj, adj_room)?;
        }

        let entries_base = &r[ROOM_HEADER_SIZE..];
        for e in 0..count {
            let obj_idx = ri16(entries_base, e * 2);
            writeln!(out, "    Contains object #{}", obj_idx)?;
        }
    }

    Ok(())
}

fn dump_common_block(lv: &Level, out: &mut dyn Write) -> io::Result<()> {
    writeln!(out, "Common Block Dump:")?;
    hdump(lv.common_block(), 4, out)?;
    Ok(())
}

fn dump_object_histogram(lv: &Level, ctx: &OadContext, out: &mut dyn Write) -> io::Result<()> {
    let mut buckets = [0u32; 256];
    let obj_count = lv.object_count() as usize;
    let obj_arr = lv.obj_array();
    for index in 1..obj_count {
        let obj_offset = ri32(obj_arr, index * 4) as usize;
        let obj_type = ri16(&lv.data[obj_offset..], OBJ_TYPE_OFF) as usize;
        if obj_type < 256 {
            buckets[obj_type] += 1;
        }
    }

    writeln!(out, "Object Histogram:")?;
    for (i, &count) in buckets.iter().enumerate() {
        if count > 0 {
            if let Some(name) = ctx.type_name(i) {
                writeln!(out, "{}({}): {}", name, i, count)?;
            } else {
                writeln!(out, "{}: {}", i, count)?;
            }
        }
    }
    Ok(())
}

// ── public entry point ───────────────────────────────────────────────────────

pub fn dump_level(
    data: &[u8],
    ctx: &OadContext,
    analysis: bool,
    out: &mut dyn Write,
) -> io::Result<()> {
    let lv = Level { data };

    writeln!(out, "{}", SEP)?;

    if ctx.has_lc() {
        dump_lc_file(ctx, out)?;
        writeln!(out, "{}", SEP)?;
    }

    writeln!(out, "Level Loaded: ")?;
    writeln!(out, "Version #: {}", lv.version_num())?;
    if lv.version_num() != LEVEL_VERSION {
        eprintln!(
            "Warning: level version # does not match, expected <{}>,found <{}>, data could be incorrect",
            LEVEL_VERSION, lv.version_num()
        );
    }

    writeln!(out, "Object Count: {} at offset {}", lv.object_count(), lv.objects_offset())?;
    writeln!(out, "Path Count {} at offset {}", lv.path_count(), lv.paths_offset())?;
    writeln!(out, "Channel Count {} at offset {}", lv.channel_count(), lv.channels_offset())?;
    writeln!(out, "Room Count {} at offset {}", lv.room_count(), lv.rooms_offset())?;
    writeln!(out, "Common Data Length {} at offset {}", lv.common_data_length(), lv.common_data_offset())?;

    writeln!(out, "{}", SEP)?;
    dump_objects(&lv, ctx, out)?;
    writeln!(out, "{}", SEP)?;
    dump_paths(&lv, out)?;
    writeln!(out, "{}", SEP)?;
    dump_channels(&lv, out)?;
    writeln!(out, "{}", SEP)?;
    dump_rooms(&lv, out)?;
    writeln!(out, "{}", SEP)?;
    dump_common_block(&lv, out)?;
    writeln!(out, "{}", SEP)?;

    if analysis {
        dump_object_histogram(&lv, ctx, out)?;
        writeln!(out, "{}", SEP)?;
    }

    Ok(())
}
