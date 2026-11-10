//! OAD (Object Attribute Data) binary file reader.
//!
//! Ports `wftools/oaddump/oad.{cc,hp}` and `wfsource/source/oas/oad.h`.
//!
//! # Binary format (all fields little-endian, `#pragma pack(1)`)
//!
//! ## Header (`_oadHeader`) — 80 bytes
//! ```text
//! [4]  chunkId   — must be b"OAD " stored as LE u32 = 0x2044414F
//! [4]  chunkSize — u32 (not validated by oaddump)
//! [68] name      — NUL-terminated display name
//! [4]  version   — u32
//! ```
//!
//! ## Entry (`_typeDescriptor`) — 1491 bytes
//! ```text
//! [1]   type (buttonType)
//! [64]  name
//! [4]   min  (i32)
//! [4]   max  (i32)
//! [4]   def  (i32)
//! [2]   len  (i16)
//! [512] string
//! [1]   showAs (visualRepresentation)
//! [2]   x  (i16)
//! [2]   y  (i16)
//! [128] helpMessage
//! [255] union (xdata / pad)
//! [512] lpstrFilter
//! ```

use std::fmt;
use std::io::{self, Read};

// ── error ────────────────────────────────────────────────────────────────────

#[derive(Debug)]
pub enum OadError {
    Io(io::Error),
    BadMagic(u32),
}

impl fmt::Display for OadError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            OadError::Io(e) => write!(f, "I/O error: {}", e),
            OadError::BadMagic(got) => write!(
                f,
                "not an OAD file: bad magic {:#010x} (expected {:#010x})",
                got, CHUNK_ID
            ),
        }
    }
}

impl std::error::Error for OadError {}
impl From<io::Error> for OadError { fn from(e: io::Error) -> Self { OadError::Io(e) } }

pub type Result<T> = std::result::Result<T, OadError>;

// ── constants ─────────────────────────────────────────────────────────────────

/// `'OAD '` stored as little-endian u32 on an x86 machine.
/// In C: `long chunkId = 'OAD '` (GCC multi-char literal = 0x4F414420),
/// written to disk as LE → bytes `[0x20, 0x44, 0x41, 0x4F]`,
/// read back as LE u32 = 0x4F414420.
pub const CHUNK_ID: u32 = u32::from_be_bytes(*b"OAD ");

pub const HEADER_SIZE: usize = 80;
pub const ENTRY_SIZE: usize = 1491;

// ── button types ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum ButtonType {
    Fixed16 = 0,
    Fixed32 = 1,
    Int8 = 2,
    Int16 = 3,
    Int32 = 4,
    String = 5,
    ObjectReference = 6,
    Filename = 7,
    PropertySheet = 8,
    NoInstances = 9,
    NoMesh = 10,
    SingleInstance = 11,
    Template = 12,
    ExtractCamera = 13,
    CameraReference = 14,
    LightReference = 15,
    Room = 16,
    CommonBlock = 17,
    EndCommon = 18,
    MeshName = 19,
    XData = 20,
    ExtractCamera2 = 21,
    ExtractCameraNew = 22,
    Waveform = 23,
    ClassReference = 24,
    GroupStart = 25,
    GroupStop = 26,
    ExtractLight = 27,
    Shortcut = 28,
    Unknown(u8),
}

impl ButtonType {
    pub fn from_u8_pub(v: u8) -> Self { Self::from_u8(v) }

    fn from_u8(v: u8) -> Self {
        match v {
            0 => ButtonType::Fixed16,
            1 => ButtonType::Fixed32,
            2 => ButtonType::Int8,
            3 => ButtonType::Int16,
            4 => ButtonType::Int32,
            5 => ButtonType::String,
            6 => ButtonType::ObjectReference,
            7 => ButtonType::Filename,
            8 => ButtonType::PropertySheet,
            9 => ButtonType::NoInstances,
            10 => ButtonType::NoMesh,
            11 => ButtonType::SingleInstance,
            12 => ButtonType::Template,
            13 => ButtonType::ExtractCamera,
            14 => ButtonType::CameraReference,
            15 => ButtonType::LightReference,
            16 => ButtonType::Room,
            17 => ButtonType::CommonBlock,
            18 => ButtonType::EndCommon,
            19 => ButtonType::MeshName,
            20 => ButtonType::XData,
            21 => ButtonType::ExtractCamera2,
            22 => ButtonType::ExtractCameraNew,
            23 => ButtonType::Waveform,
            24 => ButtonType::ClassReference,
            25 => ButtonType::GroupStart,
            26 => ButtonType::GroupStop,
            27 => ButtonType::ExtractLight,
            28 => ButtonType::Shortcut,
            other => ButtonType::Unknown(other),
        }
    }

