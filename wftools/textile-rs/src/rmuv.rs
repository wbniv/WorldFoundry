// rmuv.rs — RMUV UV-mapping binary output (port of rmuv.hp/cc + write_rmuv in texture.cc)
//
// _RMUV binary layout (48 bytes, #pragma pack(1) in C++):
//   szTextureName[33]  — basename + extension, null-padded
//   nFrame: i8
//   u, v:   i16 LE    — position in atlas
//   w, h:   i16 LE    — texture dimensions
//   palx, paly: i16 LE — palette coordinates
//   flags:  u16 LE    — bits [15:11]=bitdepth, [10]=bTranslucent, [9:0]=padding

use std::fs::File;
use std::io::{self, BufWriter, Write};
use std::path::Path;

use crate::bitmap::Bitmap;
use crate::locfile::{file_stem, file_ext};

/// Write an RMUV .ruv file for all textures in `textures`.
pub fn write_rmuv(
    path: &Path,
    textures: &[Bitmap],
    pal_x_align: i32,
    pal_y_align: i32,
) -> io::Result<()> {
    let f = File::create(path)?;
    let mut w = BufWriter::new(f);

    let n = textures.len() as u32;
    // cb = sizeof(u32) + 48 * n
    let cb_rmuv: u32 = 4 + 48 * n;

    w.write_all(b"rmuv")?;
    w.write_all(&cb_rmuv.to_le_bytes())?;
    w.write_all(&n.to_le_bytes())?;

    for tex in textures {
        write_entry(&mut w, tex, pal_x_align, pal_y_align)?;
    }

    Ok(())
}

fn write_entry(
    w: &mut impl Write,
    tex: &Bitmap,
    pal_x_align: i32,
    pal_y_align: i32,
) -> io::Result<()> {
    // szTextureName[33] — stem + ext, max 32 chars + null
    let stem = file_stem(&tex.name);
    let ext  = file_ext(&tex.name);
    let full = format!("{}{}", stem, ext);
    let bytes = full.as_bytes();
    let mut name_buf = [0u8; 33];
    let len = bytes.len().min(32);
    name_buf[..len].copy_from_slice(&bytes[..len]);
    w.write_all(&name_buf)?;

    // nFrame
    w.write_all(&[0u8])?;

    // u, v, w, h
    w.write_all(&(tex.subx as i16).to_le_bytes())?;
    w.write_all(&(tex.suby as i16).to_le_bytes())?;
    w.write_all(&(tex.width as i16).to_le_bytes())?;
    w.write_all(&(tex.height as i16).to_le_bytes())?;

    // palx, paly — palette grid coordinates. For 16-bit textures (no
    // palette), C++ textile leaves xPal/yPal as -1 and still divides
    // (texture.cc:777-778), producing palx = -1/16 = 0 (truncates to
    // zero) and paly = -1/1 = -1 (stored as int16 = 0xFFFF). Match
    // exactly rather than gating on >= 0 — the -1→0xFFFF sentinel is
    // visible in oracle bytes for every 16-bit entry.
    let palx = tex.xpal / pal_x_align;
    let paly = tex.ypal / pal_y_align;
    w.write_all(&(palx as i16).to_le_bytes())?;
    w.write_all(&(paly as i16).to_le_bytes())?;

    // flags: bits [15:11]=bitdepth, [10]=bTranslucent, [9:0]=0
    let bd: u16 = match tex.bitdepth {
        4 | 8 => tex.bitdepth as u16,
        15 | 16 => 15,
        _ => 15,
    };
    let flags: u16 = (bd << 11) | (if tex.has_transparent { 1 << 10 } else { 0 });
    w.write_all(&flags.to_le_bytes())?;

    // Total per entry: 33+1+2+2+2+2+2+2+2 = 48 bytes ✓
    Ok(())
}
