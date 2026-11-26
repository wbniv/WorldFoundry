// forth_math.hpp: the maths behind the zForth bridge's math words.
//
// Plans: docs/plans/2026-11-21-forth-trig-words.md (the trigonometry and sqrt) and
// docs/plans/2026-11-26-forth-math-words.md (rounding, integer bits, exponentials, logarithms). Header-only and free of engine types, so a
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

#include <cfloat>
#include <cmath>
#include <cstdint>
#include <cstring>

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

// ---------------------------------------------------------------------------------------------
// Part 2: rounding, integer bits, exponentials and logarithms.
// Plan: docs/plans/2026-11-26-forth-math-words.md.
// Same contract as above: plain libm in Real, rounded into the float cell. A non-finite argument and
// a non-finite result are refused (a result that overflows the float cell counts as non-finite), and
// so is each domain error in the plan's table. Group A and B results are exact.

constexpr const char* kNotFinite = "argument is not a finite number";
constexpr const char* kResultNotFinite = "result is not a finite number";

inline bool Finite(Real x) { return std::isfinite(x); }

// The result as the cell will hold it, refused if it does not fit (exp 89 is finite in double and
// infinite in float).
inline Result Checked(Real v)
{
    const float f = static_cast<float>(v);
    if (!std::isfinite(f)) return Fail(kResultNotFinite);
    return Result{f, nullptr};
}

// --- A: exact -------------------------------------------------------------------------------
inline Result Floor(Real x) { return Finite(x) ? Checked(std::floor(x)) : Fail(kNotFinite); }
inline Result Ceil(Real x) { return Finite(x) ? Checked(std::ceil(x)) : Fail(kNotFinite); }
inline Result Trunc(Real x) { return Finite(x) ? Checked(std::trunc(x)) : Fail(kNotFinite); }
// Ties away from zero: 2.5 -> 3, -2.5 -> -3 (C round).
inline Result Round(Real x) { return Finite(x) ? Checked(std::round(x)) : Fail(kNotFinite); }
// Ties to even: 2.5 -> 2, 3.5 -> 4 (C23 roundeven, WebAssembly nearest). nearbyint rounds in the
// current rounding mode, which the engine never changes from the default, round-to-nearest-even.
inline Result RoundEven(Real x) { return Finite(x) ? Checked(std::nearbyint(x)) : Fail(kNotFinite); }

// a*b + c for floats with ONE rounding, computed without fmaf and without touching the rounding mode
// (decision D8 of docs/plans/2026-11-26-forth-math-words.md). The product of two floats is exact in
// double (24 + 24 = 48 significant bits, exponents within double's range, and every product a multiple
// of 2^-298, far above double's smallest normal), so only the sum needs care. Two-sum gives the double
// nearest the exact sum and the exact remainder; rounding that double to odd (when the remainder is
// not zero, force the last bit to 1 by stepping one ulp toward the remainder) keeps the information a
// second rounding needs, and a double has 53 >= 24 + 2 bits, so the one conversion to float is then
// correctly rounded, halfway cases, subnormal results and overflow to infinity included. It needs only
// the default round-to-nearest, which the engine never changes. A non-finite input or sum is returned
// as it is, for the caller to refuse.
inline float ExactFmaf(float a, float b, float c)
{
    const double p = static_cast<double>(a) * static_cast<double>(b);   // exact
    const double q = static_cast<double>(c);
    const double s = p + q;
    if (!std::isfinite(s)) return static_cast<float>(s);
    const double bv = s - p;                                            // two-sum (Knuth): s + t == p + q
    const double t = (p - (s - bv)) + (q - bv);
    if (t == 0.0) return static_cast<float>(s);
    uint64_t bits;
    std::memcpy(&bits, &s, sizeof bits);
    if ((bits & 1u) == 0) bits = ((t > 0.0) == (s > 0.0)) ? bits + 1 : bits - 1;   // toward t: odd
    double odd;
    std::memcpy(&odd, &bits, sizeof odd);
    return static_cast<float>(odd);
}

// Hardware FMA or not (that plan's D8). Where the compiler reports a fused multiply-add instruction
// for the target (__ARM_FEATURE_FMA: 32-bit ARM with VFPv4 or ARMv8, and all AArch64; __FMA__: x86
// with FMA3; __FP_FAST_FMAF: the compiler's own statement that fmaf is an instruction) std::fma is
// that instruction, correctly rounded by IEEE 754, and is kept. Everywhere else std::fma(float) is a
// library routine, and those differ: bionic's on armeabi-v7a returns 0x3f801001 for (1 + 2^-12)^2 -
// 1e-24 where the answer is 0x3f801000 (both Chromecasts, 2026-11-26), so those builds (armeabi-v7a,
// x86-64 at our baseline SSE2, WebAssembly) use ExactFmaf, which gives the same bits as a
// correct fmaf. WF_FORTH_MATH_SOFT_FMA forces ExactFmaf, for the tests.
#if !defined(WF_FORTH_MATH_SOFT_FMA) && \
    (defined(__ARM_FEATURE_FMA) || defined(__FMA__) || defined(__FP_FAST_FMAF))
#define WF_FORTH_MATH_HARDWARE_FMA 1
#else
#define WF_FORTH_MATH_HARDWARE_FMA 0
#if defined(FLT_EVAL_METHOD) && FLT_EVAL_METHOD == 2
#error "ExactFmaf needs double arithmetic in double (FLT_EVAL_METHOD 0 or 1), not in x87 long double"
#endif
#endif

