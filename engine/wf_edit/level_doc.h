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

}  // namespace wfedit
