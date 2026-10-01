//! cdpack — assemble a WF GAME cd.iff from a SHEL script + N level LVAS IFFs.
//!
//! Usage: cdpack <shel.fth> <L0.iff> [<L1.iff> ...] -o <cd.iff>
//!        cdpack <shel.fth> --manifest <menu.manifest> -o <cd.iff>
//!
//! Output layout:
//!   Sector 0 (2048 B): GAME<total> + TOC<entries> + ALGN<pad>
//!   Sector 1 (2048 B): SHEL<script> + ALGN<pad>
//!   Sector 2+        : each level IFF, sector-aligned
//!   (--manifest only) : one more TOC entry and chunk, MENU, after the last level
//!
//! Without --manifest the output is exactly what it always was (tests/test_level_menu.py
//! pins it against the tracked bundles). The manifest names the levels for the level menu
//! (wfsource/source/game/level_menu.cc); see docs/plans/2026-10-01-level-menu-selector.md.

use std::fs;
use std::io::Write;
use std::path::Path;
use std::process;

const SECTOR: usize = 2048;

/// Longest title / level name the menu accepts (the engine checks the same bounds).
const MAX_NAME: usize = 60;
const MENU_VERSION: u32 = 1;

/// A parsed level-menu manifest: the bundle's title and its levels, in TOC order.
struct Manifest {
    title: String,
    prompt: String,
    levels: Vec<(String, String)>, // (path, display name)
}

fn check_name(what: &str, s: &str, origin: &str) -> Result<(), String> {
    if s.is_empty() || s.len() > MAX_NAME {
        return Err(format!("{}: {} must be 1 to {} characters, got {}: {:?}", origin, what, MAX_NAME, s.len(), s));
    }
    if let Some(c) = s.chars().find(|c| !(' '..='~').contains(c)) {
        return Err(format!("{}: {} has {:?}, only printable ASCII is drawable: {:?}", origin, what, c, s));
    }
    Ok(())
}

/// Parse a manifest. Lines: `# comment`, blank, `title <text>`, `prompt <text>`, `level <path> | <name>`.
/// Level paths are relative to the manifest's directory.
fn parse_manifest(path: &str) -> Result<Manifest, String> {
    let text = fs::read_to_string(path).map_err(|e| format!("reading {}: {}", path, e))?;
    let base = Path::new(path).parent().unwrap_or_else(|| Path::new("."));
    let mut title = String::from("World Foundry");
    let mut prompt = String::from("Choose a game");
    let mut levels = Vec::new();
    for (n, raw) in text.lines().enumerate() {
        let origin = format!("{}:{}", path, n + 1);
        let line = raw.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let (key, rest) = line.split_once(char::is_whitespace).unwrap_or((line, ""));
        let rest = rest.trim();
        match key {
            "title" => {
                check_name("title", rest, &origin)?;
                title = rest.to_string();
            }
            "prompt" => {
                check_name("prompt", rest, &origin)?;
                prompt = rest.to_string();
            }
            "level" => {
                let (file, name) = rest
                    .split_once('|')
                    .ok_or_else(|| format!("{}: want `level <path> | <name>`", origin))?;
                let (file, name) = (file.trim(), name.trim());
                if file.is_empty() {
                    return Err(format!("{}: empty level path", origin));
                }
                check_name("name", name, &origin)?;
                levels.push((base.join(file).to_string_lossy().into_owned(), name.to_string()));
            }
            _ => return Err(format!("{}: unknown keyword {:?} (want title, prompt or level)", origin, key)),
        }
    }
    if levels.is_empty() {
        return Err(format!("{}: no \"level\" lines", path));
    }
    Ok(Manifest { title, prompt, levels })
}

/// The MENU chunk (header included): version, level count, entry count, title, prompt,
/// then one (level index, name) per entry. Little-endian; level_menu.cc is the reader.
fn menu_chunk(m: &Manifest) -> Vec<u8> {
    let mut p: Vec<u8> = Vec::new();
    write_u32_le(&mut p, MENU_VERSION);
    write_u32_le(&mut p, m.levels.len() as u32);
    write_u32_le(&mut p, m.levels.len() as u32);
    p.extend_from_slice(&(m.title.len() as u16).to_le_bytes());
    p.extend_from_slice(m.title.as_bytes());
    p.extend_from_slice(&(m.prompt.len() as u16).to_le_bytes());
    p.extend_from_slice(m.prompt.as_bytes());
    for (i, (_, name)) in m.levels.iter().enumerate() {
        write_u32_le(&mut p, i as u32);
        p.extend_from_slice(&(name.len() as u16).to_le_bytes());
        p.extend_from_slice(name.as_bytes());
    }
    let mut chunk = Vec::with_capacity(8 + p.len());
    write_tag(&mut chunk, b"MENU");
    write_u32_le(&mut chunk, p.len() as u32);
    chunk.extend_from_slice(&p);
    chunk
}

