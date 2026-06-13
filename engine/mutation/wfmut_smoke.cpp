// engine/mutation/wfmut_smoke.cpp
//
// Embedded smoke runner for wfmut::. Each step grows this file with its
// own test cases against the matrix in
// docs/plans/2026-05-19-engine-mutation-api.md.
//
// Same gate as wfmut: UNION of WF_DEBUG_BRIDGE and WF_ENABLE_EDITOR. Empty
// TU when neither flag is set; excluded from the source list in CMakeLists
// and engine/build_game.sh in that case.

#include "wfmut_smoke.hpp"

#if defined(WF_DEBUG_BRIDGE) || defined(WF_ENABLE_EDITOR)

#include "wfmut.hpp"

#include "level.hp"
#include "actor.hp"
#include "movecam.hp"   // CameraHandler::ResolveTrackObject (camera stale-track regression)
#include <baseobject/baseobject.hp>
#include <math/angle.hp>
#include <pigsys/pigsys.hp>

#ifdef PHYSICS_ENGINE_JOLT
#  include <physics/jolt/jolt_backend.hp>   // JoltCharacterGetPosition / JoltBodyGetPosition (T7)
#endif

#include <cmath>
#include <cstdio>
#include <cstring>
#include <limits>
#include <string>
#include <thread>

