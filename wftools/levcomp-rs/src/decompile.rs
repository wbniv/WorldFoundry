//! Decompile a compiled LVAS `.iff` file back to a `.lev` text IFF.
//!
//! Reads the binary level format (`_LevelOnDisk` + `_ObjectOnDisk` structs)
//! and emits text IFF that can be re-consumed by `iffcomp-rs` + `levcomp`.
//!
//! Usage:
//!   levcomp decompile <input.iff> <objects.lc> [--oad-dir <dir>] [-o <output.lev>]

use std::collections::HashMap;
use std::path::Path;

use wf_iff::{id_to_str, read_chunks};
use wf_oad::{ButtonType, OadFile};

use crate::lc_parser::ClassMap;
use crate::oad_loader::{field_size, OadSchemas};

// ── Binary layout constants (mirror of lvl_writer.rs / level.rs) ─────────────

const OBJ_TYPE_OFF:   usize = 0;
const OBJ_X_OFF:      usize = 4;
const OBJ_Y_OFF:      usize = 8;
const OBJ_Z_OFF:      usize = 12;
// scale at 16..28 — not used during decompile
const OBJ_ROT_A_OFF:  usize = 28;  // u16
const OBJ_ROT_B_OFF:  usize = 30;  // u16
const OBJ_ROT_C_OFF:  usize = 32;  // u16
const OBJ_COARSE_OFF: usize = 36;  // i32×6
const OBJ_OADSIZE_OFF: usize = 66; // i16
const OBJ_HEADER_SIZE: usize = 68;

// ── byte helpers ──────────────────────────────────────────────────────────────

fn ri32(data: &[u8], off: usize) -> i32 {
    i32::from_le_bytes(data[off..off + 4].try_into().unwrap())
}

fn ru16(data: &[u8], off: usize) -> u16 {
    u16::from_le_bytes(data[off..off + 2].try_into().unwrap())
}

fn ri16(data: &[u8], off: usize) -> i16 {
    i16::from_le_bytes(data[off..off + 2].try_into().unwrap())
}

// ── fixed-point formatting ─────────────────────────────────────────────────────

/// Format a raw fixed32 value (i32) as `V(1.15.16)` matching snowgoons.lev.
fn fmt_fx32(raw: i32) -> String {
    let v = raw as f64 / 65536.0;
    format!("{:.16}(1.15.16)", v)
}

/// Inverse of `radians_fx_to_u16_revs` (lvl_writer.rs):
/// u16 revolutions → fixed32 radians.
fn u16_revs_to_radians_fx(v: u16) -> i32 {
    const TWO_PI: f64 = std::f64::consts::TAU;
    let revs = v as f64 / 65536.0;
    let radians = revs * TWO_PI;
    (radians * 65536.0) as i32
}

// ── NUL-terminated string helper ──────────────────────────────────────────────

fn read_cstr_nul(data: &[u8]) -> String {
    let end = data.iter().position(|&b| b == 0).unwrap_or(data.len());
    String::from_utf8_lossy(&data[..end]).into_owned()
}

// ── ASMP asset map ────────────────────────────────────────────────────────────

/// Parse the ASMP chunk payload into a map from packed-asset-ID → filename.
///
/// Format: loop { i32 packed_id; IFF 'STR' chunk with filename }
fn parse_asmp(payload: &[u8]) -> HashMap<i32, String> {
    let mut map = HashMap::new();
    let mut pos = 0;
    while pos + 4 <= payload.len() {
        let packed_id = ri32(payload, pos);
        pos += 4;
        // Try to parse an IFF chunk for the STR
        if pos + 8 > payload.len() {
            break;
        }
        let chunk_id_bytes = &payload[pos..pos + 4];
        let chunk_tag: String = chunk_id_bytes.iter().map(|&b| b as char).collect();
        let chunk_size = u32::from_le_bytes(payload[pos + 4..pos + 8].try_into().unwrap()) as usize;
        pos += 8;
        if pos + chunk_size > payload.len() {
            break;
        }
        let str_bytes = &payload[pos..pos + chunk_size];
        let filename = read_cstr_nul(str_bytes);
        let aligned = (chunk_size + 3) & !3;
        pos += aligned;

        if chunk_tag.trim_end() == "STR" || chunk_tag.starts_with("STR") {
            map.insert(packed_id, filename);
        }
    }
    map
}

