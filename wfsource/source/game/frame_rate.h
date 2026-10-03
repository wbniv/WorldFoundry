#pragma once

#include <math/scalar.hp>
#include <chrono>
#include <cstdint>

// Diagnostic cadence only. Simulation clamps/overrides never enter this sampler.
// Time points are arguments so tests can exercise stalls without real sleeps.
class FrameRateSampler
{
public:
    using Clock = std::chrono::steady_clock;
    using TimePoint = Clock::time_point;
    static_assert(Clock::is_steady, "FPS requires a monotonic clock");

    void Reset()
    {
        _hasBaseline = false;
        _fps = Scalar(0, 0);
    }

    void BeginFrame(TimePoint now, unsigned int lifecycleGeneration)
    {
        if (_generation != lifecycleGeneration)
            Reset();
        _generation = lifecycleGeneration;
        if (!_hasBaseline)
        {
            _last = now;
            _hasBaseline = true;
        }
    }

    void EndFrame(TimePoint now, unsigned int lifecycleGeneration)
    {
        // A lifecycle event during this frame invalidates the whole interval.
        if (_generation != lifecycleGeneration || !_hasBaseline || now <= _last)
        {
            Reset();
            return;
        }
#if defined(SCALAR_TYPE_FIXED)
        // Divide integer time directly into 16.16 FPS. Quantizing elapsed
        // seconds to Scalar first would distort short frame intervals.
        const auto nanoseconds = std::chrono::duration_cast<std::chrono::nanoseconds>(now - _last).count();
        constexpr std::uint64_t numerator = 1000000000ULL * SCALAR_ONE_LS;
        constexpr std::uint64_t maximum = 0x7fffffffULL;
        const std::uint64_t raw = nanoseconds > 0 ? numerator / nanoseconds : maximum;
        const std::uint64_t bounded = raw > maximum ? maximum : raw;
        _fps = Scalar(static_cast<int16>(bounded >> 16), static_cast<uint16>(bounded & 0xffff));
#else
        // FLOAT_TYPE is the mailbox Scalar's native representation.
        const Scalar seconds(std::chrono::duration<FLOAT_TYPE>(now - _last).count());
        _fps = Scalar(1, 0) / seconds;
#endif
        _last = now;
    }

    Scalar Read(unsigned int lifecycleGeneration) const
    {
        // Also handles suspend/resume between steps, when no suspended step ran.
        return _generation == lifecycleGeneration ? _fps : Scalar(0, 0);
    }

private:
    TimePoint _last{};
    unsigned int _generation = 0;
    bool _hasBaseline = false;
    Scalar _fps{0, 0};
};
