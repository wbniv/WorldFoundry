// profile.rs — Windows-style INI file reader (port of profile.cc)
//
// Supports:
//   [SectionName]
//   key = value
//
// Case-insensitive section and key matching.
// Strips CR/LF from line ends.

use std::fs;

pub fn get_int(section: &str, key: &str, default: i32, filename: &str) -> i32 {
    if filename.is_empty() {
        return default;
    }
    match find_value(section, key, filename) {
        Some(val) => val.trim().parse().unwrap_or(default),
        None => default,
    }
}

pub fn get_string(section: &str, key: &str, default: &str, filename: &str) -> String {
    if filename.is_empty() {
        return default.to_string();
    }
    match find_value(section, key, filename) {
        Some(val) => val.trim_start().to_string(),
        None => default.to_string(),
    }
}

fn find_value(section: &str, key: &str, filename: &str) -> Option<String> {
    let content = fs::read_to_string(filename).ok()?;
    let section_header = format!("[{}]", section);
    let key_lower = key.to_lowercase();

    let mut in_section = false;
    for line in content.lines() {
        // strip CR
        let line = line.trim_end_matches('\r');

        if line.eq_ignore_ascii_case(&section_header) {
            in_section = true;
            continue;
        }

        if in_section {
            if line.starts_with('[') {
                break; // entered a new section
            }
            // case-insensitive prefix match on key
            if line.to_lowercase().starts_with(&key_lower) {
                if let Some(eq_pos) = line.find('=') {
                    return Some(line[eq_pos + 1..].to_string());
                }
            }
        }
    }
    None
}