// ── Object name table ─────────────────────────────────────────────────────────

/// Build a table of object names: index_in_level (1-based) → "ClassName_N".
/// Object at array index N gets name `{class_name}_{N}`.
fn build_object_names(
    lv_data: &[u8],
    obj_count: usize,
    classes: &ClassMap,
) -> Vec<String> {
    let objects_offset = ri32(lv_data, 8) as usize;
    let obj_arr = &lv_data[objects_offset..];

    let mut names = Vec::with_capacity(obj_count);
    // Index 0 = NULL_Object, skipped; indices 1..obj_count are real objects
    // We push "" for index 0, then names for 1..obj_count
    names.push(String::new()); // placeholder for NULL_Object
    for index in 1..obj_count {
        let obj_offset = ri32(obj_arr, index * 4) as usize;
        let obj = &lv_data[obj_offset..];
        let obj_type = ri16(obj, OBJ_TYPE_OFF) as usize;
        let class_name = classes.names.get(obj_type)
            .cloned()
            .unwrap_or_else(|| format!("type{}", obj_type));
        names.push(format!("{}_{}", class_name, index));
    }
    names
}

// ── OAD field decoding ────────────────────────────────────────────────────────

struct OadReader<'a> {
    per_obj: &'a [u8],
    common: &'a [u8],
    per_obj_cursor: usize,
    common_cursor: usize,
    in_common: bool,
}

impl<'a> OadReader<'a> {
    fn new(per_obj: &'a [u8], common: &'a [u8]) -> Self {
        Self {
            per_obj,
            common,
            per_obj_cursor: 0,
            common_cursor: 0,
            in_common: false,
        }
    }

    fn read_bytes(&mut self, n: usize) -> &'a [u8] {
        if self.in_common {
            let start = self.common_cursor;
            self.common_cursor += n;
            if self.common_cursor <= self.common.len() {
                &self.common[start..self.common_cursor]
            } else {
                &[]
            }
        } else {
            let start = self.per_obj_cursor;
            self.per_obj_cursor += n;
            if self.per_obj_cursor <= self.per_obj.len() {
                &self.per_obj[start..self.per_obj_cursor]
            } else {
                &[]
            }
        }
    }

    fn enter_common(&mut self) {
        if self.per_obj_cursor + 4 <= self.per_obj.len() {
            let offset = ri32(self.per_obj, self.per_obj_cursor) as usize;
            self.per_obj_cursor += 4;
            self.common_cursor = offset;
            self.in_common = true;
        }
    }

    fn leave_common(&mut self) {
        self.in_common = false;
    }
}

// ── Per-object .lev text emission ─────────────────────────────────────────────

struct DecompileCtx<'a> {
    #[allow(dead_code)]
    classes: &'a ClassMap,
    #[allow(dead_code)]
    schemas: &'a OadSchemas,
    asset_map: &'a HashMap<i32, String>,
    obj_names: &'a Vec<String>,
}

