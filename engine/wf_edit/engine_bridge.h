//=============================================================================
// engine/wf_edit/engine_bridge.h — CRDT->engine bridge (Option C).
//
// Propagates Doc edits into the live engine via wfmut:: so the viewport
// reflects them. M1: identity mapping (Doc content[] index -> engine 1-based
// wfmut::ActorIdx) + a verification dump. M2 adds field translation; M3 wires
// the panel commit through to wfmut.
//
// EDITOR-ONLY (WF_ENABLE_EDITOR / wf_edit target). The engine stays untouched —
// this consumes the existing wfmut:: surface (engine/mutation/wfmut.hpp). See
// plan docs/plans/2026-05-20-crdt-engine-bridge.md.
//=============================================================================
#pragma once

#include <string>

namespace wfcrdt { class Doc; }

namespace wfedit {

struct PropField;  // property_panel.h — a Doc field after OAD correlation

// Map a Doc content[] index (0-based — what the Outliner selects, i.e.
// EditorCtx::selected) to the engine's 1-based actor index (Actor::GetActorIndex
// / BaseObjectList slot, the same id wfmut::ActorIdx uses). Returns 0 (an
// invalid actor index) when there is no live level or the index is out of range.
//
// v1 is positional with a verified constant offset: the Doc and the engine load
// the same .lev source, so content[i] corresponds to engine actor
// (i + kDocToEngineIdx). DumpIdentityMap is the proof it holds (plan M1).
int DocActorToEngineIdx(int doc_index);

// Verification (WF_EDIT_BRIDGE_DEBUG): print, for every Doc actor, its
// doc_index -> mapped engine_idx -> engine currentPos() alongside the Doc's own
// Position leaf, flagging any mismatch. Called once when the live level is
// available (the global `theLevel`). Reads only — no mutation.
void DumpIdentityMap(wfcrdt::Doc& doc);

// ── M2: field translation ────────────────────────────────────────────────────
// The engine write a Doc field maps to. v1 covers transform (Position/
// Orientation) + the 15 wfmut kPropMap scalar/enum fields (D4); everything else
// is `None` (the Doc still holds the edit — the viewport just won't change).
struct EngineWrite {
    enum Kind {
        NoOp,       // no engine mapping in v1 (`NoOp` not `None` — Xlib #defines None 0L)
        Pos,        // wfmut::SetActorPos(vec)
        Orient,     // wfmut::SetActorOrientation(vec, revolutions)
        FieldFloat, // wfmut::SetActorField(path, d)   — fixed-point fields
        FieldInt,   // wfmut::SetActorField(path, i)   — int / enum / bool fields
    } kind = NoOp;
    std::string        path;          // "block.field" for FieldFloat/FieldInt
    float              vec[3] = {0, 0, 0};   // Pos / Orient (Orient in revolutions)
    double             d = 0.0;       // FieldFloat
    long long          i = 0;         // FieldInt (enum -> index, bool -> 0/1)
};

// Translate one OAD-correlated Doc field into the engine write that mirrors it.
// Pure (no live engine, no mutation) — M3 dispatches the result through wfmut.
// Coercion preserves WF conventions: Orientation stays in revolutions; float
// fields pass a double (wfmut applies the fixed-point scale); enum/bool fields
// pass the index/flag as an int. Returns kind==NoOp for the unmapped long tail.
EngineWrite TranslateField(const PropField& f);

// WF_EDIT_BRIDGE_DEBUG: resolve a Doc actor's fields and print each field's
// TranslateField result (name -> kind/path/value), so the mapping + coercion is
// visible on real level data. Reads only — no mutation.
void DumpTranslations(wfcrdt::Doc& doc, int doc_index);

}  // namespace wfedit
