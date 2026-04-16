//! Load `.oad` schema files and compute the per-object OAD data block size
//! for each class.
//!
//! Per-object OAD layout (matches `wftools/iff2lvl/oad.cc` + `lvldump-rs/src/oad.rs`):
//!
//! ```text
//! For each OAD entry in schema order:
//!   CommonBlock     → write 4-byte offset into common data; next fields read
//!                     from common data, not per-object
//!   EndCommon       → back to per-object data
//!   inside common   → 0 bytes here (stored in common data)
//!   outside common  → `field_size(entry)` bytes, per ButtonType
//! ```

use std::path::Path;
use wf_oad::{ButtonType, OadEntry, OadFile};

use std::collections::HashMap;

use crate::common_block::CommonBlockBuilder;
use crate::lev_parser::{field_data, field_str_value, LevObject};

/// Per-class schema bundle — maps a class name to its parsed `.oad` file.
pub struct OadSchemas {
    by_class: std::collections::HashMap<String, OadFile>,
}

impl OadSchemas {
    pub fn empty() -> Self {
        Self { by_class: std::collections::HashMap::new() }
    }

    /// Load every `<class>.oad` file found in `dir`.  Class name is the file
    /// stem, lowercased, to match how objects.lc records class identity.
    ///
    /// `class_index` resolves a class name to its `objects.lc` index; used to
    /// patch the `MovementClass` field's default, which the .oas authors
    /// specify via the `@e0(OASNAME_KIND)` prep macro (currently bottoms out
    /// to 0 in oas2oad-rs but should be the class's KIND = its type index).
    pub fn load_dir(
        dir: &Path,
        class_index: impl Fn(&str) -> Option<i32>,
    ) -> Result<Self, String> {
        let mut by_class = std::collections::HashMap::new();
        for entry in std::fs::read_dir(dir).map_err(|e| format!("read_dir {}: {e}", dir.display()))? {
            let entry = entry.map_err(|e| e.to_string())?;
            let path = entry.path();
            if path.extension().and_then(|s| s.to_str()) != Some("oad") {
                continue;
            }
            let stem = path
                .file_stem()
                .and_then(|s| s.to_str())
                .map(|s| s.to_lowercase())
                .unwrap_or_default();
            if stem.is_empty() || stem == "common" {
                continue;  // skip common.oad — handled separately for common block fields
            }
            let bytes = std::fs::read(&path).map_err(|e| format!("read {}: {e}", path.display()))?;
            let mut oad = OadFile::read(&mut std::io::Cursor::new(&bytes))
                .map_err(|e| format!("parse {}: {e}", path.display()))?;
            // Patch MovementClass default — see doc comment above.
            if let Some(idx) = class_index(&stem) {
                for field in &mut oad.entries {
                    if field.name_str() == "MovementClass" {
                        field.def = idx;
                        break;
                    }
                }
            }
            by_class.insert(stem, oad);
        }
        Ok(Self { by_class })
    }

    pub fn get(&self, class: &str) -> Option<&OadFile> {
        self.by_class.get(&class.to_lowercase())
    }
}

/// Field binary size when stored in either per-object OAD or common block.
/// Matches `wftools/lvldump-rs/src/oad.rs::field_size` (which is itself a port
/// of `wftools/iff2lvl/oad.cc::QObjectAttributeDataEntry::SizeOfOnDisk`).
pub fn field_size(entry: &OadEntry) -> usize {
    match entry.button_type {
        ButtonType::Fixed32
        | ButtonType::Int32
        | ButtonType::ObjectReference
        | ButtonType::Filename
        | ButtonType::CommonBlock
        | ButtonType::MeshName
        | ButtonType::ClassReference => 4,

        ButtonType::Fixed16 | ButtonType::Int16 => 2,
        ButtonType::Int8 => 1,
        ButtonType::String => entry.len as usize,

        ButtonType::XData => {
            // Action ∈ [1..=4] (COPY/OBJECTLIST/CONTEXTUALANIMATIONLIST/SCRIPT)
            // burns 4 bytes; IGNORE (0) and anything else burns 0.
            let action = entry.xdata_conversion_action();
            if (1..=4).contains(&action) { 4 } else { 0 }
        }

        _ => 0,
    }
}

