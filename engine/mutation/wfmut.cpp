// engine/mutation/wfmut.cpp
//
// Implementation of the wfmut:: engine mutation API.
// See docs/plans/2026-05-19-engine-mutation-api.md for plan and test matrix.
//
// Gated at the UNION of WF_DEBUG_BRIDGE and WF_ENABLE_EDITOR — both
// consumers drive wfmut::. The header provides no-op stubs when neither
// flag is set, so callers compile cleanly; this TU compiles to an empty
// translation unit and is excluded from the source list in CMakeLists.txt
// and engine/build_game.sh in that case.

#include "wfmut.hpp"

#if defined(WF_DEBUG_BRIDGE) || defined(WF_ENABLE_EDITOR)

#include "level.hp"
#include "actor.hp"

#ifdef PHYSICS_ENGINE_JOLT
#  include <physics/jolt/jolt_backend.hp>
#endif

#ifdef WF_WITH_FORTH
#  include "scripting_forth.hp"
#endif

#include <cstddef>          // offsetof
#include <unordered_map>

namespace wfmut {

namespace {

thread_local std::string g_lastError;

bool fail(const char* msg)
{
    g_lastError = msg;
    return false;
}

template <typename T>
std::optional<T> failopt(const char* msg)
{
    g_lastError = msg;
    return std::nullopt;
}

void ok() { g_lastError.clear(); }

// Centralised actor resolution. Differentiates the four common failure modes
// so tests T3/T4/T5 can distinguish them via lastError():
//   - idx == 0                          → "idx must be >= 1"
//   - idx >= list size                  → "idx out of range"
//   - slot is empty                     → "no object at idx"
//   - object exists but isn't an Actor  → "object at idx is not an Actor"
Actor* resolve_actor(const Level& level, ActorIdx idx, const char* func)
{
    if (idx == 0) {
        g_lastError.assign(func).append(": idx must be >= 1");
        return nullptr;
    }
    // GetObjectList() has no const overload — we promise not to mutate the
    // list itself.
    BaseObjectList& list = const_cast<Level&>(level).GetObjectList();
    int signed_idx = static_cast<int>(idx);
    if (signed_idx >= list.Size()) {
        g_lastError.assign(func).append(": idx out of range");
        return nullptr;
    }
    BaseObject* bo = level.GetObject(signed_idx);
    if (!bo) {
        g_lastError.assign(func).append(": no object at idx");
        return nullptr;
    }
    Actor* actor = dynamic_cast<Actor*>(bo);
    if (!actor) {
        g_lastError.assign(func).append(": object at idx is not an Actor");
        return nullptr;
    }
    return actor;
}

} // namespace

const char* lastError() { return g_lastError.c_str(); }

// ── Transform ───────────────────────────────────────────────────────────────

bool SetActorPos(Level& level, ActorIdx idx, const Vector3& pos)
{
    Actor* actor = resolve_actor(level, idx, "wfmut::SetActorPos");
    if (!actor) return false;
    // Actor::setCurrentPos already syncs the Jolt character + body if the
    // handles are valid; nothing extra to do here. The Mobility==0 cerror
    // surfaces inside setCurrentPos itself in DBSTREAM1 builds — we treat
    // that as a warning, not a failure, and still return true.
    actor->setCurrentPos(pos);
    ok();
    return true;
}

std::optional<Vector3> GetActorPos(const Level& level, ActorIdx idx)
{
    Actor* actor = resolve_actor(level, idx, "wfmut::GetActorPos");
    if (!actor) return std::nullopt;
    ok();
    return actor->currentPos();
}

bool SetActorOrientation(Level& level, ActorIdx idx, const Euler& e)
{
    Actor* actor = resolve_actor(level, idx, "wfmut::SetActorOrientation");
    if (!actor) return false;
    actor->GetWritablePhysicalAttributes().SetRotation(e);
#ifdef PHYSICS_ENGINE_JOLT
    // PhysicalAttributes::SetRotation only writes the engine-side orientation;
    // unlike setCurrentPos it does not also push to the Jolt body. Mirror the
    // sync pattern from actor.hpi:93-108 manually so the renderer and physics
    // agree. Follow-up: docs/plans/2026-05-19-engine-mutation-api.md TODO —
    // add Actor::setOrientation() so this lives next to setCurrentPos.
    uint32_t bodyID = actor->GetPhysicalAttributes().JoltBodyID();
    if (bodyID != kJoltInvalidBodyID)
        JoltBodySetRotation(bodyID, e);
#endif
    ok();
    return true;
}

std::optional<Euler> GetActorOrientation(const Level& level, ActorIdx idx)
{
    Actor* actor = resolve_actor(level, idx, "wfmut::GetActorOrientation");
    if (!actor) return std::nullopt;
    ok();
    return actor->GetPhysicalAttributes().Rotation();
}

// ── OAD field writes ────────────────────────────────────────────────────────
// Field schema. Relocated from engine/stubs/debug_server.cc:214-241 (step 3
// of the mutation API plan); the bridge now consumes wfmut::SetActorField
// rather than maintaining a duplicate table.

namespace {

struct PropInfo {
    enum Block { COMMON, MOVEBLOC, MESH } block;
    std::size_t field_offset;
    bool        is_fixed32;     // true: float×65536 → int32; false: float→int32 truncate
};

const std::unordered_map<std::string, PropInfo>& propMap()
{
    static const std::unordered_map<std::string, PropInfo> kPropMap = {
        // common block
        {"common.hp",                     {PropInfo::COMMON,   offsetof(_Common,   hp),                    true }},
        {"common.Script",                 {PropInfo::COMMON,   offsetof(_Common,   Script),                false}},
        {"common.NumberOfLocalMailboxes", {PropInfo::COMMON,   offsetof(_Common,   NumberOfLocalMailboxes), false}},
        {"common.WriteToMailboxOnDeath",  {PropInfo::COMMON,   offsetof(_Common,   WriteToMailboxOnDeath),  false}},
        // movebloc block
        {"movebloc.Mass",                 {PropInfo::MOVEBLOC, offsetof(_Movement, Mass),                  true }},
        {"movebloc.MaxGroundSpeed",       {PropInfo::MOVEBLOC, offsetof(_Movement, MaxGroundSpeed),        true }},
        {"movebloc.RunningAcceleration",  {PropInfo::MOVEBLOC, offsetof(_Movement, RunningAcceleration),   true }},
        {"movebloc.JumpingAcceleration",  {PropInfo::MOVEBLOC, offsetof(_Movement, JumpingAcceleration),   true }},
        {"movebloc.FallingAcceleration",  {PropInfo::MOVEBLOC, offsetof(_Movement, FallingAcceleration),   true }},
        {"movebloc.StepSize",             {PropInfo::MOVEBLOC, offsetof(_Movement, StepSize),              true }},
        {"movebloc.Mobility",             {PropInfo::MOVEBLOC, offsetof(_Movement, Mobility),              false}},
        {"movebloc.MovementClass",        {PropInfo::MOVEBLOC, offsetof(_Movement, MovementClass),         false}},
        // mesh block
        {"mesh.ModelType",                {PropInfo::MESH,     offsetof(_Mesh,     ModelType),             false}},
        {"mesh.AnimationMailbox",         {PropInfo::MESH,     offsetof(_Mesh,     AnimationMailbox),      false}},
        {"mesh.VisibilityMailbox",        {PropInfo::MESH,     offsetof(_Mesh,     VisibilityMailbox),     false}},
    };
    return kPropMap;
}

// Return a mutable pointer to the named sub-block, or nullptr if unavailable.
// The underlying storage is heap-allocated char[]; const_cast follows the
// pattern actor.hpi uses for its own in-place writes.
char* get_block(Actor* actor, PropInfo::Block block_id)
{
    const void* ptr = nullptr;
    switch (block_id) {
        case PropInfo::COMMON:   ptr = actor->GetCommonBlockPtr();    break;
        case PropInfo::MOVEBLOC: ptr = actor->GetMovementBlockPtr();  break;
        case PropInfo::MESH:     ptr = actor->GetMeshBlockPtr();      break;
    }
    if (!ptr) return nullptr;
    return const_cast<char*>(static_cast<const char*>(ptr));
}

// Resolve fieldPath → (actor, block pointer, PropInfo). Populates lastError
// and returns false on any failure (bad idx, unknown path, block missing).
bool resolve_field(Level& level, ActorIdx idx, const char* fieldPath,
                   const char* func, Actor** out_actor,
                   char** out_block, PropInfo* out_info)
{
    *out_actor = resolve_actor(level, idx, func);
    if (!*out_actor) return false;

    auto& m = propMap();
    auto it = m.find(fieldPath);
    if (it == m.end()) {
        g_lastError.assign(func).append(": unknown field path '").append(fieldPath).append("'");
        return false;
    }
    *out_info = it->second;

    *out_block = get_block(*out_actor, out_info->block);
    if (!*out_block) {
        g_lastError.assign(func).append(": block accessor returned null for '").append(fieldPath).append("'");
        return false;
    }
    return true;
}

} // namespace

namespace {
// common.Script holds a resolved script handle, not a plain int — writing
// raw bytes corrupts script dispatch. Reject numeric writes; callers route
// script updates via wfmut::ReloadActorScript.
bool reject_script_write(const char* fieldPath, const char* func)
{
    if (fieldPath && std::string(fieldPath) == "common.Script") {
        g_lastError.assign(func).append(": common.Script is read-only here; use wfmut::ReloadActorScript");
        return true;
    }
    return false;
}
} // namespace

bool SetActorField(Level& level, ActorIdx idx, const char* fieldPath, std::int64_t value)
{
    if (reject_script_write(fieldPath, "wfmut::SetActorField(int64)")) return false;
    Actor* actor; char* block; PropInfo info;
    if (!resolve_field(level, idx, fieldPath, "wfmut::SetActorField(int64)", &actor, &block, &info))
        return false;
    // int64 path treats the value as raw int32 (no fixed-point scaling).
    // Saturate to int32 range to avoid silent wraparound.
    std::int64_t v = value;
    if (v > 0x7FFFFFFFll)        v = 0x7FFFFFFFll;
    else if (v < -0x80000000ll)  v = -0x80000000ll;
    *reinterpret_cast<int32*>(block + info.field_offset) = static_cast<int32>(v);
    ok();
    return true;
}

bool SetActorField(Level& level, ActorIdx idx, const char* fieldPath, double value)
{
    if (reject_script_write(fieldPath, "wfmut::SetActorField(double)")) return false;
    Actor* actor; char* block; PropInfo info;
    if (!resolve_field(level, idx, fieldPath, "wfmut::SetActorField(double)", &actor, &block, &info))
        return false;
    // Fixed32 fields: multiply by 65536; raw fields: truncate. Saturate so
    // out-of-range values don't silently wrap (F11 in the test matrix).
    double raw = info.is_fixed32 ? (value * 65536.0) : value;
    if (raw > 2147483647.0)       raw = 2147483647.0;
    else if (raw < -2147483648.0) raw = -2147483648.0;
    *reinterpret_cast<int32*>(block + info.field_offset) = static_cast<int32>(raw);
    ok();
    return true;
}

bool SetActorField(Level&, ActorIdx, const char* fieldPath, const char* /*value*/)
{
    // String overload reserved for future string-typed OAD fields. common.Script
    // is the only string-flavoured slot today; it's a resolved pointer into
    // level data — writing a raw int32 here corrupts script dispatch. Use
    // wfmut::ReloadActorScript instead.
    std::string p = fieldPath ? fieldPath : "";
    if (p == "common.Script") {
        return fail("wfmut::SetActorField(string): common.Script is read-only here; use wfmut::ReloadActorScript");
    }
    g_lastError.assign("wfmut::SetActorField(string): no string-typed field at '").append(p).append("'");
    return false;
}

std::optional<std::int64_t> GetActorFieldInt(const Level& level, ActorIdx idx, const char* fieldPath)
{
    Actor* actor; char* block; PropInfo info;
    if (!resolve_field(const_cast<Level&>(level), idx, fieldPath,
                       "wfmut::GetActorFieldInt", &actor, &block, &info))
        return std::nullopt;
    int32 raw = *reinterpret_cast<const int32*>(block + info.field_offset);
    ok();
    return static_cast<std::int64_t>(raw);
}

std::optional<double> GetActorFieldFloat(const Level& level, ActorIdx idx, const char* fieldPath)
{
    Actor* actor; char* block; PropInfo info;
    if (!resolve_field(const_cast<Level&>(level), idx, fieldPath,
                       "wfmut::GetActorFieldFloat", &actor, &block, &info))
        return std::nullopt;
    int32 raw = *reinterpret_cast<const int32*>(block + info.field_offset);
    ok();
    return info.is_fixed32 ? (static_cast<double>(raw) / 65536.0)
                           :  static_cast<double>(raw);
}

std::optional<std::string> GetActorFieldString(const Level&, ActorIdx, const char* fieldPath)
{
    // Matches SetActorField(string) — no string-typed OAD field today.
    std::string p = fieldPath ? fieldPath : "";
    g_lastError.assign("wfmut::GetActorFieldString: no string-typed field at '").append(p).append("'");
    return std::nullopt;
}

bool ReloadActorScript(Level& level, ActorIdx idx, const char* forthSource)
{
    Actor* actor = resolve_actor(level, idx, "wfmut::ReloadActorScript");
    if (!actor) return false;
    if (!forthSource) return fail("wfmut::ReloadActorScript: null source");
#ifdef WF_WITH_FORTH
    std::string log;
    bool compiled = forth_engine::ReloadActorScript(static_cast<int>(idx), forthSource, log);
    if (!compiled) {
        g_lastError.assign("wfmut::ReloadActorScript: compile failed: ").append(log);
        return false;
    }
    ok();
    return true;
#else
    return fail("wfmut::ReloadActorScript: engine built without Forth support");
#endif
}

// ── Spawn / remove ──────────────────────────────────────────────────────────

std::optional<ActorIdx> SpawnActor(Level& level, int templateIdx,
                                   const Vector3& pos, ActorIdx parentIdx)
{
    // The engine's SafelyConstructTemplateObject asserts on bad template /
    // parent indices, so pre-validate here. Level::HasTemplate is the public
    // probe added alongside this API.
    if (templateIdx <= 0)
        return failopt<ActorIdx>("wfmut::SpawnActor: templateIdx must be >= 1");
    if (!level.HasTemplate(templateIdx))
        return failopt<ActorIdx>("wfmut::SpawnActor: no template at idx");
    if (parentIdx == 0)
        return failopt<ActorIdx>("wfmut::SpawnActor: parentIdx must be >= 1 (engine asserts otherwise)");
    if (!resolve_actor(level, parentIdx, "wfmut::SpawnActor"))
        return std::nullopt;  // resolve_actor populated lastError already

    Actor* created = level.ConstructTemplateObject(
        templateIdx, static_cast<int>(parentIdx), pos, Vector3::zero);
    if (!created)
        return failopt<ActorIdx>("wfmut::SpawnActor: ConstructTemplateObject returned null");

    ok();
    return static_cast<ActorIdx>(created->GetActorIndex());
}

bool RemoveActor(Level& level, ActorIdx idx)
{
    Actor* actor = resolve_actor(level, idx, "wfmut::RemoveActor");
    if (!actor) return false;
    // SetPendingRemove asserts on statplats and the camera; the bridge has
    // happily relied on this behaviour, so we don't second-guess. Callers
    // wanting to remove non-removable objects will see the engine abort —
    // that's a level-content bug, not an API bug.
    level.SetPendingRemove(actor);
    ok();
    return true;
}

// ── Mailbox ─────────────────────────────────────────────────────────────────
// Per-actor mailbox slots only. Level-global mailbox access (idx == 0 in the
// engine's convention) is deferred to a sibling primitive — keep the API
// shape "idx is a real actor" consistent with the rest of wfmut.

bool SetMailbox(Level& level, ActorIdx idx, int mailboxIndex, double value)
{
    Actor* actor = resolve_actor(level, idx, "wfmut::SetMailbox");
    if (!actor) return false;
    if (mailboxIndex < 0)
        return fail("wfmut::SetMailbox: mailboxIndex must be >= 0");
    // Actor exposes its mailbox bank via GetMailboxes(); backing storage is
    // bounds-checked by MailboxesWithStorage in DBSTREAM builds.
    actor->GetMailboxes().WriteMailbox(static_cast<long>(mailboxIndex), Scalar::FromDouble(value));
    ok();
    return true;
}

std::optional<double> GetMailbox(const Level& level, ActorIdx idx, int mailboxIndex)
{
    Actor* actor = resolve_actor(const_cast<Level&>(level), idx, "wfmut::GetMailbox");
    if (!actor) return std::nullopt;
    if (mailboxIndex < 0)
        return failopt<double>("wfmut::GetMailbox: mailboxIndex must be >= 0");
    Scalar v = actor->GetMailboxes().ReadMailbox(static_cast<long>(mailboxIndex));
    ok();
    return static_cast<double>(v.AsFloat());
}

} // namespace wfmut

#endif // WF_DEBUG_BRIDGE || WF_ENABLE_EDITOR
