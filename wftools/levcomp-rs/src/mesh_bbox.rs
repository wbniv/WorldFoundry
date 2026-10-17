//! Extract the local-space bounding box from a MODL mesh IFF file.
//!
//! The MODL payload contains a VRTX sub-chunk whose data is a flat array of
//! `Vertex3DOnDisk` records (24 bytes each, from gfx/rendobj3.hp):
//!
//! ```text
//! offset  type      field
//!      0  fixed32   u  (UV)
//!      4  fixed32   v  (UV)
//!      8  uint32    color
//!     12  fixed32   x  ← position
//!     16  fixed32   y  ← position
//!     20  fixed32   z  ← position
//! ```
//!
//! All coordinates are fixed32 (1.15.16), matching the units used everywhere
//! in the level (positions, bboxes).

use std::path::Path;
use wf_iff::{id_to_str, read_chunks};

const VERTEX_STRIDE: usize = 24;
const POS_OFFSET: usize = 12;  // byte offset of x within Vertex3DOnDisk

/// Parse a mesh IFF at `path` and return its local-space bbox
/// `[minX, minY, minZ, maxX, maxY, maxZ]` in fixed32 units.
///
/// A shared-geometry appearance (`GREF` instead of `VRTX`) is resolved to the
/// geometry file in the same directory and its bbox comes from `POSN`, which
/// equals the bbox of the plain model it replaced. A malformed or unresolvable
/// `GREF` is an error naming the model and the reference.
///
/// Returns `Ok(None)` (as before sharing) if the file contains no MODL or
/// VRTX chunk, or has no complete vertices.
pub fn load(path: &Path) -> Result<Option<[i32; 6]>, String> {
    if let Some(shared) = crate::shared_geometry::inspect(path)? {
        return Ok(Some(shared.bbox()));
    }
    Ok(load_plain(path))
}

fn load_plain(path: &Path) -> Option<[i32; 6]> {
    let data = std::fs::read(path).ok()?;
    let top = read_chunks(&data).ok()?;

    // Top-level chunk must be MODL (for mesh IFFs); we also accept any
    // top-level wrapper and walk it for a MODL sub-chunk.
    let modl_payload: &[u8] = {
        let direct = top.iter().find(|c| id_to_str(c.id) == "MODL");
        match direct {
            Some(c) => &c.payload,
            None => return None,
        }
    };

    let subs = read_chunks(modl_payload).ok()?;
    let vrtx = subs.iter().find(|c| id_to_str(c.id) == "VRTX")?;
    let data = &vrtx.payload;

    if data.len() < VERTEX_STRIDE {
        return None;
    }
    let n = data.len() / VERTEX_STRIDE;

    let mut min = [i32::MAX; 3];
    let mut max = [i32::MIN; 3];

    for i in 0..n {
        let base = i * VERTEX_STRIDE + POS_OFFSET;
        if base + 12 > data.len() { break; }
        for axis in 0..3 {
            let off = base + axis * 4;
            let v = i32::from_le_bytes(data[off..off + 4].try_into().unwrap());
            if v < min[axis] { min[axis] = v; }
            if v > max[axis] { max[axis] = v; }
        }
    }

    if min[0] == i32::MAX {
        return None;
    }
    Some([min[0], min[1], min[2], max[0], max[1], max[2]])
}

/// Case-insensitive file lookup inside `dir`.  Returns the first entry whose
/// filename matches `name` ignoring ASCII case, or `None`.
pub fn find_case_insensitive(dir: &Path, name: &str) -> Option<std::path::PathBuf> {
    let lower = name.to_ascii_lowercase();
    let entries = std::fs::read_dir(dir).ok()?;
    for entry in entries.flatten() {
        let fname = entry.file_name();
        let s = fname.to_string_lossy();
        if s.to_ascii_lowercase() == lower {
            return Some(entry.path());
        }
    }
    None
}
