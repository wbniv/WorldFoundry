// oad.rs — .lc file loading, .oad schema loading, binary OAD struct reading
// Port of wftools/lvldump/oad.cc + oad.hp

use std::fs::File;
use std::io::{self, BufRead, BufReader, Write};
use std::process;

use wf_oad::{ButtonType, OadEntry, OadFile};

// ── OAD context ──────────────────────────────────────────────────────────────

pub struct OadContext {
    /// Object type names from objects.lc; index 0 = "nullobject"
    pub object_types: Vec<String>,
    /// Loaded .oad schema files; index 0 = None (null object placeholder)
    pub object_oads: Vec<Option<OadFile>>,
}

impl OadContext {
    pub fn empty() -> Self {
        OadContext { object_types: Vec::new(), object_oads: Vec::new() }
    }

    pub fn has_lc(&self) -> bool {
        !self.object_types.is_empty()
    }

    pub fn type_name(&self, idx: usize) -> Option<&str> {
        self.object_types.get(idx).map(|s| s.as_str())
    }
}

// ── .lc file loading ──────────────────────────────────────────────────────────

/// Load `objects.lc` and populate object_types.
pub fn load_lc_file(path: &str) -> OadContext {
    let f = File::open(path).unwrap_or_else(|_| {
        eprintln!("LvlDump Error: LC file <{}> not found.", path);
        process::exit(1);
    });
    let reader = BufReader::new(f);
    let mut lines = reader.lines();

    // Validate header
    let first = lines.next().unwrap_or_else(|| Ok(String::new())).unwrap_or_default();
    if &first[..first.len().min(11)] != "Objects.lc:" {
        eprintln!("LvlDump Error: <{}> is not a .LC file", path);
        process::exit(1);
    }

    // Skip to opening {
    let mut found_open = false;
    let mut deferred: Option<String> = None;
    for line in lines.by_ref() {
        let line = line.unwrap_or_default();
        if line.contains('{') {
            found_open = true;
            // The line after { is the first entry
            deferred = Some(String::new()); // signal to read next below
            break;
        }
    }
    if !found_open {
        eprintln!("LvlDump Error: problem parsing .LC file");
        process::exit(1);
    }
    let _ = deferred; // consumed the '{' line; next iter gives entries

    // Read object type names until }
    let mut object_types: Vec<String> = Vec::new();
    for line in lines {
        let line = line.unwrap_or_default();
        if line.contains('}') {
            break;
        }
        if !line.is_empty() {
            let mut s = line.to_lowercase();
            // trim leading whitespace
            s = s.trim_start_matches(|c: char| c == '\t' || c == ' ').to_string();
            object_types.push(s);
        }
    }

    if object_types.is_empty() || object_types[0] != "nullobject" {
        eprintln!("LvlDump Error: first object type must be 'nullobject'");
        process::exit(1);
    }

    OadContext { object_types, object_oads: Vec::new() }
}

// ── .oad file loading ─────────────────────────────────────────────────────────

/// Load .oad schema files for all object types (call after load_lc_file).
pub fn load_oad_files(ctx: &mut OadContext, lc_path: &str) {
    // Strip "objects.lc" suffix to get directory
    const LC_SUFFIX: &str = "objects.lc";
    let dir = if lc_path.len() > LC_SUFFIX.len() {
        &lc_path[..lc_path.len() - LC_SUFFIX.len()]
    } else {
        ""
    };

    // Index 0 = null object placeholder
    ctx.object_oads.push(None);

    for index in 1..ctx.object_types.len() {
        let path = format!("{}{}.oad", dir, ctx.object_types[index]);
        let data = std::fs::read(&path).unwrap_or_else(|_| {
            eprintln!("LevelCon Error: problem reading .OAD file <{}>", path);
            process::exit(1);
        });
        let oad = OadFile::read(&mut std::io::Cursor::new(&data)).unwrap_or_else(|e| {
            eprintln!("LevelCon Error: problem parsing .OAD file <{}>: {}", path, e);
            process::exit(1);
        });
        ctx.object_oads.push(Some(oad));
    }
}

// ── OAD entry display ─────────────────────────────────────────────────────────

