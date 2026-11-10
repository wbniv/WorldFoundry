//! Builders for unit tests: in-memory `.oad` schemas and `.lev` objects, so a
//! test states the one field it is about instead of loading a real level.

use wf_iff::{str_to_id, write_chunk, IffChunk};
use wf_oad::{ButtonType, OadEntry, OadFile, OadHeader, CHUNK_ID};

use crate::lev_parser::{Box3, Eulr, LevObject, Vec3};

fn fixed<const N: usize>(text: &str) -> [u8; N] {
    let mut out = [0u8; N];
    let bytes = text.as_bytes();
    let n = bytes.len().min(N - 1);
    out[..n].copy_from_slice(&bytes[..n]);
    out
}

/// One OAD entry. `items` is the pipe-separated `string` field ("A|B").
pub fn entry(button_type: ButtonType, name: &str, items: &str, show_as: u8, def: i32) -> OadEntry {
    OadEntry {
        button_type,
        name: fixed(name),
        min: 0,
        max: 0,
        def,
        len: 0,
        string: fixed(items),
        show_as,
        x: -1,
        y: -1,
        help_message: [0; 128],
        union_bytes: [0; 255],
        lpstr_filter: [0; 512],
    }
}

/// A `.oad` whose header names the type `display`.
pub fn schema(display: &str, entries: Vec<OadEntry>) -> OadFile {
    OadFile {
        header: OadHeader { chunk_id: CHUNK_ID, chunk_size: 0, name: fixed(display), version: 0x0001_0202 },
        entries,
    }
}

fn cstr(text: &str) -> Vec<u8> {
    let mut v = text.as_bytes().to_vec();
    v.push(0);
    v
}

/// A `.lev` field chunk `{ 'KIND' { 'NAME' "name" } { 'STR' "label" } }`, as
/// the exporter writes an enum label or an XDATA text.
pub fn str_field(kind: &str, name: &str, label: &str) -> IffChunk {
    let mut payload = write_chunk(str_to_id("NAME"), &cstr(name));
    payload.extend(write_chunk(str_to_id("STR"), &cstr(label)));
    IffChunk { id: str_to_id(kind), payload }
}

/// A `.lev` object of `class`, at the origin, with the given field chunks.
pub fn object(name: &str, class: &str, fields: Vec<IffChunk>) -> LevObject {
    LevObject {
        name: name.to_string(),
        class_name: class.to_string(),
        position: Vec3 { x: 0, y: 0, z: 0 },
        rotation: Eulr { a: 0, b: 0, c: 0 },
        scale: Vec3 { x: 0x10000, y: 0x10000, z: 0x10000 },
        bbox: Box3 { min: [0; 3], max: [0; 3] },
        path: None,
        fields,
    }
}
