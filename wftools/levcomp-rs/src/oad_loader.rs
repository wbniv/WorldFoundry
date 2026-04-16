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
    pub fn load_dir(dir: &Path) -> Result<Self, String> {
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
            let oad = OadFile::read(&mut std::io::Cursor::new(&bytes))
                .map_err(|e| format!("parse {}: {e}", path.display()))?;
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
