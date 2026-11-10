//! Shared strict value validation for authoring and runtime property editors.
//! The C ABI takes normalized descriptors; no editor/CRDT/Python dependency.
use wf_attr_schema::{FieldDescriptor, FieldKind, FieldValue, Schema, Values};

/// kind: 0 integer, 1 fixed, 2 enum, 3 text, 4 boolean.
/// rule: 0 ordinary, 1 unsigned decimal uint32 text.
pub fn check(kind: u32, low: i32, high: i32, scale: u32, width: u32,
             max_len: u32, rule: u32, choices: &str, value: &str) -> i32 {
    let items: Vec<String> = choices.split('|').map(str::to_owned).collect();
    let (field_kind, parsed) = match kind {
        0 => {
            let Ok(v) = value.parse::<i64>() else { return 1 };
            let (min,max) = match width {1 => (-128,127), 2 => (-32768,32767), _ => (i32::MIN as i64,i32::MAX as i64)};
            if v < min || v > max {return 2}
            (FieldKind::Int, FieldValue::Int(v))
        },
        1 => {
            let Ok(v) = value.parse::<f64>() else { return 1 };
            if !v.is_finite() || scale == 0 { return 1 }
            let raw = v * scale as f64;
            let (min,max) = if width==2 {(-32768.0,32767.0)} else {(i32::MIN as f64,i32::MAX as f64)};
            if raw.round() < min || raw.round() > max {return 2}
            (FieldKind::Float,FieldValue::Float(v))
        },
        2 => {
            let Ok(v) = value.parse::<i64>() else {return 1};
            if v < low as i64 || v > high as i64 {return 3}
            let Some(label) = items.get((v-low as i64) as usize) else {return 3};
            (FieldKind::Enum{items:items.clone()},FieldValue::Enum(label.clone()))
        },
        3 => {
            if value.len() > max_len as usize {return 4}
            if rule==1 && (value.is_empty() || !value.bytes().all(|c|c.is_ascii_digit()) || value.parse::<u32>().is_err()) {return 5}
            (FieldKind::Str,FieldValue::Str(value.to_owned()))
        },
        4 => {
            if value!="0" && value!="1" {return 1}
            return 0;
        },
        _ => return 1,
    };
    let f = FieldDescriptor {key:"value".into(),label:"value".into(),kind:field_kind,
        help:String::new(),group:String::new(),min_raw:low,max_raw:if kind==3 {max_len as i32} else {high},
        default_raw:0,byte_width:width as u8,fp_scale:scale as f64,show_as:0,live:false,file_filter:String::new()};
    let schema=Schema{name:String::new(),fields:vec![f]};
    let mut values=Values::new();values.insert("value".into(),parsed);
    if wf_attr_validate::validate(&schema,&values).iter().any(|i|i.is_error) {2} else {0}
}

/// Strings are UTF-8 pointer/length pairs, borrowed only for this call.
#[no_mangle]
pub unsafe extern "C" fn wf_attr_check(kind:u32, low:i32, high:i32, scale:u32,
    width:u32,max_len:u32,rule:u32,choices:*const u8,choices_len:usize,
    value:*const u8,value_len:usize) -> i32 {
    if choices.is_null() || value.is_null() || choices_len>65536 || value_len>65536 {return 1}
    let Ok(c)=std::str::from_utf8(std::slice::from_raw_parts(choices,choices_len)) else {return 1};
    let Ok(v)=std::str::from_utf8(std::slice::from_raw_parts(value,value_len)) else {return 1};
    check(kind,low,high,scale,width,max_len,rule,c,v)
}

/// Location of a field in an object payload or a referenced common block.
/// `common_pointer` is -1 for an object field; otherwise it is the byte offset
/// of the common-area pointer in the payload and `offset` is within that block.
#[repr(C)]
#[derive(Debug, Default, PartialEq, Eq)]
pub struct OadFieldLocation {
    pub common_pointer: i32,
    pub offset: u32,
    pub width: u32,
}

#[repr(C)]
struct OadString { data: *const u8, length: usize }
impl OadString {
    fn borrowed(s: &str) -> Self { Self { data: s.as_ptr(), length: s.len() } }
}

#[repr(C)]
pub struct OadField {
    index: usize,
    kind: u32, show: u32, live: u32, width: u32, scale: u32, storage_width: u32,
    minimum: i32, maximum: i32, default_value: i32,
    key: OadString, label: OadString, help: OadString, group: OadString, choices: OadString,
}

