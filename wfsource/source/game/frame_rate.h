#pragma once

#include <chrono>

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
        _fps = 0.0;
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
        const double seconds = std::chrono::duration<double>(now - _last).count();
        _fps = 1.0 / seconds;
        _last = now;
    }

    double Read(unsigned int lifecycleGeneration) const
    {
        // Also handles suspend/resume between steps, when no suspended step ran.
        return _generation == lifecycleGeneration ? _fps : 0.0;
    }

private:
    TimePoint _last{};
    unsigned int _generation = 0;
    bool _hasBaseline = false;
    double _fps = 0.0;
};
