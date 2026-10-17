//! Shared model geometry (v1): an appearance `MODL` whose `GREF` names a
//! `GEOM` asset holding the positions and faces it shares with other
//! appearances. Format: finding-your-way
//! `docs/plans/2026-10-17-texture-variant-mesh-sharing.md`, "Exporter finding
//! and the v1 format"; reference reader `game/parmenides-slice/modl_reader.py`.
//!
//! ```text
//! GEOM { POSN  N x {fixed32 x, y, z}             12 bytes each
//!        FACE  M x {int16 v1, v2, v3, material}   8 bytes each }
//! MODL { MATL ..., [OPAC], [HNDL],
//!        GREF  {u32 version=1, vertexCount, faceCount, posCrc32, faceCrc32, char name[32]}
//!        UVCL  N x {fixed32 u, v, uint32 color}   12 bytes each }
//! ```
//!
//! Chunk order inside the appearance is not significant. The level compiler
//! validates every reference here so a broken one fails the build, naming the
//! model and the geometry, instead of failing on the device.

use crate::asset_registry::{room_from_id, AssetRegistry, ROOM_PERM};
use std::path::{Path, PathBuf};
use wf_iff::{id_to_str, read_chunks, IffChunk};

pub const GREF_VERSION: u32 = 1;
pub const GREF_SIZE: usize = 52;
/// The GREF name field is 32 bytes with NUL (format limit).
pub const NAME_LIMIT: usize = 31;
/// The geometry is looked up by its ASMP name, and `AssetManager::ReadAssetMap`
/// asserts each ASMP `'STR'` payload (name + NUL) is under 32 bytes, so a name
/// that reaches the runtime has at most 30 characters.
pub const ASMP_NAME_LIMIT: usize = 30;
const POSITION_SIZE: usize = 12;
const APPEARANCE_SIZE: usize = 12;
const FACE_SIZE: usize = 8;
/// `_MaterialOnDisk`: int32 flags, Color, char textureName[256].
const MATERIAL_SIZE: usize = 264;

/// A parsed `GREF` chunk.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GeometryRef {
    pub vertex_count: u32,
    pub face_count: u32,
    pub pos_crc32: u32,
    pub face_crc32: u32,
    pub name: String,
}

/// A validated appearance and the geometry it names.
#[derive(Debug, Clone)]
pub struct SharedModel {
    pub gref: GeometryRef,
    pub geometry_path: PathBuf,
    /// `POSN` payload of the geometry (N x 12 bytes).
    pub posn: Vec<u8>,
}

impl SharedModel {
    /// Local bbox `[minX, minY, minZ, maxX, maxY, maxZ]` in fixed32 units.
    pub fn bbox(&self) -> [i32; 6] {
        let mut min = [i32::MAX; 3];
        let mut max = [i32::MIN; 3];
        for p in self.posn.chunks_exact(POSITION_SIZE) {
            for axis in 0..3 {
                let v = i32::from_le_bytes(p[axis * 4..axis * 4 + 4].try_into().unwrap());
                min[axis] = min[axis].min(v);
                max[axis] = max[axis].max(v);
            }
        }
        [min[0], min[1], min[2], max[0], max[1], max[2]]
    }
}

/// CRC-32/ISO-HDLC (zlib's `crc32`): reflected 0x04C11DB7, init and xorout 0xFFFFFFFF.
pub fn crc32(data: &[u8]) -> u32 {
    let mut crc = 0xFFFF_FFFFu32;
    for &byte in data {
        crc ^= byte as u32;
        for _ in 0..8 {
            crc = if crc & 1 != 0 { (crc >> 1) ^ 0xEDB8_8320 } else { crc >> 1 };
        }
    }
    !crc
}

