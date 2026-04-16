//! levcomp — compile a `.lev.bin` (binary IFF) into a flat `.lvl` level file.
//!
//! Rust port of `wftools/iff2lvl`.  MVP scope: objects only (type + position +
//! rotation + bounding box).  OAD data, paths, channels, rooms, and the common
//! block are not yet populated — they appear as empty sections so `lvldump-rs`
//! can still parse the output.
//!
//! Usage:
//!   levcomp <input.lev.bin> <objects.lc> <output.lvl>

mod common_block;
mod lc_parser;
mod lev_parser;
mod lvl_writer;
mod oad_loader;

use std::path::Path;
use std::process;

const VERSION: &str = env!("CARGO_PKG_VERSION");

fn usage() -> ! {
    eprintln!("Usage: levcomp <input.lev.bin> <objects.lc> <output.lvl> [<oad_dir>]");
    eprintln!();
    eprintln!("  oad_dir:  directory of compiled <class>.oad files (optional).");
    eprintln!("            When present, each object's OAD data block is sized");
    eprintln!("            from its class schema; when absent, OADSize = 0.");
    process::exit(1);
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 4 { usage(); }

    let lev_path = Path::new(&args[1]);
    let lc_path  = Path::new(&args[2]);
    let out_path = Path::new(&args[3]);
    let oad_dir  = args.get(4).map(Path::new);

    eprintln!("levcomp v{VERSION}");
    eprintln!("  input : {}", lev_path.display());
    eprintln!("  .lc   : {}", lc_path.display());
    eprintln!("  output: {}", out_path.display());
    if let Some(d) = oad_dir {
        eprintln!("  oad   : {}", d.display());
    }

    let lev_data = std::fs::read(lev_path).unwrap_or_else(|e| {
        eprintln!("error: cannot read {}: {}", lev_path.display(), e);
        process::exit(1);
    });

    let objects = lev_parser::parse(&lev_data).unwrap_or_else(|e| {
        eprintln!("error: parsing {}: {}", lev_path.display(), e);
        process::exit(1);
    });
    eprintln!("  parsed {} objects", objects.len());

    let classes = lc_parser::load(lc_path).unwrap_or_else(|e| {
        eprintln!("error: {}", e);
        process::exit(1);
    });
    eprintln!("  loaded {} classes", classes.names.len());

    let schemas = if let Some(d) = oad_dir {
        let s = oad_loader::OadSchemas::load_dir(d).unwrap_or_else(|e| {
            eprintln!("error: {}", e);
            process::exit(1);
        });
        eprintln!("  loaded OAD schemas");
        s
    } else {
        oad_loader::OadSchemas::empty()
    };

    let plan = lvl_writer::LevelPlan { objects: &objects, classes: &classes, schemas: &schemas };
    let bytes = lvl_writer::write(&plan).unwrap_or_else(|e| {
        eprintln!("error: writing level: {}", e);
        process::exit(1);
    });

    std::fs::write(out_path, &bytes).unwrap_or_else(|e| {
        eprintln!("error: writing {}: {}", out_path.display(), e);
        process::exit(1);
    });
    eprintln!("  wrote {} bytes", bytes.len());
}