    pub fn name(&self) -> String {
        match self {
            ButtonType::Fixed16 => "BUTTON_FIXED16".into(),
            ButtonType::Fixed32 => "BUTTON_FIXED32".into(),
            ButtonType::Int8 => "BUTTON_INT8".into(),
            ButtonType::Int16 => "BUTTON_INT16".into(),
            ButtonType::Int32 => "BUTTON_INT32".into(),
            ButtonType::String => "BUTTON_STRING".into(),
            ButtonType::ObjectReference => "BUTTON_OBJECT_REFERENCE".into(),
            ButtonType::Filename => "BUTTON_FILENAME".into(),
            ButtonType::PropertySheet => "BUTTON_PROPERTY_SHEET".into(),
            ButtonType::NoInstances => "LEVELCONFLAG_NOINSTANCES".into(),
            ButtonType::NoMesh => "LEVELCONFLAG_NOMESH".into(),
            ButtonType::SingleInstance => "LEVELCONFLAG_SINGLEINSTANCE".into(),
            ButtonType::Template => "LEVELCONFLAG_TEMPLATE".into(),
            ButtonType::ExtractCamera => "LEVELCONFLAG_EXTRACTCAMERA".into(),
            ButtonType::CameraReference => "BUTTON_CAMERA_REFERENCE".into(),
            ButtonType::LightReference => "BUTTON_LIGHT_REFERENCE".into(),
            ButtonType::Room => "LEVELCONFLAG_ROOM".into(),
            ButtonType::CommonBlock => "LEVELCONFLAG_COMMONBLOCK".into(),
            ButtonType::EndCommon => "LEVELCONFLAG_ENDCOMMON".into(),
            ButtonType::MeshName => "BUTTON_MESHNAME".into(),
            ButtonType::XData => "BUTTON_XDATA".into(),
            ButtonType::ExtractCamera2 => "BUTTON_EXTRACT_CAMERA".into(),
            ButtonType::ExtractCameraNew => "LEVELCONFLAG_EXTRACTCAMERANEW".into(),
            ButtonType::Waveform => "BUTTON_WAVEFORM".into(),
            ButtonType::ClassReference => "BUTTON_CLASS_REFERENCE".into(),
            ButtonType::GroupStart => "BUTTON_GROUP_START".into(),
            ButtonType::GroupStop => "BUTTON_GROUP_STOP".into(),
            ButtonType::ExtractLight => "LEVELCONFLAG_EXTRACTLIGHT".into(),
            ButtonType::Shortcut => "LEVELCONFLAG_SHORTCUT".into(),
            ButtonType::Unknown(_) => "Unknown".into(),
        }
    }

    pub fn raw(&self) -> u8 {
        match self {
            ButtonType::Unknown(v) => *v,
            _ => unsafe { *(self as *const Self as *const u8) },
        }
    }
}

// ── showAs modifier bits ──────────────────────────────────────────────────────

/// `SHOW_AS_LIVE` (oad.h): the engine re-reads this field after construction,
/// so a runtime edit takes effect. A modifier bit OR-ed onto a presentation,
/// e.g. `SHOW_AS_RADIOBUTTONS|SHOW_AS_LIVE`, like `SHOW_AS_VECTOR`.
pub const SHOW_AS_LIVE: u8 = 0x40;
/// `SHOW_AS_VECTOR` (oad.h): an object reference drawn as a vector.
pub const SHOW_AS_VECTOR: u8 = 0x80;
/// The presentation code without the modifier bits (`SHOW_AS_BASE_MASK`, oad.h).
pub const SHOW_AS_BASE_MASK: u8 = 0x3f;

