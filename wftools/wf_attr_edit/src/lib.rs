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
        default_raw:0,byte_width:width as u8,fp_scale:scale as f64,show_as:0,file_filter:String::new()};
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

#[cfg(test)] mod tests {
    use super::*;
    #[test] fn enum_offset_and_width(){assert_eq!(check(2,3,5,0,4,0,0,"a|b|c","4"),0);assert_eq!(check(2,3,5,0,4,0,0,"a|b|c","2"),3);assert_eq!(check(0,-1000,1000,0,1,0,0,"","128"),2);}
    #[test] fn exact_seed_text(){for s in ["0","713","4294967295"]{assert_eq!(check(3,0,0,0,0,10,1,"",s),0)}for s in ["-1","4294967296","NaN",""]{assert_ne!(check(3,0,0,0,0,10,1,"",s),0)}}
    #[test] fn fixed_scale_and_finite(){assert_eq!(check(1,0,65536,65536,4,0,0,"",".5"),0);assert_eq!(check(1,0,65536,65536,4,0,0,"","NaN"),1);assert_eq!(check(1,0,65536,65536,4,0,0,"","2"),2);}
}
