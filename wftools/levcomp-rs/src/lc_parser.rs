//! Parse `objects.lc` — a class-index mapping text file.
//!
//! Format (same as read by `wftools/lvldump-rs/src/oad.rs`):
//! ```text
//! Objects.lc: this file is automaticaly generated... DO NOT MODIFY
//! ...
//! {
//!     NullObject
//!     actbox
//!     generator
//!     ...
//! }
//! ```
//! Line 0 (`NullObject`) is a reserved placeholder; real class indices start at 1.

use std::fs;
use std::path::Path;

pub struct ClassMap {
    pub names: Vec<String>,  // lowercase, index 0 = "nullobject"
}

impl ClassMap {
    /// Return the 1-based type index for a class name, or `None`.
    /// Lookup is case-insensitive.
    pub fn index_of(&self, name: &str) -> Option<usize> {
        let lc = name.to_lowercase();
        self.names.iter().position(|n| n == &lc)
    }
}

pub fn load(path: &Path) -> Result<ClassMap, String> {
    let text = fs::read_to_string(path)
        .map_err(|e| format!("cannot read {}: {}", path.display(), e))?;

    let mut lines = text.lines();
    let first = lines.next().unwrap_or("");
    if !first.starts_with("Objects.lc:") {
        return Err(format!("{} is not a .lc file (missing 'Objects.lc:' header)", path.display()));
    }

    let mut names = Vec::new();
    let mut in_block = false;
    for line in lines {
        let t = line.trim();
        if !in_block {
            if t.starts_with('{') {
                in_block = true;
            }
            continue;
        }
        if t.starts_with('}') {
            break;
        }
        if !t.is_empty() {
            names.push(t.to_lowercase());
        }
    }

    if names.first().map(|s| s.as_str()) != Some("nullobject") {
        return Err(format!("{}: first class must be 'NullObject'", path.display()));
    }
    Ok(ClassMap { names })
}
