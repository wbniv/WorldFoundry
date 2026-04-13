// main.rs — textile CLI entry point (port of main.cc)
//
// Usage: textile -ini=<file> [switches]
//
// See usage() for full switch listing.

mod allocmap;
mod bitmap;
mod ccyc;
mod config;
mod locfile;
mod profile;
mod rmuv;
mod texture;

use std::fs::File;
use std::io::{BufWriter, Write};
use std::process;

use config::{Config, TargetSystem};
use bitmap::br_colour_rgb_555;
use profile::{get_int, get_string};
use texture::process_room;

const VERSION: &str = "1.0.0-rs";

fn usage() -> ! {
    eprintln!("textile v{} Copyright 1995-2001 World Foundry Group.", VERSION);
    eprintln!("by William B. Norris IV (Rust port)");
    eprintln!("Constructs single Targa file composite of all input texture maps");
    eprintln!();
    eprintln!("Usage: textile [switches]  []=default value");
    eprintln!("  -ini=<file>          Read room descriptions from INI file (required)");
    eprintln!("  -outdir=<dir>        Output directory [.]");
    eprintln!("  -pagex=N             Page width [512]");
    eprintln!("  -pagey=N             Page height [2048]");
    eprintln!("  -permpagex=N         Permanent page width [128]");
    eprintln!("  -permpagey=N         Permanent page height [512]");
    eprintln!("  -palx=N              Palette width [320]");
    eprintln!("  -paly=N              Palette height [8]");
    eprintln!("  -alignx=(N|w)        X-alignment [16] (w=texture width)");
    eprintln!("  -aligny=(N|h)        Y-alignment [1] (h=texture height)");
    eprintln!("  -transparent=r,g,b   Transparent colour [0,0,0]");
    eprintln!("  -colourcycle=<file>  Colour cycle INI file");
    eprintln!("  -powerof2size        Require power-of-two texture dimensions");
    eprintln!("  -mipmap              Generate mip-mapping bitmaps");
    eprintln!("  -Tpsx                Target: PlayStation");
    eprintln!("  -Twin                Target: Windows");
    eprintln!("  -Tlinux              Target: Linux");
    eprintln!("  -o=<file>            Output data file [room%d.bin]");
    eprintln!("  -verbose             Enable verbose messages");
    eprintln!("  -frame               Show frames around textures");
    eprintln!("  -showalign           Show alignment waste");
    eprintln!("  -showpacking         Show packing waste");
    eprintln!("  -nocrop              Don't crop output bitmap");
    eprintln!("  -flipyout            Flip output image vertically");
    eprintln!("  -translucent         Force all textures translucent");
    eprintln!("  -sourcecontrol       Verify input files are in source control");
    eprintln!("  -debug               Debug output");
    process::exit(-1);
}

