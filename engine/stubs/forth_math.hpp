// forth_math.hpp: the maths behind the zForth bridge's trigonometry words.
//
// Plan: docs/plans/2026-11-21-forth-trig-words.md. Header-only and free of engine types, so a
// unit test includes it alone; the zForth glue (stack effects, aborts) is in forth_math_zforth.hpp.
//
// Contract (decision D3, recommended option B):
//   * Every angle is in REVOLUTIONS (D2): 1.0 is a full turn, 0.25 a right angle.
//   * Each result is the true value computed by the hardware libm and rounded to a 32-bit float
//     (the zForth cell). No promise is made at special points: sin-rev 0.5 is about 1.2e-16, not 0.
//   * The maths runs in `Real`, the widest type the chip does natively (D8): double on phones and
//     desktops, float on a chip whose FPU is single-precision. Define WF_FORTH_MATH_FLOAT to force float.
//   * A domain error is reported, never papered over (D4): the caller prints it and aborts the script.
#ifndef WF_FORTH_MATH_HPP
#define WF_FORTH_MATH_HPP

#include <cmath>

namespace wf {
namespace forthmath {

#if defined(WF_FORTH_MATH_FLOAT) || defined(__XTENSA__) || defined(ESP_PLATFORM)
using Real = float;
#else
using Real = double;
#endif

// How far past 1 an asin/acos argument may be and still be clamped to 1: the dot product of two
// unit vectors in a 32-bit cell is often 1.0000001, and that is rounding, not a mistake.
constexpr double kDomainSlack = 1e-6;
constexpr Real kTwoPi = static_cast<Real>(6.283185307179586476925286766559);

// A result, or the reason there is none. `why` is a string literal; null means success.
struct Result {
    float value;
    const char* why;
    bool ok() const { return why == nullptr; }
};

inline Result Value(Real v) { return Result{static_cast<float>(v), nullptr}; }
inline Result Fail(const char* why) { return Result{0.0f, why}; }

// The fraction of a turn: x - floor(x), in [0, 1). Reducing first keeps the angle small, so the
// sine of 1000000.25 turns is as accurate as the sine of 0.25.
inline Real Fraction(Real turns) { return turns - std::floor(turns); }

inline Result SinRev(Real turns)
{
    if (!std::isfinite(turns)) return Fail("argument is not a finite number");
    return Value(std::sin(kTwoPi * Fraction(turns)));
}

inline Result CosRev(Real turns)
{
    if (!std::isfinite(turns)) return Fail("argument is not a finite number");
    return Value(std::cos(kTwoPi * Fraction(turns)));
}

// ( rev -- sin cos ): both from one reduction.
struct Pair {
    Result sin, cos;
};
inline Pair SinCosRev(Real turns)
{
    if (!std::isfinite(turns)) return Pair{Fail("argument is not a finite number"), Fail("argument is not a finite number")};
    const Real a = kTwoPi * Fraction(turns);
    return Pair{Value(std::sin(a)), Value(std::cos(a))};
}

// Near a quarter or three quarters of a turn the tangent is huge (about 1.6e16 at exactly 0.25) but
// finite; it is returned as it is. A script that cannot tolerate that must not call it there.
inline Result TanRev(Real turns)
{
    if (!std::isfinite(turns)) return Fail("argument is not a finite number");
    return Value(std::tan(kTwoPi * Fraction(turns)));
}

inline bool InUnitRange(Real x) { return std::fabs(x) <= static_cast<Real>(1.0 + kDomainSlack); }

inline Result AsinRev(Real x)
{
    if (!InUnitRange(x)) return Fail("argument is outside -1 to 1");     // also catches NaN
    if (x > 1) x = 1;
    if (x < -1) x = -1;
    return Value(std::asin(x) / kTwoPi);
}

inline Result AcosRev(Real x)
{
    if (!InUnitRange(x)) return Fail("argument is outside -1 to 1");
    if (x > 1) x = 1;
    if (x < -1) x = -1;
    return Value(std::acos(x) / kTwoPi);
}

inline Result AtanRev(Real x)
{
    if (!std::isfinite(x)) return Fail("argument is not a finite number");
    return Value(std::atan(x) / kTwoPi);
}

// ( y x -- rev ): the heading of the vector (x, y) in the engine's convention, 0 along +x and
// 0.25 along +y. A zero vector has no heading; it is 0, as the level scripts' own atan2 treats it.
inline Result Atan2Rev(Real y, Real x)
{
    if (!std::isfinite(y) || !std::isfinite(x)) return Fail("argument is not a finite number");
    return Value(std::atan2(y, x) / kTwoPi);
}

inline Result Sqrt(Real x)
{
    if (!(x >= 0)) return Fail("argument is negative or not a number");  // -0 passes
    if (!std::isfinite(x)) return Fail("argument is not a finite number");
    return Value(std::sqrt(x));
}

}  // namespace forthmath
}  // namespace wf

#endif
