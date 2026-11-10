//! Runtime object editing, export side (docs/plans/2026-10-16-runtime-object-editing.md).
//!
//! levcomp decides, once, which objects of a level can be edited at runtime
//! and writes the answer into the level's Level Object, so the engine follows
//! a list instead of scanning types (M3):
//!
//! * **Editable Objects** (`XDATA_OBJECTLIST`): the `-1`-terminated `int32`
//!   level object indices (`.lev` order plus 1) of every object whose type's
//!   `.oad` declares at least one `SHOW_AS_LIVE` field (M7).
//! * **Editable Object Labels** (`XDATA_COPY`): one NUL-terminated label per
//!   list entry, in list order (R3). The label is the object's `Editor Label`
//!   (a plain `.lev` field, not an OAD field, R1), else the type's display
//!   name, plus a 1-based ordinal when the level lists more than one object of
//!   that type ("Seahorse 2"). Labels must be unique in a level, or the build
//!   fails (M6).
//! * **Editable Type Descriptors** (`XDATA_COPY`): `int32 count`, then five
//!   `int32` per editable type in order of first appearance in the list:
//!   type id (the `objects.lc` index), index of the first descriptor shipped,
//!   payload offset of that descriptor's data in the object's OAD payload,
//!   common-area offset of the trimmed `.oad`, and its length in bytes. The
//!   trimmed `.oad` is the type's 80-byte header followed by its entries from
//!   its first own `PROPERTY_SHEET_HEADER` on, the entries after those it
//!   inherits from `actor.inc` (R2, R9). Indices stay global: entry `k` of the
//!   trimmed file is descriptor `first + k` of the full one.
//!
//! All three are common-area offsets, `-1` when the level lists nothing. The
//! blobs are appended after every other common-area block, with an exact-match
//! [`CommonBlockBuilder::add_exact`] (R8), and patched into the Level Object's
//! payload, so a level with nothing editable keeps its common area unchanged.

use std::collections::HashMap;

use wf_oad::{ButtonType, OadFile};

use crate::common_block::CommonBlockBuilder;
use crate::lc_parser::ClassMap;
use crate::lev_parser::{field_str_value, LevObject};
use crate::oad_loader::{field_size, OadSchemas};

pub const LEVELOBJ_CLASS: &str = "levelobj";
pub const EDITABLE_OBJECTS: &str = "Editable Objects";
pub const EDITABLE_OBJECT_LABELS: &str = "Editable Object Labels";
pub const EDITABLE_TYPE_DESCRIPTORS: &str = "Editable Type Descriptors";
/// The per-object override of the automatic label: a plain `.lev` field.
pub const EDITOR_LABEL: &str = "Editor Label";
/// The schema whose entries every type inherits first (`actor.inc`).
const ACTOR_CLASS: &str = "actor";

/// True for the Level Object fields levcomp computes itself; any value a
/// `.lev` authors for them is ignored.
pub fn is_synthesized_field(name: &str) -> bool {
    matches!(name, EDITABLE_OBJECTS | EDITABLE_OBJECT_LABELS | EDITABLE_TYPE_DESCRIPTORS)
}

/// True when `class` is the Level Object and `field` is one levcomp computes.
pub fn is_synthesized(class: &str, field: &str) -> bool {
    class.eq_ignore_ascii_case(LEVELOBJ_CLASS) && is_synthesized_field(field)
}

/// True when the type declares at least one `SHOW_AS_LIVE` field (M7).
pub fn is_editable_type(schema: &OadFile) -> bool {
    schema.entries.iter().any(|e| e.is_live())
}

/// One editable type's shipped descriptors.
#[derive(Debug, Clone, PartialEq)]
pub struct EditableType {
    pub type_id: i32,
    pub first_index: i32,
    pub payload_offset: i32,
    /// The trimmed `.oad`: header, then entries `first_index..`.
    pub oad: Vec<u8>,
}

/// What the export writes into the Level Object.
#[derive(Debug, Default, PartialEq)]
pub struct EditablePlan {
    /// Level object indices (`.lev` position plus 1).
    pub indices: Vec<i32>,
    /// One label per index, in the same order.
    pub labels: Vec<String>,
    pub types: Vec<EditableType>,
}

/// Bytes of the object's OAD payload before entry `index`, walking the schema
/// as `per_object_size` does. `None` when the entry lies inside a
/// COMMONBLOCK section, where it has no per-object bytes.
pub fn payload_offset(schema: &OadFile, index: usize) -> Option<usize> {
    match wf_oad::field_location(&schema.entries, index, 0)? {
        wf_oad::FieldLocation::Object { offset } => Some(offset),
        wf_oad::FieldLocation::Common { .. } => None,
    }
}

