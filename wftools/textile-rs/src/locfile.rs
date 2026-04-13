// locfile.rs — file path searching (port of locfile.cc)
//
// Searches for a file across a semicolon-delimited path list, optionally
// looking inside a per-object subdirectory within each path entry.

use std::path::{Path, PathBuf};

/// Extract the basename without extension (last 4 chars = ".ext").
/// Matches C++ GetFilename behaviour exactly: after last '/', drop last 4 chars.
pub fn file_stem(path: &str) -> &str {
    let s = path.trim_end_matches('\0');
    let start = s.rfind('/').map(|i| i + 1).unwrap_or(0);
    let s = &s[start..];
    if s.len() > 4 { &s[..s.len() - 4] } else { s }
}

/// Extract the 4-character extension including the dot (e.g. ".tga").
/// Matches C++ GetFileExtension behaviour: last 4 chars if len > 4.
pub fn file_ext(path: &str) -> &str {
    let s = path.trim_end_matches('\0');
    if s.len() > 4 { &s[s.len() - 4..] } else { "" }
}

fn try_file(p: &Path) -> bool {
    p.exists()
}

/// Search for `filename` across a semicolon-delimited `search_path`.
/// If `another_dir` is given, also tries each path entry + another_dir.
/// Replicates the search strategy in C++ locateFile().
pub fn locate_file(filename: &str, search_path: &str, another_dir: Option<&str>) -> Option<PathBuf> {
    // 1. Try the filename as-is (absolute or relative to cwd)
    if try_file(Path::new(filename)) {
        return Some(PathBuf::from(filename));
    }

    let stem = file_stem(filename);
    let ext  = file_ext(filename);

    // First pass: reconstruct from stem+ext (strips any leading directory)
    for dir in search_path.split(';') {
        // dir/stem.ext
        let p = Path::new(dir).join(format!("{}{}", stem, ext));
        if try_file(&p) { return Some(p); }

        // dir/anotherDir/stem..ext  (note: C++ code has double-dot bug; replicated)
        if let Some(ad) = another_dir {
            let p = Path::new(dir).join(ad)
                .join(format!("{}.{}", stem, ext));  // stem + "." + ext (which already has dot)
            if try_file(&p) { return Some(p); }
        }
    }

    // Second pass: use the full filename (any original subdirectory preserved)
    for dir in search_path.split(';') {
        // dir/filename
        let p = Path::new(dir).join(filename);
        if try_file(&p) { return Some(p); }

        // dir/anotherDir/filename
        if let Some(ad) = another_dir {
            let p = Path::new(dir).join(ad).join(filename);
            if try_file(&p) { return Some(p); }
        }
    }

    None
}