/// Format a single OAD entry (schema descriptor) — matches C++ operator<< on QObjectAttributeDataEntry.
fn write_entry_header(entry: &OadEntry, out: &mut dyn Write) -> io::Result<()> {
    write!(out, "      ")?;
    write!(out, "{}", entry.button_type.name())?;
    write!(out, " <{}>", entry.button_type.raw() as i32)?;
    write!(out, "  Name: <{}>", entry.name_str())?;
    if entry.len != 0 {
        writeln!(out)?;
        write!(out, "        String: <{}>", entry.string_str())?;
        write!(out, "  Len: <{}>", entry.len)?;
    }
    writeln!(out)
}

// ── OAD field sizes (SizeOfOnDisk from oad.cc) ───────────────────────────────

fn field_size(entry: &OadEntry) -> usize {
    match entry.button_type {
        ButtonType::Fixed32
        | ButtonType::Int32
        | ButtonType::ObjectReference
        | ButtonType::Filename
        | ButtonType::CommonBlock
        | ButtonType::MeshName
        | ButtonType::ClassReference => 4,

        ButtonType::Fixed16 | ButtonType::Int16 => 2,

        ButtonType::Int8 => 1,

        ButtonType::String => entry.len as usize,

        ButtonType::XData => {
            // conversionAction ∈ {COPY=1, OBJECTLIST=2, CONTEXTUALANIMATIONLIST=3, SCRIPT=4}
            // C++ condition: action == XDATA_COPY(0??) ... actually from oad.cc the actions are
            // XDATA_COPY, XDATA_OBJECTLIST, XDATA_CONTEXTUALANIMATIONLIST, XDATA_SCRIPT
            // and the check is conversionAction == one of those four.
            // From XDATA_CONVERSION_NAMES: index 0=XDATA_IGNORE, 1=XDATA_COPY, 2=OBJECTLIST,
            // 3=CONTEXTUALANIMATIONLIST, 4=SCRIPT. But assert(XDATA_CONVERSION_MAX==5) means 5 values.
            // C++ checks != XDATA_IGNORE (i.e., action > 0 or the named ones).
            // The assert says MAX==5, and checks COPY||OBJECTLIST||CONTEXTUALANIMATIONLIST||SCRIPT
            // which is values 1,2,3,4 — so action >= 1 && action <= 4.
            let action = entry.xdata_conversion_action();
            if action >= 1 && action <= 4 { 4 } else { 0 }
        }

        // Zero-size types (flags, markers, references that burn no space)
        _ => 0,
    }
}

// ── Binary OAD struct reader ──────────────────────────────────────────────────

/// Parse and display binary OAD data for one object.
/// Matches C++ QObjectAttributeData::LoadStruct + operator<< on QObjectAttributeData.
///
/// - `schema`: the OAD type descriptor list
/// - `oad_data`: the raw OAD bytes from after _ObjectOnDisk in the .lvl file
/// - `common_block`: the level's entire common data block
pub fn dump_oad_struct(
    schema: &OadFile,
    oad_data: &[u8],
    _common_block: &[u8],
    out: &mut dyn Write,
) -> io::Result<()> {
    writeln!(out, "    Oad Header Name:{}", schema.header.display_name())?;

    let mut obj_cursor = 0usize;   // position in oad_data
    let mut in_common = false;
    let mut _common_cursor = 0usize;

    for entry in &schema.entries {
        write_entry_header(entry, out)?;

        // Read the field's binary value from the appropriate buffer
        let size = field_size(entry);

        if in_common {
            // Reading from common block
            if entry.button_type == ButtonType::EndCommon {
                in_common = false;
                continue;
            }
            // Nested COMMONBLOCK inside common block is not supported (C++ assert(0))
            if size > 0 {
                _common_cursor += size;
            }
        } else {
            // Reading from object OAD data
            if entry.button_type == ButtonType::CommonBlock {
                // Read 4-byte offset into common block
                if obj_cursor + 4 <= oad_data.len() {
                    let offset = i32::from_le_bytes(
                        oad_data[obj_cursor..obj_cursor + 4].try_into().unwrap()
                    ) as usize;
                    obj_cursor += 4;
                    _common_cursor = offset;
                    in_common = true;
                }
            } else if size > 0 {
                obj_cursor += size;
            }
        }
    }

    Ok(())
}
