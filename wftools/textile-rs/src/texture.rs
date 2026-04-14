// texture.rs — room processing pipeline (port of texture.cc)

use std::io::Write;
use std::path::Path;

use crate::allocmap::{AllocationMap, AllocationRestrictions, round};
use crate::bitmap::Bitmap;
use crate::ccyc::write_ccyc;
use crate::config::Config;
use crate::locfile::{locate_file, file_stem, file_ext};
use crate::profile;
use crate::rmuv::write_rmuv;

const MATERIAL_NAME_LEN: usize = 256;

// ─── IFF parsing ─────────────────────────────────────────────────────────────

/// Parse an IFF object file and collect texture filename references.
/// Returns false if the file is not a recognisable IFF format.
pub fn parse_iff(
    data: &[u8],
    texture_names: &mut Vec<String>,
    texture_dirs: &mut Vec<String>,
    obj_dir: &str,
    verbose: bool,
) -> bool {
    if data.len() < 8 { return false; }
    let tag = &data[0..4];
    let len = u32::from_le_bytes([data[4], data[5], data[6], data[7]]) as usize;
    if data.len() < 8 + len { return false; }
    let payload = &data[8..8 + len];

    match tag {
        b"MODL" => { parse_modl(payload, texture_names, texture_dirs, obj_dir, verbose); true }
        b"CROW" => { parse_crow(payload, texture_names, texture_dirs, obj_dir, verbose); true }
        _ => false,
    }
}

fn in_texture_list(names: &[String], name: &str) -> bool {
    names.iter().any(|n| n == name)
}

/// Parse MODL chunk payload: series of (tag[4] + size: u32 LE + payload) sub-chunks.
/// Looks for MATL sub-chunks containing _MaterialOnDisk entries.
fn parse_modl(
    data: &[u8],
    texture_names: &mut Vec<String>,
    texture_dirs: &mut Vec<String>,
    obj_dir: &str,
    verbose: bool,
) {
    // _MaterialOnDisk layout: i32 flags + i32 color + 256-byte textureName
    const ENTRY: usize = 4 + 4 + MATERIAL_NAME_LEN;

    let mut pos = 0usize;
    while pos + 8 <= data.len() {
        let tag  = &data[pos..pos + 4];
        let size = u32::from_le_bytes([data[pos+4], data[pos+5], data[pos+6], data[pos+7]]) as usize;
        let payload_start = pos + 8;
        let payload_end   = payload_start + size;

        if verbose {
            eprintln!("  [MODL] tag={} size={}", String::from_utf8_lossy(tag), size);
        }

        if tag == b"MATL" && payload_end <= data.len() {
            assert_eq!(size % ENTRY, 0, "MATL size not a multiple of material entry size");
            let n = size / ENTRY;
            for i in 0..n {
                let base       = payload_start + i * ENTRY;
                let name_start = base + 8; // skip flags (4) + color (4)
                let name_bytes = &data[name_start..name_start + MATERIAL_NAME_LEN];
                if let Some(tex_name) = cstr_to_string(name_bytes) {
                    if !tex_name.is_empty() && !in_texture_list(texture_names, &tex_name) {
                        if verbose { eprintln!("  [MODL] material: {}", tex_name); }
                        texture_names.push(tex_name);
                        texture_dirs.push(obj_dir.to_string());
                    }
                }
            }
        }

        // Advance past this sub-chunk (payload aligned to 4 bytes)
        pos = payload_start + round(size as i32, 4) as usize;
    }
}

/// Parse CROW chunk payload: series of sub-chunks.
/// Looks for BMPL sub-chunks containing null-terminated texture names.
fn parse_crow(
    data: &[u8],
    texture_names: &mut Vec<String>,
    texture_dirs: &mut Vec<String>,
    obj_dir: &str,
    verbose: bool,
) {
    let mut pos = 0usize;
    while pos + 8 <= data.len() {
        let tag  = &data[pos..pos + 4];
        let size = u32::from_le_bytes([data[pos+4], data[pos+5], data[pos+6], data[pos+7]]) as usize;
        pos += 8;

        if verbose {
            eprintln!("  [CROW] tag={} size={}", String::from_utf8_lossy(tag), size);
        }

        if tag == b"BMPL" && pos + size <= data.len() {
            // Null-terminated strings packed end-to-end
            let bmpl = &data[pos..pos + size];
            let mut start = 0usize;
            while start < bmpl.len() {
                let end = bmpl[start..].iter().position(|&b| b == 0)
                    .map(|i| start + i)
                    .unwrap_or(bmpl.len());
                let tex_name = std::str::from_utf8(&bmpl[start..end]).unwrap_or("").to_string();
                if !tex_name.is_empty() && !in_texture_list(texture_names, &tex_name) {
                    if verbose { eprintln!("  [CROW] material: {}", tex_name); }
                    texture_names.push(tex_name);
                    texture_dirs.push(obj_dir.to_string());
                }
                start = end + 1;
            }
        }

        let aligned = round(size as i32, 4) as usize;
        pos += aligned;
    }
}

