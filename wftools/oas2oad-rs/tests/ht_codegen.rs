//! Oracle test for the `.ht` / `objects.{c,e,h}` codegen pipeline.
//!
//! Runs `wfsource/source/oas/regen-headers.sh` into a temp directory and
//! asserts every committed `.ht` and `objects.{c,e,h}` reproduces byte-for-byte.
//!
//! This guards the two-stage pipeline (prep → raw .pp, awk canonicalizer → .ht)
//! restored in commit 8da3ab9 after cstruct.pl was lost in 61761e4 "slash & burn".
//!
//! Run with `cargo test` from `wftools/oas2oad-rs/` or via `task test-codegen`.

use std::path::{Path, PathBuf};
use std::process::Command;

/// Repo root: `CARGO_MANIFEST_DIR` is `<root>/wftools/oas2oad-rs`.
fn repo_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .ancestors()
        .nth(2)
        .expect("repo root is two levels above the crate")
        .to_path_buf()
}

fn oas_dir() -> PathBuf {
    repo_root().join("wfsource/source/oas")
}

fn regen_script() -> PathBuf {
    oas_dir().join("regen-headers.sh")
}

/// Every committed `.ht` and `objects.{c,e,h}` regenerates byte-for-byte
/// from `.oas` sources via `regen-headers.sh`.
#[test]
fn ht_and_objects_match_golden() {
    let dir = oas_dir();
    let script = regen_script();
    assert!(
        script.exists(),
        "regen-headers.sh not found at {}",
        script.display()
    );

    let tmp = std::env::temp_dir().join(format!("ht-codegen-oracle-{}", std::process::id()));
    std::fs::create_dir_all(&tmp).expect("create temp dir");

    // Run the regen script with OUTDIR = tmp so it never mutates the source tree.
    let result = Command::new("bash")
        .arg(&script)
        .arg(&tmp)
        .status()
        .expect("failed to spawn regen-headers.sh");
    assert!(result.success(), "regen-headers.sh exited with {result}");

    let mut checked = 0usize;
    let mut failures: Vec<String> = Vec::new();

    // Check every committed .ht.
    let mut ht_files: Vec<PathBuf> = std::fs::read_dir(&dir)
        .expect("read oas dir")
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.extension().is_some_and(|x| x == "ht"))
        .collect();
    ht_files.sort();

    for golden in &ht_files {
        let name = golden.file_name().unwrap().to_string_lossy().into_owned();
        let got_path = tmp.join(&name);
        checked += 1;
        let got = std::fs::read(&got_path)
            .unwrap_or_else(|e| panic!("regen did not produce {name}: {e}"));
        let want = std::fs::read(golden).expect("read golden .ht");
        if got != want {
            failures.push(format!(
                "{name}: got {} bytes, golden is {} bytes",
                got.len(),
                want.len()
            ));
        }
    }

    // Check objects.{c,e,h}.
    for name in &["objects.c", "objects.e", "objects.h"] {
        let golden = dir.join(name);
        let got_path = tmp.join(name);
        checked += 1;
        let got = std::fs::read(&got_path)
            .unwrap_or_else(|e| panic!("regen did not produce {name}: {e}"));
        let want = std::fs::read(&golden).expect("read golden objects file");
        if got != want {
            failures.push(format!(
                "{name}: got {} bytes, golden is {} bytes",
                got.len(),
                want.len()
            ));
        }
    }

    // Check kpropmap_generated.inc (generated from the .ht files above).
    {
        let name = "kpropmap_generated.inc";
        let golden = repo_root().join("engine/mutation").join(name);
        let got_path = tmp.join(name);
        checked += 1;
        let got = std::fs::read(&got_path)
            .unwrap_or_else(|e| panic!("regen did not produce {name}: {e}"));
        let want = std::fs::read(&golden).expect("read golden kpropmap_generated.inc");
        if got != want {
            failures.push(format!(
                "{name}: got {} bytes, golden is {} bytes (run `task gen-oas-headers` to update)",
                got.len(),
                want.len()
            ));
        }
    }

    let _ = std::fs::remove_dir_all(&tmp);

    assert!(checked > 0, "found no .ht files under {}", dir.display());
    assert!(
        failures.is_empty(),
        "{}/{} files did not reproduce their golden:\n  {}",
        failures.len(),
        checked,
        failures.join("\n  ")
    );
}