/// Emit all field chunks for one object's OAD data.
fn emit_oad_fields(
    schema: &OadFile,
    oad_data: &[u8],
    common: &[u8],
    ctx: &DecompileCtx,
    out: &mut String,
) {
    let mut reader = OadReader::new(oad_data, common);
    let mut i = 0;
    while i < schema.entries.len() {
        let entry = &schema.entries[i];
        match entry.button_type {
            ButtonType::CommonBlock => {
                reader.enter_common();
                i += 1;
                continue;
            }
            ButtonType::EndCommon => {
                reader.leave_common();
                i += 1;
                continue;
            }
            // Zero-size markers — skip without emitting or consuming bytes
            ButtonType::PropertySheet
            | ButtonType::NoInstances
            | ButtonType::NoMesh
            | ButtonType::SingleInstance
            | ButtonType::Template
            | ButtonType::ExtractCamera
            | ButtonType::ExtractCamera2
            | ButtonType::ExtractCameraNew
            | ButtonType::ExtractLight
            | ButtonType::Room
            | ButtonType::GroupStart
            | ButtonType::GroupStop
            | ButtonType::Shortcut
            | ButtonType::Waveform
            | ButtonType::CameraReference
            | ButtonType::LightReference
            | ButtonType::Unknown(_) => {
                // Field size 0 — no bytes consumed, no chunk emitted
                i += 1;
                continue;
            }
            _ => {}
        }

        let name = entry.name_str();
        let sz = field_size(entry);

        match entry.button_type {
            ButtonType::Fixed32 => {
                let raw_bytes = reader.read_bytes(sz);
                let raw = if raw_bytes.len() >= 4 {
                    ri32(raw_bytes, 0)
                } else {
                    entry.def
                };
                let v = raw as f64 / 65536.0;
                out.push_str(&format!(
                    "\t\t{{ 'FX32' \n\
                     \t\t\t{{ 'NAME' \"{name}\" \n\
                     \t\t\t}}\n\
                     \t\t\t{{ 'DATA' {val} \n\
                     \t\t\t}}\n\
                     \t\t\t{{ 'STR' \"{plain}\" \n\
                     \t\t\t}}\n\
                     \t\t}}\n",
                    name = name,
                    val = fmt_fx32(raw),
                    plain = format!("{}", v),
                ));
            }
            ButtonType::Fixed16 => {
                let raw_bytes = reader.read_bytes(sz);
                let raw = if raw_bytes.len() >= 2 {
                    i16::from_le_bytes(raw_bytes[..2].try_into().unwrap()) as i32
                } else {
                    entry.def
                };
                let v = raw as f64 / 65536.0;
                out.push_str(&format!(
                    "\t\t{{ 'FX32' \n\
                     \t\t\t{{ 'NAME' \"{name}\" \n\
                     \t\t\t}}\n\
                     \t\t\t{{ 'DATA' {val} \n\
                     \t\t\t}}\n\
                     \t\t\t{{ 'STR' \"{plain}\" \n\
                     \t\t\t}}\n\
                     \t\t}}\n",
                    name = name,
                    val = fmt_fx32(raw),
                    plain = format!("{}", v),
                ));
            }
            ButtonType::Int32 => {
                let raw_bytes = reader.read_bytes(sz);
                let raw = if raw_bytes.len() >= 4 {
                    ri32(raw_bytes, 0)
                } else {
                    entry.def
                };
                let items = entry.string_str();
                // SHOW_AS_DROPMENU (4): enum label stored in string; no DATA chunk.
                // All other showAs values: DATA chunk with integer + STR with decimal.
                if entry.show_as == 4 {
                    let labels: Vec<&str> = items.split('|').collect();
                    let label = labels.get(raw as usize).copied().unwrap_or("");
                    out.push_str(&format!(
                        "\t\t{{ 'I32' \n\
                         \t\t\t{{ 'NAME' \"{name}\" \n\
                         \t\t\t}}\n\
                         \t\t\t{{ 'STR' \"{label}\" \n\
                         \t\t\t}}\n\
                         \t\t}}\n",
                        name = name,
                        label = label,
                    ));
                } else {
                    // DATA + STR with integer value; items string appears as DATA comment.
                    out.push_str(&format!(
                        "\t\t{{ 'I32' \n\
                         \t\t\t{{ 'NAME' \"{name}\" \n\
                         \t\t\t}}\n\
                         \t\t\t{{ 'DATA' {raw}l  //{items}\n\
                         \t\t\t\t\t\n\
                         \t\t\t}}\n\
                         \t\t\t{{ 'STR' \"{raw}\" \n\
                         \t\t\t}}\n\
                         \t\t}}\n",
                        name = name,
                        raw = raw,
                        items = items,
                    ));
                }
            }
            ButtonType::Int16 => {
                let raw_bytes = reader.read_bytes(sz);
                let raw = if raw_bytes.len() >= 2 {
                    i16::from_le_bytes(raw_bytes[..2].try_into().unwrap()) as i32
                } else {
                    entry.def
                };
                let items = entry.string_str();
                // Same showAs logic as Int32.
                if entry.show_as == 4 {
                    let labels: Vec<&str> = items.split('|').collect();
                    let label = labels.get(raw as usize).copied().unwrap_or("");
                    out.push_str(&format!(
                        "\t\t{{ 'I32' \n\
                         \t\t\t{{ 'NAME' \"{name}\" \n\
                         \t\t\t}}\n\
                         \t\t\t{{ 'STR' \"{label}\" \n\
                         \t\t\t}}\n\
                         \t\t}}\n",
                        name = name,
                        label = label,
                    ));
                } else {
                    out.push_str(&format!(
                        "\t\t{{ 'I32' \n\
                         \t\t\t{{ 'NAME' \"{name}\" \n\
                         \t\t\t}}\n\
                         \t\t\t{{ 'DATA' {raw}l  //{items}\n\
                         \t\t\t\t\t\n\
                         \t\t\t}}\n\
                         \t\t\t{{ 'STR' \"{raw}\" \n\
                         \t\t\t}}\n\
                         \t\t}}\n",
                        name = name,
                        raw = raw,
                        items = items,
                    ));
                }
            }
            ButtonType::Int8 => {
                let raw_bytes = reader.read_bytes(1);
                let raw = if !raw_bytes.is_empty() {
                    raw_bytes[0] as i8 as i32
                } else {
                    entry.def
                };
                let items = entry.string_str();
                if entry.show_as == 4 {
                    let labels: Vec<&str> = items.split('|').collect();
                    let label = labels.get(raw as usize).copied().unwrap_or("");
                    out.push_str(&format!(
                        "\t\t{{ 'I32' \n\
                         \t\t\t{{ 'NAME' \"{name}\" \n\
                         \t\t\t}}\n\
                         \t\t\t{{ 'STR' \"{label}\" \n\
                         \t\t\t}}\n\
                         \t\t}}\n",
                        name = name,
                        label = label,
                    ));
                } else {
                    out.push_str(&format!(
                        "\t\t{{ 'I32' \n\
                         \t\t\t{{ 'NAME' \"{name}\" \n\
                         \t\t\t}}\n\
                         \t\t\t{{ 'DATA' {raw}l  //{items}\n\
                         \t\t\t\t\t\n\
                         \t\t\t}}\n\
                         \t\t\t{{ 'STR' \"{raw}\" \n\
                         \t\t\t}}\n\
                         \t\t}}\n",
                        name = name,
                        raw = raw,
                        items = items,
                    ));
                }
            }
            ButtonType::String => {
                let len = entry.len as usize;
                let raw_bytes = reader.read_bytes(len);
                let text = read_cstr_nul(raw_bytes);
                out.push_str(&format!(
                    "\t\t{{ 'STR' \n\
                     \t\t\t{{ 'NAME' \"{name}\" \n\
                     \t\t\t}}\n\
                     \t\t\t{{ 'STR' \"{text}\" \n\
                     \t\t\t}}\n\
                     \t\t}}\n",
                    name = name,
                    text = text,
                ));
            }
            ButtonType::ObjectReference | ButtonType::ClassReference => {
                let raw_bytes = reader.read_bytes(4);
                let idx = if raw_bytes.len() >= 4 {
                    ri32(raw_bytes, 0)
                } else {
                    0
                };
                // idx is 1-based; look up the object name
                let obj_name = if idx > 0 && (idx as usize) < ctx.obj_names.len() {
                    ctx.obj_names[idx as usize].clone()
                } else {
                    String::new()
                };
                out.push_str(&format!(
                    "\t\t{{ 'STR' \n\
                     \t\t\t{{ 'NAME' \"{name}\" \n\
                     \t\t\t}}\n\
                     \t\t\t{{ 'STR' \"{obj_name}\" \n\
                     \t\t\t}}\n\
                     \t\t}}\n",
                    name = name,
                    obj_name = obj_name,
                ));
            }
            ButtonType::MeshName | ButtonType::Filename => {
                let raw_bytes = reader.read_bytes(4);
                let packed_id = if raw_bytes.len() >= 4 {
                    ri32(raw_bytes, 0)
                } else {
                    0
                };
                let filename = ctx.asset_map.get(&packed_id)
                    .cloned()
                    .unwrap_or_default();
                out.push_str(&format!(
                    "\t\t{{ 'FILE' \n\
                     \t\t\t{{ 'NAME' \"{name}\" \n\
                     \t\t\t}}\n\
                     \t\t\t{{ 'STR' \"{filename}\" \n\
                     \t\t\t}}\n\
                     \t\t}}\n",
                    name = name,
                    filename = filename,
                ));
            }
            ButtonType::XData => {
                let action = entry.xdata_conversion_action();
                if !(1..=4).contains(&action) {
                    i += 1;
                    continue;
                }
                let raw_bytes = reader.read_bytes(4);
                let offset = if raw_bytes.len() >= 4 {
                    ri32(raw_bytes, 0)
                } else {
                    -1
                };
                match action {
                    4 | 1 | 3 => {
                        // SCRIPT / COPY / CONTEXTUALANIMATIONLIST
                        // offset = -1 means no script; else read NUL-term string from common
                        let text = if offset >= 0 && (offset as usize) < common.len() {
                            let s = read_cstr_nul(&common[offset as usize..]);
                            s
                        } else {
                            String::new()
                        };
                        // Emit as STR field, splitting on \n for multi-line scripts
                        if text.contains('\n') {
                            out.push_str(&format!(
                                "\t\t{{ 'STR' \n\
                                 \t\t\t{{ 'NAME' \"{name}\" \n\
                                 \t\t\t}}\n\
                                 \t\t\t{{ 'STR' ",
                                name = name,
                            ));
                            let parts: Vec<&str> = text.split('\n').collect();
                            for (pi, part) in parts.iter().enumerate() {
                                if pi < parts.len() - 1 {
                                    out.push_str(&format!("\"{}\\n\"\n", part));
                                } else if !part.is_empty() {
                                    out.push_str(&format!("\"{}\"", part));
                                } else {
                                    out.push_str("\"\"");
                                }
                            }
                            out.push_str("\n\t\t\t}\n\t\t}\n");
                        } else {
                            out.push_str(&format!(
                                "\t\t{{ 'STR' \n\
                                 \t\t\t{{ 'NAME' \"{name}\" \n\
                                 \t\t\t}}\n\
                                 \t\t\t{{ 'STR' \"{text}\" \n\
                                 \t\t\t}}\n\
                                 \t\t}}\n",
                                name = name,
                                text = text,
                            ));
                        }
                    }
                    2 => {
                        // OBJECTLIST — emit empty string
                        out.push_str(&format!(
                            "\t\t{{ 'STR' \n\
                             \t\t\t{{ 'NAME' \"{name}\" \n\
                             \t\t\t}}\n\
                             \t\t\t{{ 'STR' \"\" \n\
                             \t\t\t}}\n\
                             \t\t}}\n",
                            name = name,
                        ));
                    }
                    _ => {}
                }
            }
            _ => {
                // Consume bytes for any other non-zero-size types
                if sz > 0 {
                    reader.read_bytes(sz);
                }
            }
        }
        i += 1;
    }
}