fn cstr_to_string(bytes: &[u8]) -> Option<String> {
    let end = bytes.iter().position(|&b| b == 0).unwrap_or(bytes.len());
    std::str::from_utf8(&bytes[..end]).ok().map(|s| s.to_string())
}

// ─── Lookup textures from object list ────────────────────────────────────────

/// For each object in `object_names`, find all texture references.
/// Direct image files are added as-is; IFF files are parsed.
pub fn lookup_textures(
    object_names: &[String],
    texture_names: &mut Vec<String>,
    texture_dirs: &mut Vec<String>,
    cfg: &Config,
    log: &mut dyn Write,
) {
    if cfg.verbose { eprintln!("Objects:"); }

    for obj in object_names {
        if cfg.verbose { eprintln!("  {}", obj); }
        let _ = write!(log, "<a href=\"{}\">{}</a> ", obj, obj);

        let ext = file_ext(obj).to_lowercase();

        // Direct image file — add as texture directly
        if ext == ".tga" || ext == ".bmp"
            || ext == ".rgb" || ext == ".rgba"
            || ext == ".bw"  || ext == ".sgi"
        {
            if !in_texture_list(texture_names, obj) {
                texture_names.push(obj.clone());
                texture_dirs.push("texture".to_string());
            }
            continue;
        }

        // Object/mesh file — locate and parse IFF
        let found = locate_file(obj, &cfg.vrml_path, None)
            .or_else(|| {
                let lc = obj.to_lowercase();
                locate_file(&lc, &cfg.vrml_path, None)
            });

        let path = match found {
            Some(p) => p,
            None => {
                eprintln!("TEXTILE error: couldn't find mesh \"{}\" in path {}", obj, cfg.vrml_path);
                std::process::exit(1);
            }
        };

        let data = match std::fs::read(&path) {
            Ok(d) => d,
            Err(e) => {
                eprintln!("TEXTILE error: couldn't open \"{}\": {}", path.display(), e);
                std::process::exit(1);
            }
        };

        // Object directory = directory containing the object file
        let obj_dir = path.parent()
            .map(|p| p.to_string_lossy().into_owned())
            .unwrap_or_default();

        if !parse_iff(&data, texture_names, texture_dirs, &obj_dir, cfg.verbose) {
            eprintln!("Don't know how to process file \"{}\" (not a valid IFF binary file)", obj);
        }
    }
}

// ─── Load texture images ──────────────────────────────────────────────────────