pub fn parse_gref(payload: &[u8]) -> Result<GeometryRef, String> {
    if payload.len() != GREF_SIZE {
        return Err(format!("GREF is {} bytes, expected {GREF_SIZE}", payload.len()));
    }
    let word = |i: usize| u32::from_le_bytes(payload[i * 4..i * 4 + 4].try_into().unwrap());
    if word(0) != GREF_VERSION {
        return Err(format!("GREF version {}, expected {GREF_VERSION}", word(0)));
    }
    let raw = &payload[20..52];
    let len = raw.iter().position(|&b| b == 0).unwrap_or(raw.len());
    if len == 0 || len > NAME_LIMIT {
        return Err(format!("GREF name is empty or longer than {NAME_LIMIT} characters"));
    }
    let name = std::str::from_utf8(&raw[..len])
        .ok()
        .filter(|s| s.is_ascii())
        .ok_or("GREF name is not ASCII")?;
    if name.bytes().any(|b| b.is_ascii_uppercase()) {
        return Err(format!("GREF name {name:?} is not lowercase"));
    }
    Ok(GeometryRef {
        vertex_count: word(1),
        face_count: word(2),
        pos_crc32: word(3),
        face_crc32: word(4),
        name: name.to_string(),
    })
}

pub fn check_asmp_name(name: &str) -> Result<(), String> {
    if name.len() > ASMP_NAME_LIMIT {
        return Err(format!(
            "name is {} characters; the runtime asset map (AssetManager::ReadAssetMap) holds at most {ASMP_NAME_LIMIT}",
            name.len()));
    }
    Ok(())
}

fn top_level(data: &[u8], what: &str) -> Result<IffChunk, String> {
    let mut top = read_chunks(data).map_err(|e| format!("{what}: {e}"))?;
    if top.len() != 1 {
        return Err(format!("{what}: expected one top-level chunk, found {}", top.len()));
    }
    Ok(top.remove(0))
}

/// Inspect the mesh file at `path`. `Ok(None)` for anything that is not a
/// `GREF` appearance (plain `MODL`, or a file this pass does not understand —
/// those keep their historical treatment). `Ok(Some)` for a valid appearance.
/// `Err` names the model and the reference for every malformed one.
pub fn inspect(path: &Path) -> Result<Option<SharedModel>, String> {
    let model = path.file_name().map(|s| s.to_string_lossy().into_owned()).unwrap_or_default();
    let data = std::fs::read(path).map_err(|e| format!("model {model}: cannot read: {e}"))?;
    let Ok(top) = top_level(&data, &model) else { return Ok(None) };
    if id_to_str(top.id) != "MODL" {
        return Ok(None);
    }
    let subs = read_chunks(&top.payload).map_err(|e| format!("model {model}: {e}"))?;
    let find = |tag: &str| subs.iter().filter(|c| id_to_str(c.id) == tag).collect::<Vec<_>>();
    let grefs = find("GREF");
    if grefs.is_empty() {
        return Ok(None);
    }
    let fail = |reference: &str, why: String| format!("model {model} -> geometry {reference}: {why}");
    if grefs.len() > 1 {
        return Err(fail("?", "more than one GREF chunk".into()));
    }
    let gref = parse_gref(&grefs[0].payload).map_err(|e| fail("?", e))?;
    let reference = gref.name.clone();
    check_asmp_name(&reference).map_err(|e| fail(&reference, e))?;
    for tag in ["VRTX", "FACE", "LRIG", "DFRM"] {
        if !find(tag).is_empty() {
            return Err(fail(&reference, format!("a GREF model must not carry {tag}")));
        }
    }
    let uvcl = find("UVCL");
    let matl = find("MATL");
    if uvcl.len() != 1 || matl.len() != 1 {
        return Err(fail(&reference, "needs exactly one UVCL and one MATL chunk".into()));
    }
    if matl[0].payload.is_empty() || matl[0].payload.len() % MATERIAL_SIZE != 0 {
        return Err(fail(&reference, format!("MATL is {} bytes, not a multiple of {MATERIAL_SIZE}",
                                            matl[0].payload.len())));
    }
    let material_count = matl[0].payload.len() / MATERIAL_SIZE;

    let dir = path.parent().unwrap_or(Path::new("."));
    let geometry_path = crate::mesh_bbox::find_case_insensitive(dir, &reference)
        .ok_or_else(|| fail(&reference, format!("geometry file is missing from {}", dir.display())))?;
    let geometry = std::fs::read(&geometry_path).map_err(|e| fail(&reference, format!("cannot read: {e}")))?;
    let top = top_level(&geometry, &reference).map_err(|e| fail(&reference, e))?;
    if id_to_str(top.id) != "GEOM" {
        return Err(fail(&reference, format!("top-level chunk is {}, expected GEOM", id_to_str(top.id))));
    }
    let gsubs = read_chunks(&top.payload).map_err(|e| fail(&reference, e.to_string()))?;
    let tags: Vec<String> = gsubs.iter().map(|c| id_to_str(c.id)).collect();
    if tags.len() != 2 || !tags.contains(&"POSN".to_string()) || !tags.contains(&"FACE".to_string()) {
        return Err(fail(&reference, format!("GEOM must hold exactly POSN and FACE, has {tags:?}")));
    }
    let posn = &gsubs.iter().find(|c| id_to_str(c.id) == "POSN").unwrap().payload;
    let face = &gsubs.iter().find(|c| id_to_str(c.id) == "FACE").unwrap().payload;
    if posn.len() % POSITION_SIZE != 0 || face.len() % FACE_SIZE != 0 {
        return Err(fail(&reference, "POSN or FACE size is not a whole number of records".into()));
    }
    let (n, m) = (posn.len() / POSITION_SIZE, face.len() / FACE_SIZE);
    if n == 0 || m == 0 || n > i16::MAX as usize {
        return Err(fail(&reference, format!("{n} vertices / {m} faces is out of range")));
    }
    if (n as u32, m as u32) != (gref.vertex_count, gref.face_count) {
        return Err(fail(&reference, format!("GREF counts {}/{} do not match geometry {n}/{m}",
                                            gref.vertex_count, gref.face_count)));
    }
    if crc32(posn) != gref.pos_crc32 || crc32(face) != gref.face_crc32 {
        return Err(fail(&reference, "GREF CRC does not match the geometry".into()));
    }
    for (index, f) in face.chunks_exact(FACE_SIZE).enumerate() {
        let v = |i: usize| i16::from_le_bytes([f[i * 2], f[i * 2 + 1]]);
        for corner in 0..3 {
            if v(corner) < 0 || v(corner) as usize >= n {
                return Err(fail(&reference, format!("face {index} vertex index {} is out of range", v(corner))));
            }
        }
        if v(3) < 0 || v(3) as usize >= material_count {
            return Err(fail(&reference, format!("face {index} material {} is out of range ({material_count} materials)", v(3))));
        }
    }
    if uvcl[0].payload.len() != n * APPEARANCE_SIZE {
        return Err(fail(&reference, format!("UVCL holds {} bytes, expected {} for {n} vertices",
                                            uvcl[0].payload.len(), n * APPEARANCE_SIZE)));
    }
    Ok(Some(SharedModel { gref, geometry_path, posn: posn.clone() }))
}

