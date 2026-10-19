//! Oracle tests for the OAS → OAD pipeline.
//!
//! Every committed `.oas` actor schema in `wfsource/source/oas/` must compile to
//! a `.oad` that byte-matches its committed golden, using the locally-built
//! `prep` plus the system `g++` / `objcopy`. This is the regression guard for
//! the `prep` `eval` rebuild — see
//! `docs/investigations/2026-05-19-prep-rebuild-or-replace.md`.
//!
//! Run with `cargo test` from `wftools/oas2oad-rs/`. On a fresh checkout the
//! `prep` binary is gitignored, so the first run builds it from source via
//! `wftools/prep/build.sh` (needs only `g++` — the bison/flex output is
//! committed alongside its `.y`/`.l` sources).

use std::path::{Path, PathBuf};
use std::process::{Command, Output};
use std::sync::Once;

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

fn prep_bin() -> PathBuf {
    repo_root().join("wftools/prep/prep")
}

/// Build `prep` from source once if its binary is missing, so `cargo test`
/// is self-contained. The committed `eval/expr_tab.cc` + `eval/lexyy.cc` mean
/// this needs only `g++`, not bison/flex.
fn ensure_prep() {
    static BUILD: Once = Once::new();
    BUILD.call_once(|| {
        if prep_bin().exists() {
            return;
        }
        let script = repo_root().join("wftools/prep/build.sh");
        let status = Command::new("bash")
            .arg(&script)
            .status()
            .expect("failed to spawn prep build.sh");
        assert!(status.success(), "prep build.sh failed");
        assert!(
            prep_bin().exists(),
            "prep build.sh did not produce {}",
            prep_bin().display()
        );
    });
}

fn run_oas2oad(oas: &Path, out: &Path) -> Output {
    let oas_dir = oas_dir();
    Command::new(env!("CARGO_BIN_EXE_oas2oad"))
        .arg(format!("--prep={}", prep_bin().display()))
        .arg(format!("--types={}", oas_dir.join("types3ds.s").display()))
        .arg(format!("--objects-lc={}", oas_dir.join("objects.lc").display()))
        .arg("-o")
        .arg(out)
        .arg(oas)
        .output()
        .expect("failed to run oas2oad")
}

/// Every `.oas` with a committed golden `.oad` compiles to a byte-identical `.oad`.
#[test]
fn every_oas_matches_golden_oad() {
    ensure_prep();
    let dir = oas_dir();

    let tmp = std::env::temp_dir().join(format!("oas2oad-oracle-{}", std::process::id()));
    std::fs::create_dir_all(&tmp).expect("create temp dir");

    let mut oas_files: Vec<PathBuf> = std::fs::read_dir(&dir)
        .expect("read oas dir")
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.extension().is_some_and(|x| x == "oas"))
        .collect();
    oas_files.sort();

    let mut checked = 0usize;
    let mut failures: Vec<String> = Vec::new();

    for oas in &oas_files {
        let stem = oas.file_stem().unwrap().to_string_lossy().into_owned();
        let golden = dir.join(format!("{stem}.oad"));
        if !golden.exists() {
            // include-only `.oas` with no compiled descriptor — nothing to check.
            continue;
        }
        checked += 1;

        let out = tmp.join(format!("{stem}.oad"));
        let result = run_oas2oad(oas, &out);
        if !result.status.success() {
            failures.push(format!(
                "{stem}: pipeline failed ({})\n    {}",
                result.status,
                String::from_utf8_lossy(&result.stderr).trim()
            ));
            continue;
        }

        let got = std::fs::read(&out).unwrap_or_default();
        let want = std::fs::read(&golden).expect("read golden oad");
        if got != want {
            failures.push(format!(
                "{stem}: produced {} bytes, golden is {} bytes",
                got.len(),
                want.len()
            ));
        }
    }

    let _ = std::fs::remove_dir_all(&tmp);

    assert!(checked > 0, "found no .oas/.oad pairs under {}", dir.display());
    assert!(
        failures.is_empty(),
        "{}/{} .oas did not reproduce their golden .oad:\n  {}",
        failures.len(),
        checked,
        failures.join("\n  ")
    );
}

/// Focused guard for the restored `eval/` parser (the feature the deleted
/// `eval/` had broken). If this fails, the regression is in prep's expression
/// evaluator specifically, not the wider pipeline.
#[test]
fn prep_eval_arithmetic() {
    ensure_prep();

    let stem = format!("prep-eval-{}", std::process::id());
    let infile = std::env::temp_dir().join(format!("{stem}.in"));
    let outfile = std::env::temp_dir().join(format!("{stem}.out"));
    std::fs::write(
        &infile,
        "@define X 10\nadd=@=i(X + 5)\nprec=@=i(2 + 3 * 4)\nfixed=@=f(2)\ncond=@if(X > 3)(YES)\n",
    )
    .expect("write eval input");

    let status = Command::new(prep_bin())
        .arg(&infile)
        .arg(&outfile)
        .status()
        .expect("run prep");
    assert!(status.success(), "prep exited unsuccessfully");

    let out = std::fs::read_to_string(&outfile).expect("read prep output");
    let _ = std::fs::remove_file(&infile);
    let _ = std::fs::remove_file(&outfile);

    assert!(out.contains("add=15"), "addition wrong:\n{out}");
    assert!(out.contains("prec=14"), "operator precedence wrong:\n{out}");
    assert!(out.contains("fixed=2.00000"), "fixed-point format wrong:\n{out}");
    assert!(out.contains("cond=YES"), "conditional wrong:\n{out}");
}