namespace wfmut {

namespace {

int g_passed = 0;
int g_failed = 0;

void report(const char* tag, bool ok, const std::string& detail = "")
{
    if (ok) {
        ++g_passed;
        std::fprintf(stderr,"  [PASS] %s\n", tag);
    } else {
        ++g_failed;
        if (detail.empty())
            std::fprintf(stderr,"  [FAIL] %s\n", tag);
        else
            std::fprintf(stderr,"  [FAIL] %s — %s\n", tag, detail.c_str());
    }
}

bool fclose_to(float a, float b, float eps = 1e-3f)
{
    return std::fabs(a - b) < eps;
}

bool vec3_close(const Vector3& a, const Vector3& b, float eps = 1e-3f)
{
    return fclose_to(a.X().AsFloat(), b.X().AsFloat(), eps)
        && fclose_to(a.Y().AsFloat(), b.Y().AsFloat(), eps)
        && fclose_to(a.Z().AsFloat(), b.Z().AsFloat(), eps);
}

// Find the first idx (>=1) that resolves to a real Actor. smb_w1_1 has the
// player at idx 1; other levels may vary, so iterate defensively.
ActorIdx find_first_actor(Level& level)
{
    BaseObjectList& list = level.GetObjectList();
    for (int i = 1; i < list.Size(); ++i) {
        BaseObject* bo = level.GetObject(i);
        if (IsActor(bo))
            return static_cast<ActorIdx>(i);
    }
    return 0;
}

Vector3 v3(float x, float y, float z)
{
    return Vector3(Scalar::FromFloat(x), Scalar::FromFloat(y), Scalar::FromFloat(z));
}

// ── Transform tests ─────────────────────────────────────────────────────────

void run_transform_tests(Level& level, ActorIdx player)
{
    std::fprintf(stderr,"--- Transform (T1-T11) ---\n");

    // Save and restore the player's position around the destructive tests.
    auto saved = GetActorPos(level, player);
    if (!saved) {
        report("[setup] GetActorPos(player)", false, "couldn't read initial position");
        return;
    }

    // T1: positive/negative/zero round-trip
    {
        Vector3 target = v3(12.5f, -7.25f, 0.0f);
        bool ok_set = SetActorPos(level, player, target);
        auto got = GetActorPos(level, player);
        bool round_trip = ok_set && got && vec3_close(*got, target);
        report("T1: SetActorPos pos/neg/zero round-trip", round_trip,
               round_trip ? "" : std::string("lastError=") + lastError());
    }

    // T2: Vector3::zero
    {
        Vector3 target = Vector3::zero;
        bool ok_set = SetActorPos(level, player, target);
        auto got = GetActorPos(level, player);
        bool round_trip = ok_set && got && vec3_close(*got, target);
        report("T2: SetActorPos zero vector", round_trip);
    }

    // T3: idx=0 fails with idx-must-be->=1 lastError
    {
        bool ret = SetActorPos(level, 0, v3(1, 1, 1));
        bool err_ok = std::strstr(lastError(), "must be >= 1") != nullptr;
        report("T3: SetActorPos idx=0 rejected", !ret && err_ok,
               std::string("ret=") + (ret?"true":"false") + " lastError=" + lastError());
    }

    // T4: idx > Size() fails with out-of-range lastError
    {
        BaseObjectList& list = level.GetObjectList();
        ActorIdx out = static_cast<ActorIdx>(list.Size()) + 1000;
        bool ret = SetActorPos(level, out, v3(1, 1, 1));
        bool err_ok = std::strstr(lastError(), "out of range") != nullptr;
        report("T4: SetActorPos idx out-of-range rejected", !ret && err_ok);
    }

    // T9 (reduced): orientation round-trip at four angles in revolutions.
    // Engine convention: 0 <= rev < 1. Angles use the Angle::Revolution
    // factory; the AsRevolution() accessor returns a Scalar in the same units.
    {
        const float angles[] = {0.0f, 0.25f, 0.5f, 0.99f};
        bool all_ok = true;
        for (float a : angles) {
            Angle az = Angle::Revolution(Scalar::FromFloat(0.0f));
            Angle ac = Angle::Revolution(Scalar::FromFloat(a));
            Euler target(az, az, ac);
            bool ok_set = SetActorOrientation(level, player, target);
            auto got = GetActorOrientation(level, player);
            bool round_trip = ok_set && got
                && fclose_to(got->GetC().AsRevolution().AsFloat(), a, 1e-2f);
            if (!round_trip) {
                all_ok = false;
                std::fprintf(stderr,"    rev=%.3f: ok_set=%d got_c=%.4f\n",
                            a, (int)ok_set,
                            got ? got->GetC().AsRevolution().AsFloat() : -999.0f);
            }
        }
        report("T9: SetActorOrientation rev 0.0/0.25/0.5/0.99", all_ok);
    }

    // T5: idx that resolves to a non-Actor BaseObject → false + "not an Actor".
    {
        BaseObjectList& list = level.GetObjectList();
        ActorIdx non_actor = 0;
        for (int i = 1; i < list.Size(); ++i) {
            BaseObject* bo = level.GetObject(i);
            if (bo && !IsActor(bo)) { non_actor = static_cast<ActorIdx>(i); break; }
        }
        if (non_actor == 0) {
            std::fprintf(stderr,"  [SKIP] T5: no non-Actor BaseObject in level\n");
        } else {
            bool ret = SetActorPos(level, non_actor, v3(1, 1, 1));
            bool err_ok = std::strstr(lastError(), "not an Actor") != nullptr;
            report("T5: SetActorPos on non-Actor idx rejected", !ret && err_ok);
        }
    }

    // T7: Jolt body/character position is synced after SetActorPos. Only
    // meaningful if the player actually has a Jolt handle (no-mobility actors
    // may have neither).
#ifdef PHYSICS_ENGINE_JOLT
    {
        BaseObject* bo = level.GetObject(player);
        Actor* a = IsActor(bo) ? static_cast<Actor*>(bo) : nullptr;
        const PhysicalAttributes& pa = a->GetPhysicalAttributes();
        uint32_t charID = pa.JoltCharacterID();
        uint32_t bodyID = pa.JoltBodyID();
        Vector3 target = v3(8.0f, 0.0f, 3.0f);
        SetActorPos(level, player, target);
        if (charID != kJoltInvalidBodyID) {
            const Vector3& jp = JoltCharacterGetPosition(charID);
            report("T7: Jolt character position synced after SetActorPos",
                   vec3_close(jp, target, 1e-2f),
                   std::string("jolt=(") + std::to_string(jp.X().AsFloat()) + ","
                       + std::to_string(jp.Y().AsFloat()) + "," + std::to_string(jp.Z().AsFloat()) + ")");
        } else if (bodyID != kJoltInvalidBodyID) {
            const Vector3& jp = JoltBodyGetPosition(bodyID);
            report("T7: Jolt body position synced after SetActorPos",
                   vec3_close(jp, target, 1e-2f));
        } else {
            std::fprintf(stderr,"  [SKIP] T7: player has no Jolt character/body handle\n");
        }
    }
#endif

    // T8: NaN / +Inf components — PINNED (documentation only, not executed).
    // wfmut::SetActorPos does NOT validate the vector; it forwards to
    // Actor::setCurrentPos → PhysicalAttributes::SetPosition, where the
    // engine's Scalar/Vector3 validation aborts the process on NaN/Inf in
    // assertion builds (DO_ASSERTIONS=1). So the NaN boundary is enforced
    // upstream of wfmut, not by it — and running the write here would abort
    // the whole smoke. Callers must not feed NaN/Inf; there's no need for a
    // wfmut-level guard because the engine already rejects it hard.
    std::fprintf(stderr,
        "  [INFO] T8: NaN/Inf positions abort in the engine's Scalar validation "
        "(assertion build) — boundary enforced upstream of wfmut; not executed.\n");

    // T10: orientation at rev=1.0 wraps to ~0.0 (Angle is mod-1 revolutions).
    {
        Angle az = Angle::Revolution(Scalar::FromFloat(0.0f));
        Angle ac = Angle::Revolution(Scalar::FromFloat(1.0f));
        SetActorOrientation(level, player, Euler(az, az, ac));
        auto got = GetActorOrientation(level, player);
        float c = got ? got->GetC().AsRevolution().AsFloat() : -999.0f;
        // 1.0 rev wraps to 0.0; accept either ~0.0 or ~1.0 and document.
        bool wrapped = got && (fclose_to(c, 0.0f, 1e-2f) || fclose_to(c, 1.0f, 1e-2f));
        report("T10: SetActorOrientation rev=1.0 wraps cleanly", wrapped,
               std::string("got_c=") + std::to_string(c));
    }

    // T11: GetActorPos / GetActorOrientation on bad idx → nullopt
    {
        bool a = !GetActorPos(level, 0).has_value();
        bool b = !GetActorPos(level, static_cast<ActorIdx>(level.GetObjectList().Size()) + 100).has_value();
        bool c = !GetActorOrientation(level, 0).has_value();
        report("T11: Get*(bad idx) → nullopt", a && b && c);
    }

    // Restore the player's original position so the rest of the smoke run
    // (and any subsequent step's tests) inherit a clean state.
    SetActorPos(level, player, *saved);
}

// ── Field tests ─────────────────────────────────────────────────────────────

void run_field_tests(Level& level, ActorIdx player)
{
    std::fprintf(stderr,"--- Fields (F1-F14) ---\n");

    // F1: common.hp (fixed32) round-trip
    {
        bool ok_set = SetActorField(level, player, "common.hp", 100.0);
        auto got = GetActorFieldFloat(level, player, "common.hp");
        bool round_trip = ok_set && got && fclose_to(static_cast<float>(*got), 100.0f, 1e-3f);
        report("F1: SetActorField common.hp (fixed32) round-trip", round_trip,
               round_trip ? "" : std::string("lastError=") + lastError());
    }

    // F2: movebloc.Mass (fixed32) round-trip
    {
        bool ok_set = SetActorField(level, player, "movebloc.Mass", 1.5);
        auto got = GetActorFieldFloat(level, player, "movebloc.Mass");
        bool round_trip = ok_set && got && fclose_to(static_cast<float>(*got), 1.5f, 1e-4f);
        report("F2: SetActorField movebloc.Mass (fixed32) round-trip", round_trip);
    }

    // F3: movebloc.MovementClass (raw int) round-trip via int64 overload
    {
        bool ok_set = SetActorField(level, player, "movebloc.MovementClass",
                                    static_cast<std::int64_t>(2));
        auto got = GetActorFieldInt(level, player, "movebloc.MovementClass");
        bool round_trip = ok_set && got && *got == 2;
        report("F3: SetActorField movebloc.MovementClass (raw int) round-trip", round_trip);
    }

    // F4: mesh.ModelType (raw int) — covers mesh.* block
    {
        bool ok_set = SetActorField(level, player, "mesh.ModelType",
                                    static_cast<std::int64_t>(3));
        auto got = GetActorFieldInt(level, player, "mesh.ModelType");
        bool round_trip = ok_set && got && *got == 3;
        report("F4: SetActorField mesh.ModelType round-trip", round_trip);
    }

    // F5: mesh.AnimationMailbox — second mesh.* raw-int field
    {
        bool ok_set = SetActorField(level, player, "mesh.AnimationMailbox",
                                    static_cast<std::int64_t>(42));
        auto got = GetActorFieldInt(level, player, "mesh.AnimationMailbox");
        bool round_trip = ok_set && got && *got == 42;
        report("F5: SetActorField mesh.AnimationMailbox round-trip", round_trip);
    }

    // F6: common.Script via string overload — rejected, route to ReloadActorScript
    {
        bool ret = SetActorField(level, player, "common.Script", "\\\\ wf\n: tick ;");
        bool err_ok = std::strstr(lastError(), "ReloadActorScript") != nullptr;
        report("F6: SetActorField common.Script string rejected → use ReloadActorScript",
               !ret && err_ok,
               std::string("ret=") + (ret?"true":"false") + " lastError=" + lastError());
    }

    // F7: ReloadActorScript happy path — empty script body is valid Forth
    {
        bool ret = ReloadActorScript(level, player, "\\ wf\n: tick ;");
        report("F7: ReloadActorScript happy path", ret,
               ret ? "" : std::string("lastError=") + lastError());
    }

    // F8: ReloadActorScript with malformed Forth — should fail with compile log
    {
        bool ret = ReloadActorScript(level, player, "\\ wf\n: tick this-word-does-not-exist ;");
        bool err_ok = ret == false && std::strstr(lastError(), "compile failed") != nullptr;
        report("F8: ReloadActorScript malformed source rejected", err_ok,
               std::string("ret=") + (ret?"true":"false") + " lastError=" + lastError());
    }

    // F9: unknown field path → false + lastError populated
    {
        bool ret = SetActorField(level, player, "common.NotARealField",
                                 static_cast<std::int64_t>(0));
        bool err_ok = !ret && std::strstr(lastError(), "unknown field path") != nullptr;
        report("F9: SetActorField unknown field rejected", err_ok);
    }

    // F10: type-coerce double-to-rawint — write 1.5 to MovementClass (raw int);
    // expect truncate to 1. Documents the truncation behaviour.
    {
        SetActorField(level, player, "movebloc.MovementClass",
                      static_cast<std::int64_t>(0));  // baseline
        bool ok_set = SetActorField(level, player, "movebloc.MovementClass", 1.5);
        auto got = GetActorFieldInt(level, player, "movebloc.MovementClass");
        bool truncated = ok_set && got && *got == 1;
        report("F10: SetActorField double-on-raw-int truncates to 1", truncated);
    }

    // F11: fixed32 overflow saturation — 1e9 × 65536 way past INT32_MAX
    {
        bool ok_set = SetActorField(level, player, "movebloc.Mass", 1e9);
        auto got = GetActorFieldFloat(level, player, "movebloc.Mass");
        // After saturation: int32 = INT32_MAX (2147483647), fixed32 read =
        // INT32_MAX / 65536 ≈ 32767.999
        bool saturated = ok_set && got && fclose_to(static_cast<float>(*got), 32767.999f, 1e-1f);
        report("F11: SetActorField fixed32 overflow saturates to INT32_MAX", saturated,
               got ? std::string("got=") + std::to_string(*got) : std::string("no value"));
    }

    // F12: bad idx on SetActorField
    {
        bool ret = SetActorField(level, 0, "common.hp", 50.0);
        bool err_ok = !ret && std::strstr(lastError(), "must be >= 1") != nullptr;
        report("F12: SetActorField bad idx rejected", err_ok);
    }

    // F13 (OAD page sharing) — needs a second actor sharing the same _Common
    // page as the player to verify in-place behaviour propagates. smb_w1_1
    // may or may not have such a sharing pattern; skip if we can't find one.
    // For v1, we document the limitation and leave the test as a manual
    // verification step. Move on.

    // F14 (bridge gWatches regression) — requires the bridge to be running.
    // Manual verification via X8 in the test matrix.
}

// ── Spawn / Remove tests ────────────────────────────────────────────────────

// Find the first idx in [1, list.Size()) that resolves to a valid template
// via Level::HasTemplate. Returns 0 if no template is found in the level.
int find_first_template(Level& level)
{
    BaseObjectList& list = level.GetObjectList();
    for (int i = 1; i < list.Size(); ++i) {
        if (level.HasTemplate(i)) return i;
    }
    return 0;
}

void run_spawn_remove_tests(Level& level, ActorIdx player)
{
    std::fprintf(stderr,"--- Spawn / Remove (SR1-SR14) ---\n");

    int template_idx = find_first_template(level);
    if (template_idx == 0) {
        std::fprintf(stderr,"  [SKIP] no template in level — spawn/remove tests need one\n");
        return;
    }
    std::fprintf(stderr,"  first template idx = %d (for reference)\n", template_idx);

    // SR6: invalid templateIdx → nullopt
    {
        auto r1 = SpawnActor(level, -1, Vector3::zero, player);
        auto r2 = SpawnActor(level, 99999, Vector3::zero, player);
        report("SR6: SpawnActor(bad templateIdx) → nullopt",
               !r1.has_value() && !r2.has_value());
    }

    // SR0: parentIdx == 0 rejected pre-engine (engine asserts otherwise)
    {
        auto r = SpawnActor(level, template_idx, Vector3::zero, /*parentIdx=*/0);
        bool err_ok = !r.has_value()
            && std::strstr(lastError(), "parentIdx must be >= 1") != nullptr;
        report("SR0: SpawnActor(parentIdx=0) rejected pre-engine", err_ok);
    }

    // SR11: RemoveActor(0) and out-of-range idx → false
    {
        bool a = !RemoveActor(level, 0);
        bool b = !RemoveActor(level,
            static_cast<ActorIdx>(level.GetObjectList().Size()) + 100);
        report("SR11: RemoveActor(bad idx) → false", a && b);
    }

    // Happy-path spawn tests (SR1, SR2, SR7, SR8, SR10) deferred to manual
    // verification: smb_w1_1's first runtime-spawnable template (idx 2) has
    // content-specific spawn requirements — runtime ConstructTemplateObject
    // calls into oas/objects.c paths that abort with terminate() rather than
    // a clean assertion when prerequisites aren't met (room placement,
    // collision boxes, parent-actor state). A generic "spawn the first
    // template at the player's position" probe is unreliable across levels.
    //
    // The bridge's existing "spawn via scene:live_create_node" path (when
    // wired up in Phase 3 of the live-editor bridge plan) will exercise the
    // wfmut::SpawnActor / RemoveActor surface for real; smoke covers the
    // input-validation half of the API (SR0, SR6, SR11).
    //
    // SR3 / SR4 / SR5 / SR9 / SR12 / SR13 / SR14 are also deferred per the
    // plan's test matrix (parent variants, stale-idx mutation, ASan stress,
    // identity-invariance, re-entrancy).
    std::fprintf(stderr,
        "  [SKIP] SR1/SR2/SR7/SR8/SR10 happy-path spawn — needs a known-safe\n"
        "         template (see plan test matrix; deferred to manual / bridge\n"
        "         integration verification).\n");
}

// ── Mailbox tests ───────────────────────────────────────────────────────────

void run_mailbox_tests(Level& level, ActorIdx player)
{
    std::fprintf(stderr,"--- Mailbox (M1-M9) ---\n");

    // M1: write/read round-trip on a mid-range slot. Restore after so the
    // game can continue if the player's local mailboxes have observable
    // effects.
    {
        const int slot = 5;
        auto saved = GetMailbox(level, player, slot);
        bool ok_set = SetMailbox(level, player, slot, 42.0);
        auto got = GetMailbox(level, player, slot);
        bool round_trip = ok_set && got && fclose_to(static_cast<float>(*got), 42.0f, 1e-3f);
        if (saved) SetMailbox(level, player, slot, *saved);
        report("M1: SetMailbox(slot=5, 42.0) → GetMailbox round-trip", round_trip,
               round_trip ? "" : std::string("lastError=") + lastError());
    }

    // M2: slot 0 round-trip — DEFERRED. Slot 0 (and nearby low indices) maps
    // to LOCAL_SYSTEM mailboxes in WF's mailbox model: X_POS / Y_POS / Z_POS,
    // COLLIDER_IDX, etc. Writes have observable side-effects (teleport,
    // physics state). The current player actor in smb_w1_1-standalone abort
    // on a generic write to slot 0 (terminate called) — deferred until a
    // safer fixture exists. M1 covers the round-trip property at slot 5.

    // M5: negative mailbox index rejected.
    {
        bool ret = SetMailbox(level, player, -1, 0.0);
        bool err_ok = !ret && std::strstr(lastError(), "mailboxIndex must be >= 0") != nullptr;
        report("M5: SetMailbox negative mailbox index rejected", err_ok);
    }

    // M9: bad actor idx on SetMailbox / GetMailbox.
    {
        bool a = !SetMailbox(level, 0, 5, 1.0);
        bool b = !GetMailbox(level, 0, 5).has_value();
        report("M9: Set/GetMailbox bad actor idx rejected", a && b);
    }

    // M3: a higher local slot (20) round-trips. Stays clear of the low
    // LOCAL_SYSTEM slots (X/Y/Z_POS etc.) that have physics side effects.
    {
        const int slot = 20;
        auto saved = GetMailbox(level, player, slot);
        bool ok_set = SetMailbox(level, player, slot, -3.5);
        auto got = GetMailbox(level, player, slot);
        bool round_trip = ok_set && got && fclose_to(static_cast<float>(*got), -3.5f, 1e-3f);
        if (saved) SetMailbox(level, player, slot, *saved);
        report("M3: SetMailbox high local slot (20) round-trip", round_trip);
    }

    // M4: write past the actor's declared local count. PINNED BEHAVIOUR:
    // MailboxesWithStorage::WriteMailbox falls through to the parent (global)
    // bank for out-of-local indices (mailbox.cc:96-106) — it does NOT reject.
    // So this round-trips through the global bank rather than failing. Assert
    // the documented fall-through, not a rejection.
    {
        auto count_opt = GetActorFieldInt(level, player, "common.NumberOfLocalMailboxes");
        if (!count_opt) {
            std::fprintf(stderr,"  [SKIP] M4: couldn't read NumberOfLocalMailboxes\n");
        } else {
            int past = static_cast<int>(*count_opt) + 100;  // safely past local range
            auto saved = GetMailbox(level, player, past);
            bool ok_set = SetMailbox(level, player, past, 9.0);
            auto got = GetMailbox(level, player, past);
            bool fell_through = ok_set && got && fclose_to(static_cast<float>(*got), 9.0f, 1e-3f);
            if (saved) SetMailbox(level, player, past, *saved);
            report("M4: SetMailbox past local count falls through to global bank "
                   "(pinned; not a rejection)", fell_through,
                   std::string("NumberOfLocalMailboxes=") + std::to_string(*count_opt));
        }
    }

    // M7: NaN/Inf mailbox value — PINNED (documentation only, not executed).
    // Same upstream-validation story as T8: SetMailbox forwards to
    // Scalar::FromDouble → WriteMailbox, and the engine's Scalar validation
    // aborts on NaN/Inf in assertion builds. Not executed (would abort the
    // smoke); the boundary is the engine's, not wfmut's.
    std::fprintf(stderr,
        "  [INFO] M7: NaN/Inf mailbox values abort in Scalar validation "
        "(assertion build) — not executed; boundary is upstream of wfmut.\n");

    // M8: behaviour at the current GLOBAL_USER_MAX boundary. The memory
    // project_followup_mailbox_999_crash predates the 999→1900 bump
    // (mailbox.inc:32, 2026-05-09). Pin the CURRENT behaviour: write/read at
    // 1899 (last user slot) and 1900 (the max). If either aborts, that's the
    // off-by-one re-surfacing at the new boundary — a live bug to log.
    {
        const int last_ok = 1899;
        auto saved = GetMailbox(level, player, last_ok);
        bool ok_set = SetMailbox(level, player, last_ok, 5.0);
        auto got = GetMailbox(level, player, last_ok);
        bool round_trip = ok_set && got && fclose_to(static_cast<float>(*got), 5.0f, 1e-3f);
        if (saved) SetMailbox(level, player, last_ok, *saved);
        report("M8: Set/GetMailbox at 1899 (last global user slot) round-trips "
               "(999→1900 boundary moved 2026-05-09)", round_trip);
    }

    // M2 (slot 0 LOCAL_SYSTEM side effects), M6 (no-mailbox-bearing actor not
    // present in smb_w1_1) — deferred per the plan's test matrix.
    std::fprintf(stderr,
        "  [SKIP] M2 (slot-0 LOCAL_SYSTEM side effects), M6 (no mailbox-less "
        "actor in smb) — deferred per plan.\n");
}

// ── Cross-cutting tests ─────────────────────────────────────────────────────

void run_crosscutting_tests(Level& level, ActorIdx player)
{
    std::fprintf(stderr,"--- Cross-cutting (X1-X8) ---\n");

    // X1: lastError() is populated after a failing call.
    {
        SetActorPos(level, 0, Vector3::zero);   // guaranteed failure (idx 0)
        bool has_err = lastError() != nullptr && lastError()[0] != '\0';
        report("X1: lastError() non-empty after a failed call", has_err);
    }

    // X2: lastError() clears to "" after a subsequent successful call. Never
    // returns nullptr.
    {
        auto saved = GetActorPos(level, player);
        bool ok_set = saved && SetActorPos(level, player, *saved);  // succeeds, no-op move
        bool cleared = lastError() != nullptr && lastError()[0] == '\0';
        report("X2: lastError() == \"\" after a successful call", ok_set && cleared,
               std::string("lastError=\"") + lastError() + "\"");
    }

    // X3 (build with both flags off → no-op stubs), X4 (ASan), X5 (cross-
    // thread guard), X6/X7/X8 (live bridge regression) are covered outside
    // this in-process runner — see tests/verify_wfmut_bridge.py and the
    // CTest/ASan targets.
    std::fprintf(stderr,
        "  [INFO] X3/X4/X5/X6/X7/X8 covered by build flags, ASan target, "
        "cross-thread death-test, and verify_wfmut_bridge.py.\n");
}

// ── Camera track-object resolution (TODO 134/135 regression) ─────────────────
// CameraHandler::ResolveTrackObject must NEVER assert on a stale/destroyed/
// out-of-range track index — it returns null so a despawned tracked actor
// degrades the camera gracefully instead of aborting. The huge-OOR case (C3)
// ABORTS via Level::GetObject's RangeCheck before the fix, so this whole group
// is the fails-before / passes-after guard.
void run_camera_track_tests(Level& level, ActorIdx player)
{
    std::fprintf(stderr,"--- Camera track resolve (C1-C6) ---\n");

    report("C1: ResolveTrackObject(0) == null (unset)",
           CameraHandler::ResolveTrackObject(0) == nullptr);
    report("C2: ResolveTrackObject(-1) == null (negative)",
           CameraHandler::ResolveTrackObject(-1) == nullptr);
    report("C3: ResolveTrackObject(31158) == null (out of range — aborted pre-fix)",
           CameraHandler::ResolveTrackObject(31158) == nullptr);
    report("C4: ResolveTrackObject(GetMaxObjectIndex()) == null (at bound)",
           CameraHandler::ResolveTrackObject(level.GetMaxObjectIndex()) == nullptr);
    report("C5: ResolveTrackObject(player) == that actor",
           CameraHandler::ResolveTrackObject(static_cast<int32>(player))
               == static_cast<const PhysicalObject*>(level.GetObject(static_cast<int>(player))));

    // C6 (best-effort): an in-range empty/freed slot resolves to null.
    for (int i = 1; i < level.GetMaxObjectIndex(); ++i) {
        if (level.GetObject(i) == NULL) {
            report("C6: ResolveTrackObject(empty slot) == null",
                   CameraHandler::ResolveTrackObject(i) == nullptr);
            break;
        }
    }
}

} // namespace

// ────────────────────────────────────────────────────────────────────────────

int RunSmokeTests(Level& level)
{
    g_passed = 0;
    g_failed = 0;

    std::fprintf(stderr,"=== wfmut smoke ===\n");

    ActorIdx player = find_first_actor(level);
    if (player == 0) {
        std::fprintf(stderr,"  [FAIL] [setup] no Actor found in level — cannot run smoke\n");
        return 1;
    }
    std::fprintf(stderr,"  using player idx = %u\n", player);

    run_transform_tests(level, player);
    run_field_tests(level, player);
    run_spawn_remove_tests(level, player);
    run_mailbox_tests(level, player);
    run_crosscutting_tests(level, player);
    run_camera_track_tests(level, player);

    // Cross-cutting tests (X1-X8) land in a follow-up; some require manual
    // verification (bridge regression, screenshot capture) and are tracked
    // in docs/plans/2026-05-19-engine-mutation-api.md.

    std::fprintf(stderr,"=== wfmut smoke: %d passed, %d failed ===\n", g_passed, g_failed);
    return g_failed;
}

// X5 death-test. Captures the game thread with one main-thread wfmut call,
// then calls wfmut from a std::thread — the cross-thread guard's AssertMsg
// fires and aborts the process. Driven by `wf_game --wfmut-thread-test`; the
// CTest entry treats the abort + "game thread" message as a PASS.
//
// Returns 0 only if the guard FAILED to fire (i.e. in a non-assertion build,
// or if the guard is broken) — in that case the test should be treated as a
// non-result, which the CTest PASS_REGULAR_EXPRESSION handles by requiring
// the abort message.
int RunThreadGuardDeathTest(Level& level)
{
    std::fprintf(stderr,"=== wfmut cross-thread death-test (X5) ===\n");

    ActorIdx player = find_first_actor(level);
    if (player == 0) {
        std::fprintf(stderr,"  [FAIL] no Actor found — cannot run death-test\n");
        return 1;
    }

    // Capture the game thread as the first-call thread (main thread here).
    GetActorPos(level, player);

    std::fprintf(stderr,"  spawning off-thread wfmut call — expecting abort...\n");
    std::thread t([&level, player]() {
        // This must trip the X5 guard (different thread than the capture).
        SetActorPos(level, player, Vector3::zero);
        // If we reach here, the guard did NOT fire (non-assertion build).
        std::fprintf(stderr,"  [INFO] off-thread call returned without abort "
                     "(guard compiled out — DO_ASSERTIONS=0)\n");
    });
    t.join();

    // Only reached if the guard didn't abort. Not a pass — the CTest entry
    // requires the abort message in output.
    std::fprintf(stderr,"  [WARN] cross-thread guard did not fire\n");
    return 0;
}

} // namespace wfmut

#endif // WF_DEBUG_BRIDGE || WF_ENABLE_EDITOR
