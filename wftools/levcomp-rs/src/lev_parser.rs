//! Parse a `.lev.bin` file (binary IFF produced by `iffcomp` from `.lev` text).
//!
//! The top-level `LVL` chunk contains one `OBJ` chunk per level object.  Each
//! `OBJ` has a handful of named sub-chunks that we care about:
//!
//! | Sub-chunk | Shape                       | Meaning                     |
//! |-----------|-----------------------------|-----------------------------|
//! | `NAME`    | raw string                  | object instance name        |
//! | `VEC3`    | `NAME "Position" / DATA`    | 3× fixed32 → (x, y, z)      |
//! | `EULR`    | `NAME "Orientation" / DATA` | 3× fixed32 → (a, b, c)      |
//! | `BOX3`    | `NAME "Global Bounding Box" / DATA` | 6× fixed32 min/max  |
//! | `STR`     | `NAME "Class Name" / DATA`  | class name (e.g. "statplat")|
//!
//! Per-class OAD fields (I32/FX32/STR/XDAT) also appear but are not consumed
//! in this MVP — we stash each object's raw sub-chunks so later phases can
//! serialize OAD data.

use wf_iff::{id_to_str, read_chunks, str_to_id, IffChunk, IffError};

#[derive(Debug, Clone, Copy)]
pub struct Vec3 {
    pub x: i32,
    pub y: i32,
    pub z: i32,
}

#[derive(Debug, Clone, Copy)]
pub struct Eulr {
    pub a: i32,
    pub b: i32,
    pub c: i32,
}

#[derive(Debug, Clone, Copy)]
pub struct Box3 {
    pub min: [i32; 3],
    pub max: [i32; 3],
}

/// A single channel of animated values (one axis).  Binary layout mirrors
/// `_ChannelOnDisk`: compressor type, end time, and a list of (time, value)
/// entries.  `time` is in the channel's native time units (seconds as
/// fixed32) and `value` is whatever the client expects (fixed32 meters for
/// position, fixed32 radians for rotation).
#[derive(Debug, Clone)]
pub struct Channel {
    pub compressor: i32,
    pub end_time: i32,
    pub entries: Vec<(i32, i32)>,  // (time_fx32, value_i32)
}

impl Channel {
    /// A single-key constant channel of value 0 at time 0.
    pub fn constant_zero() -> Self {
        Self { compressor: 1, end_time: 0, entries: vec![(0, 0)] }
    }
}

/// Path block attached to an OBJ — base position/rotation plus the six
/// animation channels (position.x/y/z + rotation.a/b/c).  Any channel
/// missing from the `.lev` is filled with `Channel::constant_zero()`.
#[derive(Debug, Clone)]
pub struct PathBlock {
    pub base_pos:  (i32, i32, i32),
    // Base rotation is authored as a quaternion in the .lev (BROT), but
    // iff2lvl always wrote the _PathOnDisk.base.rot Euler as zeros.  We
    // mirror that — the runtime engine reads per-channel rotation.
    pub channels:  [Channel; 6],  // x, y, z, a, b, c (order matches _PathOnDisk)
}

pub struct LevObject {
    pub name: String,
    pub class_name: String,
    pub position: Vec3,
    pub rotation: Eulr,
    pub bbox: Box3,
    /// Path/keyframe animation block, if the object carries a PATH chunk.
    pub path: Option<PathBlock>,
    /// All sub-chunks of this OBJ, in order.  Each field chunk carries a NAME
    /// child (the schema key) plus its value as either a DATA child (raw bytes)
    /// or a nested STR child (label, used for enum selections).
    pub fields: Vec<IffChunk>,
}

impl LevObject {
    /// Find a field by its NAME.  Matches on schema key (e.g. "Mobility",
    /// "Mesh Name").  Returns the outer chunk (I32/FX32/STR/etc.) whose NAME
    /// child equals `key`.
    pub fn find_field(&self, key: &str) -> Option<&IffChunk> {
        self.fields.iter().find(|c| field_name(c) == key)
    }
}

/// Build a map from object name → 1-based index matching the `.lev` order.
/// (Index 0 is reserved for NULL_Object in the output, so `objects[0]`
/// becomes index 1, etc.)  Used for resolving ObjectReference fields.
pub fn name_to_index(objects: &[LevObject]) -> std::collections::HashMap<String, i32> {
    let mut map = std::collections::HashMap::new();
    for (i, obj) in objects.iter().enumerate() {
        map.insert(obj.name.clone(), (i + 1) as i32);
    }
    map
}

