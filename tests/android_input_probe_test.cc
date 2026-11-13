// android_input_probe: the per-key latency bookkeeping behind the Android input
// probe (wfsource/source/hal/android/input_probe.h; docs/plans/2026-11-13-android-
// input-latency.md). Synthetic frames and key events in, timestamps out: event to
// receive, the first swap (the probe's flash) and the second (the first frame whose
// game tick read the key), the flash's held set, and the per-pump backlog counts.
#include <hal/android/input_probe.h>
#include <cstdio>

static int failures = 0;
#define CHECK(cond) do{ if(!(cond)){ std::printf("FAIL %s:%d: %s\n",__FILE__,__LINE__,#cond); ++failures; } }while(0)

static const int64_t MS = 1000000;

int main()
{
    using inputprobe::Tracker;
    using inputprobe::Edge;
    using inputprobe::Stats;

    // One tap: DOWN generated at 100 ms, received in the pump of frame 1 at 130 ms.
    {
        Tracker t;
        Edge done[8];
        t.PumpBegin(116 * MS);                      // frame 0's boundary, before the key
        t.PumpEnd();
        CHECK(t.Swap(117 * MS, done, 8) == 0);
        t.PumpBegin(130 * MS);
        t.Ident();
        CHECK(t.Key(22, 0, 0, 100 * MS, 130 * MS) == 30 * MS);
        t.PumpEnd();
        CHECK(t.Held());
        CHECK(t.Swap(133 * MS, done, 8) == 0);      // swap 1: the flash frame
        t.PumpBegin(147 * MS);
        t.PumpEnd();
        CHECK(t.Swap(150 * MS, done, 8) == 1);      // swap 2: the tick that read it
        CHECK(done[0].code == 22 && done[0].action == 0);
        CHECK(done[0].eventNs == 100 * MS && done[0].receiveNs == 130 * MS);
        CHECK(done[0].swap1Ns == 133 * MS && done[0].swap2Ns == 150 * MS);
        CHECK(done[0].frame == 2);
        CHECK(t.Pending() == 0);
        // The UP clears the flash.
        t.PumpBegin(163 * MS);
        t.Key(22, 1, 0, 160 * MS, 163 * MS);
        t.PumpEnd();
        CHECK(!t.Held());
    }

    // Auto-repeat DOWNs are counted as backlog but not timed and do not re-hold.
    {
        Tracker t;
        Edge done[8];
        t.PumpBegin(0);
        t.Key(19, 0, 0, 0, 1 * MS);
        t.Key(19, 0, 1, 0, 2 * MS);
        t.Key(19, 0, 2, 0, 3 * MS);
        t.PumpEnd();
        CHECK(t.Pending() == 1);
        t.Key(19, 1, 0, 0, 4 * MS);
        CHECK(!t.Held());
        t.Swap(5 * MS, done, 8);
        CHECK(t.Swap(6 * MS, done, 8) == 2);        // the DOWN and the UP, no repeats
    }

    // Two keys held: the flash stays until both are released.
    {
        Tracker t;
        t.Key(21, 0, 0, 0, 0);
        t.Key(23, 0, 0, 0, 0);
        t.Key(21, 1, 0, 0, 0);
        CHECK(t.Held());
        t.Key(23, 1, 0, 0, 0);
        CHECK(!t.Held());
        t.Key(23, 1, 0, 0, 0);                      // a stray UP never goes negative
        CHECK(!t.Held());
        t.Key(20, 0, 0, 0, 0);
        t.ReleaseAll();
        CHECK(!t.Held());
    }

    // Stats: a backlog shows as many events in one pump; the longest frame gap is kept.
    {
        Tracker t;
        Stats s;
        t.PumpBegin(0);
        t.Ident();
        t.PumpEnd();
        CHECK(!t.TakeStats(500 * MS, &s));
        t.PumpBegin(16 * MS);
        t.PumpEnd();
        t.PumpBegin(316 * MS);                      // a 300 ms frame
        t.Ident(); t.Ident();
        for (int i = 0; i < 12; ++i) t.Key(22, i % 2, 0, 0, 316 * MS);
        t.PumpEnd();
        t.PumpBegin(332 * MS);
        t.PumpEnd();
        CHECK(t.TakeStats(1000 * MS, &s));
        CHECK(s.frames == 4);
        CHECK(s.maxFrameNs == 300 * MS);
        CHECK(s.events == 12 && s.maxEventsPerPump == 12);
        CHECK(s.idents == 3 && s.maxIdentsPerPump == 2);
        CHECK(!t.TakeStats(1500 * MS, &s));         // the window restarted at 1000 ms
    }

    // The pending ring is bounded: overflow is counted, never written past the end.
    {
        Tracker t;
        for (int i = 0; i < inputprobe::kMaxPending + 5; ++i) t.Key(22, i % 2, 0, 0, 0);
        CHECK(t.Pending() == inputprobe::kMaxPending);
        CHECK(t.Dropped() == 5);
        Edge done[4];
        t.Swap(1, done, 4);
        CHECK(t.Swap(2, done, 4) == 4);
        CHECK(t.Pending() == 0);
        CHECK(t.Dropped() == 5 + inputprobe::kMaxPending - 4);
    }

    if (failures) { std::printf("%d failure(s)\n", failures); return 1; }
    std::printf("android_input_probe: all checks passed\n");
    return 0;
}
