// main.rs — lvldump CLI entry point (port of lvldump.cc)
//
// Usage: lvldump [switches] <.lvl file> [output file]
//   -analysis         print object type histogram
//   -l<lc_file>       load objects.lc + companion .oad files

mod level;
mod oad;

use std::fs::File;
use std::io::{self, BufWriter, Write};
use std::process;

const VERSION: &str = "1.0.0-rs";

fn usage() -> ! {
    println!("By Kevin T. Seghetti (Rust port)");
    println!("Usage: lvldump {{switches}} <.lvl file name> {{<output name>}}");
    println!("Switches:");
    println!("    -analysis");
    println!("    -l<.lc filename>");
    process::exit(1);
}

fn main() {
    let args: Vec<String> = std::env::args().collect();

    println!("lvldump v{}", VERSION);
    println!("Copyright 1995,96,97,98,99,2001 World Foundry Group.");

    let mut analysis = false;
    let mut lc_file: Option<String> = None;
    let mut first_non_switch = 1usize;

    // Parse switches (all args starting with '-')
    for i in 1..args.len() {
        let arg = &args[i];
        if !arg.starts_with('-') {
            first_non_switch = i;
            break;
        }
        if arg == "-analysis" {
            analysis = true;
        } else if let Some(lc) = arg.strip_prefix("-l").or_else(|| arg.strip_prefix("-L")) {
            lc_file = Some(lc.to_string());
        } else if arg.starts_with("-p") || arg.starts_with("-P") {
            // Stream redirection — ignored in Rust port
        } else {
            eprintln!("lvldump Error: Unrecognized command line switch \"{}\"", &arg[1..2]);
        }
    }

    // Need at least one positional argument (the .lvl file)
    if args.len() <= first_non_switch {
        usage();
    }

    let lvl_path = &args[first_non_switch];
    let out_path = args.get(first_non_switch + 1);

    // Load .lc and .oad files if requested
    let ctx = if let Some(lc) = &lc_file {
        let mut ctx = oad::load_lc_file(lc);
        oad::load_oad_files(&mut ctx, lc);
        ctx
    } else {
        oad::OadContext::empty()
    };

    // Load entire .lvl file into memory
    let data = std::fs::read(lvl_path).unwrap_or_else(|_| {
        eprintln!("lvldump Error: input .LVL file <{}> not found.", lvl_path);
        process::exit(1);
    });

    // Open output (file or stdout)
    let stdout;
    let file_out;
    let mut out: Box<dyn Write> = if let Some(path) = out_path {
        file_out = File::create(path).unwrap_or_else(|e| {
            eprintln!("Unable to open output file {}: {}", path, e);
            process::exit(1);
        });
        Box::new(BufWriter::new(file_out))
    } else {
        stdout = io::stdout();
        Box::new(BufWriter::new(stdout.lock()))
    };

    writeln!(out, "Level Dump created by Lvldump version {}", VERSION).unwrap();

    level::dump_level(&data, &ctx, analysis, &mut *out).unwrap_or_else(|e| {
        eprintln!("lvldump: error writing output: {}", e);
        process::exit(1);
    });

    let _ = out.flush();
}
