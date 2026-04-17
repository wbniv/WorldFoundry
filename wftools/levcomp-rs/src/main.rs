//! levcomp — compile a `.lev.bin` (binary IFF) into a flat `.lvl` level file.
//!
//! Rust port of `wftools/iff2lvl`.  MVP scope: objects only (type + position +
//! rotation + bounding box).  OAD data, paths, channels, rooms, and the common
//! block are not yet populated — they appear as empty sections so `lvldump-rs`
//! can still parse the output.
//!
//! Usage:
//!   levcomp <input.lev.bin> <objects.lc> <output.lvl> [<oad_dir>] [--mesh-dir <dir>]

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
    eprintln!("Usage: levcomp <input.lev.bin> <objects.lc> <output.lvl> [<oad_dir>] [--mesh-dir <dir>]");
    eprintln!();
    eprintln!("  oad_dir:    directory of compiled <class>.oad files (optional).");
    eprintln!("              When present, each object's OAD data block is sized");
    eprintln!("              from its class schema; when absent, OADSize = 0.");
    eprintln!("  --mesh-dir: directory containing mesh .iff files (optional).");
    eprintln!("              When present, each object's bbox is extended to");
    eprintln!("              encompass its mesh vertices.  Also writes asset.inc");
    eprintln!("              alongside the output .lvl for the iff.prp pipeline.");
    process::exit(1);
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 4 { usage(); }

    let lev_path = Path::new(&args[1]);
    let lc_path  = Path::new(&args[2]);
    let out_path = Path::new(&args[3]);

    // Parse remaining args: positional oad_dir + named --mesh-dir.
    let mut oad_dir_str: Option<String> = None;
    let mut mesh_dir_str: Option<String> = None;
    {
        let mut i = 4;
        while i < args.len() {
            if args[i] == "--mesh-dir" {
                i += 1;
                if i >= args.len() { usage(); }
                mesh_dir_str = Some(args[i].clone());
            } else if oad_dir_str.is_none() && !args[i].starts_with("--") {
                oad_dir_str = Some(args[i].clone());
            } else {
                eprintln!("error: unexpected argument: {}", args[i]);
                usage();
            }
            i += 1;
        }
    }
    let oad_dir  = oad_dir_str.as_deref().map(Path::new);

    let mesh_dir = mesh_dir_str.as_deref().map(Path::new);

    eprintln!("levcomp v{VERSION}");
    eprintln!("  input : {}", lev_path.display());
    eprintln!("  .lc   : {}", lc_path.display());
    eprintln!("  output: {}", out_path.display());
    if let Some(d) = oad_dir  { eprintln!("  oad   : {}", d.display()); }
    if let Some(d) = mesh_dir { eprintln!("  meshes: {}", d.display()); }

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

    // Pre-compute mesh bboxes per object (None when no mesh dir or no Mesh Name).
    let mesh_bboxes: Vec<Option<[i32; 6]>> = objects.iter().map(|obj| {
        let mdir = mesh_dir?;
        let name = obj.find_field("Mesh Name")
            .map(crate::lev_parser::field_str_value)?;
        if name.is_empty() { return None; }
        let path = mesh_bbox::find_case_insensitive(mdir, &name)?;
        let bbox = mesh_bbox::load(&path)?;
        eprintln!("  mesh bbox for {}: {:?}", name, bbox);
        Some(bbox)
    }).collect();

    // Build asset registry — populated during OAD serialization inside write().
    let mut assets = asset_registry::AssetRegistry::new();

    let mut plan = lvl_writer::LevelPlan {
        objects: &objects,
        classes: &classes,
        schemas: &schemas,
        mesh_bboxes: &mesh_bboxes,
        assets: &mut assets,
    };
    let bytes = lvl_writer::write(&mut plan).unwrap_or_else(|e| {
        eprintln!("error: writing level: {}", e);
        process::exit(1);
    });

    std::fs::write(out_path, &bytes).unwrap_or_else(|e| {
        eprintln!("error: writing {}: {}", out_path.display(), e);
        process::exit(1);
    });
    eprintln!("  wrote {} bytes", bytes.len());

    // Write asset.inc alongside the .lvl when mesh assets were registered.
    if !assets.is_empty() {
        let level_name = out_path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("level");
        let asset_inc_path = out_path.with_file_name("asset.inc");
        let text = assets.asset_inc(level_name);
        std::fs::write(&asset_inc_path, text).unwrap_or_else(|e| {
            eprintln!("warning: could not write {}: {}", asset_inc_path.display(), e);
        });
        eprintln!("  wrote {}", asset_inc_path.display());
    }
}