/// Return the NAME text of a field chunk, or empty string if absent.
fn field_name(chunk: &IffChunk) -> String {
    let children = match read_chunks(&chunk.payload) {
        Ok(c) => c,
        Err(_) => return String::new(),
    };
    for c in children {
        if id_to_str(c.id) == "NAME" {
            return read_cstr(&c.payload);
        }
    }
    String::new()
}

/// Extract a field's raw DATA bytes (for I32/FX32/BOX3/VEC3/etc.).
pub fn field_data(chunk: &IffChunk) -> Vec<u8> {
    let children = match read_chunks(&chunk.payload) { Ok(c) => c, Err(_) => return Vec::new() };
    for c in children {
        if id_to_str(c.id) == "DATA" {
            return c.payload;
        }
    }
    Vec::new()
}

/// Extract a field's nested STR value (enum label, or some STR-kind fields).
pub fn field_str_value(chunk: &IffChunk) -> String {
    let children = match read_chunks(&chunk.payload) { Ok(c) => c, Err(_) => return String::new() };
    // STR fields can hold either a DATA child with the text or a nested STR.
    // Both forms appear; prefer DATA if present, otherwise fall back to nested STR.
    let mut via_data = None;
    let mut via_str  = None;
    for c in children {
        match id_to_str(c.id).as_str() {
            "DATA" => via_data = Some(read_cstr(&c.payload)),
            "STR"  => via_str  = Some(read_cstr(&c.payload)),
            _ => {}
        }
    }
    via_data.or(via_str).unwrap_or_default()
}

pub fn parse(data: &[u8]) -> Result<Vec<LevObject>, String> {
    let chunks = read_chunks(data).map_err(|e: IffError| e.message)?;

    let lvl = chunks
        .iter()
        .find(|c| id_to_str(c.id) == "LVL")
        .ok_or_else(|| "no LVL chunk at top level".to_string())?;

    let sub = read_chunks(&lvl.payload).map_err(|e: IffError| e.message)?;

    let mut objects = Vec::new();
    for chunk in sub {
        if id_to_str(chunk.id) != "OBJ" {
            continue;
        }
        if let Some(obj) = parse_obj(&chunk.payload)? {
            objects.push(obj);
        }
    }
    Ok(objects)
}

/// Returns `None` for objects with no Class Name — these are 3ds Max helper objects
/// (e.g. light targets) whose position was consumed at export time.
fn parse_obj(payload: &[u8]) -> Result<Option<LevObject>, String> {
    let fields = read_chunks(payload).map_err(|e: IffError| e.message)?;

    let mut name = String::new();
    let mut class_name = String::new();
    let mut position = Vec3 { x: 0, y: 0, z: 0 };
    let mut rotation = Eulr { a: 0, b: 0, c: 0 };
    let mut bbox = Box3 { min: [0; 3], max: [0; 3] };
    let mut path: Option<PathBlock> = None;

    for f in &fields {
        match id_to_str(f.id).as_str() {
            "NAME" => name = read_cstr(&f.payload),
            "PATH" => path = parse_path_block(&f.payload)?,

            "VEC3" => {
                let (named, data) = read_named_data(&f.payload)?;
                if named == "Position" && data.len() >= 12 {
                    position = Vec3 {
                        x: le_i32(&data, 0),
                        y: le_i32(&data, 4),
                        z: le_i32(&data, 8),
                    };
                }
            }
            "EULR" => {
                let (named, data) = read_named_data(&f.payload)?;
                if named == "Orientation" && data.len() >= 12 {
                    rotation = Eulr {
                        a: le_i32(&data, 0),
                        b: le_i32(&data, 4),
                        c: le_i32(&data, 8),
                    };
                }
            }
            "BOX3" => {
                let (named, data) = read_named_data(&f.payload)?;
                if named == "Global Bounding Box" && data.len() >= 24 {
                    bbox = Box3 {
                        min: [le_i32(&data, 0), le_i32(&data, 4), le_i32(&data, 8)],
                        max: [le_i32(&data, 12), le_i32(&data, 16), le_i32(&data, 20)],
                    };
                }
            }
            "STR" => {
                let (named, data) = read_named_data(&f.payload)?;
                if named == "Class Name" {
                    class_name = read_cstr(&data);
                }
            }
            _ => {}
        }
    }

    if class_name.is_empty() {
        return Ok(None);
    }

    Ok(Some(LevObject { name, class_name, position, rotation, bbox, path, fields }))
}

