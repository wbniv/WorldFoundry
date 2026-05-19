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
#include <baseobject/baseobject.hp>
#include <math/angle.hp>
#include <pigsys/pigsys.hp>

#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>

namespace wfmut {

namespace {

int g_passed = 0;
int g_failed = 0;

void report(const char* tag, bool ok, const std::string& detail = "")
{
    if (ok) {
        ++g_passed;
        std::printf("  [PASS] %s\n", tag);
    } else {
        ++g_failed;
        if (detail.empty())
            std::printf("  [FAIL] %s\n", tag);
        else
            std::printf("  [FAIL] %s — %s\n", tag, detail.c_str());
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
        if (bo && dynamic_cast<Actor*>(bo))
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
    std::printf("--- Transform (T1-T11) ---\n");

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
                std::printf("    rev=%.3f: ok_set=%d got_c=%.4f\n",
                            a, (int)ok_set,
                            got ? got->GetC().AsRevolution().AsFloat() : -999.0f);
            }
        }
        report("T9: SetActorOrientation rev 0.0/0.25/0.5/0.99", all_ok);
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
    std::printf("--- Fields (F1-F14) ---\n");

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

} // namespace

// ────────────────────────────────────────────────────────────────────────────

int RunSmokeTests(Level& level)
{
    g_passed = 0;
    g_failed = 0;

    std::printf("=== wfmut smoke ===\n");

    ActorIdx player = find_first_actor(level);
    if (player == 0) {
        std::printf("  [FAIL] [setup] no Actor found in level — cannot run smoke\n");
        return 1;
    }
    std::printf("  using player idx = %u\n", player);

    run_transform_tests(level, player);
    run_field_tests(level, player);

    // Step 4+ tests append here as they land.

    std::printf("=== wfmut smoke: %d passed, %d failed ===\n", g_passed, g_failed);
    return g_failed;
}

} // namespace wfmut

#endif // WF_DEBUG_BRIDGE || WF_ENABLE_EDITOR
