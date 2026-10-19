//! OAD → normalized JSON using the same schema model as Blender.
use std::{env,fs,io::Cursor};
fn quote(s:&str)->String {let mut out=String::from("\"");for c in s.chars(){match c {'"'=>out.push_str("\\\""),'\\'=>out.push_str("\\\\"),'\n'=>out.push_str("\\n"),'\r'=>out.push_str("\\r"),'\t'=>out.push_str("\\t"),c if c<' '=>out.push_str(&format!("\\u{:04x}",c as u32)),_=>out.push(c)}}out.push('"');out}
fn main(){let path=env::args().nth(1).expect("catalog <schema.oad>");let bytes=fs::read(path).unwrap();let oad=wf_oad::OadFile::read(&mut Cursor::new(bytes)).unwrap();let s=wf_attr_schema::from_oad(&oad);
    print!("{{\"name\":{},\"fields\":[",quote(&s.name));
    for (i,f) in s.fields.iter().enumerate(){if i>0{print!(",")};let choices=if let wf_attr_schema::FieldKind::Enum{items}=&f.kind{items.join("|")}else{String::new()};
        print!("{{\"key\":{},\"label\":{},\"kind\":{},\"help\":{},\"group\":{},\"choices\":{},\"min\":{},\"max\":{},\"default\":{},\"show\":{},\"width\":{},\"scale\":{}}}",quote(&f.key),quote(&f.label),quote(f.kind.tag()),quote(&f.help),quote(&f.group),quote(&choices),f.min_raw,f.max_raw,f.default_raw,f.show_as,f.byte_width,f.fp_scale as u32);
    }println!("]}}");}
