// wf::WallClock (wfsource/source/game/wallclock.hp), the date and time of day behind the WALL_HOUR,
// WALL_MINUTE, WALL_SECOND, WALL_DAY and WALL_UTC_OFFSET mailboxes. Plans:
// docs/plans/2026-11-21-sixty-second-chain-reaction.md (time of day) and
// docs/plans/2026-11-21-tide-harbour-clock.md, E1 (the date and the offset).
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
    wf::WallClockSpec spec;
    const bool ok = wf::ParseWallClockSpec(s, spec, err);
    start = spec.startSecondOfDay;
    rate = spec.rate;
    return ok;
}
bool parseSpec(const char* s, wf::WallClockSpec& spec)
{
    std::string err;
    return wf::ParseWallClockSpec(s, spec, err);
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
        wf::WallClockSpec spec;
        const bool ok = wf::ParseWallClockSpec(bad, spec, err);
        if (ok) std::fprintf(stderr, "accepted '%s'\n", bad);
        CHECK(!ok);
        CHECK(!err.empty());
    }

    // the date and the offset (E1). Day numbers are days since 2000-01-01, checked against an independent count
    CHECK(wf::DayNumber(2000, 1, 1) == 0 && wf::DayNumber(2000, 2, 29) == 59 && wf::DayNumber(2000, 3, 1) == 60);
    CHECK(wf::DayNumber(2024, 2, 29) == 8825 && wf::DayNumber(2026, 11, 21) == 9821 && wf::DayNumber(2026, 12, 31) == 9861);
    CHECK(wf::DayNumber(2027, 1, 1) == 9862 && wf::DayNumber(2099, 12, 31) == 36524);
    CHECK(wf::DaysInMonth(2000, 2) == 29 && wf::DaysInMonth(2100, 2) == 28 && wf::DaysInMonth(2024, 2) == 29 && wf::DaysInMonth(2026, 11) == 30);
    wf::WallClockSpec sp;
    CHECK(parseSpec("2026-11-21T10:08:22", sp) && sp.hasDate && sp.day == 9821 && !sp.hasOffset && sp.startSecondOfDay == 36502.0 && sp.rate == 1.0);
    CHECK(parseSpec("2026-11-21T10:08:22+07:00@0", sp) && sp.hasOffset && sp.utcOffsetMinutes == 420 && sp.rate == 0.0 && sp.hasDate);
    CHECK(parseSpec("2026-11-21T10:08:22.5-03:30", sp) && sp.utcOffsetMinutes == -210 && sp.startSecondOfDay == 36502.5);
    CHECK(parseSpec("10:08:22Z", sp) && !sp.hasDate && sp.hasOffset && sp.utcOffsetMinutes == 0);
    CHECK(parseSpec("10:08:22+05:45@600", sp) && !sp.hasDate && sp.utcOffsetMinutes == 345 && sp.rate == 600.0);
    CHECK(parseSpec("2000-01-01T00:00:00", sp) && sp.day == 0);
    CHECK(parseSpec("2099-12-31T23:59:59", sp) && sp.day == 36524);
    CHECK(parseSpec("2024-02-29T12:00:00", sp) && sp.day == 8825);
    for (const char* bad : {"2026-11-21", "2026-11-21T", "2026-13-01T10:00:00", "2026-00-10T10:00:00", "2026-11-31T10:00:00",
                            "2023-02-29T10:00:00", "2100-02-29T10:00:00", "1999-12-31T23:59:59", "2100-01-01T00:00:00",
                            "2026-11-21 10:08:22", "26-11-21T10:08:22", "2026-11-21T10:08:22+7", "2026-11-21T10:08:22+15:00",
                            "2026-11-21T10:08:22+07:60", "2026-11-21T10:08:22*07:00", "10:08:22+07:00x", "2026/11/21T10:08:22"}) {
        std::string err;
        wf::WallClockSpec spec;
        const bool ok = wf::ParseWallClockSpec(bad, spec, err);
        if (ok) std::fprintf(stderr, "accepted '%s'\n", bad);
        CHECK(!ok);
        CHECK(!err.empty());
    }
    {
        // a frozen clock reports exactly the date, offset and time it was given
        wf::WallClock frozen;
        wf::WallClockSpec spec;
        CHECK(parseSpec("2026-11-21T10:08:22+07:00@0", spec));
        frozen.setOverride(spec);
        const auto f = frozen.sample();
        CHECK(f.day == 9821 && f.utcOffsetMinutes == 420 && f.hour == 10 && f.minute == 8 && f.second == 22.0f);
        // the same instant gives the same day however often it is read
        const auto f2 = frozen.sample();
        CHECK(f2.day == f.day && f2.hour == f.hour && f2.minute == f.minute);
        // a date-only-omitted override uses today's date and this machine's offset, matching the real clock
        wf::WallClock today;
        today.setOverride(3600.0, 0.0);
        wf::WallClock real;
        const auto td = today.sample();
        const auto rl = real.sample();
        CHECK(td.day == rl.day || td.day == rl.day + 1 || td.day == rl.day - 1);   // a midnight may fall between the two reads
        CHECK(td.utcOffsetMinutes == rl.utcOffsetMinutes);
    }
    {
        // the day rolls over with midnight, on the very sample that wraps the hour
        wf::WallClock clock;
        wf::WallClockSpec spec;
        CHECK(parseSpec("2026-12-31T23:59:30+07:00", spec));                  // real time, from 30 s before the new year
        clock.setOverride(spec);
        auto at = [&](double elapsed) { return clock.sampleAfter(elapsed); };
        auto before = at(29.0);                                               // 23:59:59
        CHECK(before.day == 9861 && before.hour == 23 && before.minute == 59 && before.second > 58.9f && before.second < 59.1f);
        auto edge = at(30.0);                                                 // exactly midnight
        CHECK(edge.day == 9862 && edge.hour == 0 && edge.minute == 0 && edge.second == 0.0f);
        auto after = at(31.5);
        CHECK(after.day == 9862 && after.hour == 0 && after.minute == 0 && after.second == 1.5f);
        CHECK(at(30.0 + 86400.0).day == 9863 && at(30.0 + 86400.0).hour == 0);            // a full day later
        CHECK(at(0.0).day == 9861 && at(0.0).utcOffsetMinutes == 420);
        // the hour and the day always move together: no sample is ever 23:xx on the new day or 00:xx on the old one
        for (double e = 0.0; e < 120.0; e += 0.37) {
            const auto t = at(e);
            CHECK((t.day == 9861 && t.hour == 23) || (t.day == 9862 && t.hour == 0));
        }
        // a fast clock: an hour a second, from 23:00 on the last day of February in a leap year
        wf::WallClock fast;
        CHECK(parseSpec("2024-02-29T23:00:00+07:00@3600", spec));
        fast.setOverride(spec);
        CHECK(fast.sampleAfter(0.0).day == 8825 && fast.sampleAfter(0.0).hour == 23);
        CHECK(fast.sampleAfter(1.0).day == 8826 && fast.sampleAfter(1.0).hour == 0);        // 2024-03-01
        CHECK(fast.sampleAfter(25.0).day == 8827 && fast.sampleAfter(25.0).hour == 0);
    }
    CHECK(wf::WallTimeFromSecondOfDay(0.0).day == 0 && wf::WallTimeFromSecondOfDay(0.0).utcOffsetMinutes == 0);   // defaults

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
    CHECK(r0.day >= wf::DayNumber(2026, 1, 1) && r0.day < wf::DayNumber(2100, 1, 1));    // a plausible date
    CHECK(r0.utcOffsetMinutes >= -14 * 60 && r0.utcOffsetMinutes <= 14 * 60);

    // WF_WALL_CLOCK from the environment, through the same path the engine uses
    setenv("WF_WALL_CLOCK", "2026-11-21T10:08:22+07:00@0", 1);
    wf::WallClock envDate;
    std::string errDate;
    CHECK(envDate.initFromEnvironment(errDate) && envDate.overridden());
    const auto ed = envDate.sample();
    CHECK(ed.day == 9821 && ed.utcOffsetMinutes == 420 && ed.hour == 10 && ed.minute == 8 && ed.second == 22.0f);
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
