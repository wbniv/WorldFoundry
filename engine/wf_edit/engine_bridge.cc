//=============================================================================
// engine/wf_edit/engine_bridge.cc — CRDT->engine bridge (Option C).
//
// M1: identity mapping + verification dump.
// M2: stable doc→engine index map — structural edits (delete/duplicate) keep the
//     map valid so field→viewport propagation continues without a reload.
// M3: field translation + panel commit wired through wfmut.
//=============================================================================
#include "engine_bridge.h"
#include "level_doc.h"      // ReadActorNames / ReadActorFields
#include "property_panel.h" // PropField, FieldKind, ResolveProperties
#include "wfcrdt.hpp"       // wfcrdt::Doc, Map, Array, Subscription, YArrayEvent

#include <game/level.hp>            // Level, theLevel, GetObject, GetObjectList
#include <game/actor.hp>            // Actor, currentPos (pulls in Vector3/Scalar)
#include <baseobject/baseobject.hp> // IsActor, BaseObject
#include <math/euler.hp>            // Euler
#include <math/angle.hp>            // Angle::Revolution
#include "wfmut.hpp"                // wfmut::SetActorPos / SetActorOrientation / SetActorField

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <optional>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace wfedit {

// ── stable eid→engine bridge (Phase 3) ──────────────────────────────────────
// s_eid_to_engine: stable map — survives delete/duplicate of other actors.
// s_doc_to_engine: positional snapshot rebuilt by RebuildFromDoc; used by
//                  DocActorToEngineIdx (existing callers unchanged).
// s_needs_rebuild: set by the content-array observer; cleared by UpdateBridgeMap.
static std::unordered_map<std::string, wfmut::ActorIdx> s_eid_to_engine;
static std::vector<wfmut::ActorIdx>                     s_doc_to_engine;
static std::optional<wfcrdt::Subscription>              s_content_sub;
static bool                                             s_needs_rebuild = false;
static bool                                             s_bridge_ready  = false;

// Deep-observer field-sync state (single propagation path for ALL Doc writers —
// local panel, remote collaborator, undo/redo, replay, DAP). s_deep_sub fires on
// any field-leaf edit under content[]; its callback only records the touched
// actor's doc index (no Doc access — Yrs forbids a txn inside an observer).
// DrainEngineSync flushes the set at frame top. s_resync_all forces a full
// re-propagate after a structural rebuild shifted doc indices (see R2 below).
static std::unordered_set<int>             s_pending_resync;
static std::optional<wfcrdt::Subscription> s_deep_sub;
static bool                                s_resync_all = false;

int DocActorToEngineIdx(int doc_index)
{
    if (doc_index < 0 || doc_index >= static_cast<int>(s_doc_to_engine.size()))
        return 0;
    return static_cast<int>(s_doc_to_engine[doc_index]);
}

// Diff current Doc content against s_eid_to_engine; call wfmut Remove/Spawn
// as needed; rebuild s_doc_to_engine positional snapshot. Called outside any
// active transaction (from UpdateBridgeMap → frame loop).
static void RebuildFromDoc(wfcrdt::Doc& doc)
{
    if (!theLevel) return;
    auto txn = doc.begin();
    auto content = txn.array("content");
    const int n = content.len();

    std::vector<std::string> cur_eids;
    cur_eids.reserve(n);
    for (int i = 0; i < n; ++i) {
        wfcrdt::Map m = content.get(i).asMap();
        cur_eids.push_back(m.valid() ? m.get("_eid").readString().value_or("") : "");
    }

    std::unordered_set<std::string> cur_set(cur_eids.begin(), cur_eids.end());
    cur_set.erase("");

    // Remove actors whose eid left the content array.
    std::vector<std::string> to_remove;
    for (const auto& [eid, eng] : s_eid_to_engine)
        if (!cur_set.count(eid)) to_remove.push_back(eid);
    for (const auto& eid : to_remove) {
        const wfmut::ActorIdx eng = s_eid_to_engine[eid];
        if (eng > 0)
            wfmut::RemoveActor(*theLevel, eng);
        s_eid_to_engine.erase(eid);
        std::fprintf(stderr, "[bridge] removed eid %.8s… eng=%u\n", eid.c_str(), eng);
    }

    // Spawn actors whose eid is new in the content array.
    for (int i = 0; i < n; ++i) {
        const std::string& eid = cur_eids[i];
        if (eid.empty() || s_eid_to_engine.count(eid)) continue;
        wfcrdt::Map m = content.get(i).asMap();
        const std::string src_eid = m.valid() ? m.get("_src_eid").readString().value_or("") : "";
        wfmut::ActorIdx new_eng = 0;
        auto sit = s_eid_to_engine.find(src_eid);
        if (!src_eid.empty() && sit != s_eid_to_engine.end() && sit->second > 0) {
            const wfmut::ActorIdx src = sit->second;
            if (wfmut::HasTemplate(*theLevel, static_cast<int>(src))) {
                const auto sp = wfmut::GetActorPos(*theLevel, src);
                const Vector3 off(Scalar::zero, Scalar::zero, Scalar::FromFloat(0.5f));
                const Vector3 pos = sp ? (*sp + off) : off;
                if (auto ni = wfmut::SpawnActor(*theLevel, static_cast<int>(src), pos, 1))
                    new_eng = *ni;
            }
        }
        s_eid_to_engine[eid] = new_eng;
        std::fprintf(stderr, "[bridge] new eid %.8s… eng=%u\n", eid.c_str(), new_eng);
    }

    // Rebuild positional snapshot.
    s_doc_to_engine.assign(n, 0);
    for (int i = 0; i < n; ++i) {
        auto it = s_eid_to_engine.find(cur_eids[i]);
        if (it != s_eid_to_engine.end()) s_doc_to_engine[i] = it->second;
    }
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
        "[bridge] identity map: %zu Doc actors vs %d engine actor slots (eid map, %s, %zu eids)\n",
        names.size(), engine_count, s_bridge_ready ? "initialized" : "not yet initialized",
        s_eid_to_engine.size());
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
        "[bridge] identity map: %d matched, %d no-engine-actor, "
        "%d differ (activation boxes repositioned at load) of %zu\n",
        matched, no_actor, differs, names.size());
}