pub fn load_textures(
    _room_name: &str,
    texture_names: &[String],
    texture_dirs: &[String],
    x_page: i32,
    y_page: i32,
    cfg: &Config,
    global_error: &mut bool,
) -> Vec<Bitmap> {
    let mut textures: Vec<Bitmap> = Vec::new();

    for (tex_name, tex_dir) in texture_names.iter().zip(texture_dirs.iter()) {
        // Build search path: object directory + texture path
        let combined_path = format!("{};{}", tex_dir, cfg.texture_path);

        // Try locating the file
        let found = locate_file(tex_name, &combined_path, None)
            .or_else(|| {
                let lc = tex_name.to_lowercase();
                locate_file(&lc, &combined_path, None)
            });

        let path = match found {
            Some(p) => p,
            None => {
                eprintln!("TEXTILE error: couldn't find texture \"{}\"", tex_name);
                *global_error = true;
                continue;
            }
        };

        let ext = file_ext(&path.to_string_lossy()).to_lowercase();

        let mut bm = match ext.as_str() {
            ".tga" | ".bmp" | ".png" => Bitmap::load(&path, cfg),
            ".rgb" | ".bw" | ".sgi" => {
                eprintln!("textile: SGI format not supported; convert with: convert {} {}.png",
                    path.display(),
                    path.file_stem().unwrap_or_default().to_string_lossy());
                continue;
            }
            _ => {
                eprintln!("textile: unknown file format for texture \"{}\" (must be .tga, .bmp, or .png)",
                    path.display());
                continue;
            }
        };

        let bm = match bm.take() {
            Some(b) => b,
            None => {
                eprintln!("textile: unknown error loading file \"{}\"", path.display());
                *global_error = true;
                continue;
            }
        };

        if bm.pixels.is_empty() {
            eprintln!("textile: unknown error loading file \"{}\"", path.display());
            *global_error = true;
            continue;
        }

        // Check per-texture power-of-two override from INI
        // (uses "RoomN::texture.tga" key in Configuration section)
        // Skipping this detail for now; cfg.power_of2 was set at load time.

        // Warn if texture doesn't fit on page
        let bpp_scale = 16 / bm.bitdepth;
        if bm.width > x_page * bpp_scale || bm.height > y_page {
            eprintln!("texture width: {}  height: {}", bm.width, bm.height);
            eprintln!("x_page: {}  y_page: {}", x_page, y_page);
            eprintln!("Texture \"{}\" does not even fit on page!", bm.name);
        }

        textures.push(bm);
    }

    textures
}

// ─── Texture packing ─────────────────────────────────────────────────────────

/// Sort textures by area (largest first) and pack into an atlas.
pub fn texture_fit_all(
    textures: &mut Vec<Bitmap>,
    x_page: i32,
    y_page: i32,
    ar: &AllocationRestrictions,
    room_name: &str,
    cfg: &Config,
    log: &mut dyn Write,
    global_error: &mut bool,
) -> Bitmap {
    let bg = if cfg.show_packing { 0x77u8 } else { 0u8 };
    let mut atlas = Bitmap::new_blank(x_page, y_page, bg, cfg.power_of2);

    // Sort by area descending
    textures.sort_by(|a, b| b.area().cmp(&a.area()));

    let mut am = AllocationMap::new(ar);

    for (i, tex) in textures.iter_mut().enumerate() {
        atlas.texture_fit(tex, &mut am, room_name, "texture", i as i32, cfg, log, global_error);
    }

    if cfg.crop_output {
        let new_w = am.x_extent() * ar.x_align / (16 / 4);
        let new_h = am.y_extent() * ar.y_align;
        atlas.crop(new_w, new_h);
    }

    atlas
}

/// Pack palette data (for paletted textures) into a palette atlas.
pub fn palette_fit_all(
    textures: &mut Vec<Bitmap>,
    pal_x_page: i32,
    pal_y_page: i32,
    ar: &AllocationRestrictions,
    room_name: &str,
    cfg: &Config,
    log: &mut dyn Write,
    global_error: &mut bool,
) -> Bitmap {
    let mut pal_atlas = Bitmap::new_blank(pal_x_page, pal_y_page, 0, cfg.power_of2);

    // Sort by colours_used descending
    let mut order: Vec<usize> = (0..textures.len()).collect();
    order.sort_by(|&a, &b| textures[b].colours_used().cmp(&textures[a].colours_used()));

    let mut am = AllocationMap::new(ar);

    for &idx in &order {
        let tex = &textures[idx];
        if tex.bitdepth <= 8 {
            let mut pal_bm = Bitmap::from_palette(tex);
            pal_atlas.texture_fit(
                &mut pal_bm, &mut am, room_name, "palette for", idx as i32, cfg, log, global_error,
            );
            textures[idx].xpal = pal_bm.subx * 16;
            textures[idx].ypal = pal_bm.suby;
        }
    }

    pal_atlas
}

// ─── HTML log ────────────────────────────────────────────────────────────────

pub fn write_texture_log(textures: &[Bitmap], log: &mut dyn Write) {
    if textures.is_empty() { return; }

    let _ = writeln!(log, "<div align=\"left\">");
    let _ = writeln!(log, "<table border=1>");
    let _ = writeln!(log, "<thead><tr>");
    let _ = writeln!(log, "<td>#</td><td>Bitmap</td><td>Dimensions</td><td>Colours Used</td><td>Translucent</td>");
    let _ = writeln!(log, "</tr></thead>");
    let _ = writeln!(log, "<tbody>");

    for (i, tex) in textures.iter().enumerate() {
        let stem = file_stem(&tex.name).to_string();
        let ext  = file_ext(&tex.name).to_string();
        let full = format!("{}{}", stem, ext);
        let _ = writeln!(log, "<tr><td>{}</td><td><a href=\"{}\">{}</a></td><td>{}x{}x{}</td><td>{}</td><td>{}</td></tr>",
            i + 1,
            full, full,
            tex.width, tex.height, 1 << tex.bitdepth,
            if tex.bitdepth <= 8 { tex.colours_used().to_string() } else { String::new() },
            if tex.has_transparent { "yes" } else { "no" },
        );
    }

    let _ = writeln!(log, "</tbody></table></div>");
}

