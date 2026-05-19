// engine/mutation/wfmut_smoke.cpp
//
// Embedded smoke runner for wfmut::. Each step grows this file with its
// own test cases against the matrix in
// docs/plans/2026-05-19-engine-mutation-api.md.
//
// Editor-stack only — gated by WF_ENABLE_EDITOR. Empty TU when the flag is
// off; also excluded from the source list in CMakeLists / build_game.sh.

#include "wfmut_smoke.hpp"

#ifdef WF_ENABLE_EDITOR

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

    // Step 3+ tests append here as they land.

    std::printf("=== wfmut smoke: %d passed, %d failed ===\n", g_passed, g_failed);
    return g_failed;
}

} // namespace wfmut

#endif // WF_ENABLE_EDITOR