void InitBridgeMap(wfcrdt::Doc& doc)
{
    if (s_bridge_ready || !theLevel) return;

    auto txn = doc.begin();
    auto content = txn.array("content");
    const int n = content.len();

    s_eid_to_engine.clear();
    s_doc_to_engine.assign(n, 0);
    for (int i = 0; i < n; ++i) {
        wfcrdt::Map m = content.get(i).asMap();
        const std::string eid = m.valid() ? m.get("_eid").readString().value_or("") : "";
        const wfmut::ActorIdx eng = static_cast<wfmut::ActorIdx>(i + 1);
        if (!eid.empty()) s_eid_to_engine[eid] = eng;
        s_doc_to_engine[i] = eng;
    }

    // Dirty flag only — no transaction started inside the callback.
    s_content_sub = content.observe([](const YArrayEvent*) {
        s_needs_rebuild = true;
    });

    // Deep observer: a field-leaf edit anywhere under content[] fires here with a
    // path relative to content, so path[0] is the actor's doc index. Record it
    // and propagate at frame top (DrainEngineSync). A structural add/remove fires
    // *at* content (empty path) — skipped here; s_content_sub handles the rebuild.
    s_deep_sub = content.observeDeep([](const std::vector<wfcrdt::DeepPath>& evs) {
        for (const auto& p : evs)
            if (!p.empty() && p[0].isIndex)
                s_pending_resync.insert(static_cast<int>(p[0].index));
    });

    s_bridge_ready = true;
    std::fprintf(stderr, "[bridge] InitBridgeMap: %d actors, %zu eids tracked\n",
                 n, s_eid_to_engine.size());
}

void UpdateBridgeMap(wfcrdt::Doc& doc)
{
    if (!s_bridge_ready || !s_needs_rebuild) return;
    s_needs_rebuild = false;
    RebuildFromDoc(doc);
    // R2: a structural insert/remove shifts content[] indices, so any actor index
    // queued by the deep observer before this rebuild may now point at a different
    // actor. Drop the stale queue and re-propagate every live actor this frame.
    s_pending_resync.clear();
    s_resync_all = true;
}