/// The type's own descriptors (R2): the index of its first own
/// `PROPERTY_SHEET_HEADER`, the first entry after the `actor.inc` entries it
/// inherits, and the trimmed `.oad` bytes from there on.
pub fn trimmed_descriptor(class: &str, schema: &OadFile, actor: &OadFile) -> Result<(usize, Vec<u8>), String> {
    let inherited = actor.entries.len();
    let prefix_matches = schema.entries.len() >= inherited
        && schema.entries.iter().zip(&actor.entries)
            .all(|(a, b)| a.button_type == b.button_type && a.name == b.name);
    if !prefix_matches {
        return Err(format!(
            "editable type '{class}' does not start with the actor.inc entries; \
             it must include actor.inc (or settings.inc) before its own sheets"));
    }
    let first = (inherited..schema.entries.len())
        .find(|&i| schema.entries[i].button_type == ButtonType::PropertySheet)
        .ok_or_else(|| format!("editable type '{class}' has no PROPERTY_SHEET_HEADER of its own"))?;
    // Nothing that has a value may fall outside the shipped range: the runtime
    // form would never see it.
    for (i, e) in schema.entries.iter().enumerate().take(first) {
        if e.is_live() {
            return Err(format!(
                "editable type '{class}': live field '{}' precedes its first own property sheet \
                 and would not be shipped", e.name_str()));
        }
        if i >= inherited && field_size(e) > 0 {
            return Err(format!(
                "editable type '{class}': field '{}' sits outside any property sheet; \
                 put it after a PROPERTY_SHEET_HEADER", e.name_str()));
        }
    }
    let trimmed = OadFile { header: schema.header.clone(), entries: schema.entries[first..].to_vec() };
    let mut bytes = Vec::new();
    trimmed.write(&mut bytes).map_err(|e| e.to_string())?;
    Ok((first, bytes))
}

/// The object's `Editor Label`, when it authors a non-empty one.
fn editor_label(obj: &LevObject) -> Option<String> {
    obj.find_field(EDITOR_LABEL).map(field_str_value).filter(|s| !s.is_empty())
}

/// Decide the Editable Objects list, labels and shipped descriptors.
pub fn plan(objects: &[LevObject], schemas: &OadSchemas, classes: &ClassMap) -> Result<EditablePlan, String> {
    let mut plan = EditablePlan::default();
    let mut members: Vec<(usize, &OadFile)> = Vec::new();
    let mut per_type: HashMap<String, usize> = HashMap::new();
    for (i, obj) in objects.iter().enumerate() {
        let class = obj.class_name.to_lowercase();
        match schemas.get(&class) {
            Some(schema) if is_editable_type(schema) => {
                members.push((i, schema));
                *per_type.entry(class).or_default() += 1;
            }
            _ => {
                if editor_label(obj).is_some() {
                    eprintln!("levcomp: warning: '{}' has an {EDITOR_LABEL} but its type '{}' \
                               declares no live field, so it is not editable", obj.name, obj.class_name);
                }
            }
        }
    }
    if members.is_empty() {
        return Ok(plan);
    }
    let actor = schemas.get(ACTOR_CLASS)
        .ok_or_else(|| format!("{ACTOR_CLASS}.oad is missing from the OAD directory; \
                                it is needed to trim the editable types' descriptors"))?;

    let mut ordinal: HashMap<String, usize> = HashMap::new();
    let mut owner: HashMap<String, &str> = HashMap::new();
    for &(i, schema) in &members {
        let obj = &objects[i];
        let class = obj.class_name.to_lowercase();
        let n = ordinal.entry(class.clone()).or_default();
        *n += 1;
        let label = editor_label(obj).unwrap_or_else(|| {
            let name = schema.header.display_name();
            if per_type[&class] > 1 { format!("{name} {n}") } else { name.to_string() }
        });
        if label.contains('\0') {
            return Err(format!("{EDITOR_LABEL} of '{}' contains a NUL byte", obj.name));
        }
        if let Some(first) = owner.insert(label.clone(), &obj.name) {
            return Err(format!(
                "duplicate editable object label \"{label}\" (objects {first} and {}): labels must be \
                 unique within a level; give one of them a different {EDITOR_LABEL}", obj.name));
        }
        plan.indices.push(i as i32 + 1);
        plan.labels.push(label);

        if !plan.types.iter().any(|t| classes.names.get(t.type_id as usize) == Some(&class)) {
            let type_id = classes.index_of(&class)
                .ok_or_else(|| format!("object '{}': unknown class '{}'", obj.name, obj.class_name))?;
            let (first, oad) = trimmed_descriptor(&class, schema, actor)?;
            let offset = payload_offset(schema, first)
                .ok_or_else(|| format!("editable type '{class}': its first own sheet is inside a common block"))?;
            plan.types.push(EditableType {
                type_id: type_id as i32,
                first_index: first as i32,
                payload_offset: offset as i32,
                oad,
            });
        }
    }
    Ok(plan)
}

