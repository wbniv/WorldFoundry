// ccyc.rs — colour cycle binary output (port of ccyc.hp / write_ccyc in texture.cc)

use std::fs::File;
use std::io::{self, BufWriter, Write};
use std::path::Path;

use crate::bitmap::Bitmap;

/// Write a .cyc file for the given bitmap's colour cycles.
/// Format:
///   b"ccyc"          — 4-byte tag
///   cb_ccyc: u32 LE  — sizeof(u32) + 8*n
///   n:       u32 LE  — number of colour cycles
///   [start: i16 LE, end: i16 LE, speed: i32 LE] * n
pub fn write_ccyc(path: &Path, bitmap: &Bitmap) -> io::Result<()> {
    let f = File::create(path)?;
    let mut w = BufWriter::new(f);

    let n = bitmap.colour_cycles.len() as u32;
    // each CCYC entry: i16 + i16 + i32 = 8 bytes
    let cb_ccyc: u32 = 4 + 8 * n;

    w.write_all(b"ccyc")?;
    w.write_all(&cb_ccyc.to_le_bytes())?;
    w.write_all(&n.to_le_bytes())?;

    for cc in &bitmap.colour_cycles {
        let start = cc.start as i16;
        let end   = cc.end as i16;
        let speed = (cc.speed * 65536.0) as i32;
        w.write_all(&start.to_le_bytes())?;
        w.write_all(&end.to_le_bytes())?;
        w.write_all(&speed.to_le_bytes())?;
    }

    Ok(())
}
