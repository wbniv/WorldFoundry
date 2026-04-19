//! levcomp — compile a `.lev.bin` (binary IFF) into a flat `.lvl` level file,
//! or decompile a compiled LVAS `.iff` back to a `.lev` text IFF.
//!
//! Rust port of `wftools/iff2lvl`.  MVP scope: objects only (type + position +
//! rotation + bounding box).  OAD data, paths, channels, rooms, and the common
//! block are not yet populated — they appear as empty sections so `lvldump-rs`
//! can still parse the output.
//!
//! Usage (compile):
//!   levcomp <input.lev.bin> <objects.lc> <output.lvl> [<oad_dir>] [--mesh-dir <dir>]
//!
//! Usage (decompile):
//!   levcomp decompile <input.iff> <objects.lc> [--oad-dir <dir>] [-o <output.lev>]

mod asset_registry;
mod common_block;
mod decompile;
mod lc_parser;
mod lev_parser;
mod lvas_writer;
mod lvl_writer;
mod mesh_bbox;
mod oad_loader;
mod rooms;

use std::path::Path;
use std::process;

const VERSION: &str = env!("CARGO_PKG_VERSION");

fn usage() -> ! {
    eprintln!("Usage: levcomp <input.lev.bin> <objects.lc> <output.lvl> [<oad_dir>] [--mesh-dir <dir>] [--iff-txt <path>]");
    eprintln!("       levcomp decompile <input.iff> <objects.lc> [--oad-dir <dir>] [-o <output.lev>]");
    eprintln!();
    eprintln!("  oad_dir:    directory of compiled <class>.oad files (optional).");
    eprintln!("              When present, each object's OAD data block is sized");
    eprintln!("              from its class schema; when absent, OADSize = 0.");
    eprintln!("  --mesh-dir: directory containing mesh .iff files (optional).");
    eprintln!("              When present, each object's bbox is extended to");
    eprintln!("              encompass its mesh vertices.  Also writes asset.inc");
    eprintln!("              alongside the output .lvl for the iff.prp pipeline.");
    eprintln!("  --iff-txt:  also emit a LVAS text-IFF that subsumes the prep step.");
    eprintln!("              Compile via iffcomp-rs to produce the final <level>.iff.");
    process::exit(1);
}

fn run_decompile(args: &[String]) {
    // args[0] = "decompile", args[1..] = remaining
    if args.len() < 3 {
        eprintln!("Usage: levcomp decompile <input.iff> <objects.lc> [--oad-dir <dir>] [-o <output.lev>]");
        process::exit(1);
    }
    let iff_path = Path::new(&args[1]);
    let lc_path  = Path::new(&args[2]);

    let mut oad_dir_str: Option<String> = None;
    let mut out_str: Option<String> = None;

    let mut i = 3;
    while i < args.len() {
        match args[i].as_str() {
            "--oad-dir" => {
                i += 1;
                if i >= args.len() {
                    eprintln!("error: --oad-dir requires a directory argument");
                    process::exit(1);
                }
                oad_dir_str = Some(args[i].clone());
            }
            "-o" => {
                i += 1;
                if i >= args.len() {
                    eprintln!("error: -o requires a file argument");
                    process::exit(1);
                }
                out_str = Some(args[i].clone());
            }
            other => {
                eprintln!("error: unexpected argument: {}", other);
                process::exit(1);
            }
        }
        i += 1;
    }

    // Default output: replace .iff extension with .lev, or add .lev
    let out_path_buf = if let Some(s) = out_str {
        std::path::PathBuf::from(s)
    } else {
        iff_path.with_extension("lev")
    };
    let out_path = out_path_buf.as_path();
    let oad_dir = oad_dir_str.as_deref().map(Path::new);

    eprintln!("levcomp v{VERSION} decompile");
    eprintln!("  input : {}", iff_path.display());
    eprintln!("  .lc   : {}", lc_path.display());
    eprintln!("  output: {}", out_path.display());
    if let Some(d) = oad_dir { eprintln!("  oad   : {}", d.display()); }

    decompile::run(iff_path, lc_path, oad_dir, out_path).unwrap_or_else(|e| {
        eprintln!("error: {}", e);
        process::exit(1);
    });
}

fn main() {
    let args: Vec<String> = std::env::args().collect();

    // Dispatch on first argument being "decompile"
    if args.get(1).map(|s| s.as_str()) == Some("decompile") {
        run_decompile(&args[1..]);
        return;
    }

    if args.len() < 4 { usage(); }

    let lev_path = Path::new(&args[1]);
    let lc_path  = Path::new(&args[2]);
    let out_path = Path::new(&args[3]);

    // Parse remaining args: positional oad_dir + named --mesh-dir / --iff-txt.
    let mut oad_dir_str: Option<String> = None;
    let mut mesh_dir_str: Option<String> = None;
    let mut iff_txt_str: Option<String> = None;
    {
        let mut i = 4;
        while i < args.len() {
            if args[i] == "--mesh-dir" {
                i += 1;
                if i >= args.len() { usage(); }
                mesh_dir_str = Some(args[i].clone());
            } else if args[i] == "--iff-txt" {
                i += 1;
                if i >= args.len() { usage(); }
                iff_txt_str = Some(args[i].clone());
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
        let s = oad_loader::OadSchemas::load_dir(d)
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
    let level_name = out_path
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("level")
        .to_string();
    if !assets.is_empty() {
        let asset_inc_path = out_path.with_file_name("asset.inc");
        let text = assets.asset_inc(&level_name);
        std::fs::write(&asset_inc_path, text).unwrap_or_else(|e| {
            eprintln!("warning: could not write {}: {}", asset_inc_path.display(), e);
        });
        eprintln!("  wrote {}", asset_inc_path.display());
    }

    // Emit the LVAS text-IFF when --iff-txt was given. Subsumes prep.
    if let Some(iff_txt) = iff_txt_str.as_deref() {
        let iff_txt_path = Path::new(iff_txt);
        // Collect the distinct, sorted list of room indices that own
        // mesh assets (all registered non-PERM entries). Texture rooms
        // that carry no meshes — e.g. `RM0` in snowgoons — still need
        // their own ASS-slot chunk in the LVAS, so callers can widen
        // this set as more of the texture pipeline lands. For now we
        // include any room that appears in the registry plus a fixed
        // RM0 slot when the level has at least one per-room bucket
        // (matches snowgoons; other levels may need different handling
        // once textile-rs is wired up).
        use std::collections::BTreeSet;
        let mut room_set: BTreeSet<i32> = BTreeSet::new();
        for (_, id) in assets.entries() {
            let room = ((*id as u32) >> 12) & 0xFFF;
            if room != 0xFFF {
                room_set.insert(room as i32);
            }
        }
        // Snowgoons has RM0 (textures only) + RM1 (meshes + textures).
        // The registry only surfaces RM1; add RM0 explicitly so the TOC
        // and chunk list match the oracle.
        if !room_set.is_empty() {
            room_set.insert(0);
        }
        let rooms: Vec<i32> = room_set.into_iter().collect();
        lvas_writer::write(&assets, &level_name, &rooms, iff_txt_path)
            .unwrap_or_else(|e| {
                eprintln!("warning: could not write {}: {}", iff_txt_path.display(), e);
            });
        eprintln!("  wrote {}", iff_txt_path.display());
    }
}