/// The presentation (`SHOW_AS_NUMBER` … `SHOW_AS_FILENAME`) of a raw showAs
/// byte, with `SHOW_AS_LIVE` and `SHOW_AS_VECTOR` taken off. Compare this,
/// never the raw byte: a live radio field is `0x45`, not `5`. The C++ twin is
/// `ShowAsBase` in wfsource/source/oas/oad.h.
pub fn show_as_base(show_as: u8) -> u8 { show_as & SHOW_AS_BASE_MASK }

/// True when a raw showAs byte carries `SHOW_AS_LIVE`.
pub fn show_as_is_live(show_as: u8) -> bool { show_as & SHOW_AS_LIVE != 0 }

// ── xdata conversion actions ──────────────────────────────────────────────────

pub const XDATA_CONVERSION_NAMES: &[&str] = &[
    "XDATA_IGNORE",
    "XDATA_COPY",
    "XDATA_OBJECTLIST",
    "XDATA_CONTEXTUALANIMATIONLIST",
    "XDATA_SCRIPT",
];

fn xdata_name(action: u8) -> &'static str {
    XDATA_CONVERSION_NAMES
        .get(action as usize)
        .copied()
        .unwrap_or("XDATA_UNKNOWN")
}

// ── reading helpers ───────────────────────────────────────────────────────────

fn read_exact_buf<R: Read, const N: usize>(r: &mut R) -> io::Result<[u8; N]> {
    let mut buf = [0u8; N];
    r.read_exact(&mut buf)?;
    Ok(buf)
}

fn cstr(bytes: &[u8]) -> &str {
    let end = bytes.iter().position(|&b| b == 0).unwrap_or(bytes.len());
    std::str::from_utf8(&bytes[..end]).unwrap_or("<invalid utf8>")
}

// ── OAD header ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct OadHeader {
    pub chunk_id: u32,
    pub chunk_size: u32,
    pub name: [u8; 68],
    pub version: u32,
}

impl OadHeader {
    fn read<R: Read>(r: &mut R) -> io::Result<Self> {
        let chunk_id = u32::from_le_bytes(read_exact_buf::<_, 4>(r)?);
        let chunk_size = u32::from_le_bytes(read_exact_buf::<_, 4>(r)?);
        let name = read_exact_buf::<_, 68>(r)?;
        let version = u32::from_le_bytes(read_exact_buf::<_, 4>(r)?);
        Ok(OadHeader { chunk_id, chunk_size, name, version })
    }

    pub fn display_name(&self) -> &str {
        cstr(&self.name)
    }
}

// ── OAD entry ─────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct OadEntry {
    pub button_type: ButtonType,
    pub name: [u8; 64],
    pub min: i32,
    pub max: i32,
    pub def: i32,
    pub len: i16,
    pub string: [u8; 512],
    pub show_as: u8,
    pub x: i16,
    pub y: i16,
    pub help_message: [u8; 128],
    /// Raw union bytes (255 bytes: xdata or pad)
    pub union_bytes: [u8; 255],
    pub lpstr_filter: [u8; 512],
}

impl OadEntry {
    fn read<R: Read>(r: &mut R) -> io::Result<Self> {
        let type_byte = read_exact_buf::<_, 1>(r)?[0];
        let name = read_exact_buf::<_, 64>(r)?;
        let min = i32::from_le_bytes(read_exact_buf::<_, 4>(r)?);
        let max = i32::from_le_bytes(read_exact_buf::<_, 4>(r)?);
        let def = i32::from_le_bytes(read_exact_buf::<_, 4>(r)?);
        let len = i16::from_le_bytes(read_exact_buf::<_, 2>(r)?);
        let string = read_exact_buf::<_, 512>(r)?;
        let show_as = read_exact_buf::<_, 1>(r)?[0];
        let x = i16::from_le_bytes(read_exact_buf::<_, 2>(r)?);
        let y = i16::from_le_bytes(read_exact_buf::<_, 2>(r)?);
        let help_message = read_exact_buf::<_, 128>(r)?;
        let union_bytes = read_exact_buf::<_, 255>(r)?;
        let lpstr_filter = read_exact_buf::<_, 512>(r)?;

        Ok(OadEntry {
            button_type: ButtonType::from_u8(type_byte),
            name,
            min,
            max,
            def,
            len,
            string,
            show_as,
            x,
            y,
            help_message,
            union_bytes,
            lpstr_filter,
        })
    }

