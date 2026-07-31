//! cdpack — assemble a WF GAME cd.iff from a SHEL script + N level LVAS IFFs.
//!
//! Usage: cdpack <shel.fth> <L0.iff> [<L1.iff> ...] -o <cd.iff>
//!
//! Output layout:
//!   Sector 0 (2048 B): GAME<total> + TOC<entries> + ALGN<pad>
//!   Sector 1 (2048 B): SHEL<script> + ALGN<pad>
//!   Sector 2+        : each level IFF, sector-aligned

use std::fs;
use std::io::Write;
use std::path::Path;
use std::process;

const SECTOR: usize = 2048;

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

fn usage() -> ! {
    eprintln!("Usage: cdpack <shel.fth> <L0.iff> [<L1.iff> ...] -o <cd.iff>");
    process::exit(1);
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 4 {
        usage();
    }

    let shel_path = &args[1];

    let mut level_paths: Vec<&str> = Vec::new();
    let mut out_path: Option<&str> = None;

    let mut i = 2;
    while i < args.len() {
        if args[i] == "-o" {
            i += 1;
            if i >= args.len() {
                eprintln!("error: -o requires a file argument");
                process::exit(1);
            }
            out_path = Some(&args[i]);
        } else {
            level_paths.push(&args[i]);
        }
        i += 1;
    }

    let out_path = out_path.unwrap_or_else(|| { eprintln!("error: missing -o <output>"); process::exit(1); });

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
    let total_file_size = cur;

    let n_entries = 1 + level_data.len();        // SHEL + N levels
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
}