/// Visit visible normalized OAD fields; borrowed strings live for one callback.
///
/// # Safety
/// `oad` must point to `oad_len` readable bytes, and the visitor must obey the
/// callback contract and not retain the borrowed pointers.
#[no_mangle]
pub unsafe extern "C" fn wf_attr_oad_visit(
    oad: *const u8, oad_len: usize,
    visitor: Option<unsafe extern "C" fn(*mut std::ffi::c_void, *const OadField) -> i32>,
    context: *mut std::ffi::c_void,
) -> i32 {
    if oad.is_null() || visitor.is_none() || oad_len < wf_oad::HEADER_SIZE || oad_len > 16 * 1024 * 1024
        || (oad_len - wf_oad::HEADER_SIZE) % wf_oad::ENTRY_SIZE != 0 { return 1; }
    let bytes = std::slice::from_raw_parts(oad, oad_len);
    let Ok(oad) = wf_oad::OadFile::read(&mut std::io::Cursor::new(bytes)) else { return 1; };
    let schema = wf_attr_schema::from_oad(&oad);
    for (index, field) in schema.fields.iter().enumerate() {
        if !field.is_visible() { continue; }
        let (kind, choices) = match &field.kind {
            FieldKind::Int => (0, String::new()),
            FieldKind::Float => (1, String::new()),
            FieldKind::Enum { items } => (2, items.join("|")),
            FieldKind::Str | FieldKind::Annotation => (3, String::new()),
            FieldKind::Bool => (4, String::new()),
            FieldKind::Section => (5, String::new()),
            FieldKind::Group => (6, String::new()),
            FieldKind::GroupEnd => (7, String::new()),
            FieldKind::FileRef { .. } | FieldKind::ObjRef { .. } => (8, String::new()),
            FieldKind::Skip => continue,
        };
        let item = OadField {
            index, kind, show: field.show_as as u32, live: u32::from(field.live),
            width: field.byte_width as u32, scale: field.fp_scale as u32,
            storage_width: wf_oad::field_size(&oad.entries[index]) as u32,
            minimum: field.min_raw, maximum: field.max_raw, default_value: field.default_raw,
            key: OadString::borrowed(&field.key), label: OadString::borrowed(&field.label),
            help: OadString::borrowed(&field.help), group: OadString::borrowed(&field.group),
            choices: OadString::borrowed(&choices),
        };
        if visitor.unwrap()(context, &item) != 0 { return 1; }
    }
    0
}

/// Resolve a local entry index in a full or trimmed OAD. Returns 0 on success;
/// malformed descriptors, structural fields and invalid arguments return 1.
/// The caller supplies the payload offset of the first descriptor in the OAD.
///
/// # Safety
/// `oad` must point to `oad_len` readable bytes and `out` to writable storage.
#[no_mangle]
pub unsafe extern "C" fn wf_attr_oad_field_location(
    oad: *const u8, oad_len: usize, index: usize, start_offset: u32,
    out: *mut OadFieldLocation,
) -> i32 {
    if oad.is_null() || out.is_null() || oad_len < wf_oad::HEADER_SIZE || oad_len > 16 * 1024 * 1024
        || (oad_len - wf_oad::HEADER_SIZE) % wf_oad::ENTRY_SIZE != 0 { return 1; }
    let bytes = std::slice::from_raw_parts(oad, oad_len);
    let Ok(schema) = wf_oad::OadFile::read(&mut std::io::Cursor::new(bytes)) else { return 1; };
    let Some(entry) = schema.entries.get(index) else { return 1; };
    let width = wf_oad::field_size(entry);
    if width == 0 || entry.button_type == wf_oad::ButtonType::CommonBlock { return 1; }
    let Some(location) = wf_oad::field_location(&schema.entries, index, start_offset as usize) else { return 1; };
    let (common_pointer, offset) = match location {
        wf_oad::FieldLocation::Object { offset } => (-1, offset),
        wf_oad::FieldLocation::Common { pointer_offset, offset } => {
            let Ok(pointer_offset) = i32::try_from(pointer_offset) else { return 1; };
            (pointer_offset, offset)
        }
    };
    let Ok(offset) = u32::try_from(offset) else { return 1; };
    let Ok(width) = u32::try_from(width) else { return 1; };
    *out = OadFieldLocation { common_pointer, offset, width };
    0
}