/// Common-area offsets of the three blobs, `-1` each when nothing is editable.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct EditableOffsets {
    pub objects: i32,
    pub labels: i32,
    pub types: i32,
}

impl EditableOffsets {
    pub const NONE: Self = Self { objects: -1, labels: -1, types: -1 };
}

fn padded(mut bytes: Vec<u8>) -> Vec<u8> {
    while bytes.len() % 4 != 0 { bytes.push(0); }
    bytes
}

fn push_i32(out: &mut Vec<u8>, v: i32) { out.extend_from_slice(&v.to_le_bytes()); }

/// Add the plan's blobs to the common area. Call after every other block has
/// been added, so no greedy (last-byte-blind) `add` can alias into them.
pub fn emit(plan: &EditablePlan, common: &mut CommonBlockBuilder) -> EditableOffsets {
    if plan.indices.is_empty() {
        return EditableOffsets::NONE;
    }
    let mut list = Vec::new();
    for &i in &plan.indices { push_i32(&mut list, i); }
    push_i32(&mut list, -1);
    let objects = common.add_exact(&list);

    let mut labels = Vec::new();
    for l in &plan.labels { labels.extend_from_slice(l.as_bytes()); labels.push(0); }
    let labels = common.add_exact(&padded(labels));

    let mut table = Vec::new();
    push_i32(&mut table, plan.types.len() as i32);
    for t in &plan.types {
        let at = common.add_exact(&padded(t.oad.clone()));
        for v in [t.type_id, t.first_index, t.payload_offset, at, t.oad.len() as i32] {
            push_i32(&mut table, v);
        }
    }
    let types = common.add_exact(&table);
    EditableOffsets { objects, labels, types }
}

