//! levcomp — compile a `.lev.bin` (binary IFF) into a flat `.lvl` level file.
//!
//! Rust port of `wftools/iff2lvl`.
//!
//! Usage:
//!   levcomp <input.lev.bin> <objects.lc> <output.lvl> [<oad_dir>]
//!           [--mesh-dir <dir>] [--asset-inc <out.inc>]
//!
//!   oad_dir    — directory of compiled <class>.oad files.
//!   --mesh-dir — directory of mesh .iff files; extends each object's bbox
//!                to cover its mesh geometry (Phase 2c).
//!   --asset-inc — write asset.inc for use with iff.prp to produce LVAS wrapper.

mod asset_registry;
mod common_block;
mod lc_parser;
mod lev_parser;
mod lvl_writer;
mod mesh_bbox;
mod oad_loader;
mod rooms;

use std::path::Path;
use std::process;

const VERSION: &str = env!("CARGO_PKG_VERSION");

fn usage() -> ! {
    eprintln!("Usage: levcomp <input.lev.bin> <objects.lc> <output.lvl> [<oad_dir>]");
    eprintln!("              [--mesh-dir <dir>] [--asset-inc <out.inc>]");
    eprintln!();
    eprintln!("  oad_dir      directory of compiled <class>.oad files");
    eprintln!("  --mesh-dir   mesh .iff directory; extends bboxes to cover geometry");
    eprintln!("  --asset-inc  write asset.inc (for iff.prp LVAS wrapper generation)");
    process::exit(1);
}

fn main() {
    let raw: Vec<String> = std::env::args().collect();
    if raw.len() < 4 { usage(); }

    let lev_path = Path::new(&raw[1]);
    let lc_path  = Path::new(&raw[2]);
    let out_path = Path::new(&raw[3]);

    // Parse optional positional oad_dir (arg[4] if not a flag) and named flags.
    let mut oad_dir_str: Option<String> = None;
    let mut mesh_dir_str: Option<String> = None;
    let mut asset_inc_path: Option<String> = None;
    let mut i = 4;
    while i < raw.len() {
        match raw[i].as_str() {
            "--mesh-dir" => {
                i += 1;
                mesh_dir_str = raw.get(i).cloned();
            }
            "--asset-inc" => {
                i += 1;
                asset_inc_path = raw.get(i).cloned();
            }
            s if !s.starts_with("--") => {
                if oad_dir_str.is_none() {
                    oad_dir_str = Some(s.to_string());
                }
            }
            _ => {}
        }
        i += 1;
    }

    let oad_dir  = oad_dir_str.as_deref().map(Path::new);
    let mesh_dir = mesh_dir_str.as_deref().map(Path::new);

    eprintln!("levcomp v{VERSION}");
    eprintln!("  input    : {}", lev_path.display());
    eprintln!("  .lc      : {}", lc_path.display());
    eprintln!("  output   : {}", out_path.display());
    if let Some(d) = oad_dir  { eprintln!("  oad      : {}", d.display()); }
    if let Some(d) = mesh_dir { eprintln!("  mesh-dir : {}", d.display()); }

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
        let s = oad_loader::OadSchemas::load_dir(d, |name| {
            classes.index_of(name).map(|i| i as i32)
        })
        .unwrap_or_else(|e| {
            eprintln!("error: {}", e);
            process::exit(1);
        });
        eprintln!("  loaded OAD schemas");
        s
    } else {
        oad_loader::OadSchemas::empty()
    };

    // Build rooms so the asset registry knows which room each object lives in.
    let rooms::SortResult { rooms, room_of_obj } =
        rooms::sort(&objects, &schemas);

    let registry = asset_registry::AssetRegistry::build(&objects, &rooms);
    eprintln!("  built asset registry");

    if let Some(ref inc_path) = asset_inc_path {
        let level_name = lev_path.file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("level");
        let content = registry.write_asset_inc(level_name, lvl_writer::LEVEL_VERSION);
        std::fs::write(inc_path, &content).unwrap_or_else(|e| {
            eprintln!("error: writing {}: {}", inc_path, e);
            process::exit(1);
        });
        eprintln!("  wrote asset.inc → {}", inc_path);
    }

    let plan = lvl_writer::LevelPlan {
        objects: &objects,
        classes: &classes,
        schemas: &schemas,
        mesh_dir,
        asset_registry: &registry,
        rooms: &rooms,
        room_of_obj: &room_of_obj,
    };
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
