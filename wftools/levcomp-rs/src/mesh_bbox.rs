//! Read a MODL `.iff` mesh file and compute its bounding box from VRTX data.
//!
//! Vertex3DOnDisk layout (24 bytes, little-endian):
//!   offset  0: fixed32 u   (UV, not needed)
//!   offset  4: fixed32 v   (UV, not needed)
//!   offset  8: uint32  color
//!   offset 12: fixed32 x
//!   offset 16: fixed32 y
//!   offset 20: fixed32 z
//!
//! fixed32 = 1.15.16 format — raw i32 value is in the same units as the level
//! bbox, so no conversion is needed.

use std::path::{Path, PathBuf};

const VERTEX_SIZE: usize = 24;
const XYZ_OFFSET: usize = 12;

/// Return the bounding box [minX, minY, minZ, maxX, maxY, maxZ] (fixed32) of
/// the mesh stored in `<dir>/<mesh_name>`, or None if the file cannot be read
/// or parsed.  The lookup is case-insensitive to handle WF levels that store
/// filenames with inconsistent capitalisation ("House.iff" vs "house.iff").
pub fn mesh_bbox(dir: &Path, mesh_name: &str) -> Option<[i32; 6]> {
    let path = find_case_insensitive(dir, mesh_name)?;
    let data = std::fs::read(path).ok()?;
    extract_bbox(&data)
}

fn find_case_insensitive(dir: &Path, name: &str) -> Option<PathBuf> {
    let lower = name.to_lowercase();
    // Fast path: try the exact name first.
    let direct = dir.join(name);
    if direct.exists() {
        return Some(direct);
    }
    // Fallback: scan directory entries for a case-insensitive match.
    for entry in std::fs::read_dir(dir).ok()?.flatten() {
        let fname = entry.file_name();
        let s = fname.to_string_lossy();
        if s.to_lowercase() == lower {
            return Some(entry.path());
        }
    }
    None
}

fn extract_bbox(data: &[u8]) -> Option<[i32; 6]> {
    // Outer MODL chunk: 4-byte tag + 4-byte LE size + payload
    if data.len() < 8 { return None; }
    let outer_tag = &data[0..4];
    if outer_tag != b"MODL" { return None; }
    let outer_size = u32::from_le_bytes(data[4..8].try_into().ok()?) as usize;
    if data.len() < 8 + outer_size { return None; }
    let inner = &data[8..8 + outer_size];

    // Walk inner chunks looking for VRTX.
    let vrtx = find_chunk(inner, b"VRTX")?;
    if vrtx.len() < VERTEX_SIZE { return None; }

    let n = vrtx.len() / VERTEX_SIZE;
    let mut min = [i32::MAX; 3];
    let mut max = [i32::MIN; 3];
    for i in 0..n {
        let base = i * VERTEX_SIZE + XYZ_OFFSET;
        if base + 12 > vrtx.len() { break; }
        for axis in 0..3 {
            let off = base + axis * 4;
            let v = i32::from_le_bytes(vrtx[off..off + 4].try_into().ok()?);
            if v < min[axis] { min[axis] = v; }
            if v > max[axis] { max[axis] = v; }
        }
    }
    if min[0] == i32::MAX { return None; }
    Some([min[0], min[1], min[2], max[0], max[1], max[2]])
}

/// Find the first chunk with the given 4-byte tag in a flat IFF payload.
/// Returns the chunk payload (excluding the 8-byte header).
fn find_chunk<'a>(data: &'a [u8], tag: &[u8; 4]) -> Option<&'a [u8]> {
    let mut off = 0;
    while off + 8 <= data.len() {
        let chunk_tag = &data[off..off + 4];
        let size = u32::from_le_bytes(data[off + 4..off + 8].try_into().ok()?) as usize;
        off += 8;
        let end = off + size;
        if chunk_tag == tag {
            return data.get(off..end);
        }
        off = end;
        // Align to 4-byte boundary.
        if off % 4 != 0 { off += 4 - (off % 4); }
    }
    None
}