/// Write the offsets into every Level Object payload (normally there is one).
/// `payloads[i + 1]` is the payload of `objects[i]`; slot 0 is NULL_Object.
pub fn patch_levelobj(
    objects: &[LevObject],
    schemas: &OadSchemas,
    payloads: &mut [Vec<u8>],
    offsets: EditableOffsets,
) -> Result<(), String> {
    if offsets == EditableOffsets::NONE {
        return Ok(());  // pass 2 already wrote -1 for each
    }
    let mut patched = 0;
    for (i, obj) in objects.iter().enumerate() {
        if !obj.class_name.eq_ignore_ascii_case(LEVELOBJ_CLASS) { continue; }
        let schema = schemas.get(LEVELOBJ_CLASS).ok_or("levelobj.oad is missing")?;
        for (name, value) in [(EDITABLE_OBJECTS, offsets.objects),
                              (EDITABLE_OBJECT_LABELS, offsets.labels),
                              (EDITABLE_TYPE_DESCRIPTORS, offsets.types)] {
            let index = schema.entries.iter().position(|e| e.name_str() == name)
                .ok_or_else(|| format!("levelobj.oad has no '{name}' field: it predates runtime \
                                        object editing; regenerate it from levelobj.oas"))?;
            let at = payload_offset(schema, index)
                .ok_or_else(|| format!("levelobj.oad: '{name}' is inside a common block"))?;
            payloads[i + 1][at..at + 4].copy_from_slice(&value.to_le_bytes());
        }
        patched += 1;
    }
    if patched == 0 {
        return Err("the level has editable objects but no Level Object to list them in".into());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_support::{entry, object, schema, str_field, xdata};
    use wf_oad::{SHOW_AS_LIVE, HEADER_SIZE, ENTRY_SIZE};

    const RADIO: u8 = 5;
    const NUMBER: u8 = 1;

    /// `actor.inc` in miniature: a common block, a sheet and a flag.
    fn actor_entries() -> Vec<wf_oad::OadEntry> {
        vec![
            entry(ButtonType::CommonBlock, "movebloc", "", 6, 0),
            entry(ButtonType::Int32, "Mobility", "", NUMBER, 0),
            entry(ButtonType::EndCommon, "LEVELCONFLAG_ENDCOMMON", "", 6, 0),
            entry(ButtonType::PropertySheet, "Flags", "", 0, 0),
            entry(ButtonType::Int32, "Template Object", "False|True", 8, 0),
        ]
    }

    fn with_actor(display: &str, own: Vec<wf_oad::OadEntry>) -> OadFile {
        let mut entries = actor_entries();
        entries.extend(own);
        schema(display, entries)
    }

    fn schemas() -> OadSchemas {
        let mut s = OadSchemas::empty();
        s.insert("actor", schema("Actor", actor_entries()));
        s.insert("seahorse", with_actor("Seahorse", vec![
            entry(ButtonType::PropertySheet, "Seahorse", "", 0, 0),
            entry(ButtonType::Int32, "Colour", "Yellow|Black", RADIO | SHOW_AS_LIVE, 0),
            entry(ButtonType::Int32, "Size", "", NUMBER, 3),
        ]));
        s.insert("tanksettings", with_actor("Tank Settings", vec![
            entry(ButtonType::PropertySheet, "Tank", "", 0, 0),
            entry(ButtonType::Int32, "Seed", "", NUMBER | SHOW_AS_LIVE, 0),
        ]));
        s.insert("statplat", with_actor("Stationary Platform", vec![
            entry(ButtonType::PropertySheet, "Platform", "", 0, 0),
            entry(ButtonType::Int32, "Slope", "", NUMBER, 0),
        ]));
        s.insert("levelobj", with_actor("Level Object", vec![
            entry(ButtonType::PropertySheet, "Level Object", "", 0, 0),
            entry(ButtonType::Int32, "Number Of Mailboxes", "", NUMBER, 101),
            xdata(EDITABLE_OBJECTS, 2),
            xdata(EDITABLE_OBJECT_LABELS, 1),
            xdata(EDITABLE_TYPE_DESCRIPTORS, 1),
        ]));
        s
    }

    fn classes() -> ClassMap {
        ClassMap { names: ["nullobject", "statplat", "levelobj", "seahorse", "tanksettings"]
            .iter().map(|s| s.to_string()).collect() }
    }

    fn label(text: &str) -> wf_iff::IffChunk { str_field("STR", EDITOR_LABEL, text) }

    #[test]
    fn lists_only_objects_whose_type_declares_a_live_field() {
        let objects = vec![
            object("LevelObj", "levelobj", vec![]),
            object("Floor", "statplat", vec![]),
            object("Seahorse.001", "seahorse", vec![]),
            object("Settings", "tanksettings", vec![]),
            object("Seahorse.002", "seahorse", vec![]),
        ];
        let plan = plan(&objects, &schemas(), &classes()).unwrap();
        assert_eq!(plan.indices, vec![3, 4, 5]);
        assert_eq!(plan.labels, vec!["Seahorse 1", "Tank Settings", "Seahorse 2"]);
        assert_eq!(plan.types.iter().map(|t| t.type_id).collect::<Vec<_>>(), vec![3, 4]);
    }

    #[test]
    fn nothing_editable_plans_nothing() {
        let objects = vec![object("LevelObj", "levelobj", vec![]), object("Floor", "statplat", vec![])];
        let plan = plan(&objects, &schemas(), &classes()).unwrap();
        assert_eq!(plan, EditablePlan::default());
        let mut common = CommonBlockBuilder::new();
        assert_eq!(emit(&plan, &mut common), EditableOffsets::NONE);
        assert!(common.bytes().is_empty(), "nothing editable must add nothing to the common area");
    }

    #[test]
    fn editor_label_overrides_and_keeps_the_ordinals() {
        let objects = vec![
            object("Seahorse.001", "seahorse", vec![label("Goldie")]),
            object("Seahorse.002", "seahorse", vec![]),
            object("Seahorse.003", "seahorse", vec![label("")]),  // empty = automatic
        ];
        let plan = plan(&objects, &schemas(), &classes()).unwrap();
        assert_eq!(plan.labels, vec!["Goldie", "Seahorse 2", "Seahorse 3"]);
    }

    #[test]
    fn duplicate_override_fails_the_build() {
        let objects = vec![
            object("Seahorse.001", "seahorse", vec![label("Goldie")]),
            object("Seahorse.002", "seahorse", vec![]),
            object("Seahorse.003", "seahorse", vec![label("Goldie")]),
        ];
        let err = plan(&objects, &schemas(), &classes()).unwrap_err();
        assert!(err.contains("\"Goldie\"") && err.contains("Seahorse.001") && err.contains("Seahorse.003"), "{err}");
    }

    #[test]
    fn override_colliding_with_an_automatic_label_fails_the_build() {
        let objects = vec![
            object("Seahorse.001", "seahorse", vec![]),
            object("Seahorse.002", "seahorse", vec![label("Seahorse 1")]),
        ];
        let err = plan(&objects, &schemas(), &classes()).unwrap_err();
        assert!(err.contains("\"Seahorse 1\""), "{err}");
    }

    #[test]
    fn descriptors_ship_from_the_first_own_sheet() {
        let s = schemas();
        let horse = s.get("seahorse").unwrap();
        let (first, bytes) = trimmed_descriptor("seahorse", horse, s.get("actor").unwrap()).unwrap();
        assert_eq!(first, 5, "the five actor entries are not shipped");
        assert_eq!(bytes.len(), HEADER_SIZE + 3 * ENTRY_SIZE);
        let back = OadFile::read(&mut std::io::Cursor::new(&bytes)).unwrap();
        assert_eq!(back.header.display_name(), "Seahorse");
        let names: Vec<&str> = back.entries.iter().map(|e| e.name_str()).collect();
        assert_eq!(names, vec!["Seahorse", "Colour", "Size"]);
        // Payload: movebloc offset (4) + Template Object (4) precede the sheet.
        assert_eq!(payload_offset(horse, first), Some(8));
    }

    #[test]
    fn shared_walker_locates_common_and_trimmed_fields() {
        let s = schemas();
        let horse = s.get("seahorse").unwrap();
        assert_eq!(wf_oad::field_location(&horse.entries, 1, 0),
                   Some(wf_oad::FieldLocation::Common { pointer_offset: 0, offset: 0 }));
        assert_eq!(wf_oad::field_location(&horse.entries, 4, 0),
                   Some(wf_oad::FieldLocation::Object { offset: 4 }));
        assert_eq!(wf_oad::field_location(&horse.entries[5..], 1, 8),
                   Some(wf_oad::FieldLocation::Object { offset: 8 }));
        assert_eq!(wf_oad::field_location(&horse.entries, horse.entries.len(), 0), None);
    }

    #[test]
    fn a_type_without_actor_entries_is_rejected() {
        let s = schemas();
        let bare = schema("Bare", vec![
            entry(ButtonType::PropertySheet, "Bare", "", 0, 0),
            entry(ButtonType::Int32, "Seed", "", NUMBER | SHOW_AS_LIVE, 0),
        ]);
        assert!(trimmed_descriptor("bare", &bare, s.get("actor").unwrap()).is_err());
    }

    #[test]
    fn emit_and_patch_write_the_three_offsets() {
        let s = schemas();
        let objects = vec![
            object("LevelObj", "levelobj", vec![]),
            object("Seahorse.001", "seahorse", vec![]),
            object("Seahorse.002", "seahorse", vec![label("Goldie")]),
        ];
        let plan = plan(&objects, &s, &classes()).unwrap();
        let mut common = CommonBlockBuilder::new();
        common.add(&[7, 0, 0, 0]);  // an earlier block
        let offsets = emit(&plan, &mut common);
        let c = common.bytes();
        let word = |at: i32, k: usize| i32::from_le_bytes(c[at as usize + 4 * k..][..4].try_into().unwrap());
        assert_eq!((word(offsets.objects, 0), word(offsets.objects, 1), word(offsets.objects, 2)), (2, 3, -1));
        assert_eq!(&c[offsets.labels as usize..][..19], b"Seahorse 1\0Goldie\0\0");
        assert_eq!(word(offsets.types, 0), 1);
        let (type_id, first, payload, oad_at, oad_len) =
            (word(offsets.types, 1), word(offsets.types, 2), word(offsets.types, 3),
             word(offsets.types, 4), word(offsets.types, 5));
        assert_eq!((type_id, first, payload), (3, 5, 8));
        assert_eq!(&c[oad_at as usize..][..oad_len as usize], plan.types[0].oad.as_slice());

        let levelobj = s.get("levelobj").unwrap();
        let size = crate::oad_loader::per_object_size(levelobj);
        let mut payloads = vec![Vec::new(), vec![0xffu8; size], Vec::new(), Vec::new()];
        patch_levelobj(&objects, &s, &mut payloads, offsets).unwrap();
        let p = &payloads[1];
        let at = |k: usize| i32::from_le_bytes(p[size - 12 + 4 * k..][..4].try_into().unwrap());
        assert_eq!((at(0), at(1), at(2)), (offsets.objects, offsets.labels, offsets.types));
    }

    #[test]
    fn synthesized_fields_are_only_the_levelobj_ones() {
        assert!(is_synthesized("LevelObj", EDITABLE_OBJECTS));
        assert!(is_synthesized("levelobj", EDITABLE_TYPE_DESCRIPTORS));
        assert!(!is_synthesized("spike", EDITABLE_OBJECTS));
        assert!(!is_synthesized("levelobj", "Script"));
    }
}