    pub fn name_str(&self) -> &str { cstr(&self.name) }
    pub fn string_str(&self) -> &str { cstr(&self.string) }
    pub fn help_str(&self) -> &str { cstr(&self.help_message) }
    /// The presentation without modifier bits; see [`show_as_base`].
    pub fn show_as_base(&self) -> u8 { show_as_base(self.show_as) }
    /// True when the field is declared `SHOW_AS_LIVE`; see [`show_as_is_live`].
    pub fn is_live(&self) -> bool { show_as_is_live(self.show_as) }
    /// Raw bytes of the Windows file-dialog filter string (null-separated pairs).
    /// Format: `Desc1\0Pattern1\0Desc2\0Pattern2\0\0`.
    pub fn lpstr_filter_bytes(&self) -> &[u8] { &self.lpstr_filter }

    /// Display name from the xdata union (first 64 bytes of union).
    pub fn display_name(&self) -> &str { cstr(&self.union_bytes[5..69]) }

    /// XData conversion action (byte 0 of union).
    pub fn xdata_conversion_action(&self) -> u8 { self.union_bytes[0] }

    /// XData bRequired (bytes 1–4 of union, LE i32).
    pub fn xdata_required(&self) -> i32 {
        i32::from_le_bytes(self.union_bytes[1..5].try_into().unwrap())
    }
}

impl fmt::Display for OadEntry {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let raw = self.button_type.raw() as i32;
        writeln!(f, "   Type: {} <{}>", self.button_type.name(), raw)?;
        writeln!(f, "   Name: {} (length = {})", self.name_str(), self.name_str().len())?;
        writeln!(f, "Display: {}", self.display_name())?;
        writeln!(f, "    Min: {}\t{}", self.min, self.min as f64 / 65536.0)?;
        if self.button_type == ButtonType::GroupStart {
            writeln!(f, "  Width: {}", self.max)?;
        } else {
            writeln!(f, "    Max: {}\t{}", self.max, self.max as f64 / 65536.0)?;
        }
        writeln!(f, "Default: {}", self.def)?;
        writeln!(f, "  String:{}", self.string_str())?;
        writeln!(f, " ShowAs: {}", self.show_as)?;
        if self.button_type == ButtonType::XData {
            writeln!(f, "conversionAction: {}", xdata_name(self.xdata_conversion_action()))?;
            writeln!(f, "bRequired: {}", self.xdata_required())?;
        }
        if !self.help_str().is_empty() {
            writeln!(f, "   Help: {}", self.help_str())?;
        }
        if self.x != -1 { writeln!(f, "      X: {}", self.x)?; }
        if self.y != -1 { writeln!(f, "      Y: {}", self.y)?; }
        Ok(())
    }
}

// ── OAD file ──────────────────────────────────────────────────────────────────

/// Field binary size when stored in either per-object OAD or common block.
/// Matches `wftools/lvldump-rs/src/oad.rs::field_size` (which is itself a port
/// of `wftools/iff2lvl/oad.cc::QObjectAttributeDataEntry::SizeOfOnDisk`).
pub fn field_size(entry: &OadEntry) -> usize {
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
            // Action ∈ [1..=4] (COPY/OBJECTLIST/CONTEXTUALANIMATIONLIST/SCRIPT)
            // burns 4 bytes; IGNORE (0) and anything else burns 0.
            let action = entry.xdata_conversion_action();
            if (1..=4).contains(&action) { 4 } else { 0 }
        }

        _ => 0,
    }
}

/// Location of a descriptor's stored bytes, relative to the object payload or
/// to a common block referenced by an offset in that payload.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FieldLocation {
    Object { offset: usize },
    Common { pointer_offset: usize, offset: usize },
}