/// For every appearance registered in a room, register the geometry its GREF
/// names in the same room. Runs after every other registration, so each
/// geometry takes the next free index of its room and every packed id
/// assigned before it is unchanged. Returns the number of geometry entries.
pub fn register(assets: &mut AssetRegistry, mesh_dir: &Path) -> Result<usize, String> {
    let models: Vec<(String, i32)> = assets.entries().iter()
        .filter(|(name, _)| name.ends_with(".iff"))
        .cloned()
        .collect();
    // Indices are per (room, type), so walking the models in registration
    // order gives each room's geometry the same ids as a per-room walk would.
    let mut added = 0;
    for (name, id) in &models {
        let Some(path) = crate::mesh_bbox::find_case_insensitive(mesh_dir, name) else { continue };
        let Some(shared) = inspect(&path)? else { continue };
        let before = assets.entries().len();
        let room = room_from_id(*id);
        let geometry_id = assets.add_iff_room(&shared.gref.name, room);
        if assets.entries().len() > before {
            added += 1;
            let slot = if room == ROOM_PERM { "PERM".to_string() } else { format!("RM{room}") };
            eprintln!("  shared geometry {} for {name} in {slot}: {geometry_id:#x} ({})",
                      shared.gref.name, shared.geometry_path.display());
        }
    }
    Ok(added)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixtures() -> PathBuf {
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../tests/fixtures/shared_geometry")
    }

    #[test]
    fn crc32_check_value() {
        assert_eq!(crc32(b"123456789"), 0xCBF4_3926);
    }

    #[test]
    fn real_pier_appearances_validate_and_keep_the_plain_bbox() {
        for stem in ["temple_pier_0", "temple_pier_1"] {
            let shared = fixtures().join(format!("pier-shared/{stem}.iff"));
            let plain = fixtures().join(format!("pier-plain/{stem}.iff"));
            let model = inspect(&shared).unwrap().expect("GREF appearance");
            assert_eq!(model.gref.name, "temple_pier_0_geo.iff");
            assert_eq!((model.gref.vertex_count, model.gref.face_count), (184, 108));
            assert!(inspect(&plain).unwrap().is_none(), "plain MODL is not an appearance");
            let before = crate::mesh_bbox::load(&plain).unwrap().unwrap();
            assert_eq!(crate::mesh_bbox::load(&shared).unwrap(), Some(before), "{stem} bbox");
        }
    }

    #[test]
    fn cube_defects_fail_naming_model_and_reference() {
        let bad = fixtures().join("cube/bad");
        for (case, needle) in [
            ("pos-crc", "CRC"), ("face-crc", "CRC"), ("vertex-count", "counts"),
            ("uvcl-count", "UVCL"), ("face-index", "vertex index"), ("version", "version"),
            ("missing", "missing"), ("material-index", "material"), ("lrig", "LRIG"),
        ] {
            let err = inspect(&bad.join(case).join("cube_a.iff")).expect_err(case);
            assert!(err.starts_with("model cube_a.iff -> geometry "), "{case}: {err}");
            assert!(err.contains(needle), "{case}: {err}");
            if case != "version" {
                assert!(err.contains("cube_"), "{case} names the reference: {err}");
            }
        }
    }

    #[test]
    fn gref_name_limits() {
        let mut payload = vec![0u8; GREF_SIZE];
        payload[0] = 1;
        assert!(parse_gref(&payload).unwrap_err().contains("empty"));
        payload[20..52].copy_from_slice(&[b'a'; 32]);
        assert!(parse_gref(&payload).unwrap_err().contains("longer than 31"));
        payload[51] = 0;
        assert_eq!(parse_gref(&payload).unwrap().name.len(), 31);
        payload[20] = b'A';
        assert!(parse_gref(&payload).unwrap_err().contains("lowercase"));
        assert!(parse_gref(&payload[..51]).unwrap_err().contains("51 bytes"));
        // A 31-character name fits GREF but not the runtime's ASMP entry.
        assert!(check_asmp_name(&"a".repeat(31)).unwrap_err().contains("at most 30"));
        assert!(check_asmp_name(&"a".repeat(30)).is_ok());
    }

    /// Registering geometry must not move any packed id assigned before it.
    #[test]
    fn geometry_registration_keeps_existing_ids() {
        let dir = fixtures().join("pier-shared");
        let build = |shared: bool| {
            let mut assets = AssetRegistry::new();
            assets.add_iff("perm_thing.iff");
            assets.add_iff_room("temple_pier_0.iff", 2);
            assets.add_iff_room("other.iff", 2);
            assets.add_iff_room("temple_pier_1.iff", 2);
            assets.add_iff_room("temple_pier_1.iff", 3);
            assets.add_iff_room("room3_late.iff", 3);
            if shared {
                assert_eq!(register(&mut assets, &dir).unwrap(), 2);
            }
            assets.entries().to_vec()
        };
        let (plain, shared) = (build(false), build(true));
        assert_eq!(&shared[..plain.len()], &plain[..], "existing ids unchanged");
        assert_eq!(&shared[plain.len()..], &[
            ("temple_pier_0_geo.iff".to_string(), crate::asset_registry::pack(2, 3, 4)),
            ("temple_pier_0_geo.iff".to_string(), crate::asset_registry::pack(3, 3, 3)),
        ]);
    }

    #[test]
    fn registration_fails_the_build_on_a_bad_reference() {
        let err = {
            let mut assets = AssetRegistry::new();
            assets.add_iff_room("cube_a.iff", 0);
            register(&mut assets, &fixtures().join("cube/bad/pos-crc")).unwrap_err()
        };
        assert!(err.contains("model cube_a.iff -> geometry cube_geo.iff"), "{err}");
    }
}