fn write_tag(buf: &mut Vec<u8>, tag: &[u8; 4]) {
    buf.extend_from_slice(tag);
}

fn write_u32_le(buf: &mut Vec<u8>, v: u32) {
    buf.extend_from_slice(&v.to_le_bytes());
}

fn pad_to_sector(buf: &mut Vec<u8>) {
    let rem = buf.len() % SECTOR;
    if rem != 0 {
        buf.resize(buf.len() + (SECTOR - rem), 0);
    }
}

const USAGE: &str = "Usage: cdpack <shel.fth> <L0.iff> [<L1.iff> ...] -o <cd.iff>\n       \
                     cdpack <shel.fth> --manifest <menu.manifest> -o <cd.iff>\n\n\
                     --manifest  levels and their menu names, one `level <path> | <name>` per line\n            \
                     (paths relative to the manifest), optional `title <text>` and `prompt <text>`;\n            \
                     adds a MENU chunk after the levels (docs/plans/2026-10-01-level-menu-selector.md)";

fn usage() -> ! {
    eprintln!("{}", USAGE);
    process::exit(1);
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.iter().skip(1).any(|a| a == "-h" || a == "--help") {
        println!("{}", USAGE);
        process::exit(0);
    }
    if args.len() < 4 {
        usage();
    }

    let shel_path = &args[1];

    let mut level_paths: Vec<String> = Vec::new();
    let mut out_path: Option<&str> = None;
    let mut manifest_path: Option<&str> = None;

    let mut i = 2;
    while i < args.len() {
        if args[i] == "-o" {
            i += 1;
            if i >= args.len() {
                eprintln!("error: -o requires a file argument");
                process::exit(1);
            }
            out_path = Some(&args[i]);
        } else if args[i] == "--manifest" {
            i += 1;
            if i >= args.len() {
                eprintln!("error: --manifest requires a file argument");
                process::exit(1);
            }
            manifest_path = Some(&args[i]);
        } else {
            level_paths.push(args[i].clone());
        }
        i += 1;
    }

    let out_path = out_path.unwrap_or_else(|| { eprintln!("error: missing -o <output>"); process::exit(1); });

    // --manifest supplies the levels (in TOC order) and their names; it does not mix with
    // positional level paths, so a bundle's level list has exactly one source.
    let manifest = manifest_path.map(|p| {
        if !level_paths.is_empty() {
            eprintln!("error: give the levels either as paths or in --manifest, not both");
            process::exit(1);
        }
        parse_manifest(p).unwrap_or_else(|e| { eprintln!("error: {}", e); process::exit(1); })
    });
    if let Some(m) = &manifest {
        level_paths = m.levels.iter().map(|(p, _)| p.clone()).collect();
    }

    if level_paths.is_empty() {
        eprintln!("error: need at least one level IFF");
        process::exit(1);
    }

    let shel_bytes = fs::read(shel_path).unwrap_or_else(|e| {
        eprintln!("error: reading {}: {}", shel_path, e);
        process::exit(1);
    });

    let level_data: Vec<Vec<u8>> = level_paths.iter().map(|p| {
        fs::read(p).unwrap_or_else(|e| {
            eprintln!("error: reading {}: {}", p, e);
            process::exit(1);
        })
    }).collect();

    // Compute sector-aligned offsets for each entry.
    // Sector 0 = TOC sector, Sector 1 = SHEL sector.
    let shel_offset = SECTOR;                    // sector 1
    let mut level_offsets: Vec<usize> = Vec::new();
    let mut cur = SECTOR * 2;                    // sector 2 = first level
    for lvl in &level_data {
        level_offsets.push(cur);
        let padded = (lvl.len() + SECTOR - 1) / SECTOR * SECTOR;
        cur += padded;
    }
    // The MENU chunk (with --manifest only) goes after the last level, so every level keeps
    // its TOC index (entry 1 + n) and level scripts' LEVEL_TO_RUN writes mean the same levels.
    let menu = manifest.as_ref().map(menu_chunk);
    let menu_offset = cur;
    if let Some(m) = &menu {
        cur += (m.len() + SECTOR - 1) / SECTOR * SECTOR;
    }
    let total_file_size = cur;

    let n_entries = 1 + level_data.len() + menu.is_some() as usize;   // SHEL + N levels (+ MENU)
    let toc_data_len = n_entries * 12;           // 12 bytes per entry

    // ── Sector 0: GAME header + TOC chunk + ALGN padding ────────────────────
    let mut sector0: Vec<u8> = Vec::with_capacity(SECTOR);

    // GAME header: tag + content_size (LE)
    write_tag(&mut sector0, b"GAME");
    write_u32_le(&mut sector0, (total_file_size - 8) as u32);

    // TOC chunk
    write_tag(&mut sector0, b"TOC\0");
    write_u32_le(&mut sector0, toc_data_len as u32);

    // SHEL TOC entry
    write_tag(&mut sector0, b"SHEL");
    write_u32_le(&mut sector0, shel_offset as u32);
    write_u32_le(&mut sector0, shel_bytes.len() as u32);

    // Level TOC entries: tag matches the first 4 bytes of each level file
    for (i, (lvl, &off)) in level_data.iter().zip(level_offsets.iter()).enumerate() {
        // Use the tag from the level file itself (first 4 bytes)
        let tag: [u8; 4] = if lvl.len() >= 4 {
            [lvl[0], lvl[1], lvl[2], lvl[3]]
        } else {
            // Fallback: L<n>\0\0
            let n = b'0' + (i as u8);
            [b'L', n, 0, 0]
        };
        sector0.extend_from_slice(&tag);
        write_u32_le(&mut sector0, off as u32);
        write_u32_le(&mut sector0, lvl.len() as u32);
    }
    if let Some(m) = &menu {
        write_tag(&mut sector0, b"MENU");
        write_u32_le(&mut sector0, menu_offset as u32);
        write_u32_le(&mut sector0, m.len() as u32);
    }

    // ALGN chunk to fill the rest of sector 0
    let algn_data_len = SECTOR - sector0.len() - 8;   // 8 = ALGN header
    assert!(algn_data_len > 0, "sector 0 overflow: headers too large");
    write_tag(&mut sector0, b"ALGN");
    write_u32_le(&mut sector0, algn_data_len as u32);
    sector0.resize(SECTOR, 0);

    // ── Sector 1: SHEL chunk + ALGN padding ──────────────────────────────────
    let mut sector1: Vec<u8> = Vec::with_capacity(SECTOR);
    write_tag(&mut sector1, b"SHEL");
    write_u32_le(&mut sector1, shel_bytes.len() as u32);
    sector1.extend_from_slice(&shel_bytes);

    let algn_data_len1 = SECTOR - sector1.len() - 8;
    assert!(algn_data_len1 > 0, "sector 1 overflow: SHEL script too large");
    write_tag(&mut sector1, b"ALGN");
    write_u32_le(&mut sector1, algn_data_len1 as u32);
    sector1.resize(SECTOR, 0);

    // ── Write output ─────────────────────────────────────────────────────────
    let mut out = fs::File::create(out_path).unwrap_or_else(|e| {
        eprintln!("error: creating {}: {}", out_path, e);
        process::exit(1);
    });

    out.write_all(&sector0).unwrap();
    out.write_all(&sector1).unwrap();

    for (lvl, &off) in level_data.iter().zip(level_offsets.iter()) {
        // Sanity: current write position should match expected offset
        let _ = off;   // offset already validated by construction
        out.write_all(lvl).unwrap();
        let padded = (lvl.len() + SECTOR - 1) / SECTOR * SECTOR;
        let pad = padded - lvl.len();
        if pad > 0 {
            let zeros = vec![0u8; pad];
            out.write_all(&zeros).unwrap();
        }
    }
    if let Some(m) = &menu {
        out.write_all(m).unwrap();
        let pad = (m.len() + SECTOR - 1) / SECTOR * SECTOR - m.len();
        out.write_all(&vec![0u8; pad]).unwrap();
    }

    let meta = fs::metadata(out_path).unwrap();
    eprintln!("cdpack: wrote {} bytes to {}", meta.len(), out_path);
    eprintln!("  SHEL: {} bytes (sector 1)", shel_bytes.len());
    for (i, (path, &off)) in level_paths.iter().zip(level_offsets.iter()).enumerate() {
        eprintln!("  L{}: {} bytes at sector {} ({})",
            i,
            level_data[i].len(),
            off / SECTOR,
            Path::new(path).file_name().unwrap_or_default().to_string_lossy());
    }
    if let (Some(m), Some(man)) = (&menu, &manifest) {
        eprintln!("  MENU: {} bytes at sector {} (\"{}\", {} entries)", m.len(), menu_offset / SECTOR, man.title, man.levels.len());
    }
}
