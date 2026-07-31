//! levtree CLI — `.lev` ↔ editable chunk tree (JSON) for the collaborative editor.
//!
//!   levtree parse <file.lev>     # .lev → JSON chunk tree on stdout
//!   levtree print [<file.json>]  # JSON → canonical .lev on stdout (stdin if no file)
//!
//! See `docs/plans/2026-05-20-iff-lev-ydoc-translator.md`.

use std::io::{Read, Write};
use std::process::ExitCode;

fn usage() {
    eprintln!("usage:");
    eprintln!("  levtree parse <file.lev>       # .lev → JSON chunk tree on stdout");
    eprintln!("  levtree print [<file.json>]    # JSON → canonical .lev on stdout (stdin if no file)");
}

fn run() -> levtree::Result<()> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match args.first().map(String::as_str) {
        Some("parse") => {
            let path = args
                .get(1)
                .ok_or_else(|| levtree::LevError::Parse("parse: missing <file.lev>".into()))?;
            let src = std::fs::read_to_string(path)?;
            let doc = levtree::parse_lev(&src)?;
            let json = serde_json::to_string_pretty(&doc)
                .map_err(|e| levtree::LevError::Parse(format!("json encode: {e}")))?;
            println!("{json}");
            Ok(())
        }
        Some("print") => {
            let json = match args.get(1) {
                Some(p) => std::fs::read_to_string(p)?,
                None => {
                    let mut s = String::new();
                    std::io::stdin().read_to_string(&mut s)?;
                    s
                }
            };
            let doc: levtree::LevelDoc = serde_json::from_str(&json)
                .map_err(|e| levtree::LevError::Parse(format!("json decode: {e}")))?;
            let lev = levtree::print_lev(&doc);
            std::io::stdout().write_all(lev.as_bytes())?;
            Ok(())
        }
        _ => {
            usage();
            Err(levtree::LevError::Parse(
                "unknown or missing subcommand".into(),
            ))
        }
    }
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("levtree: {e}");
            ExitCode::FAILURE
        }
    }
}
