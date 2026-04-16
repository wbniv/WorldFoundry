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

pub struct LevObject {
    pub name: String,
    pub class_name: String,
    pub position: Vec3,
    pub rotation: Eulr,
    pub bbox: Box3,
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
        objects.push(parse_obj(&chunk.payload)?);
    }
    Ok(objects)
}

fn parse_obj(payload: &[u8]) -> Result<LevObject, String> {
    let fields = read_chunks(payload).map_err(|e: IffError| e.message)?;

    let mut name = String::new();
    let mut class_name = String::new();
    let mut position = Vec3 { x: 0, y: 0, z: 0 };
    let mut rotation = Eulr { a: 0, b: 0, c: 0 };
    let mut bbox = Box3 { min: [0; 3], max: [0; 3] };

    for f in &fields {
        match id_to_str(f.id).as_str() {
            "NAME" => name = read_cstr(&f.payload),

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
        return Err(format!("OBJ '{name}' has no Class Name field"));
    }

    Ok(LevObject { name, class_name, position, rotation, bbox, fields })
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