// a*b + c with ONE rounding, straight into the float cell. It is computed as a float fma, not in
// Real: a double fma rounded to float would round twice, and can then differ from the exact answer
// (1.000244140625 * 1.000244140625 + 1e-24 is one such case).
inline Result Fma(Real a, Real b, Real c)
{
    if (!Finite(a) || !Finite(b) || !Finite(c)) return Fail(kNotFinite);
#if WF_FORTH_MATH_HARDWARE_FMA
    const float r = std::fma(static_cast<float>(a), static_cast<float>(b), static_cast<float>(c));
#else
    const float r = ExactFmaf(static_cast<float>(a), static_cast<float>(b), static_cast<float>(c));
#endif
    if (!std::isfinite(r)) return Fail(kResultNotFinite);
    return Result{r, nullptr};
}

// |x| with the sign of y (-0 counts as negative, as in IEEE 754).
inline Result CopySign(Real x, Real y)
{
    if (!Finite(x) || !Finite(y)) return Fail(kNotFinite);
    return Checked(std::copysign(x, y));
}

// x - n*y with n = trunc(x / y): the result takes x's sign (-7 3 fmod is -1). Exact.
inline Result Fmod(Real x, Real y)
{
    if (!Finite(x) || !Finite(y)) return Fail(kNotFinite);
    if (y == 0) return Fail("divisor is zero");
    return Checked(std::fmod(x, y));
}

// --- B: integer bits ------------------------------------------------------------------------
// The argument must be a whole number from 0 to 2^24, the range a float cell holds exactly; the
// count is over 32 bits, so clz 0 and ctz 0 are 32, as in C++20 and WebAssembly.
constexpr Real kMaxExactInt = static_cast<Real>(16777216.0);
constexpr const char* kNotWhole = "argument is not a whole number from 0 to 16777216";

inline bool WholeInRange(Real x) { return x >= 0 && x <= kMaxExactInt && x == std::floor(x); }   // NaN fails

inline Result Popcount(Real x)
{
    if (!WholeInRange(x)) return Fail(kNotWhole);
    return Value(static_cast<Real>(__builtin_popcount(static_cast<unsigned>(x))));
}

inline Result Clz(Real x)
{
    if (!WholeInRange(x)) return Fail(kNotWhole);
    const unsigned n = static_cast<unsigned>(x);
    return Value(static_cast<Real>(n == 0 ? 32 : __builtin_clz(n)));        // __builtin_clz(0) is undefined
}

inline Result Ctz(Real x)
{
    if (!WholeInRange(x)) return Fail(kNotWhole);
    const unsigned n = static_cast<unsigned>(x);
    return Value(static_cast<Real>(n == 0 ? 32 : __builtin_ctz(n)));
}

// --- C: libm --------------------------------------------------------------------------------
inline Result Exp(Real x) { return Finite(x) ? Checked(std::exp(x)) : Fail(kNotFinite); }
inline Result Expm1(Real x) { return Finite(x) ? Checked(std::expm1(x)) : Fail(kNotFinite); }
inline Result Exp2(Real x) { return Finite(x) ? Checked(std::exp2(x)) : Fail(kNotFinite); }

// x^y. A negative base needs a whole exponent, and zero has no negative powers.
inline Result Pow(Real x, Real y)
{
    if (!Finite(x) || !Finite(y)) return Fail(kNotFinite);
    if (x < 0 && y != std::floor(y)) return Fail("negative base with a non-integer exponent");
    if (x == 0 && y < 0) return Fail("zero to a negative power");
    return Checked(std::pow(x, y));
}

constexpr const char* kNotPositive = "argument is zero or negative";
inline Result Ln(Real x)
{
    if (!Finite(x)) return Fail(kNotFinite);
    if (!(x > 0)) return Fail(kNotPositive);
    return Checked(std::log(x));
}
inline Result Log1p(Real x)
{
    if (!Finite(x)) return Fail(kNotFinite);
    if (!(x > -1)) return Fail("argument is -1 or less");
    return Checked(std::log1p(x));
}
inline Result Log2(Real x)
{
    if (!Finite(x)) return Fail(kNotFinite);
    if (!(x > 0)) return Fail(kNotPositive);
    return Checked(std::log2(x));
}
inline Result Log10(Real x)
{
    if (!Finite(x)) return Fail(kNotFinite);
    if (!(x > 0)) return Fail(kNotPositive);
    return Checked(std::log10(x));
}

inline Result Cbrt(Real x) { return Finite(x) ? Checked(std::cbrt(x)) : Fail(kNotFinite); }

inline Result Hypot(Real x, Real y)
{
    if (!Finite(x) || !Finite(y)) return Fail(kNotFinite);
    return Checked(std::hypot(x, y));
}

inline Result Sinh(Real x) { return Finite(x) ? Checked(std::sinh(x)) : Fail(kNotFinite); }
inline Result Cosh(Real x) { return Finite(x) ? Checked(std::cosh(x)) : Fail(kNotFinite); }
inline Result Tanh(Real x) { return Finite(x) ? Checked(std::tanh(x)) : Fail(kNotFinite); }
inline Result Asinh(Real x) { return Finite(x) ? Checked(std::asinh(x)) : Fail(kNotFinite); }
inline Result Acosh(Real x)
{
    if (!Finite(x)) return Fail(kNotFinite);
    if (!(x >= 1)) return Fail("argument is less than 1");
    return Checked(std::acosh(x));
}
inline Result Atanh(Real x)
{
    if (!Finite(x)) return Fail(kNotFinite);
    if (!(std::fabs(x) < 1)) return Fail("argument is -1 or less, or 1 or more");
    return Checked(std::atanh(x));
}

}  // namespace forthmath
}  // namespace wf

#endif
