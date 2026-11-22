//! A level with no settings holder gets a default one.
//!
//! Every level offers the settings declared in `wfsource/source/oas/global_settings.inc` (today **Show
//! framerate**), carried by every settings holder. A level that places no holder would offer none, so after
//! parsing, if no object's class declares a global key, one `LevelSettings` object is appended (last, so no
//! existing object's index moves). docs/plans/2026-11-22-global-level-settings.md.
//!
//! It only acts when the OAD directory (which holds `global_settings.inc`) is known, so a build without
//! one, and every fixture, compiles exactly as before. `--no-default-settings` turns it off.

use wf_iff::{str_to_id, write_chunk};

use crate::lev_parser::{parse_obj, LevObject};

/// The class of the minimal holder (wfsource/source/oas/levelsettings.oas).
pub const HOLDER_CLASS: &str = "levelsettings";
const HOLDER_NAME: &str = "Level Settings";
/// 0.1 in 16.16 fixed point: the same small box a Blender-exported holder carries.
const TENTH: i32 = 6554;

/// The keys `global_settings.inc` declares (`TYPEENTRY…(key,…)` lines), in order.
pub fn global_keys(inc_text: &str) -> Vec<String> {
    inc_text
        .lines()
        .filter_map(|line| {
            let line = line.trim_start();
            if line.starts_with("@*") || !line.starts_with("TYPEENTRY") {
                return None;
            }
            let args = &line[line.find('(')? + 1..];
            Some(args[..args.find(',')?].trim().to_string())
        })
        .collect()
}

/// True when some object's class declares every key in `keys` (a level that already has a holder).
pub fn has_global(objects: &[LevObject], keys: &[String], class_has_key: &dyn Fn(&str, &str) -> bool) -> bool {
    !keys.is_empty()
        && objects.iter().any(|o| keys.iter().all(|k| class_has_key(&o.class_name, k)))
}

fn named(id: &str, name: &str, data: &[u8]) -> Vec<u8> {
    let mut cstr = name.as_bytes().to_vec();
    cstr.push(0);
    let mut payload = write_chunk(str_to_id("NAME"), &cstr);
    payload.extend(write_chunk(str_to_id("DATA"), data));
    write_chunk(str_to_id(id), &payload)
}

fn fixed3(values: [i32; 3]) -> Vec<u8> {
    values.iter().flat_map(|v| v.to_le_bytes()).collect()
}

/// The default holder as the exporter writes any settings object: name, position, orientation, a small box,
/// class name, zero mass and no model.
pub fn default_object() -> Result<LevObject, String> {
    let mut cname = HOLDER_NAME.as_bytes().to_vec();
    cname.push(0);
    let mut payload = write_chunk(str_to_id("NAME"), &cname);
    payload.extend(named("VEC3", "Position", &fixed3([0; 3])));
    payload.extend(named("EULR", "Orientation", &fixed3([0; 3])));
    let mut bbox = fixed3([-TENTH; 3]);
    bbox.extend(fixed3([TENTH; 3]));
    payload.extend(named("BOX3", "Global Bounding Box", &bbox));
    let mut class = HOLDER_CLASS.as_bytes().to_vec();
    class.push(0);
    payload.extend(named("STR", "Class Name", &class));
    payload.extend(named("FX32", "Mass", &0i32.to_le_bytes()));
    let mut model_payload = write_chunk(str_to_id("NAME"), b"Model Type\0");
    model_payload.extend(write_chunk(str_to_id("STR"), b"None\0"));
    payload.extend(write_chunk(str_to_id("I32"), &model_payload));
    parse_obj(&payload)?.ok_or_else(|| "default holder has no class name".to_string())
}

/// What `ensure` did.
#[derive(Debug, PartialEq, Eq)]
pub enum Outcome {
    /// Some object already carries the global keys.
    AlreadyHas,
    /// A default holder was appended.
    Added,
    /// Nothing to do: no keys declared, or the holder class is not registered.
    Skipped(&'static str),
}

pub fn ensure(
    objects: &mut Vec<LevObject>,
    keys: &[String],
    class_registered: &dyn Fn(&str) -> bool,
    class_has_key: &dyn Fn(&str, &str) -> bool,
) -> Result<Outcome, String> {
    if keys.is_empty() {
        return Ok(Outcome::Skipped("no global settings declared"));
    }
    if has_global(objects, keys, class_has_key) {
        return Ok(Outcome::AlreadyHas);
    }
    if !class_registered(HOLDER_CLASS) {
        return Ok(Outcome::Skipped("levelsettings is not in objects.lc"));
    }
    objects.push(default_object()?);
    Ok(Outcome::Added)
}

#[cfg(test)]
mod tests {
    use super::*;

    const INC: &str = "@* comment TYPEENTRYBOOLEAN(Not,a,key)\n\tPROPERTY_SHEET_HEADER(Display,0)\n\tTYPEENTRYBOOLEAN(Show framerate,,0,SHOW_AS_CHECKBOX|SHOW_AS_LIVE,\"x\")\n\tPROPERTY_SHEET_FOOTER\n";

    fn level_object(class: &str) -> LevObject {
        let mut o = default_object().unwrap();
        o.class_name = class.to_string();
        o
    }

    #[test]
    fn keys_come_from_the_declaration_not_its_comments() {
        assert_eq!(global_keys(INC), vec!["Show framerate".to_string()]);
        assert!(global_keys("@* nothing here\n").is_empty());
    }

    #[test]
    fn the_default_object_is_a_small_massless_modelless_holder_at_the_origin() {
        let o = default_object().unwrap();
        assert_eq!(o.class_name, HOLDER_CLASS);
        assert_eq!(o.name, HOLDER_NAME);
        assert_eq!((o.position.x, o.position.y, o.position.z), (0, 0, 0));
        assert_eq!((o.bbox.min[0], o.bbox.max[2]), (-TENTH, TENTH));
        assert!(o.find_field("Mass").is_some() && o.find_field("Model Type").is_some());
    }

    #[test]
    fn a_level_without_a_holder_gets_one_appended_last() {
        let keys = global_keys(INC);
        let mut objects = vec![level_object("statplat"), level_object("camera")];
        let has = |_c: &str, _k: &str| false;
        let out = ensure(&mut objects, &keys, &|_| true, &has).unwrap();
        assert_eq!(out, Outcome::Added);
        assert_eq!(objects.len(), 3);
        assert_eq!(objects[0].class_name, "statplat");          // nothing before it moved
        assert_eq!(objects[2].class_name, HOLDER_CLASS);
    }

    #[test]
    fn a_level_that_already_has_a_holder_is_left_alone() {
        let keys = global_keys(INC);
        let mut objects = vec![level_object("statplat"), level_object("reefsettings")];
        let has = |c: &str, k: &str| c == "reefsettings" && k == "Show framerate";
        assert_eq!(ensure(&mut objects, &keys, &|_| true, &has).unwrap(), Outcome::AlreadyHas);
        assert_eq!(objects.len(), 2);
    }

    #[test]
    fn nothing_is_added_without_keys_or_without_the_registered_class() {
        let mut objects = vec![level_object("statplat")];
        let none = |_c: &str, _k: &str| false;
        assert!(matches!(ensure(&mut objects, &[], &|_| true, &none).unwrap(), Outcome::Skipped(_)));
        let keys = global_keys(INC);
        assert!(matches!(ensure(&mut objects, &keys, &|_| false, &none).unwrap(), Outcome::Skipped(_)));
        assert_eq!(objects.len(), 1);
    }
}
