// lava_pairs.hpp: the lava lamp's blob-pair pass, behind the zForth word lava-pairs (F3).
//
// docs/plans/2026-11-26-lava-lamp.md, D6 and the build record: eight (then six) blobs in Forth cost cast1 its
// refresh rate, so the one loop that grows with the square of the blob count runs here, natively. It is
// wflevels/lava_lamp/model.py's Lamp.pair over every pair i < j in order, in 32-bit floats with the same order of
// operations (one operation per statement, so no compiler contracts a multiply and an add into one rounding), so
// the level's trace against model.py stays within a float rounding. Header-only: the engine's bridge
// (scripting_zforth.cc) and the zForth test host (tests/verify_lava_lamp_forth.py) both include it.
//
// Each blob is `stride` floats starting at its base: x, y, vx, vy, r, T (more may follow; they are not touched).
#ifndef WF_LAVA_PAIRS_HPP
#define WF_LAVA_PAIRS_HPP

#include <cmath>

namespace wf {
namespace lava {

inline void Pair(float* a, float* c, float dt)
{
    const float dx = c[0] - a[0];
    const float dy = c[1] - a[1];
    float d = static_cast<float>(std::hypot(static_cast<double>(dx), static_cast<double>(dy)));
    if (d == 0.0f) d = 1e-6f;
    const float rs = a[4] + c[4];
    const float s0 = rs * 0.85f;
    if (d < s0) {
        const float gap = s0 - d;
        const float g1 = gap * 1.5f;
        const float g2 = g1 * dt;
        const float f = g2 / d;
        const float fx = dx * f;
        const float fy = dy * f;
        a[2] = a[2] - fx;
        a[3] = a[3] - fy;
        c[2] = c[2] + fx;
        c[3] = c[3] + fy;
        const float dT0 = c[5] - a[5];
        const float dT1 = dT0 * 0.08f;
        const float dT = dT1 * dt;
        a[5] = a[5] + dT;
        c[5] = c[5] - dT;
    } else if (d < 0.3f) {
        const float q = d / 0.3f;
        const float w = 1.0f - q;
        const float w1 = w * 0.004f;
        const float w2 = w1 * dt;
        const float f = w2 / d;
        const float fx = dx * f;
        const float fy = dy * f;
        a[2] = a[2] + fx;
        a[3] = a[3] + fy;
        c[2] = c[2] - fx;
        c[3] = c[3] - fy;
    }
}

// All pairs i < j of `count` blobs laid out `stride` floats apart in `cells`.
inline void Pairs(float* cells, int stride, int count, float dt)
{
    for (int i = 0; i < count; ++i)
        for (int j = i + 1; j < count; ++j)
            Pair(cells + stride * i, cells + stride * j, dt);
}

} // namespace lava
} // namespace wf

#endif
