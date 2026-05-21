//=============================================================================
// engine/wf_edit/oad_reader.h — editor-side OAD schema reader (Phase 2).
//
// A thin, clean adapter over the dumper's C++ reader (wftools/oaddump/oad.{cc,
// hp} → QObjectAttributeData). It exposes the ordered entry list as plain POD
// structs so the property panel can drive (ButtonType × showAs) widget dispatch
// without pulling oad.hp's `<iostream>`/pigsys/`using namespace std` baggage —
// or any ImGui clash — into the rendering TU.
//
// EDITOR-ONLY. Compiled into the wf_edit target under WF_ENABLE_EDITOR; never
// into wfengine / wf_game / Android / iOS (the runtime stays free of the OAD
// authoring-reader weight — design plan D1a).
//=============================================================================
#pragma once

#include <string>
#include <vector>

namespace wfedit {

// One OAD entry, distilled to what the property panel needs. Field semantics
// mirror `_typeDescriptor` (wfsource/source/oas/oad.h): `button_type` is a
// BUTTON_* / LEVELCONFLAG_* code, `show_as` a SHOW_AS_* code. `options` is the
// pipe-separated `string` field split into enum labels ("Anchored|Physics|…").
struct OadEntry {
    int                      button_type = -1;
    std::string              name;          // field label ("Mobility", "Mass", …)
    int                      show_as = 0;
    long                     min = 0;
    long                     max = 0;
    long                     def = 0;
    std::string              option_string; // raw `string` field, verbatim
    std::vector<std::string> options;       // option_string split on '|'
};

// Load <oad_path> via QObjectAttributeData::Load (validates the 'OAD ' header,
// then reads each fixed-size descriptor). Returns the entries in file order
// (== the CommonBlock field layout). Empty + false on open/parse failure.
bool LoadOad(const std::string& oad_path, std::vector<OadEntry>& out);

}  // namespace wfedit
