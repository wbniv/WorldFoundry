//=============================================================================
// engine/wf_edit/property_panel.h — OAD-driven Properties panel (Phase 2).
//
// Phase 1 listed a selected actor's named fields straight from the Doc. Phase 2
// resolves each OBJ to its class's <class>.oad, correlates the OAD's ordered
// field layout against the Doc's fields (sequence-alignment, since the
// CommonBlock flyweight makes Doc order == OAD order modulo a per-instance
// prefix / dups / a small reorder), and renders each field with the widget its
// (ButtonType × showAs) dictates — read-only here; Phase 3 makes them editable.
//
// EDITOR-ONLY (WF_ENABLE_EDITOR / wf_edit target). See plan
// docs/plans/2026-05-20-editor-property-panel.md milestone 2.
//=============================================================================
#pragma once

#include "level_doc.h"   // wfedit::ActorField

#include <string>
#include <vector>

namespace wfedit {

// The widget family a field renders as, after (ButtonType × showAs) dispatch
// (design doc § dispatch table). `Raw` is the no-OAD chunk_type/text fallback;
// `Skip` is a not-drawn entry (SHOW_AS_HIDDEN, common-block sentinels).
enum class FieldKind {
    Int, Float, Boolean, Enum, Mailbox, Color,   // `Boolean` not `Bool` — Xlib `#define Bool int`
    Str, MultilineStr, ObjRef, FileRef,
    Vec3, Euler, Box3,
    Section, GroupStart, GroupEnd,
    Raw, Skip,
};

// A Doc field after OAD correlation: the Doc value(s) plus, when an OAD entry
// matched, the metadata that drives the widget.
struct PropField {
    // From the Doc (always present):
    std::string name;        // display name (OAD name when matched, else Doc name)
    std::string chunk_type;  // IFF storage type (VEC3 / I32 / FX32 / STR / FILE / …)
    std::string data;        // raw scalar / vector components (DATA leaf)
    std::string label;       // enum/bool label, filename, or string body (STR leaf)
    std::string value;       // Phase-1 space-joined form (raw fallback display)

    // From the OAD (matched == true only):
    bool                     matched = false;
    int                      button_type = -1;
    int                      show_as = 0;
    long                     min = 0;
    long                     max = 0;
    std::vector<std::string> options;   // enum option labels

    FieldKind kind = FieldKind::Raw;
};

// Map (ButtonType, showAs) → FieldKind, exactly the design-doc dispatch table.
// `option_count` lets a 2-item CHECKBOX collapse to Bool; `chunk_type` drives
// the no-OAD fallback (matched == false → VEC3→Vec3, EULR→Euler, …).
FieldKind WidgetFor(int button_type, int show_as, int option_count,
                    const std::string& chunk_type, bool matched);

// Resolve the selected actor's Doc fields against its class's .oad and tag each
// with OAD metadata + a dispatched FieldKind. The class name is read from the
// fields' own "Class Name" entry; the .oad is found in $WF_OAD_DIR then
// wfsource/source/oas (mirrors the Blender add-on's _find_oad), loaded once per
// class and cached. Unmatched fields fall back to chunk_type / raw text.
std::vector<PropField> ResolveProperties(const std::vector<ActorField>& doc_fields);

// Render the resolved fields read-only into the current ImGui window.
void RenderProperties(const std::vector<PropField>& fields);

}  // namespace wfedit