/// Parse a PATH sub-chunk payload into a `PathBlock`.  Returns `None` when
/// the block carries no usable keyframe data (e.g. Blender emitted a PATH
/// scaffold but every CHAN has only a constant-zero DATA).
fn parse_path_block(payload: &[u8]) -> Result<Option<PathBlock>, String> {
    let children = read_chunks(payload).map_err(|e: IffError| e.message)?;
    const CHANNEL_NAMES: [&str; 6] = [
        "position.x", "position.y", "position.z",
        "rotation.a", "rotation.b", "rotation.c",
    ];

    let mut base_pos = (0, 0, 0);
    let mut chans: [Option<Channel>; 6] = Default::default();
    let mut saw_real_key = false;

    for c in children {
        match id_to_str(c.id).as_str() {
            "BPOS" => {
                if c.payload.len() >= 12 {
                    base_pos = (
                        le_i32(&c.payload, 0),
                        le_i32(&c.payload, 4),
                        le_i32(&c.payload, 8),
                    );
                }
            }
            "BROT" => { /* quaternion authored, but iff2lvl always zeros Euler base */ }
            "CHAN" => {
                let (name, ch) = parse_chan(&c.payload)?;
                let Some(slot) = CHANNEL_NAMES.iter().position(|n| *n == name) else {
                    continue;
                };
                if !ch.entries.is_empty() && !(ch.entries.len() == 1 && ch.entries[0].1 == 0) {
                    saw_real_key = true;
                }
                chans[slot] = Some(ch);
            }
            _ => {}
        }
    }

    if !saw_real_key {
        return Ok(None);
    }

    let channels: [Channel; 6] = std::array::from_fn(|i|
        chans[i].take().unwrap_or_else(Channel::constant_zero));

    Ok(Some(PathBlock { base_pos, channels }))
}

fn parse_chan(payload: &[u8]) -> Result<(String, Channel), String> {
    let children = read_chunks(payload).map_err(|e: IffError| e.message)?;
    let mut name = String::new();
    let mut type_ = 0i32;
    let mut dim = 0i32;
    let mut data: Vec<u8> = Vec::new();

    for c in children {
        match id_to_str(c.id).as_str() {
            "NAME" => name = read_cstr(&c.payload),
            "TYPE" => if c.payload.len() >= 4 { type_ = le_i32(&c.payload, 0); },
            "DIM"  => if c.payload.len() >= 4 { dim   = le_i32(&c.payload, 0); },
            "DATA" => data = c.payload,
            _ => {}
        }
    }

    let mut entries: Vec<(i32, i32)> = Vec::with_capacity(dim.max(0) as usize);
    let count = (data.len() / 8).min(dim.max(0) as usize);
    for i in 0..count {
        let t = le_i32(&data, i * 8);
        let v = le_i32(&data, i * 8 + 4);
        entries.push((t, v));
    }

    // iff2lvl picks CONSTANT when every value is identical; otherwise LINEAR.
    // The compiled channel stores only a single key in the CONSTANT case
    // (channel.cc:125) — collapse here to match.  Runtime LinearChannel
    // asserts channelData[0].time == 0, so the first entry's time must
    // be zero.
    let constant = entries.len() <= 1
        || entries.iter().all(|(_, v)| *v == entries[0].1);
    let compressor = if constant { 1 } else { type_.max(0) };
    if !entries.is_empty() {
        entries[0].0 = 0;
    }
    if constant {
        entries.truncate(1);
    }
    let end_time = if constant { 0 } else { entries.last().map(|(t, _)| *t).unwrap_or(0) };

    Ok((name, Channel { compressor, end_time, entries }))
}

/// An OBJ field chunk is `{ NAME "<key>" }{ DATA ... }` or similar.
/// Walk the child chunks; return the NAME string and the DATA payload (if any).
fn read_named_data(payload: &[u8]) -> Result<(String, Vec<u8>), String> {
    let children = read_chunks(payload).map_err(|e: IffError| e.message)?;
    let mut name = String::new();
    let mut data = Vec::new();
    for c in children {
        match id_to_str(c.id).as_str() {
            "NAME" => name = read_cstr(&c.payload),
            "DATA" => data = c.payload,
            _ => {}
        }
    }
    Ok((name, data))
}

fn read_cstr(b: &[u8]) -> String {
    let end = b.iter().position(|&c| c == 0).unwrap_or(b.len());
    String::from_utf8_lossy(&b[..end]).into_owned()
}

fn le_i32(b: &[u8], off: usize) -> i32 {
    i32::from_le_bytes(b[off..off + 4].try_into().unwrap())
}

#[allow(dead_code)]
fn tag_eq(id: u32, s: &str) -> bool {
    id == str_to_id(s)
}
