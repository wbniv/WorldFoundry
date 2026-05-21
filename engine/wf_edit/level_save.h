//=============================================================================
// engine/wf_edit/level_save.h — editor-side Doc → .lev save (round-trip).
//
// The inverse of level_doc's load. With the v2 lossless Doc schema (each leaf's
// literals stored as a structured `items` array, kinds intact — see plan
// docs/plans/2026-05-21-lossless-doc-schema.md), this is a pure Doc→JSON walk
// (ChunkToJson) → `levtree print`, with no retained-parse-JSON side-channel — so
// it saves structural and remote edits correctly, not just local value edits.
//
// EDITOR-ONLY (WF_ENABLE_EDITOR / wf_edit target).
//=============================================================================
#pragma once

#include <string>

namespace wfcrdt { class Doc; }

namespace wfedit {

// Save the level back to a canonical `.lev` at `out_path`: walk `doc` → levtree
// chunk-tree JSON → `levtree print`. Returns false on print/write failure. The
// emitted `.lev` is canonical (comment-free — the OAD-derived `//` hints are
// dropped at parse, regenerable, and iffcomp-stripped); the save gate is
// canonical-`print` identity, not raw-file identity.
bool SaveDocToLev(wfcrdt::Doc& doc, const std::string& out_path);

}  // namespace wfedit