fn main() {
    let args: Vec<String> = std::env::args().collect();

    if args.len() == 1 {
        usage();
    }

    let mut cfg = Config::default();

    // ── Parse command-line arguments ────────────────────────────────────────
    for arg in &args[1..] {
        let arg = arg.as_str();

        if arg == "-?" || arg == "--help" {
            usage();
        } else if arg == "-Tpsx" {
            cfg.target = TargetSystem::PlayStation;
        } else if arg == "-Twin" {
            cfg.target = TargetSystem::Windows;
        } else if arg == "-Tlinux" {
            cfg.target = TargetSystem::Linux;
        } else if arg == "-debug" {
            cfg.debug = true;
        } else if arg == "-verbose" {
            cfg.verbose = true;
        } else if arg == "-frame" {
            cfg.frame = true;
        } else if arg == "-showalign" {
            cfg.show_align = true;
        } else if arg == "-showpacking" {
            cfg.show_packing = true;
        } else if arg == "-nocrop" {
            cfg.crop_output = false;
        } else if arg == "-translucent" {
            cfg.force_translucent = true;
        } else if arg == "-flipyout" {
            cfg.flip_y_out = true;
        } else if arg == "-powerof2size" {
            cfg.power_of2 = true;
        } else if arg == "-mipmap" {
            cfg.mip_mapping = true;
        } else if arg == "-sourcecontrol" {
            cfg.source_control = true;
        } else if arg == "-aligntosizemultiple" {
            cfg.align_to_size_multiple = true;
        } else if let Some(v) = arg.strip_prefix("-pagex=") {
            cfg.x_page = v.parse().unwrap_or(cfg.x_page);
        } else if let Some(v) = arg.strip_prefix("-pagey=") {
            cfg.y_page = v.parse().unwrap_or(cfg.y_page);
        } else if let Some(v) = arg.strip_prefix("-permpagex=") {
            cfg.perm_x_page = v.parse().unwrap_or(cfg.perm_x_page);
        } else if let Some(v) = arg.strip_prefix("-permpagey=") {
            cfg.perm_y_page = v.parse().unwrap_or(cfg.perm_y_page);
        } else if let Some(v) = arg.strip_prefix("-palx=") {
            cfg.pal_x_page = v.parse().unwrap_or(cfg.pal_x_page);
        } else if let Some(v) = arg.strip_prefix("-paly=") {
            cfg.pal_y_page = v.parse().unwrap_or(cfg.pal_y_page);
        } else if let Some(v) = arg.strip_prefix("-alignx=") {
            if v == "w" {
                cfg.x_align = 16;
                cfg.y_align = 16;
                cfg.align_to_size_multiple = true;
            } else {
                cfg.x_align = v.parse().unwrap_or(cfg.x_align);
            }
        } else if let Some(v) = arg.strip_prefix("-aligny=") {
            if v == "h" {
                cfg.y_align = 16;
                cfg.align_to_size_multiple = true;
            } else {
                // C++ bug: -aligny= sets BOTH x_align and y_align; replicated here
                let n: i32 = v.parse().unwrap_or(cfg.y_align);
                cfg.x_align = n;
                cfg.y_align = n;
            }
        } else if let Some(v) = arg.strip_prefix("-transparent=") {
            let parts: Vec<&str> = v.splitn(3, ',').collect();
            if parts.len() == 3 {
                cfg.r_transparent = parts[0].parse().unwrap_or(0);
                cfg.g_transparent = parts[1].parse().unwrap_or(0);
                cfg.b_transparent = parts[2].parse().unwrap_or(0);
            }
        } else if let Some(v) = arg.strip_prefix("-colourcycle=") {
            cfg.colour_cycle_file = v.to_string();
        } else if let Some(v) = arg.strip_prefix("-outdir=") {
            cfg.out_dir = v.to_string();
        } else if let Some(v) = arg.strip_prefix("-o=") {
            cfg.out_file = v.to_string();
        } else if let Some(v) = arg.strip_prefix("-ini=") {
            cfg.ini_file = v.to_string();

            // Read configuration from INI
            let ini = &cfg.ini_file.clone();
            let sec = "Configuration";
            cfg.x_page       = get_int(sec, "pagex",     cfg.x_page,       ini);
            cfg.y_page       = get_int(sec, "pagey",     cfg.y_page,       ini);
            cfg.perm_x_page  = get_int(sec, "permpagex", cfg.perm_x_page,  ini);
            cfg.perm_y_page  = get_int(sec, "permpagey", cfg.perm_y_page,  ini);
            cfg.x_align      = get_int(sec, "alignx",    cfg.x_align,      ini);
            cfg.y_align      = get_int(sec, "aligny",    cfg.y_align,      ini);
            cfg.debug        = get_int(sec, "debug",     cfg.debug as i32, ini) != 0;
            cfg.verbose      = get_int(sec, "verbose",   cfg.verbose as i32, ini) != 0;
            cfg.frame        = get_int(sec, "showframe", cfg.frame as i32, ini) != 0;
            cfg.show_align   = get_int(sec, "showalign", cfg.show_align as i32, ini) != 0;
            cfg.show_packing = get_int(sec, "showpacking", cfg.show_packing as i32, ini) != 0;
            let no_crop = get_int(sec, "crop", (!cfg.crop_output) as i32, ini);
            cfg.crop_output  = no_crop == 0;
            cfg.out_file     = get_string(sec, "out", &cfg.out_file.clone(), ini);
            cfg.power_of2    = get_int(sec, "powerof2size", cfg.power_of2 as i32, ini) != 0;
            cfg.source_control = get_int(sec, "sourcecontrol", cfg.source_control as i32, ini) != 0;
            let ts_int = get_int(sec, "TargetSystem", cfg.target as i32, ini);
            cfg.target = TargetSystem::from_int(ts_int);

            // Palette configuration
            let pal = "Palette";
            cfg.pal_x_page  = get_int(pal, "pagex",  cfg.pal_x_page,  ini);
            cfg.pal_y_page  = get_int(pal, "pagey",  cfg.pal_y_page,  ini);
            cfg.pal_x_align = get_int(pal, "alignx", cfg.pal_x_align, ini);
            cfg.pal_y_align = get_int(pal, "aligny", cfg.pal_y_align, ini);
            let trans_default = format!("{},{},{}", cfg.r_transparent, cfg.g_transparent, cfg.b_transparent);
            let trans_str = get_string(pal, "transparent", &trans_default, ini);
            let parts: Vec<&str> = trans_str.splitn(3, ',').collect();
            if parts.len() == 3 {
                cfg.r_transparent = parts[0].trim().parse().unwrap_or(cfg.r_transparent);
                cfg.g_transparent = parts[1].trim().parse().unwrap_or(cfg.g_transparent);
                cfg.b_transparent = parts[2].trim().parse().unwrap_or(cfg.b_transparent);
            }

            // Paths
            cfg.texture_path = get_string("Texture", "Path", &cfg.texture_path.clone(), ini);
            cfg.vrml_path    = get_string("VRML",    "Path", &cfg.vrml_path.clone(),    ini);
        } else {
            eprintln!("textile: unknown command line option \"{}\"", arg);
        }
    }

    if cfg.ini_file.is_empty() {
        eprintln!("textile: -ini=<file> is required");
        process::exit(1);
    }

    assert!(cfg.x_page > 0, "x_page must be positive");
    assert!(cfg.y_page > 0, "y_page must be positive");

    // Compute transparent colour value
    cfg.col_transparent = br_colour_rgb_555(
        cfg.r_transparent as u8,
        cfg.g_transparent as u8,
        cfg.b_transparent as u8,
    );

    // Create output directory if needed
    if cfg.out_dir != "." {
        let _ = std::fs::create_dir_all(&cfg.out_dir);
    }

    // ── Open HTML log ───────────────────────────────────────────────────────
    let log_file = File::create("textile.log.htm").unwrap_or_else(|e| {
        eprintln!("textile: couldn't create textile.log.htm: {}", e);
        process::exit(1);
    });
    let mut log = BufWriter::new(log_file);

    write_html_header(&mut log, VERSION);

    // ── Process rooms ────────────────────────────────────────────────────────
    let n_rooms = get_int("Rooms", "nRooms", 1, &cfg.ini_file);

    let mut global_error = false;

    for room in 0..n_rooms {
        let room_name = format!("Room{}", room);
        process_room(&room_name, cfg.x_page, cfg.y_page, &cfg, &mut log, &mut global_error);
    }

    process_room("Perm", cfg.perm_x_page, cfg.perm_y_page, &cfg, &mut log, &mut global_error);

    // ── Close HTML log ───────────────────────────────────────────────────────
    write_html_footer(&mut log);
    let _ = log.flush();   // must flush before process::exit() skips Drop

    process::exit(if global_error { 10 } else { 0 });
}

fn write_html_header(log: &mut impl Write, version: &str) {
    let _ = writeln!(log, "<html>");
    let _ = writeln!(log);
    let _ = writeln!(log, "<head>");
    let _ = writeln!(log, "<title>Textile Log</title>");
    let _ = writeln!(log, "<meta name=\"GENERATOR\" content=\"World Foundry Textile v{}\">" , version);
    let _ = writeln!(log, "<style>");
    let _ = writeln!(log, "\t.thd {{ color: \"#0000FF\"; background: \"#808000\"; font-weight: \"bold\"; cursor: \"s-resize\" }}");
    let _ = writeln!(log, "</style>");
    let _ = writeln!(log, "</head>");
    let _ = writeln!(log);
    let _ = writeln!(log, "<body>");
}

fn write_html_footer(log: &mut impl Write) {
    let _ = writeln!(log, "</body>");
    let _ = writeln!(log, "</html>");
}