/// Walk OAD entries using the same sizes levcomp writes. `start_offset` is the
/// object payload position at the first supplied entry, allowing a trimmed OAD
/// to use the prefix offset shipped beside it.
pub fn field_location(entries: &[OadEntry], index: usize, start_offset: usize) -> Option<FieldLocation> {
    let mut object = start_offset;
    let mut common: Option<(usize, usize)> = None;
    for (i, entry) in entries.iter().enumerate() {
        if i == index {
            return match (entry.button_type, common) {
                (ButtonType::EndCommon, Some(_)) => None,
                (ButtonType::CommonBlock, _) => Some(FieldLocation::Object { offset: object }),
                (_, Some((pointer_offset, offset))) => Some(FieldLocation::Common { pointer_offset, offset }),
                _ => Some(FieldLocation::Object { offset: object }),
            };
        }
        match entry.button_type {
            ButtonType::CommonBlock => {
                if common.is_some() { return None; }
                common = Some((object, 0));
                object = object.checked_add(4)?;
            }
            ButtonType::EndCommon => { common = None; }
            _ => match &mut common {
                Some((_, offset)) => *offset = offset.checked_add(field_size(entry))?,
                None => object = object.checked_add(field_size(entry))?,
            },
        }
    }
    None
}

#[derive(Debug, Clone)]
pub struct OadFile {
    pub header: OadHeader,
    pub entries: Vec<OadEntry>,
}

impl OadFile {
    /// Write an OAD binary to a writer.
    pub fn write<W: std::io::Write>(&self, w: &mut W) -> io::Result<()> {
        w.write_all(&self.header.chunk_id.to_le_bytes())?;
        w.write_all(&self.header.chunk_size.to_le_bytes())?;
        w.write_all(&self.header.name)?;
        w.write_all(&self.header.version.to_le_bytes())?;
        for e in &self.entries {
            w.write_all(&[e.button_type.raw()])?;
            w.write_all(&e.name)?;
            w.write_all(&e.min.to_le_bytes())?;
            w.write_all(&e.max.to_le_bytes())?;
            w.write_all(&e.def.to_le_bytes())?;
            w.write_all(&e.len.to_le_bytes())?;
            w.write_all(&e.string)?;
            w.write_all(&[e.show_as])?;
            w.write_all(&e.x.to_le_bytes())?;
            w.write_all(&e.y.to_le_bytes())?;
            w.write_all(&e.help_message)?;
            w.write_all(&e.union_bytes)?;
            w.write_all(&e.lpstr_filter)?;
        }
        Ok(())
    }

    /// Parse an OAD binary from a reader.
    pub fn read<R: Read>(r: &mut R) -> Result<Self> {
        let header = OadHeader::read(r)?;
        if header.chunk_id != CHUNK_ID {
            return Err(OadError::BadMagic(header.chunk_id));
        }
        let mut entries = Vec::new();
        loop {
            match OadEntry::read(r) {
                Ok(e) => entries.push(e),
                Err(e) if e.kind() == io::ErrorKind::UnexpectedEof => break,
                Err(e) => return Err(OadError::Io(e)),
            }
        }
        Ok(OadFile { header, entries })
    }
}

impl fmt::Display for OadFile {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        writeln!(f, "{}", self.header.display_name())?;
        writeln!(f)?;
        for entry in &self.entries {
            writeln!(f, "{}", entry)?;
        }
        Ok(())
    }
}

// ── tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    fn make_oad_bytes(name: &str, entries: &[(&str, u8, i32, i32, i32)]) -> Vec<u8> {
        let mut buf = Vec::new();
        // header
        buf.extend_from_slice(&CHUNK_ID.to_le_bytes());       // chunkId
        buf.extend_from_slice(&0u32.to_le_bytes());           // chunkSize
        let mut hname = [0u8; 68];
        let nb = name.as_bytes();
        hname[..nb.len().min(67)].copy_from_slice(&nb[..nb.len().min(67)]);
        buf.extend_from_slice(&hname);
        buf.extend_from_slice(&0x00010202u32.to_le_bytes());  // version
        assert_eq!(buf.len(), HEADER_SIZE);

        for (ename, btype, min, max, def) in entries {
            let start = buf.len();
            buf.push(*btype);                                  // type
            let mut nm = [0u8; 64];
            let eb = ename.as_bytes();
            nm[..eb.len().min(63)].copy_from_slice(&eb[..eb.len().min(63)]);
            buf.extend_from_slice(&nm);                        // name
            buf.extend_from_slice(&min.to_le_bytes());         // min
            buf.extend_from_slice(&max.to_le_bytes());         // max
            buf.extend_from_slice(&def.to_le_bytes());         // def
            buf.extend_from_slice(&0i16.to_le_bytes());        // len
            buf.extend_from_slice(&[0u8; 512]);                // string
            buf.push(1);                                       // showAs = SHOW_AS_NUMBER
            buf.extend_from_slice(&(-1i16).to_le_bytes());     // x = -1
            buf.extend_from_slice(&(-1i16).to_le_bytes());     // y = -1
            buf.extend_from_slice(&[0u8; 128]);                // helpMessage
            buf.extend_from_slice(&[0u8; 255]);                // union
            buf.extend_from_slice(&[0u8; 512]);                // lpstrFilter
            assert_eq!(buf.len() - start, ENTRY_SIZE, "entry size mismatch");
        }
        buf
    }

    #[test]
    fn round_trip_empty() {
        let bytes = make_oad_bytes("EmptyObject", &[]);
        let mut cur = Cursor::new(&bytes);
        let oad = OadFile::read(&mut cur).unwrap();
        assert_eq!(oad.header.display_name(), "EmptyObject");
        assert!(oad.entries.is_empty());
    }

    #[test]
    fn round_trip_one_entry() {
        let bytes = make_oad_bytes("TestObject", &[("speed", 4, 0, 65536, 0)]);
        let mut cur = Cursor::new(&bytes);
        let oad = OadFile::read(&mut cur).unwrap();
        assert_eq!(oad.entries.len(), 1);
        assert_eq!(oad.entries[0].name_str(), "speed");
        assert_eq!(oad.entries[0].button_type, ButtonType::Int32);
        assert_eq!(oad.entries[0].min, 0);
        assert_eq!(oad.entries[0].max, 65536);
    }

    #[test]
    fn bad_magic_rejected() {
        let mut bytes = make_oad_bytes("X", &[]);
        bytes[0] = 0xFF; // corrupt magic
        let mut cur = Cursor::new(&bytes);
        assert!(matches!(OadFile::read(&mut cur), Err(OadError::BadMagic(_))));
    }

    /// Parse a real .oad binary produced by oas2oad (prep → g++ → objcopy).
    /// This test catches byte-order bugs in CHUNK_ID that synthetic round-trip
    /// tests miss (both sides would use the same wrong constant).
    #[test]
    fn parse_real_oad_fixture() {
        let bytes = include_bytes!("../tests/fixtures/disabled.oad");
        let mut cur = Cursor::new(bytes.as_ref());
        let oad = OadFile::read(&mut cur).expect("failed to parse disabled.oad fixture");
        assert_eq!(oad.header.display_name(), "Disabled");
        assert_eq!(oad.entries.len(), 1);
        assert_eq!(oad.entries[0].name_str(), "LEVELCONFLAG_NOINSTANCES");
    }

    /// Parse all original .oad files from the 2016 game data as fixtures.
    /// Verifies header name and entry count for each.
    #[test]
    fn parse_all_original_fixtures() {
        let cases: &[(&str, &str, usize)] = &[
            ("actbox.oad",    "Activation Box",                    149),
            ("actboxor.oad",  "Activation Box Object Reference",   139),
            ("alias.oad",     "Alias",                               3),
            ("camera.oad",    "Camera",                            144),
            ("camshot.oad",   "Camera Shot",                       158),
            ("destroy.oad",   "Destroyer",                         138),
            ("director.oad",  "Director",                          129),
            ("disabled.oad",  "Disabled",                            1),
            ("enemy.oad",     "Enemy",                             129),
            ("explode.oad",   "Explosion",                         131),
            ("generato.oad",  "Generator",                         142),
            ("gold.oad",      "Gold",                              129),
            ("levelobj.oad",  "Level Object",                      276),
            ("light.oad",     "Light",                             137),
            ("matte.oad",     "Matte",                             129),
            ("missile.oad",   "Missile",                           132),
            ("platform.oad",  "Platform",                          129),
            ("player.oad",    "Player",                            129),
            ("room.oad",      "Room",                               22),
            ("shadow.oad",    "Shadow",                            129),
            ("shield.oad",    "Shield",                            134),
            ("spike.oad",     "Spike",                             138),
            ("statplat.oad",  "Stationary Platform",               129),
            ("target.oad",    "Target Position",                   128),
            ("test.oad",      "Test",                              146),
            ("tool.oad",      "Tool",                              143),
            ("warp.oad",      "Warp",                              138),
        ];

        let fixture_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("tests/fixtures");

        for (filename, expected_name, expected_entries) in cases {
            let data = std::fs::read(fixture_dir.join(filename))
                .unwrap_or_else(|e| panic!("failed to read {filename}: {e}"));
            let mut cur = Cursor::new(&data);
            let oad = OadFile::read(&mut cur)
                .unwrap_or_else(|e| panic!("failed to parse {filename}: {e}"));
            assert_eq!(oad.header.display_name(), *expected_name,
                "name mismatch in {filename}");
            assert_eq!(oad.entries.len(), *expected_entries,
                "entry count mismatch in {filename}");
        }
    }

    #[test]
    fn show_as_modifiers_mask_off() {
        const RADIO: u8 = 5;
        assert_eq!(show_as_base(RADIO | SHOW_AS_LIVE), RADIO);
        assert_eq!(show_as_base(6 | SHOW_AS_VECTOR), 6);
        assert_eq!(show_as_base(2 | SHOW_AS_LIVE | SHOW_AS_VECTOR), 2);
        assert!(show_as_is_live(RADIO | SHOW_AS_LIVE));
        assert!(!show_as_is_live(RADIO));
        assert!(!show_as_is_live(6 | SHOW_AS_VECTOR));
        // Every base code (0..=12) fits under the mask, so masking never changes one.
        for code in 0..=12u8 { assert_eq!(show_as_base(code), code); }
    }

    /// R10 (runtime object editing): the Blender generators read their schemas
    /// from tests/fixtures/, levcomp from wfsource/source/oas/. A field missing
    /// from a stale fixture is silently dropped from every level a generator
    /// exports, so every fixture that has a counterpart in wfsource/source/oas
    /// must be byte-identical to it. After regenerating a `.oad` there, copy it
    /// here: `cp wfsource/source/oas/<stem>.oad wftools/wf_oad/tests/fixtures/`.
    /// (`destroy.oad` and `generato.oad` are the 2016 files under their old
    /// 8.3 names and have no counterpart.)
    #[test]
    fn fixtures_match_wfsource_oas() {
        let manifest = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let fixtures = manifest.join("tests/fixtures");
        let source = manifest.join("../../wfsource/source/oas");
        let mut checked = 0;
        let mut stale = Vec::new();
        for entry in std::fs::read_dir(&fixtures).expect("read fixtures") {
            let path = entry.unwrap().path();
            if path.extension().and_then(|e| e.to_str()) != Some("oad") { continue; }
            let twin = source.join(path.file_name().unwrap());
            if !twin.exists() { continue; }
            checked += 1;
            if std::fs::read(&path).unwrap() != std::fs::read(&twin).unwrap() {
                stale.push(path.file_name().unwrap().to_string_lossy().into_owned());
            }
        }
        stale.sort();
        assert!(checked >= 25, "expected the fixtures to have counterparts, checked {checked}");
        assert!(stale.is_empty(),
            "fixtures differ from wfsource/source/oas (copy them over): {stale:?}");
    }

    #[test]
    fn parse_common_oad() {
        let data = include_bytes!("../tests/fixtures/common.oad");
        let oad = OadFile::read(&mut Cursor::new(data)).unwrap();
        assert_eq!(oad.header.display_name(), "Common");
        assert_eq!(oad.entries.len(), 14);
        assert!(oad.entries.iter().any(|e| e.name_str() == "Script"),
            "common.oad must contain a Script field");
    }
}
