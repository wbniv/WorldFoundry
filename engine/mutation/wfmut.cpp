// engine/mutation/wfmut.cpp
//
// Step-1 skeleton: every primitive is a stub that returns false / nullopt
// and sets lastError() to "not implemented". Real bodies land step-by-step
// per docs/plans/2026-05-19-engine-mutation-api.md.

#include "wfmut.hpp"

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
} // namespace

const char* lastError() { return g_lastError.c_str(); }

// ── Transform ───────────────────────────────────────────────────────────────

bool SetActorPos(Level&, ActorIdx, const Vector3&)
{
    return fail("wfmut::SetActorPos: not implemented (step 2)");
}

std::optional<Vector3> GetActorPos(const Level&, ActorIdx)
{
    return failopt<Vector3>("wfmut::GetActorPos: not implemented (step 2)");
}

bool SetActorOrientation(Level&, ActorIdx, const Euler&)
{
    return fail("wfmut::SetActorOrientation: not implemented (step 2)");
}

std::optional<Euler> GetActorOrientation(const Level&, ActorIdx)
{
    return failopt<Euler>("wfmut::GetActorOrientation: not implemented (step 2)");
}

// ── OAD field writes ────────────────────────────────────────────────────────

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

// Silence unused-warning for the success helper until step 2 wires real
// bodies that actually call ok().
[[maybe_unused]] static void touch_ok_helper() { ok(); }

} // namespace wfmut