// Push queued Doc field edits into the live engine. Runs at frame top (after
// UpdateBridgeMap, with no live txn) — safe to open the read txns ReadActorFields
// needs. Drives the viewport for EVERY Doc writer; the local panel no longer
// calls PropagateToEngine directly. Re-reads each touched actor and re-applies
// its OAD-matched fields (idempotent — the engine never writes back to the Doc).
void DrainEngineSync(wfcrdt::Doc& doc)
{
    if (!s_bridge_ready || !theLevel) return;

    std::vector<int> actors;
    if (s_resync_all) {
        s_resync_all = false;
        s_pending_resync.clear();
        const int n = static_cast<int>(s_doc_to_engine.size());
        actors.reserve(n);
        for (int i = 0; i < n; ++i) actors.push_back(i);
    } else {
        if (s_pending_resync.empty()) return;
        actors.assign(s_pending_resync.begin(), s_pending_resync.end());
        s_pending_resync.clear();
    }

    for (int idx : actors) {
        if (DocActorToEngineIdx(idx) < 1) continue;   // no live engine actor
        // Propagate every field — NOT just OAD-`matched` ones. TranslateField
        // returns NoOp for the unmapped long tail (and PropagateToEngine skips
        // those), but the transform fields Position/Orientation are addressed
        // by name and are NOT OAD-matched (per-instance prefix), so a `matched`
        // guard would silently drop exactly the edits that move the viewport.
        for (const auto& pf : ResolveProperties(ReadActorFields(doc, idx)))
            PropagateToEngine(idx, pf);
    }
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
// Generated by regen-headers.sh from common.inc/movebloc.inc/mesh.inc; covers
// all 77 kpropmap fields. Regenerate: task gen-oas-headers.
struct PathInfo { const char* path; bool is_float; };
const std::unordered_map<std::string, PathInfo>& nameToPath()
{
    static const std::unordered_map<std::string, PathInfo> m = {
#include "name_to_path_generated.inc"
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
        w.kind = EngineWrite::Orient;   // radians as stored; converted to revs in PropagateToEngine
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
                k = "Orient"; std::snprintf(val, sizeof val, "(%.4f %.4f %.4f) rad", w.vec[0], w.vec[1], w.vec[2]); break;
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

// ── M3: propagate into the live engine ───────────────────────────────────────

void PropagateToEngine(int doc_index, const PropField& f)
{
    if (!theLevel) return;
    const int idx = DocActorToEngineIdx(doc_index);
    if (idx < 1) return;

    const EngineWrite w = TranslateField(f);
    switch (w.kind) {
        case EngineWrite::Pos:
            wfmut::SetActorPos(*theLevel, idx,
                Vector3(Scalar::FromFloat(w.vec[0]),
                        Scalar::FromFloat(w.vec[1]),
                        Scalar::FromFloat(w.vec[2])));
            break;
        case EngineWrite::Orient: {
            // The Doc/.lev EULR DATA is in RADIANS (levcomp-rs converts via
            // radians_fx_to_u16_revs; decompile.rs:56-60 inverse). Convert to
            // revolutions for Angle::Revolution, wrapping to [0,1) (Validate is
            // happiest with an in-range fraction; a panel edit isn't clamped).
            constexpr float kTwoPi = 6.28318530717958647692f;
            auto rev = [](float r) { r = std::fmod(r, 1.0f); return Scalar::FromFloat(r < 0 ? r + 1.0f : r); };
            wfmut::SetActorOrientation(*theLevel, idx,
                Euler(Angle::Revolution(rev(w.vec[0] / kTwoPi)),
                      Angle::Revolution(rev(w.vec[1] / kTwoPi)),
                      Angle::Revolution(rev(w.vec[2] / kTwoPi))));
            break;
        }
        case EngineWrite::FieldFloat:
            wfmut::SetActorField(*theLevel, idx, w.path.c_str(), w.d);
            break;
        case EngineWrite::FieldInt:
            wfmut::SetActorField(*theLevel, idx, w.path.c_str(),
                                 static_cast<std::int64_t>(w.i));
            break;
        case EngineWrite::NoOp:
            break;
    }
}

void RunBridgeTest(wfcrdt::Doc& doc, int doc_index,
                   const std::string& field_name, const std::string& new_data)
{
    if (!theLevel) { std::fprintf(stderr, "[bridge-test] no live level\n"); return; }
    const int eidx = DocActorToEngineIdx(doc_index);

    const auto before = wfmut::GetActorPos(*theLevel, eidx);

    // Locate the field's Doc address and overwrite its DATA leaf, exactly as the
    // panel's commit would (WriteFieldLeaf).
    int child = -1;
    for (const auto& af : ReadActorFields(doc, doc_index))
        if (af.name == field_name) { child = af.child_index; break; }
    if (child < 0) {
        std::fprintf(stderr, "[bridge-test] field '%s' not found on actor %d\n",
                     field_name.c_str(), doc_index);
        return;
    }
    WriteFieldLeaf(doc, doc_index, child, "DATA", new_data);

    // Re-resolve the actor and propagate the edited field through the bridge.
    bool propagated = false;
    for (const auto& pf : ResolveProperties(ReadActorFields(doc, doc_index)))
        if (pf.name == field_name) { PropagateToEngine(doc_index, pf); propagated = true; break; }

    const auto after = wfmut::GetActorPos(*theLevel, eidx);
    auto fmt = [](const std::optional<Vector3>& p) -> std::string {
        if (!p) return "(n/a)";
        char b[64];
        std::snprintf(b, sizeof b, "(%.3f %.3f %.3f)",
                      p->X().AsFloat(), p->Y().AsFloat(), p->Z().AsFloat());
        return b;
    };
    std::fprintf(stderr,
        "[bridge-test] actor %d (eng %d) %s := \"%s\"  %s  pos before %s  after %s\n",
        doc_index, eidx, field_name.c_str(), new_data.c_str(),
        propagated ? "propagated" : "NOT propagated",
        fmt(before).c_str(), fmt(after).c_str());
}

void RunRemoteSyncTest(wfcrdt::Doc& doc, int selectedA, int docB,
                       const std::string& new_pos)
{
    if (!theLevel) { std::fprintf(stderr, "[remote-test] no live level\n"); return; }
    if (docB == selectedA) {
        std::fprintf(stderr, "[remote-test] FAIL: docB (%d) must differ from "
                             "selected A (%d) — that's the whole regression\n",
                     docB, selectedA);
        return;
    }
    const int engB = DocActorToEngineIdx(docB);
    if (engB < 1) {
        std::fprintf(stderr, "[remote-test] FAIL: actor %d has no live engine counterpart\n", docB);
        return;
    }

    const auto before = wfmut::GetActorPos(*theLevel, engB);

    int child = -1;
    for (const auto& af : ReadActorFields(doc, docB))
        if (af.name == "Position") { child = af.child_index; break; }
    if (child < 0) {
        std::fprintf(stderr, "[remote-test] FAIL: actor %d has no Position field\n", docB);
        return;
    }

    // Apply on a REMOTE-origin txn (a peer/replay/DAP edit). The commit fires the
    // bridge's deep observer, which queues actor B — there is deliberately NO
    // PropagateToEngine call here, so only the deep observer + DrainEngineSync can
    // move the engine actor.
    if (!WriteFieldLeaf(doc, docB, child, "DATA", new_pos, /*remote=*/true)) {
        std::fprintf(stderr, "[remote-test] FAIL: WriteFieldLeaf on actor %d failed\n", docB);
        return;
    }

    DrainEngineSync(doc);   // exactly what editor_build calls before StepFrame

    const auto after = wfmut::GetActorPos(*theLevel, engB);
    auto fmt = [](const std::optional<Vector3>& p) -> std::string {
        if (!p) return "(n/a)";
        char b[64];
        std::snprintf(b, sizeof b, "(%.3f %.3f %.3f)",
                      p->X().AsFloat(), p->Y().AsFloat(), p->Z().AsFloat());
        return b;
    };
    auto moved = [](const std::optional<Vector3>& a, const std::optional<Vector3>& b) {
        if (!a || !b) return false;
        auto d = [](Scalar x, Scalar y) { return std::fabs(x.AsFloat() - y.AsFloat()); };
        return d(a->X(), b->X()) > 1e-4f || d(a->Y(), b->Y()) > 1e-4f || d(a->Z(), b->Z()) > 1e-4f;
    };
    std::fprintf(stderr,
        "[remote-test] selected A=%d  remote-edit B=%d (eng %d) Position := \"%s\"  "
        "before %s  after %s  ==> %s\n",
        selectedA, docB, engB, new_pos.c_str(), fmt(before).c_str(), fmt(after).c_str(),
        moved(before, after)
            ? "PASS (deep observer propagated a remote edit to a NON-selected actor)"
            : "FAIL (engine actor did not move)");
}

void RunSpawnConfirmTest()
{
    if (!theLevel) { std::fprintf(stderr, "[spawn-test] no live level\n"); return; }

    // ── Part A: HasTemplate scan ─────────────────────────────────────────────
    // Identify which slots have template entries. _templateObjects[i] is non-null
    // for actors the level compiler marked "templated" (not constructed at startup).
    // In practice these include Rooms, Level, Tool objects as well as runtime-
    // spawnable actors. The first non-null entry is logged but NOT spawned —
    // SpawnActor on Room/Level/Tool types aborts via terminate() in the OAS-
    // generated constructor. SpawnActor confirmation for real Actor templates is
    // deferred until a level with confirmed-spawnable actor entries is available.
    int template_idx = -1;
    const int obj_list_size = theLevel->GetObjectList().Size();
    for (int i = 1; i < obj_list_size; ++i) {
        if (wfmut::HasTemplate(*theLevel, i)) { template_idx = i; break; }
    }
    if (template_idx < 0) {
        std::fprintf(stderr, "[spawn-test] HasTemplate: no non-null entries in 1..%d\n",
                     obj_list_size - 1);
    } else {
        std::fprintf(stderr, "[spawn-test] HasTemplate: first non-null entry at idx %d "
                             "(NOT spawned — Room/Tool types abort in OAS constructor)\n",
                     template_idx);
    }

    // ── Part B: RemoveActor on a real startup actor ──────────────────────────
    // Find the first startup-constructed actor (HasTemplate false + GetActorPos
    // returns a value) that is safe to remove (not the camera). This confirms the
    // live-delete path that M2 wired up. Removal is deferred (SetPendingRemove);
    // the actor stays alive until the next Level::update().
    int remove_idx = -1;
    for (int i = 2; i < std::min(obj_list_size, 40); ++i) {
        if (wfmut::HasTemplate(*theLevel, i)) continue;  // skip templated (Room/Level/Tool)
        const auto pos = wfmut::GetActorPos(*theLevel, i);
        if (!pos) continue;     // no live actor at this slot
        // Skip statplats — engine asserts on SetPendingRemove; Part C covers that path.
        BaseObject* bo = theLevel->GetObject(i);
        if (bo && bo->kind() == Actor::StatPlat_KIND) continue;
        remove_idx = i;
        break;
    }
    if (remove_idx < 0) {
        std::fprintf(stderr, "[spawn-test] FAIL: no removable startup actor found\n");
        return;
    }
    const auto before = wfmut::GetActorPos(*theLevel, remove_idx);
    std::fprintf(stderr, "[spawn-test] RemoveActor: target engine idx %d  pos (%.3f %.3f %.3f)\n",
                 remove_idx,
                 before->X().AsFloat(), before->Y().AsFloat(), before->Z().AsFloat());

    const bool removed = wfmut::RemoveActor(*theLevel, remove_idx);
    if (!removed) {
        std::fprintf(stderr, "[spawn-test] FAIL: RemoveActor(%d) returned false — %s\n",
                     remove_idx, wfmut::lastError());
        return;
    }
    std::fprintf(stderr, "[spawn-test] B-PASS: RemoveActor queued (deferred deletion confirmed)\n");

    // ── Part C: statplat rejection (regression for wfmut::RemoveActor guard) ──
    // Engine slot 1 in snowgoons is House — a StatPlat_KIND. wfmut::RemoveActor
    // must return false (not crash) when asked to remove one. This guards the
    // fix that prevents BridgeNotifyDelete from aborting on statplat actors.
    const bool statplat_rejected = !wfmut::RemoveActor(*theLevel, 1);
    if (!statplat_rejected) {
        std::fprintf(stderr, "[spawn-test] C-FAIL: RemoveActor(1) should have rejected statplat\n");
        return;
    }
    const char* errmsg = wfmut::lastError();
    const bool has_error = errmsg && errmsg[0];
    std::fprintf(stderr, "[spawn-test] C-PASS: statplat rejected gracefully — %s\n",
                 has_error ? errmsg : "(no error message)");
    std::fprintf(stderr, "[spawn-test] PASS (all parts)\n"
                         "[spawn-test] SpawnActor deferred: Room/Tool templates abort; needs "
                         "a level with confirmed Actor-kind templates\n");
}

}  // namespace wfedit