// ── Top-level decompile ───────────────────────────────────────────────────────

pub fn run(
    iff_path: &Path,
    lc_path: &Path,
    oad_dir: Option<&Path>,
    out_path: &Path,
) -> Result<(), String> {
    // ── Load and parse LVAS IFF ───────────────────────────────────────────────
    let iff_data = std::fs::read(iff_path)
        .map_err(|e| format!("cannot read {}: {}", iff_path.display(), e))?;

    // The file is a top-level IFF chunk; its payload contains nested chunks.
    let top_chunks = read_chunks(&iff_data)
        .map_err(|e| format!("IFF parse error in {}: {}", iff_path.display(), e.message))?;

    let top = top_chunks.first()
        .ok_or_else(|| format!("no chunks in {}", iff_path.display()))?;

    let inner_chunks = read_chunks(&top.payload)
        .map_err(|e| format!("IFF inner parse error: {}", e.message))?;

    // The LVAS chunk is the container that holds TOC, ASMP, LVL, etc.
    // Structure: L4 → [ALGN, RAM, ALGN, LVAS]
    //            LVAS → [TOC, ALGN, ASMP, ALGN, LVL, PERM, RM0, RM1, ...]
    // So we need to recurse into LVAS to find LVL and ASMP.
    let lvas_chunks_storage;
    let search_chunks: &[wf_iff::IffChunk] = if let Some(lvas) = inner_chunks.iter()
        .find(|c| id_to_str(c.id) == "LVAS")
    {
        lvas_chunks_storage = read_chunks(&lvas.payload)
            .map_err(|e| format!("IFF LVAS parse error: {}", e.message))?;
        &lvas_chunks_storage
    } else {
        // Fallback: search inner_chunks directly (simpler files may omit LVAS)
        &inner_chunks
    };

    // Find LVL and ASMP chunks
    let lvl_chunk = search_chunks.iter()
        .find(|c| id_to_str(c.id) == "LVL")
        .ok_or_else(|| "no LVL chunk in IFF (looked in L4 → LVAS)".to_string())?;

    let asmp_chunk = search_chunks.iter()
        .find(|c| id_to_str(c.id) == "ASMP");

    let lv_data: &[u8] = &lvl_chunk.payload;

    // ── Parse ASMP ────────────────────────────────────────────────────────────
    let asset_map: HashMap<i32, String> = asmp_chunk
        .map(|c| parse_asmp(&c.payload))
        .unwrap_or_default();

    // ── Parse LVL header ─────────────────────────────────────────────────────
    if lv_data.len() < 52 {
        return Err(format!("LVL chunk too short: {} bytes", lv_data.len()));
    }

    let version      = ri32(lv_data, 0);
    let obj_count    = ri32(lv_data, 4) as usize;
    let objects_off  = ri32(lv_data, 8) as usize;
    let common_off   = ri32(lv_data, 48) as usize;
    let common_len   = ri32(lv_data, 44) as usize;

    eprintln!("  LVL version {} / {} objects", version, obj_count);

    let common: &[u8] = if common_len > 0 && common_off + common_len <= lv_data.len() {
        &lv_data[common_off..common_off + common_len]
    } else {
        &[]
    };

    // ── Load objects.lc ───────────────────────────────────────────────────────
    let classes = crate::lc_parser::load(lc_path)
        .map_err(|e| format!("lc error: {}", e))?;
    eprintln!("  loaded {} classes", classes.names.len());

    // ── Load OAD schemas ──────────────────────────────────────────────────────
    let schemas = if let Some(d) = oad_dir {
        let s = OadSchemas::load_dir(d)
            .map_err(|e| format!("OAD error: {}", e))?;
        eprintln!("  loaded OAD schemas");
        s
    } else {
        OadSchemas::empty()
    };

    // ── Build object name table ───────────────────────────────────────────────
    let obj_names = build_object_names(lv_data, obj_count, &classes);

    let ctx = DecompileCtx {
        classes: &classes,
        schemas: &schemas,
        asset_map: &asset_map,
        obj_names: &obj_names,
    };

    let obj_arr = &lv_data[objects_off..];

    // ── Emit text IFF ─────────────────────────────────────────────────────────
    let mut out = String::new();
    out.push_str("{ 'LVL' \n");

    // Start at index 1 — index 0 is NULL_Object
    for index in 1..obj_count {
        let obj_offset = ri32(obj_arr, index * 4) as usize;
        if obj_offset + OBJ_HEADER_SIZE > lv_data.len() {
            eprintln!("  warning: object {} offset {} out of range, skipping", index, obj_offset);
            continue;
        }
        let obj = &lv_data[obj_offset..];

        let obj_type   = ri16(obj, OBJ_TYPE_OFF) as usize;
        let oad_size   = ri16(obj, OBJ_OADSIZE_OFF) as usize;

        let class_name = classes.names.get(obj_type)
            .cloned()
            .unwrap_or_else(|| format!("type{}", obj_type));

        let obj_name = obj_names.get(index)
            .cloned()
            .unwrap_or_else(|| format!("{}_{}", class_name, index));

        // Position (fixed32)
        let px = ri32(obj, OBJ_X_OFF);
        let py = ri32(obj, OBJ_Y_OFF);
        let pz = ri32(obj, OBJ_Z_OFF);

        // Rotation: u16 revolutions → fixed32 radians
        let ra_u16 = ru16(obj, OBJ_ROT_A_OFF);
        let rb_u16 = ru16(obj, OBJ_ROT_B_OFF);
        let rc_u16 = ru16(obj, OBJ_ROT_C_OFF);
        let ra = u16_revs_to_radians_fx(ra_u16);
        let rb = u16_revs_to_radians_fx(rb_u16);
        let rc = u16_revs_to_radians_fx(rc_u16);

        // Bounding box (6× fixed32)
        let bbox_min = [
            ri32(obj, OBJ_COARSE_OFF),
            ri32(obj, OBJ_COARSE_OFF + 4),
            ri32(obj, OBJ_COARSE_OFF + 8),
        ];
        let bbox_max = [
            ri32(obj, OBJ_COARSE_OFF + 12),
            ri32(obj, OBJ_COARSE_OFF + 16),
            ri32(obj, OBJ_COARSE_OFF + 20),
        ];

        out.push_str("\t{ 'OBJ' \n");

        // NAME
        out.push_str(&format!("\t\t{{ 'NAME' \"{}\" \n\t\t}}\n", obj_name));

        // VEC3 Position
        out.push_str("\t\t{ 'VEC3' \n");
        out.push_str("\t\t\t{ 'NAME' \"Position\" \n\t\t\t}\n");
        out.push_str(&format!(
            "\t\t\t{{ 'DATA' {} {} {}  //x,y,z\n\t\t\t\t\t\n\t\t\t}}\n",
            fmt_fx32(px), fmt_fx32(py), fmt_fx32(pz)
        ));
        out.push_str("\t\t}\n");

        // EULR Orientation
        out.push_str("\t\t{ 'EULR' \n");
        out.push_str("\t\t\t{ 'NAME' \"Orientation\" \n\t\t\t}\n");
        out.push_str(&format!(
            "\t\t\t{{ 'DATA' {} {} {}  //a,b,c\n\t\t\t\t\t\n\t\t\t}}\n",
            fmt_fx32(ra), fmt_fx32(rb), fmt_fx32(rc)
        ));
        out.push_str("\t\t}\n");

        // BOX3 Global Bounding Box
        out.push_str("\t\t{ 'BOX3' \n");
        out.push_str("\t\t\t{ 'NAME' \"Global Bounding Box\" \n\t\t\t}\n");
        out.push_str(&format!(
            "\t\t\t{{ 'DATA' {} {} {} {} {} {}  //min(x,y,z)-max(x,y,z)\n\t\t\t\t\t\n\t\t\t}}\n",
            fmt_fx32(bbox_min[0]), fmt_fx32(bbox_min[1]), fmt_fx32(bbox_min[2]),
            fmt_fx32(bbox_max[0]), fmt_fx32(bbox_max[1]), fmt_fx32(bbox_max[2]),
        ));
        out.push_str("\t\t}\n");

        // STR Class Name
        out.push_str("\t\t{ 'STR' \n");
        out.push_str("\t\t\t{ 'NAME' \"Class Name\" \n\t\t\t}\n");
        out.push_str(&format!("\t\t\t{{ 'DATA' \"{}\" \n\t\t\t}}\n", class_name));
        out.push_str("\t\t}\n");

        // Per-class OAD fields
        if oad_size > 0 && obj_offset + OBJ_HEADER_SIZE + oad_size <= lv_data.len() {
            let oad_data = &obj[OBJ_HEADER_SIZE..OBJ_HEADER_SIZE + oad_size];
            if let Some(schema) = schemas.get(&class_name) {
                emit_oad_fields(schema, oad_data, common, &ctx, &mut out);
            }
        }

        out.push_str("\t}\n");
    }

    out.push_str("}\n");

    // ── Write output ──────────────────────────────────────────────────────────
    std::fs::write(out_path, out.as_bytes())
        .map_err(|e| format!("cannot write {}: {}", out_path.display(), e))?;

    eprintln!("  wrote {} bytes → {}", out.len(), out_path.display());
    Ok(())
}