/// Compute the per-object OAD data size for a class: sum of field sizes for
/// every entry that lives *outside* a COMMONBLOCK (including the COMMONBLOCK
/// marker itself, which contributes a 4-byte offset into the common block).
pub fn per_object_size(schema: &OadFile) -> usize {
    let mut size = 0;
    let mut in_common = false;
    for entry in &schema.entries {
        match entry.button_type {
            ButtonType::CommonBlock => {
                // Marker itself always writes its 4-byte offset.
                size += 4;
                in_common = true;
            }
            ButtonType::EndCommon => {
                in_common = false;
            }
            _ => {
                if !in_common {
                    size += field_size(entry);
                }
            }
        }
    }
    size
}

// ── Per-object OAD payload serialization ─────────────────────────────────────

/// Emit the binary OAD data block for one object.
///
/// Walks the class schema in order:
///
/// - Entries *outside* any COMMONBLOCK: their bytes are written into the
///   per-object OAD payload, with values looked up from the .lev sub-chunks.
/// - COMMONBLOCK marker: collects the enclosed section's bytes into a temp
///   buffer, hands them to `common` for dedup, then writes the returned offset
///   into the per-object payload as a 4-byte LE i32.
/// - ENDCOMMON marker: closes the common section.
///
/// `common` is the level's common data area.  XDATA script fields append
/// their text bytes here too (separately from CB sections), and their 4-byte
/// value in the CB section is the returned offset.
pub fn serialize_oad_data(
    schema: &OadFile,
    obj: &LevObject,
    common: &mut CommonBlockBuilder,
    name_to_idx: &HashMap<String, i32>,
) -> Vec<u8> {
    let mut out = Vec::new();
    let mut i = 0;
    while i < schema.entries.len() {
        let entry = &schema.entries[i];
        match entry.button_type {
            ButtonType::CommonBlock => {
                // Gather fields up to the next EndCommon into a section buffer.
                // XDATA fields serialize by appending their text to `common`
                // first, then writing the returned offset — so we pass the
                // builder down into the per-field serializer.
                let mut section = Vec::new();
                let mut j = i + 1;
                while j < schema.entries.len()
                    && schema.entries[j].button_type != ButtonType::EndCommon
                {
                    let e = &schema.entries[j];
                    serialize_entry(&mut section, e, obj, common, true, name_to_idx);
                    j += 1;
                }
                while section.len() % 4 != 0 { section.push(0); }
                let offset = common.add(&section);
                push_i32(&mut out, offset);
                i = j + 1;  // skip past EndCommon
            }
            ButtonType::EndCommon => {
                // Stray EndCommon with no matching CommonBlock — skip.
                i += 1;
            }
            _ => {
                serialize_entry(&mut out, entry, obj, common, false, name_to_idx);
                i += 1;
            }
        }
    }
    out
}

