//=============================================================================
// engine/wf_edit/engine_bridge.cc — CRDT->engine bridge (Option C), M1.
//
// Identity mapping: Doc content[] index <-> engine 1-based actor index, plus a
// WF_EDIT_BRIDGE_DEBUG verification dump that cross-checks each Doc actor's
// Position leaf against the live engine actor's currentPos(). No mutation yet
// (M2 = field translation, M3 = wire the panel commit through wfmut).
//=============================================================================
#include "engine_bridge.h"
#include "level_doc.h"      // ReadActorNames / ReadActorFields
#include "property_panel.h" // PropField, FieldKind, ResolveProperties

#include <game/level.hp>            // Level, theLevel, GetObject, GetObjectList
#include <game/actor.hp>            // Actor, currentPos (pulls in Vector3/Scalar)
#include <baseobject/baseobject.hp> // IsActor, BaseObject

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <unordered_map>
#include <vector>

namespace wfedit {

// content[i] (0-based, LVL chunk dropped by level_doc) -> engine _actors slot.
// The engine object list is 1-based (slot 0 is reserved — the mailbox manager
// returns it when the object index is 0, level.hp:97), so the natural map is
// content[i] -> i + 1. Verified by DumpIdentityMap on snowgoons (plan M1).
static constexpr int kDocToEngineIdx = 1;

int DocActorToEngineIdx(int doc_index)
{
    if (!theLevel || doc_index < 0) return 0;
    const int idx = doc_index + kDocToEngineIdx;
    if (idx < 1 || idx >= theLevel->GetObjectList().Size()) return 0;
    return idx;
}

// Parse the Doc VEC3 DATA leaf into 3 floats; returns the count read. Each
// component carries the levtree fixed-point suffix, e.g.
//   "-0.0359(1.15.16) 12.0539(1.15.16) -0.1245(1.15.16)"
// so we strtof the leading number of each whitespace token and skip the suffix.
static int ParseVec3(const std::string& s, float out[3])
{
    int n = 0;
    const char* p = s.c_str();
    while (n < 3) {
        while (*p == ' ' || *p == '\t') ++p;
        if (!*p) break;
        char* end = nullptr;
        const float v = std::strtof(p, &end);
        if (end == p) break;                  // not a number — done
        out[n++] = v;
        while (*end && *end != ' ' && *end != '\t') ++end;  // skip "(1.15.16)"
        p = end;
    }
    return n;
}

void DumpIdentityMap(wfcrdt::Doc& doc)
{
    if (!theLevel) {
        std::fprintf(stderr, "[bridge] no live level (theLevel null) — cannot verify identity map\n");
        return;
    }
    const std::vector<std::string> names = ReadActorNames(doc);
    const int engine_count = theLevel->GetObjectList().Size() - 1;  // slots 1..Size-1

    std::fprintf(stderr,
        "[bridge] identity map: %zu Doc actors vs %d engine actor slots (offset +%d)\n",
        names.size(), engine_count, kDocToEngineIdx);
    std::fprintf(stderr,
        "[bridge]  doc  eng  %-22s  Doc Position              engine currentPos()       match\n", "name");

    int matched = 0, no_actor = 0, differs = 0;
    for (int i = 0; i < static_cast<int>(names.size()); ++i) {
        const int eidx = DocActorToEngineIdx(i);

        float dp[3] = {0, 0, 0};
        bool have_doc = false;
        for (const auto& f : ReadActorFields(doc, i))
            if (f.name == "Position") { have_doc = (ParseVec3(f.data, dp) == 3); break; }

        float ep[3] = {0, 0, 0};
        bool have_eng = false;
        BaseObject* bo = (eidx >= 1) ? theLevel->GetObject(eidx) : nullptr;
        Actor* a = IsActor(bo) ? static_cast<Actor*>(bo) : nullptr;
        if (a) {
            const Vector3& p = a->currentPos();
            ep[0] = p.X().AsFloat(); ep[1] = p.Y().AsFloat(); ep[2] = p.Z().AsFloat();
            have_eng = true;
        }

        const bool xyz_match = have_doc && have_eng &&
            std::fabs(dp[0] - ep[0]) < 0.01f &&
            std::fabs(dp[1] - ep[1]) < 0.01f &&
            std::fabs(dp[2] - ep[2]) < 0.01f;
        // No live actor at the mapped slot: Rooms live in LevelRooms (not the
        // object list), and Level/Tool/GeoSphere aren't world-placed actors —
        // GetObject() returns null. Not a mapping error (the slot is still
        // sequential — the spatial neighbours either side match); editing one
        // would hit wfmut's graceful "not an actor" rejection.
        const char* tag;
        if (xyz_match)              { tag = "ok";                          ++matched;  }
        else if (!have_eng)         { tag = "no engine actor (Room/Level/Tool)"; ++no_actor; }
        else if (have_doc)          { tag = "DIFFERS (engine-managed pos)"; ++differs;  }
        else                        { tag = "(no doc Position)"; }

        std::fprintf(stderr,
            "[bridge]  %3d  %3d  %-22s  (%8.2f %8.2f %8.2f)  (%8.2f %8.2f %8.2f)  %s\n",
            i, eidx, names[i].c_str(),
            dp[0], dp[1], dp[2], ep[0], ep[1], ep[2], tag);
    }
    std::fprintf(stderr,
        "[bridge] identity map (offset +%d): %d matched, %d no-engine-actor, "
        "%d differ (activation boxes repositioned at load) of %zu — "
        "index + X confirm content[i] <-> engine idx i+%d\n",
        kDocToEngineIdx, matched, no_actor, differs, names.size(), kDocToEngineIdx);
}

// ── M2: field translation ────────────────────────────────────────────────────

namespace {

// OAD field name -> wfmut "block.field" path + whether it's a fixed-point float
// field (mirrors wfmut's kPropMap `is_fixed32` flags). Keyed on the OAD's `name`
// (descriptor.name) — the FULL, UNIQUE field identifier ("Step Size", "Model
// Type"), which is exactly the string the .lev/Doc carries. NOT the OAD's
// `displayName` (descriptor.xdata.displayName): that is a shorter, non-unique UI
// label (four movement fields share "Acceleration", "Max Ground Speed"->"Max
// Speed") — fine for compact panel labels, ambiguous for engine addressing.
// These are the 15 fields wfmut covers today (D4). Position/Orientation are
// transform, handled separately. (The wfmut path's field component is the C++
// struct member — e.g. "Step Size" -> movebloc.StepSize — the same offset-
// addressed identity the Max attrib editor's copy_to_xdata used, oaddlg.h.)
struct PathInfo { const char* path; bool is_float; };
const std::unordered_map<std::string, PathInfo>& nameToPath()
{
    static const std::unordered_map<std::string, PathInfo> m = {
        {"MovementClass",             {"movebloc.MovementClass",        false}},
        {"Mobility",                  {"movebloc.Mobility",             false}},
        {"Mass",                      {"movebloc.Mass",                 true }},
        {"Step Size",                 {"movebloc.StepSize",             true }},
        {"Running Acceleration",      {"movebloc.RunningAcceleration",  true }},
        {"Max Ground Speed",          {"movebloc.MaxGroundSpeed",       true }},
        {"Jumping Acceleration",      {"movebloc.JumpingAcceleration",  true }},
        {"Falling Acceleration",      {"movebloc.FallingAcceleration",  true }},
        {"hp",                        {"common.hp",                     true }},
        {"Number Of Local Mailboxes", {"common.NumberOfLocalMailboxes", false}},
        {"Write To Mailbox On Death", {"common.WriteToMailboxOnDeath",  false}},
        {"Model Type",                {"mesh.ModelType",                false}},
        {"Animation Mailbox",         {"mesh.AnimationMailbox",         false}},
        {"Visibility Mailbox",        {"mesh.VisibilityMailbox",        false}},
    };
    return m;
}

// Leading number of a (possibly fixed-point-suffixed) token: strtod/strtoll stop
// at the '(' of "(1.15.16)" or the trailing 'l', so the leading value is read.
double    LeadingDouble(const std::string& s) { return std::strtod(s.c_str(), nullptr); }
long long LeadingLong(const std::string& s)   { return std::strtoll(s.c_str(), nullptr, 10); }

bool HasDigit(const std::string& s)
{
    for (char c : s) if (c >= '0' && c <= '9') return true;
    return false;
}

}  // namespace

EngineWrite TranslateField(const PropField& f)
{
    EngineWrite w;

    // Address by the field's full unique name (f.name == the Doc/.lev NAME ==
    // the OAD descriptor.name). Transform fields (Position/Orientation) live in
    // the per-instance prefix and are addressed by the same name.
    const std::string& key = f.name;

    // Transform: value is the 3 components of the VEC3/EULR DATA leaf.
    if (key == "Position") {
        w.kind = EngineWrite::Pos;
        ParseVec3(f.data, w.vec);
        return w;
    }
    if (key == "Orientation") {
        w.kind = EngineWrite::Orient;   // revolutions, as stored (no conversion)
        ParseVec3(f.data, w.vec);
        return w;
    }

    const auto& m = nameToPath();
    auto it = m.find(key);
    if (it == m.end()) return w;        // NoOp — unmapped long tail (D4)

    w.path = it->second.path;
    if (it->second.is_float) {
        w.kind = EngineWrite::FieldFloat;
        w.d = LeadingDouble(f.data);
    } else {
        w.kind = EngineWrite::FieldInt;
        // int / enum / bool: prefer the raw DATA value; for an enum stored only
        // as a label (no DATA leaf, e.g. Mobility), resolve label -> option index.
        if (HasDigit(f.data)) {
            w.i = LeadingLong(f.data);
        } else {
            for (std::size_t k = 0; k < f.options.size(); ++k)
                if (f.options[k] == f.label) { w.i = static_cast<long long>(k); break; }
        }
    }
    return w;
}

void DumpTranslations(wfcrdt::Doc& doc, int doc_index)
{
    std::vector<PropField> props = ResolveProperties(ReadActorFields(doc, doc_index));
    std::fprintf(stderr, "[bridge] translations for Doc actor %d (%zu fields):\n",
                 doc_index, props.size());
    int mapped = 0;
    for (const auto& f : props) {
        const EngineWrite w = TranslateField(f);
        const char* k = "None";
        char val[96] = "";
        switch (w.kind) {
            case EngineWrite::Pos:
                k = "Pos";    std::snprintf(val, sizeof val, "(%.3f %.3f %.3f)", w.vec[0], w.vec[1], w.vec[2]); break;
            case EngineWrite::Orient:
                k = "Orient"; std::snprintf(val, sizeof val, "(%.4f %.4f %.4f) rev", w.vec[0], w.vec[1], w.vec[2]); break;
            case EngineWrite::FieldFloat:
                k = "FieldFloat"; std::snprintf(val, sizeof val, "%s = %.4f", w.path.c_str(), w.d); break;
            case EngineWrite::FieldInt:
                k = "FieldInt";   std::snprintf(val, sizeof val, "%s = %lld", w.path.c_str(), w.i); break;
            case EngineWrite::NoOp: break;
        }
        if (w.kind != EngineWrite::NoOp) ++mapped;
        std::fprintf(stderr, "[bridge]   %-26s -> %-10s %s\n", f.name.c_str(), k, val);
    }
    std::fprintf(stderr, "[bridge] translations: %d/%zu mapped to an engine write\n",
                 mapped, props.size());
}

}  // namespace wfedit