// ─── Main room processing ─────────────────────────────────────────────────────

/// Process one room: load textures, pack them, write output files.
/// Returns true if any error occurred.
pub fn process_room(
    room_name: &str,
    x_page: i32,
    y_page: i32,
    cfg: &Config,
    log: &mut dyn Write,
    global_error: &mut bool,
) {
    let tga_file = format!("{}.tga", room_name);

    // Read comma-separated object list from INI
    let objects_str = profile::get_string("Rooms", room_name, "", &cfg.ini_file);
    let object_names: Vec<String> = objects_str
        .split(',')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect();

    let _ = write!(log,
        "<p>Room &quot;{}&quot; [ <a href=\"{}\">{}</a> ] contains {} object{} [ ",
        room_name,
        tga_file, tga_file,
        object_names.len(),
        if object_names.len() == 1 { "" } else { "s" },
    );

    let mut texture_names: Vec<String> = Vec::new();
    let mut texture_dirs:  Vec<String> = Vec::new();

    lookup_textures(&object_names, &mut texture_names, &mut texture_dirs, cfg, log);

    let _ = writeln!(log, "]</p>");

    let mut textures = load_textures(
        room_name, &texture_names, &texture_dirs, x_page, y_page, cfg, global_error,
    );

    // Texture atlas allocation
    let x_align_slots = x_page / cfg.x_align * (16 / 4); // slots = page/align * bits_per_slot
    let ar_tex = AllocationRestrictions {
        width:                  x_align_slots,
        height:                 y_page / cfg.y_align,
        x_align:                cfg.x_align,
        y_align:                cfg.y_align,
        align_to_size_multiple: cfg.align_to_size_multiple,
        k:                      16 / 4,
    };

    let mut atlas = texture_fit_all(
        &mut textures, x_page, y_page, &ar_tex, room_name, cfg, log, global_error,
    );

    // Palette atlas allocation
    let ar_pal = AllocationRestrictions {
        x_align:                64,  // C++ sets 16 then overwrites with 64
        y_align:                1,
        width:                  cfg.pal_x_page / 64 * (16 / 4),
        height:                 cfg.pal_y_page,
        align_to_size_multiple: false,
        k:                      16 / 4,
    };

    let pal_atlas = palette_fit_all(
        &mut textures, cfg.pal_x_page, cfg.pal_y_page, &ar_pal,
        room_name, cfg, log, global_error,
    );

    write_texture_log(&textures, log);

    // Save texture atlas TGA
    atlas.remove_colour_cycles();
    atlas.save_tga(&cfg.out_dir, &tga_file, cfg.flip_y_out);

    // Save palette TGA ("pal0.tga" / "palPerm.tga" etc.)
    let pal_suffix = if room_name.to_lowercase().starts_with("room") {
        &room_name[4..]
    } else {
        room_name
    };
    let pal_file = format!("pal{}.tga", pal_suffix);
    pal_atlas.save_tga(&cfg.out_dir, &pal_file, cfg.flip_y_out);

    // Write RMUV .ruv
    let ruv_path = Path::new(&cfg.out_dir).join(format!("{}.ruv", room_name));
    if let Err(e) = write_rmuv(&ruv_path, &textures, cfg.pal_x_align, cfg.pal_y_align) {
        eprintln!("textile: error writing \"{}\": {}", ruv_path.display(), e);
        *global_error = true;
    }

    // Write colour cycle .cyc
    let cyc_path = Path::new(&cfg.out_dir).join(format!("{}.cyc", room_name));
    if let Err(e) = write_ccyc(&cyc_path, &pal_atlas) {
        eprintln!("textile: error writing \"{}\": {}", cyc_path.display(), e);
        *global_error = true;
    }

    let _ = writeln!(log);
}