fn serialize_entry(
    out: &mut Vec<u8>,
    entry: &OadEntry,
    obj: &LevObject,
    common: &mut CommonBlockBuilder,
    in_common: bool,
    name_to_idx: &HashMap<String, i32>,
) {
    let key = entry.name_str();
    let chunk = obj.find_field(key);

    match entry.button_type {
        ButtonType::Fixed32 | ButtonType::Int32 => {
            let value = int_value(entry, chunk, obj);
            push_i32(out, value);
        }
        ButtonType::Fixed16 | ButtonType::Int16 => {
            let value = int_value(entry, chunk, obj) as i16;
            out.extend_from_slice(&value.to_le_bytes());
        }
        ButtonType::Int8 => {
            let value = int_value(entry, chunk, obj) as i8;
            out.push(value as u8);
        }
        ButtonType::String => {
            let text = chunk.map(field_str_value).unwrap_or_default();
            let len = entry.len as usize;
            let bytes = text.as_bytes();
            let copy = bytes.len().min(len);
            out.extend_from_slice(&bytes[..copy]);
            out.extend(std::iter::repeat(0u8).take(len - copy));
        }
        ButtonType::ObjectReference | ButtonType::ClassReference => {
            // iff2lvl / max2lvl resolve ObjectReference by looking up the
            // .lev sub-chunk's nested STR value (the referenced object's
            // name) in the level's object-name table.  When no name is
            // given or it can't be resolved, iff2lvl/oad.cc:1677 uses
            // default 0 outside common blocks; level3.cc:99 uses -1 inside.
            let text = chunk.map(field_str_value).unwrap_or_default();
            let resolved = if !text.is_empty() {
                name_to_idx.get(&text).copied()
            } else {
                None
            };
            let val = resolved.unwrap_or(if in_common { -1 } else { 0 });
            push_i32(out, val);
        }
        ButtonType::Filename | ButtonType::MeshName => {
            // Asset IDs come from asset.inc; unresolved = 0.
            push_i32(out, 0);
        }
        ButtonType::XData => {
            // XData fields (actions 1..=4) materialise as a 4-byte offset
            // into the common data area.  The "empty" case differs by
            // action — mirrors `wftools/iff2lvl/level4.cc::AddXDataToCommonData`:
            //
            //   XDATA_COPY (1) / XDATA_SCRIPT (4):
            //     iff2lvl writes -1 sentinel when no script/data.  Engine
            //     guards with `!= -1` (actor.cc:294, :594) and asserts -1
            //     on classes that shouldn't carry scripts (actor.cc:604).
            //
            //   XDATA_OBJECTLIST (2):
            //     iff2lvl always emits at least an empty-list block — a
            //     single 0xffffffff terminator — and stores the offset of
            //     that block.  Engine iterates the list until terminator,
            //     so we need a valid offset pointing at a terminator.
            //
            //   XDATA_CONTEXTUALANIMATIONLIST (3):
            //     iff2lvl writes -1 sentinel when no list.
            let action = entry.xdata_conversion_action();
            if (1..=4).contains(&action) {
                let text = chunk
                    .map(crate::lev_parser::field_str_value)
                    .unwrap_or_default();
                let value = if text.is_empty() {
                    match action {
                        1 | 3 | 4 => -1,
                        2 => common.add(&0xffffffffu32.to_le_bytes()),
                        _ => -1,
                    }
                } else {
                    let mut bytes = text.into_bytes();
                    bytes.push(0);
                    while bytes.len() % 4 != 0 { bytes.push(0); }
                    common.add(&bytes)
                };
                push_i32(out, value);
            }
        }
        _ => {}  // size-0 entries (PropertySheet, GroupStart, GroupStop, flags)
    }
}

/// Resolve an integer-valued field (I32/I16/I8 with or without enum items)
/// from the .lev chunk, falling back to the schema default.
///
/// - If the entry has enum items ("A|B|C") and the .lev chunk carries a nested
///   STR label, return the matching item's index.
/// - Otherwise, if the chunk has a DATA payload, return its value as i32.
/// - Otherwise, return the schema default.
fn int_value(entry: &OadEntry, chunk: Option<&wf_iff::IffChunk>, _obj: &LevObject) -> i32 {
    let Some(chunk) = chunk else {
        return entry.def;
    };

    // Enum-style: items come from the entry's String, pipe-separated.
    let items = entry.string_str();
    if !items.is_empty() && items.contains('|') {
        let label = field_str_value(chunk);
        if !label.is_empty() {
            if let Some(idx) = items.split('|').position(|it| it.trim() == label.trim()) {
                return idx as i32;
            }
        }
    }

    // Numeric: read the DATA payload as a little-endian i32 (or shorter width).
    let data = field_data(chunk);
    if data.len() >= 4 {
        i32::from_le_bytes(data[..4].try_into().unwrap())
    } else if data.len() >= 2 {
        i16::from_le_bytes(data[..2].try_into().unwrap()) as i32
    } else if data.len() == 1 {
        data[0] as i8 as i32
    } else {
        entry.def
    }
}

fn push_i32(out: &mut Vec<u8>, v: i32) {
    out.extend_from_slice(&v.to_le_bytes());
}
