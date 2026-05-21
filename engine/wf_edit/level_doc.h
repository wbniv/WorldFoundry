//=============================================================================
// engine/wf_edit/level_doc.h — editor-side levtree → wfcrdt::Doc population.
//
// M4 of the editor-app-shell plan (docs/plans/2026-05-20-editor-app-shell.md):
// the read-only Y.Doc path. The editor shells out to `levtree parse <lev>`
// (Rust tool, keeping the editor Rust-free at the link level), parses the JSON
// chunk tree, and builds a wfcrdt::Doc in the editor's CRDT schema. The
// Outliner reads actor names back from the Doc — proving levtree → Y.Doc in the
// app without the (next-plan) CRDT→engine bridge.
//=============================================================================
#pragma once

#include <string>
#include <vector>

namespace wfcrdt { class Doc; }

namespace wfedit {

// Run `levtree parse <lev_path>` (subprocess) and populate `doc` with the
// editor CRDT schema:
//   meta    : Y.Map  { level_name, format_version }
//   content : Y.Array<chunk>   — the level's top-level OBJ chunks, LVL dropped
// where each chunk is the recursive node Y.Map { chunk_type, children|text }
// (design doc § "CRDT schema"). Returns false (and logs to stderr) if levtree
// can't be found / exits non-zero / emits unparseable JSON.
bool LoadLevelTreeIntoDoc(const std::string& lev_path, wfcrdt::Doc& doc);

// Read actor display names out of doc.content — each top-level chunk's NAME
// child text (falls back to the chunk_type for an unnamed/odd chunk). Reads
// through the Doc (not a side cache), so this exercises the Doc → UI path.
std::vector<std::string> ReadActorNames(wfcrdt::Doc& doc);

// One field of an actor, as carried by the Doc. The `.lev` names every field
// inline (a NAME sub-chunk: "Position", "Mass", "Background Color", …), so the
// Properties panel needs no OAD just to list named fields read-only — that's
// Phase 1. The OAD-driven (ButtonType×showAs) widget dispatch is Phase 2.
//
// A field chunk's leaves split into a raw value and a display string:
//   { 'I32'  {NAME "Model Type"} {DATA 1l}  {STR "Mesh"} }   data="1" label="Mesh"
//   { 'I32'  {NAME "Mobility"}             {STR "Anchored"} }  data=""  label="Anchored"
//   { 'FX32' {NAME "Mass"}     {DATA 0.0(1.15.16)} {STR "0.0"} }
//   { 'FILE' {NAME "Mesh Name"}            {STR "House.iff"} }  label="House.iff"
// `data` is the DATA leaf(s) (raw scalar / VEC3 components); `label` is the STR
// leaf (enum current-label / bool text / filename / string body). `value` keeps
// the Phase-1 space-joined form for the no-OAD raw fallback.
struct ActorField {
    std::string name;        // the field's NAME sub-chunk text ("Mass", …)
    std::string chunk_type;  // IFF storage type: "VEC3" / "I32" / "FX32" / "STR" / "FILE" / …
    std::string value;       // every non-NAME leaf, space-joined (Phase-1 form)
    std::string data;        // DATA leaf(s) only — raw scalar / vector components
    std::string label;       // STR leaf — enum/bool label, filename, or string body
};

// Read every field of content[actor_index] out of the Doc: each child chunk's
// NAME + DATA. Skips the actor's own top-level NAME (shown separately).
std::vector<ActorField> ReadActorFields(wfcrdt::Doc& doc, int actor_index);

}  // namespace wfedit
