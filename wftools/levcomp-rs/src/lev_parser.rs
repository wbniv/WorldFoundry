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
    /// All sub-chunks of this OBJ, in order.  Phase 2 will walk these to
    /// serialize per-class OAD fields (I32/FX32/STR/XDAT) into the flat OAD
    /// data block that follows each `_ObjectOnDisk` header.
    #[allow(dead_code)]
    pub fields: Vec<IffChunk>,
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
