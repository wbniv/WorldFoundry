// engine/mutation/wfmut.hpp
//
// Engine mutation API — a plain C++ surface for external mutation of live
// engine state. Editor's CRDT bridge, DAP debugger, replay UI, and headless
// test harness all consume this surface; the legacy ad-hoc paths in
// engine/stubs/debug_server.cc are being refactored to route through it.
//
// Plan: docs/plans/2026-05-19-engine-mutation-api.md
//
// Threading: synchronous, single-threaded. Caller is responsible for
// marshalling onto the game thread. No internal locks. Calling from a
// non-game thread is UB; debug builds capture the first-call thread id
// and assert on mismatch (see X5 in the plan's Test matrix).

#pragma once

#include <cstdint>
#include <optional>
#include <string>

// std::optional<Vector3> / std::optional<Euler> require the complete type at
// the declaration site, so we include the math headers rather than forward-
// declaring. Level stays forward-declared (only used as reference parameter).
#include <math/vector3.hp>
#include <math/euler.hp>

class Level;

namespace wfmut {

// ── Identity ────────────────────────────────────────────────────────────────
// 1-based actor index, matches Level::GetObject(idx) and BaseObjectList
// iteration. Zero is invalid (reserved by the engine).
using ActorIdx = std::uint32_t;

// ── Errors ──────────────────────────────────────────────────────────────────
// Thread-local; populated on the most recent wfmut call. Cleared (returns
// empty string) on a successful call. Never returns nullptr.
const char* lastError();

// ── Transform ───────────────────────────────────────────────────────────────
// SetActorPos routes through Actor::setCurrentPos which already syncs the
// Jolt character and body if their handles are valid (actor.hpi:84-110).
// Returns true if the write reached the actor; the Mobility==0 cerror at
// actor.hpi:88 surfaces independently and does NOT flip the return to false.
bool SetActorPos(Level& level, ActorIdx idx, const Vector3& pos);
std::optional<Vector3> GetActorPos(const Level& level, ActorIdx idx);

// Angles are in revolutions per the engine-wide convention; conversion to
// the underlying fixed-point Euler representation is internal.
bool SetActorOrientation(Level& level, ActorIdx idx, const Euler& e);
std::optional<Euler> GetActorOrientation(const Level& level, ActorIdx idx);

// ── OAD field writes ────────────────────────────────────────────────────────
// fieldPath := "common.<field>" | "movebloc.<field>" | "mesh.<field>".
// The kPropMap table inside wfmut.cpp dispatches the path to the right block
// accessor (GetCommonBlockPtr / GetMovementBlockPtr / GetMeshBlockPtr) and
// applies fixed-point scaling for fix32 fields (multiply by 65536 on write,
// divide on read).
//
// Writes are IN-PLACE into the (potentially-shared) OAD block. If two actors
// reference the same dedup'd page, both see the change. Full copy-on-write
// is deferred to a follow-up plan; F13 in the test matrix pins this behaviour.
//
// The const char* overload is reserved for future string-typed OAD fields.
// common.Script is the only string-flavoured slot today and is rejected via
// this path — use wfmut::ReloadActorScript instead.
bool SetActorField(Level& level, ActorIdx idx, const char* fieldPath, std::int64_t value);
bool SetActorField(Level& level, ActorIdx idx, const char* fieldPath, double       value);
bool SetActorField(Level& level, ActorIdx idx, const char* fieldPath, const char*  value);

std::optional<std::int64_t> GetActorFieldInt   (const Level& level, ActorIdx idx, const char* fieldPath);
std::optional<double>       GetActorFieldFloat (const Level& level, ActorIdx idx, const char* fieldPath);
std::optional<std::string>  GetActorFieldString(const Level& level, ActorIdx idx, const char* fieldPath);

// Replaces an actor's Forth script body. Compiles the new source; on failure
// keeps the previous body and surfaces the compile log via lastError(). The
// next per-frame script tick uses the new body.
bool ReloadActorScript(Level& level, ActorIdx idx, const char* forthSource);

// ── Spawn / remove ──────────────────────────────────────────────────────────
// SpawnActor wraps Level::ConstructTemplateObject(templateIdx, parentIdx,
// pos, vel=0). Returns the new actor's idx (read from GetActorIndex on the
// freshly-constructed instance) or std::nullopt if construction failed (bad
// template index, allocation failure, etc.).
std::optional<ActorIdx> SpawnActor(Level& level, int templateIdx, const Vector3& pos,
                                   ActorIdx parentIdx = 0);

// RemoveActor wraps Level::SetPendingRemove. Removal is deferred — the actor
// stays alive (and remains readable via the Get* functions) until the next
// Level::update() reaches removePendingObjects(). Returns true if the idx
// resolved to a live actor and was queued.
bool RemoveActor(Level& level, ActorIdx idx);

// ── Mailbox ─────────────────────────────────────────────────────────────────
// Direct mailbox slot access on an actor's local mailbox array. mailboxIndex
// is an integer slot id; scripting-side callers should resolve names via the
// INDEXOF_*/MB_* constants in wfsource/source/mailbox/mailbox.inc (see
// feedback_named_mailbox_constants), but this engine-internal API accepts
// raw indices because the constant table is scripting-side.
bool SetMailbox(Level& level, ActorIdx idx, int mailboxIndex, double value);
std::optional<double> GetMailbox(const Level& level, ActorIdx idx, int mailboxIndex);

} // namespace wfmut
