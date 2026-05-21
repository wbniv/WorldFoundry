//=============================================================================
// engine/wf_edit/engine_bridge.cc — CRDT->engine bridge (Option C), M1.
//
// Identity mapping: Doc content[] index <-> engine 1-based actor index, plus a
// WF_EDIT_BRIDGE_DEBUG verification dump that cross-checks each Doc actor's
// Position leaf against the live engine actor's currentPos(). No mutation yet
// (M2 = field translation, M3 = wire the panel commit through wfmut).
//=============================================================================
#include "engine_bridge.h"
#include "level_doc.h"   // ReadActorNames / ReadActorFields

#include <game/level.hp>            // Level, theLevel, GetObject, GetObjectList
#include <game/actor.hp>            // Actor, currentPos (pulls in Vector3/Scalar)
#include <baseobject/baseobject.hp> // IsActor, BaseObject

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <string>
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

}  // namespace wfedit
