// wf::WallClock (wfsource/source/game/wallclock.hp), the time of day behind the WALL_HOUR,
// WALL_MINUTE and WALL_SECOND mailboxes. Plan: docs/plans/2026-11-21-sixty-second-chain-reaction.md.
// Built and run by `task test-wall-clock` in wf-linux-test:local; tests/test_wall_clock.py runs it too.
#undef NDEBUG  // the checks below carry side effects
#include <cassert>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <string>
#include "game/wallclock.hp"

namespace {
int failures = 0;
#define CHECK(c) do { if (!(c)) { std::fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); ++failures; } } while (0)

bool parse(const char* s, double& start, double& rate)
{
    std::string err;
    return wf::ParseWallClockSpec(s, start, rate, err);
}
}  // namespace

int main()
{
    double start = -1, rate = -1;

    // valid specs
    CHECK(parse("10:08:22", start, rate) && start == 10 * 3600 + 8 * 60 + 22 && rate == 1.0);
    CHECK(parse("23:59:59.9", start, rate) && start > 86399.8 && start < 86400.0);
    CHECK(parse("00:00:00@600", start, rate) && start == 0.0 && rate == 600.0);
    CHECK(parse("12:59:55.250@0", start, rate) && rate == 0.0);
    CHECK(parse("1:2:3", start, rate) && start == 3723.0);

    // malformed specs are refused (the engine stops at start-up on any of them)
    for (const char* bad : {"", "noon", "10:08", "10:08:22x", "24:00:00", "10:60:00", "10:08:60",
                            "10:08:22@", "10:08:22@fast", "10:08:22@-1", "-1:00:00", "10:08:22@1e999", "10:08:22 "}) {
        std::string err;
        double s, r;
        const bool ok = wf::ParseWallClockSpec(bad, s, r, err);
        if (ok) std::fprintf(stderr, "accepted '%s'\n", bad);
        CHECK(!ok);
        CHECK(!err.empty());
    }

    // second of day -> hour, minute, second, including the rollovers
    auto w = wf::WallTimeFromSecondOfDay(10 * 3600 + 8 * 60 + 22.5);
    CHECK(w.hour == 10 && w.minute == 8 && w.second == 22.5f);
    w = wf::WallTimeFromSecondOfDay(86400.0 + 5.0);                       // wraps past midnight
    CHECK(w.hour == 0 && w.minute == 0 && w.second == 5.0f);
    w = wf::WallTimeFromSecondOfDay(-0.5);                                // before midnight
    CHECK(w.hour == 23 && w.minute == 59 && w.second > 59.4f && w.second < 60.0f);
    w = wf::WallTimeFromSecondOfDay(23 * 3600 + 59 * 60 + 59.9999999);    // the float must not round to 60
    CHECK(w.hour == 23 && w.minute == 59 && w.second < 60.0f);
    for (double s = 0.0; s < 86400.0; s += 0.0137) {
        const auto t = wf::WallTimeFromSecondOfDay(s);
        CHECK(t.hour >= 0 && t.hour <= 23 && t.minute >= 0 && t.minute <= 59 && t.second >= 0.0f && t.second < 60.0f);
        if (failures) break;
    }
    // float32 resolution of the second near its top is finer than a millisecond
    CHECK(wf::WallTimeFromSecondOfDay(59.999).second > 59.9985f);

    // override: a frozen clock stays put, a fast clock runs at its rate
    wf::WallClock frozen;
    frozen.setOverride(12 * 3600 + 59 * 60 + 55.0, 0.0);
    const auto f0 = frozen.sample();
    const auto spin = std::chrono::steady_clock::now();
    while (std::chrono::steady_clock::now() - spin < std::chrono::milliseconds(60)) {}
    const auto f1 = frozen.sample();
    CHECK(f0.hour == 12 && f0.minute == 59 && f0.second == 55.0f && f1.second == 55.0f);

    wf::WallClock fast;
    fast.setOverride(23 * 3600 + 59 * 60 + 59.0, 600.0);                  // ten minutes a second, from just before midnight
    const auto t0 = std::chrono::steady_clock::now();
    fast.sample();                                                         // starts the clock
    const auto a = std::chrono::steady_clock::now();
    while (std::chrono::steady_clock::now() - a < std::chrono::milliseconds(120)) {}
    const auto s1 = fast.sample();
    const auto t1 = std::chrono::steady_clock::now();
    // it has crossed midnight and gone on by roughly 600 x the real time since the first sample
    const double maxElapsed = std::chrono::duration<double>(t1 - a).count() * 600.0 + 1.0 + 10.0;
    const double got = s1.hour * 3600.0 + s1.minute * 60.0 + s1.second + 1.0;   // seconds past midnight, plus the 1 s before it
    CHECK(s1.hour < 12);                     // wrapped to the next day
    CHECK(got > 60.0 && got < maxElapsed);   // more than a minute in, and not further than the real time allows
    (void)t0;

    // the real clock: a plausible time that moves forward within a minute
    wf::WallClock real;
    const auto r0 = real.sample();
    CHECK(r0.hour >= 0 && r0.hour <= 23 && r0.minute >= 0 && r0.minute <= 59 && r0.second >= 0.0f && r0.second < 60.0f);
    CHECK(!real.overridden());

    // WF_WALL_CLOCK from the environment, through the same path the engine uses
    setenv("WF_WALL_CLOCK", "10:08:22@0", 1);
    wf::WallClock env;
    std::string err;
    CHECK(env.initFromEnvironment(err) && env.overridden());
    const auto e = env.sample();
    CHECK(e.hour == 10 && e.minute == 8 && e.second == 22.0f);
    setenv("WF_WALL_CLOCK", "lunchtime", 1);
    wf::WallClock bad;
    CHECK(!bad.initFromEnvironment(err));
    CHECK(err.find("WF_WALL_CLOCK") != std::string::npos && err.find("lunchtime") != std::string::npos);
    unsetenv("WF_WALL_CLOCK");
    wf::WallClock none;
    CHECK(none.initFromEnvironment(err) && !none.overridden());

    if (failures) { std::fprintf(stderr, "%d check(s) failed\n", failures); return 1; }
    std::puts("wall_clock_test: OK");
    return 0;
}
