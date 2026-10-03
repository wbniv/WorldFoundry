#include <game/frame_rate.h>
#include <hal/lifecycle.h>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <initializer_list>

#if defined(__ANDROID__)
// Standalone test has no NativeActivity. Link the real Android lifecycle HAL
// with a present window and no event pump, rather than installing a game APK.
extern "C" int WFAndroidHasWindow(void) { return 1; }
extern "C" void WFAndroidPumpEvents(void) {}
extern "C" int WFAndroidCloseRequested(void) { return 0; }
extern "C" void WFAndroidRequestClose(void) {}
#endif

static void Check(bool ok, const char* description)
{
    if (!ok)
    {
        std::fprintf(stderr, "FAIL: %s\n", description);
        std::exit(1);
    }
}

static FrameRateSampler::TimePoint At(double seconds)
{
    return FrameRateSampler::TimePoint{} +
        std::chrono::duration_cast<FrameRateSampler::Clock::duration>(
            std::chrono::duration<double>(seconds));
}

void _sys_assert(int, const char* expression, const char* file, int line)
{
    std::fprintf(stderr, "assert %s at %s:%d\n", expression, file, line);
    std::abort();
}

static bool Near(Scalar actual, double expected)
{
    return std::abs(actual.AsFloat() - expected) < 0.001;
}

int main()
{
    FrameRateSampler sampler;
    const auto generation = HALLifecycleGeneration();
    Check(sampler.Read(generation) == Scalar(0, 0), "startup is zero");
    for (double rate : {30.0, 60.0, 120.0})
    {
        sampler.Reset();
        for (int frame = 0; frame < 10; ++frame)
        {
            sampler.BeginFrame(At(10.0 + frame / rate), generation);
            sampler.EndFrame(At(10.0 + (frame + 1) / rate), generation);
            Check(Near(sampler.Read(generation), rate), "steady cadence");
        }
    }

    // Host work between steps is included, rather than timing render work only.
    sampler.Reset();
    sampler.BeginFrame(At(20), generation);
    sampler.EndFrame(At(20.01), generation);
    sampler.BeginFrame(At(20.49), generation);
    Check(Near(sampler.Read(generation), 100), "begin does not publish");
    sampler.EndFrame(At(20.51), generation);
    Check(Near(sampler.Read(generation), 2), "500 ms interval has no 10 FPS floor");
    sampler.BeginFrame(At(22), generation);
    sampler.EndFrame(At(22.51), generation);
    Check(Near(sampler.Read(generation), 0.5), "two-second stall retains fractional FPS");
    sampler.BeginFrame(At(22.52), generation);
    sampler.EndFrame(At(22.53), generation);
    Check(Near(sampler.Read(generation), 50), "next interval is unsmoothed");
    const Scalar cached = sampler.Read(generation);
    Check(sampler.Read(generation) == cached, "reads do not advance the timer");

    // Suspend/resume entirely between steps, as with the browser main loop.
    HALNotifySuspend();
    Check(HALIsSuspended(), "HAL suspended flag");
    Check(sampler.Read(HALLifecycleGeneration()) == Scalar(0, 0), "suspend invalidates cached FPS");
    HALNotifyResume();
    const auto resumed = HALLifecycleGeneration();
    Check(resumed != generation && !HALIsSuspended(), "HAL resume advances generation");
    Check(sampler.Read(resumed) == Scalar(0, 0), "resume invalidates old interval");
    sampler.BeginFrame(At(1000), resumed);
    sampler.EndFrame(At(1000.02), resumed);
    Check(Near(sampler.Read(resumed), 50), "resume excludes background gap");

    sampler.BeginFrame(At(1001), resumed);
    HALNotifySuspend();
    HALNotifyResume();
    const auto changed = HALLifecycleGeneration();
    sampler.EndFrame(At(2000), changed);
    Check(sampler.Read(changed) == Scalar(0, 0), "mid-frame transition discards sample");
    sampler.BeginFrame(At(2001), changed);
    sampler.EndFrame(At(2001.01), changed);
    Check(Near(sampler.Read(changed), 100), "recovery after mid-frame transition");

    sampler.Reset();
    Check(sampler.Read(changed) == Scalar(0, 0), "level reset clears published value");
    sampler.BeginFrame(At(3000), changed);
    sampler.EndFrame(At(3000), changed);
    Check(sampler.Read(changed) == Scalar(0, 0), "duplicate timestamp does not divide by zero");
    sampler.BeginFrame(At(3001), changed);
    sampler.EndFrame(At(3000), changed);
    Check(sampler.Read(changed) == Scalar(0, 0), "backwards timestamp resets sample");
    sampler.EndFrame(At(3002), changed);
    Check(sampler.Read(changed) == Scalar(0, 0), "end without baseline stays zero");
    sampler.BeginFrame(At(4000), changed);
    sampler.EndFrame(At(4000) + FrameRateSampler::Clock::duration{1}, changed);
    Check(std::isfinite(sampler.Read(changed).AsFloat()) && sampler.Read(changed) > Scalar(1200, 0),
          "high cadence is finite and has no display FPS cap");
#if defined(SCALAR_TYPE_FIXED)
    Check(sampler.Read(changed).AsLong() == 0x7fffffff,
          "one-tick interval saturates at the fixed mailbox maximum");
    sampler.Reset();
    sampler.BeginFrame(At(5000), changed);
    sampler.EndFrame(At(5000) + std::chrono::microseconds(100), changed);
    Check(Near(sampler.Read(changed), 10000),
          "short intervals are not quantized to fixed-point seconds");
    sampler.Reset();
    sampler.BeginFrame(At(0), changed);
    sampler.EndFrame(At(131072), changed);
    Check(sampler.Read(changed) == Scalar(0, 0),
          "rates below fixed mailbox resolution become zero without overflow");
#endif
    sampler.Reset();
    const auto start = FrameRateSampler::Clock::now();
    sampler.BeginFrame(start, changed);
    auto end = start;
    for (int i = 0; i < 1000 && end == start; ++i)
        end = FrameRateSampler::Clock::now();
    Check(end > start, "live monotonic clock advances");
    sampler.EndFrame(end, changed);
    Check(std::isfinite(sampler.Read(changed).AsFloat()) && sampler.Read(changed) > Scalar(0, 0),
          "live monotonic clock produces a valid sample");
    std::puts("PASS: raw cadence, stalls, host gaps, invalid samples, lifecycle resets");
}
