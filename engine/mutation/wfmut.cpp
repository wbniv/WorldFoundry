// engine/mutation/wfmut.cpp
//
// Implementation of the wfmut:: engine mutation API.
// See docs/plans/2026-05-19-engine-mutation-api.md for plan and test matrix.
//
// Editor-stack only — gated by WF_ENABLE_EDITOR. The header provides no-op
// stubs when the flag is off, so callers compile cleanly; this TU compiles
// to an empty translation unit (and is also excluded from the source list
// in CMakeLists.txt / build_game.sh).

#include "wfmut.hpp"

#ifdef WF_ENABLE_EDITOR

#include "level.hp"
#include "actor.hp"

#ifdef PHYSICS_ENGINE_JOLT
#  include <physics/jolt/jolt_backend.hp>
#endif

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
// Real bodies land in step 3 once kPropMap is relocated here.

bool SetActorField(Level&, ActorIdx, const char*, std::int64_t)
{
    return fail("wfmut::SetActorField(int64): not implemented (step 3)");
}

bool SetActorField(Level&, ActorIdx, const char*, double)
{
    return fail("wfmut::SetActorField(double): not implemented (step 3)");
}

bool SetActorField(Level&, ActorIdx, const char*, const char*)
{
    return fail("wfmut::SetActorField(string): not implemented (step 3)");
}

std::optional<std::int64_t> GetActorFieldInt(const Level&, ActorIdx, const char*)
{
    return failopt<std::int64_t>("wfmut::GetActorFieldInt: not implemented (step 3)");
}

std::optional<double> GetActorFieldFloat(const Level&, ActorIdx, const char*)
{
    return failopt<double>("wfmut::GetActorFieldFloat: not implemented (step 3)");
}

std::optional<std::string> GetActorFieldString(const Level&, ActorIdx, const char*)
{
    return failopt<std::string>("wfmut::GetActorFieldString: not implemented (step 3)");
}

bool ReloadActorScript(Level&, ActorIdx, const char*)
{
    return fail("wfmut::ReloadActorScript: not implemented (step 3b)");
}

// ── Spawn / remove ──────────────────────────────────────────────────────────

std::optional<ActorIdx> SpawnActor(Level&, int, const Vector3&, ActorIdx)
{
    return failopt<ActorIdx>("wfmut::SpawnActor: not implemented (step 4)");
}

bool RemoveActor(Level&, ActorIdx)
{
    return fail("wfmut::RemoveActor: not implemented (step 4)");
}

// ── Mailbox ─────────────────────────────────────────────────────────────────

bool SetMailbox(Level&, ActorIdx, int, double)
{
    return fail("wfmut::SetMailbox: not implemented (step 5)");
}

std::optional<double> GetMailbox(const Level&, ActorIdx, int)
{
    return failopt<double>("wfmut::GetMailbox: not implemented (step 5)");
}

} // namespace wfmut

#endif // WF_ENABLE_EDITOR