/// Size of the serialized common block containing the selected descriptor.
///
/// # Safety
/// `oad` must point to `oad_len` readable bytes and `out_size` to writable storage.
#[no_mangle]
pub unsafe extern "C" fn wf_attr_oad_common_size(
    oad: *const u8, oad_len: usize, index: usize, out_size: *mut u32,
) -> i32 {
    if oad.is_null() || out_size.is_null() || oad_len < wf_oad::HEADER_SIZE || oad_len > 16 * 1024 * 1024
        || (oad_len - wf_oad::HEADER_SIZE) % wf_oad::ENTRY_SIZE != 0 { return 1; }
    let bytes = std::slice::from_raw_parts(oad, oad_len);
    let Ok(schema) = wf_oad::OadFile::read(&mut std::io::Cursor::new(bytes)) else { return 1; };
    let Some(size) = wf_oad::common_block_size(&schema.entries, index) else { return 1; };
    let Ok(size) = u32::try_from(size) else { return 1; };
    *out_size = size;
    0
}

#[cfg(test)] mod tests {
    use super::*;
    #[test] fn enum_offset_and_width(){assert_eq!(check(2,3,5,0,4,0,0,"a|b|c","4"),0);assert_eq!(check(2,3,5,0,4,0,0,"a|b|c","2"),3);assert_eq!(check(0,-1000,1000,0,1,0,0,"","128"),2);}
    #[test] fn exact_seed_text(){for s in ["0","713","4294967295"]{assert_eq!(check(3,0,0,0,0,10,1,"",s),0)}for s in ["-1","4294967296","NaN",""]{assert_ne!(check(3,0,0,0,0,10,1,"",s),0)}}
    #[test] fn fixed_scale_and_finite(){assert_eq!(check(1,0,65536,65536,4,0,0,"",".5"),0);assert_eq!(check(1,0,65536,65536,4,0,0,"","NaN"),1);assert_eq!(check(1,0,65536,65536,4,0,0,"","2"),2);}
    #[test] fn oad_field_location_uses_shared_walker() {
        let bytes = include_bytes!("../../wf_oad/tests/fixtures/levelobj.oad");
        let schema = wf_oad::OadFile::read(&mut std::io::Cursor::new(bytes)).unwrap();
        let index = schema.entries.iter().position(|e| e.name_str() == "Editable Objects").unwrap();
        let mut result = OadFieldLocation::default();
        assert_eq!(unsafe { wf_attr_oad_field_location(bytes.as_ptr(), bytes.len(), index, 0, &mut result) }, 0);
        assert_eq!(result, OadFieldLocation { common_pointer: -1, offset: 572, width: 4 });
        let (common_index, pointer, offset) = schema.entries.iter().enumerate().find_map(|(i, e)| {
            if wf_oad::field_size(e) == 0 || e.button_type == wf_oad::ButtonType::CommonBlock { return None; }
            match wf_oad::field_location(&schema.entries, i, 0) {
                Some(wf_oad::FieldLocation::Common { pointer_offset, offset }) => Some((i, pointer_offset, offset)),
                _ => None,
            }
        }).expect("fixture has a stored common-block field");
        assert_eq!(unsafe { wf_attr_oad_field_location(bytes.as_ptr(), bytes.len(), common_index, 0, &mut result) }, 0);
        assert_eq!(result.common_pointer, pointer as i32);
        assert_eq!(result.offset, offset as u32);
        let mut size = 0;
        assert_eq!(unsafe { wf_attr_oad_common_size(bytes.as_ptr(), bytes.len(), common_index, &mut size) }, 0);
        assert!(size >= result.offset + result.width && size % 4 == 0);
        assert_eq!(unsafe { wf_attr_oad_common_size(bytes.as_ptr(), bytes.len(), index, &mut size) }, 1);
        let mut incomplete = schema.clone();
        incomplete.entries.truncate(common_index + 1);
        assert_eq!(wf_oad::common_block_size(&incomplete.entries, common_index), None);
        assert_eq!(unsafe { wf_attr_oad_field_location(bytes.as_ptr(), bytes.len() - 1, index, 0, &mut result) }, 1);
        assert_eq!(unsafe { wf_attr_oad_field_location(bytes.as_ptr(), bytes.len(), schema.entries.len(), 0, &mut result) }, 1);
    }
}
