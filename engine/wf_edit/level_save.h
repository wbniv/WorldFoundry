//=============================================================================
// engine/wf_edit/level_save.h — editor-side Doc → .lev save (round-trip).
//
// The inverse of level_doc's load. The Doc loader (BuildChunk) is lossy — it
// collapses each leaf chunk's literals into one space-joined `text`, dropping
// the str/num kind — so we can't reconstruct the full chunk-tree JSON from the
// Doc alone. Instead we PATCH the lossless `levtree parse` JSON retained at load
// with the Doc's current leaf values (kinds carry through verbatim), then
// `levtree print` it to canonical .lev. Works because the editor edits values,
// never structure (WriteFieldLeaf creates nothing). See plan
// docs/plans/2026-05-21-editor-save-roundtrip.md.
//
// EDITOR-ONLY (WF_ENABLE_EDITOR / wf_edit target).
//=============================================================================
#pragma once

#include <string>

namespace wfcrdt { class Doc; }

namespace wfedit {

// Save the level back to a canonical `.lev` at `out_path`: patch `parse_json`
// (the levtree-parse output retained by LoadLevelTreeIntoDoc) with `doc`'s
// current leaf values, then `levtree print`. Returns false if there's no
// retained JSON, or print/write fails. The emitted `.lev` is canonical
// (comment-free — the OAD-derived `//` hints are dropped at parse, regenerable,
// and iffcomp-stripped); the save gate is canonical-`print` identity, not
// raw-file identity.
//
// M1: no-edit passthrough (the patch is M2).
bool SaveDocToLev(wfcrdt::Doc& doc, const std::string& parse_json,
                  const std::string& out_path);

}  // namespace wfedit
