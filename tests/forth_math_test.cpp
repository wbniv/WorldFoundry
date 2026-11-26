// The Forth math words' maths (engine/stubs/forth_math.hpp), no engine and no VM.
// Plans: docs/plans/2026-11-21-forth-trig-words.md and docs/plans/2026-11-26-forth-math-words.md. Built and run by `task test-forth-math`, twice:
// once with the default Real (double) and once with -DWF_FORTH_MATH_FLOAT, the single-precision
// FPU mode, where the contract's absolute tolerance is looser (tests/data/forth_math_vectors.json).
#undef NDEBUG  // the checks below carry side effects
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
#include <string>

#include "forth_math.hpp"

using namespace wf::forthmath;

namespace {

struct Case {
    const char* word;
    int n_in;
    double in[3];
    int n_out;
    double out[2];
    bool error;
};
const Case kCases[] = {
#include "data/forth_math_vectors.inc"
};

#ifdef WF_FORTH_MATH_FLOAT
constexpr double kAbsTol = 6e-7;       // abs_single_fpu in the vector file
const char* kMode = "float";
#else
constexpr double kAbsTol = 1e-7;       // abs in the vector file
const char* kMode = "double";
#endif

int failures = 0;
int checks = 0;
#define CHECK(c) do { ++checks; if (!(c)) { std::fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); ++failures; } } while (0)

double ulp(double v)
{
    const float a = std::fabs(static_cast<float>(v));
    return static_cast<double>(std::nextafterf(a, INFINITY)) - a;
}

// within one float ulp or the absolute tolerance, whichever is larger. On a single-FPU build the
// tangent is only specified away from its poles (|tan| <= 1000), with a relative tolerance: the angle
// 2*pi*x is computed in float there, and near a pole that rounding is magnified.
bool close(double got, double want, const char* word = "")
{
    if (std::isnan(got) || std::isnan(want)) return false;
#ifdef WF_FORTH_MATH_FLOAT
    if (!std::strcmp(word, "tan-rev")) {
        if (std::fabs(want) > 1000.0) return std::isfinite(got);
        return std::fabs(got - want) <= std::fmax(kAbsTol, 1e-5 * std::fabs(want));
    }
#else
    (void)word;
#endif
    return std::fabs(got - want) <= std::fmax(kAbsTol, ulp(want));
}

struct Out {
    int n = 0;
    float v[2] = {0, 0};
    const char* why = nullptr;
};

// Groups A and B of the second plan: the result must be the exact answer, bit for bit.
const char* const kExact[] = {"floor", "ceil", "trunc", "round", "roundeven", "fma", "copysign", "fmod", "popcount", "clz", "ctz"};
bool is_exact(const char* word)
{
    for (const char* w : kExact)
        if (!std::strcmp(w, word)) return true;
    return false;
}

bool same_bits(float a, float b) { return std::memcmp(&a, &b, sizeof a) == 0; }

// Within one float ulp of the reference, with no absolute floor (the second plan's group C).
bool within_ulp(double got, double want, double ulps = 1.0)
{
    if (!std::isfinite(got) || !std::isfinite(want)) return false;
    return std::fabs(got - want) <= ulps * ulp(want);
}

Out call(const char* word, const double* in)
{
    Out o;
    auto one = [&](const Result& r) { if (!r.ok()) o.why = r.why; else { o.n = 1; o.v[0] = r.value; } };
    const Real a = static_cast<Real>(in[0]), b = static_cast<Real>(in[1]), c = static_cast<Real>(in[2]);
    if (!std::strcmp(word, "sin-rev")) one(SinRev(a));
    else if (!std::strcmp(word, "cos-rev")) one(CosRev(a));
    else if (!std::strcmp(word, "tan-rev")) one(TanRev(a));
    else if (!std::strcmp(word, "asin-rev")) one(AsinRev(a));
    else if (!std::strcmp(word, "acos-rev")) one(AcosRev(a));
    else if (!std::strcmp(word, "atan-rev")) one(AtanRev(a));
    else if (!std::strcmp(word, "atan2-rev")) one(Atan2Rev(a, b));
    else if (!std::strcmp(word, "sqrt")) one(Sqrt(a));
    else if (!std::strcmp(word, "floor")) one(Floor(a));
    else if (!std::strcmp(word, "ceil")) one(Ceil(a));
    else if (!std::strcmp(word, "trunc")) one(Trunc(a));
    else if (!std::strcmp(word, "round")) one(Round(a));
    else if (!std::strcmp(word, "roundeven")) one(RoundEven(a));
    else if (!std::strcmp(word, "fma")) one(Fma(a, b, c));
    else if (!std::strcmp(word, "copysign")) one(CopySign(a, b));
    else if (!std::strcmp(word, "fmod")) one(Fmod(a, b));
    else if (!std::strcmp(word, "popcount")) one(Popcount(a));
    else if (!std::strcmp(word, "clz")) one(Clz(a));
    else if (!std::strcmp(word, "ctz")) one(Ctz(a));
    else if (!std::strcmp(word, "exp")) one(Exp(a));
    else if (!std::strcmp(word, "expm1")) one(Expm1(a));
    else if (!std::strcmp(word, "exp2")) one(Exp2(a));
    else if (!std::strcmp(word, "pow")) one(Pow(a, b));
    else if (!std::strcmp(word, "ln")) one(Ln(a));
    else if (!std::strcmp(word, "log1p")) one(Log1p(a));
    else if (!std::strcmp(word, "log2")) one(Log2(a));
    else if (!std::strcmp(word, "log10")) one(Log10(a));
    else if (!std::strcmp(word, "cbrt")) one(Cbrt(a));
    else if (!std::strcmp(word, "hypot")) one(Hypot(a, b));
    else if (!std::strcmp(word, "sinh")) one(Sinh(a));
    else if (!std::strcmp(word, "cosh")) one(Cosh(a));
    else if (!std::strcmp(word, "tanh")) one(Tanh(a));
    else if (!std::strcmp(word, "asinh")) one(Asinh(a));
    else if (!std::strcmp(word, "acosh")) one(Acosh(a));
    else if (!std::strcmp(word, "atanh")) one(Atanh(a));
    else if (!std::strcmp(word, "sincos-rev")) {
        const Pair p = SinCosRev(a);
        if (!p.sin.ok()) o.why = p.sin.why; else { o.n = 2; o.v[0] = p.sin.value; o.v[1] = p.cos.value; }
    } else { std::fprintf(stderr, "unknown word %s\n", word); std::abort(); }
    return o;
}

float sin_rev(double x) { return SinRev(static_cast<Real>(x)).value; }
float cos_rev(double x) { return CosRev(static_cast<Real>(x)).value; }

}  // namespace

int main()
{
    // 1. every shared vector
    int words = 0;
    const char* last = "";
    for (const Case& c : kCases) {
        if (std::strcmp(c.word, last)) { ++words; last = c.word; }
        const Out o = call(c.word, c.in);
        if (c.error) {
            if (o.why == nullptr) std::fprintf(stderr, "no error for %s(%.9g, %.9g)\n", c.word, c.in[0], c.in[1]);
            CHECK(o.why != nullptr);
        } else {
            if (o.why != nullptr) std::fprintf(stderr, "unexpected error for %s(%.9g, %.9g): %s\n", c.word, c.in[0], c.in[1], o.why);
            CHECK(o.why == nullptr && o.n == c.n_out);
            for (int k = 0; k < c.n_out && o.n == c.n_out; ++k) {
                const bool ok = is_exact(c.word) ? same_bits(o.v[k], static_cast<float>(c.out[k])) : close(o.v[k], c.out[k], c.word);
                if (!ok) std::fprintf(stderr, "%s(%.9g, %.9g)[%d]: got %.9g want %.9g\n", c.word, c.in[0], c.in[1], k, (double)o.v[k], c.out[k]);
                CHECK(ok);
            }
        }
    }
    CHECK(words == 36);

    // 2. symmetries and identities
    for (double x = -3.0; x <= 3.0; x += 0.0173) {
        CHECK(std::fabs(sin_rev(-x) + sin_rev(x)) <= kAbsTol);                 // odd
        CHECK(std::fabs(cos_rev(-x) - cos_rev(x)) <= kAbsTol);                 // even
        const double s = sin_rev(x), c = cos_rev(x);
        CHECK(std::fabs(s * s + c * c - 1.0) <= 2 * kAbsTol + 1e-6);
        const Pair p = SinCosRev(static_cast<Real>(x));
        CHECK(p.sin.ok() && p.cos.ok() && p.sin.value == static_cast<float>(sin_rev(x)) && p.cos.value == static_cast<float>(cos_rev(x)));
    }

    // 3. round trips on the principal ranges
    for (double x = -0.24; x <= 0.24; x += 0.011) {
        CHECK(std::fabs(AsinRev(SinRev(static_cast<Real>(x)).value).value - x) <= 4 * kAbsTol + 2e-6);
        CHECK(std::fabs(AtanRev(TanRev(static_cast<Real>(x)).value).value - x) <= 4 * kAbsTol + 2e-6);
    }
    for (double x = 0.01; x <= 0.49; x += 0.011)
        CHECK(std::fabs(AcosRev(CosRev(static_cast<Real>(x)).value).value - x) <= 4 * kAbsTol + 2e-6);

    // 4. the eight directions of atan2-rev, in the engine's convention (0 along +x, a quarter along +y)
    const double dirs[8][3] = {{0, 1, 0.0}, {1, 1, 0.125}, {1, 0, 0.25}, {1, -1, 0.375}, {0, -1, 0.5},
                               {-1, -1, -0.375}, {-1, 0, -0.25}, {-1, 1, -0.125}};
    for (const auto& d : dirs) CHECK(std::fabs(Atan2Rev(static_cast<Real>(d[0]), static_cast<Real>(d[1])).value - d[2]) <= kAbsTol);
    CHECK(Atan2Rev(0, 0).ok() && Atan2Rev(0, 0).value == 0.0f);        // a zero vector has heading 0

    // 5. domain errors: refused, clamped, and the slack's edge
    CHECK(!AsinRev(1.5).ok() && !AcosRev(-2).ok());
    CHECK(AsinRev(static_cast<Real>(1.0000001)).ok() && std::fabs(AsinRev(static_cast<Real>(1.0000001)).value - 0.25) <= kAbsTol);   // 1e-7 over: clamped
    CHECK(AcosRev(static_cast<Real>(-1.0000001)).ok() && std::fabs(AcosRev(static_cast<Real>(-1.0000001)).value - 0.5) <= kAbsTol);
    CHECK(!AsinRev(static_cast<Real>(1.00001)).ok());                  // 1e-5 over: refused
    CHECK(!Sqrt(-1).ok() && Sqrt(0).ok() && Sqrt(-0.0).ok());
    CHECK(!SinRev(INFINITY).ok() && !CosRev(NAN).ok() && !TanRev(-INFINITY).ok() && !AtanRev(NAN).ok() && !Atan2Rev(NAN, 1).ok());

    // 6. the tangent's poles are huge and finite, not an error (D3, option B)
#ifdef WF_FORTH_MATH_FLOAT
    constexpr float kPole = 1e6f;      // float's 2*pi/4 is not pi/2: the tangent there is about 2.3e7
#else
    constexpr float kPole = 1e10f;     // double: about 1.6e16
#endif
    CHECK(TanRev(0.25).ok() && std::fabs(TanRev(0.25).value) > kPole);
    CHECK(TanRev(0.75).ok() && std::fabs(TanRev(0.75).value) > kPole);

    // 7. 100 000 random arguments against a long double reference
    std::mt19937 rng(20261121);
    std::uniform_real_distribution<double> turns(-8.0, 8.0), unit(-1.0, 1.0), wide(-50.0, 50.0), pos(0.0, 1000.0);
    const long double two_pi = 6.283185307179586476925286766559005768394L;
    int bad = 0;
    for (int i = 0; i < 100000; ++i) {
        const float t = static_cast<float>(turns(rng));
        const long double lt = t, f = lt - floorl(lt);
        if (!close(sin_rev(t), static_cast<double>(static_cast<float>(sinl(two_pi * f))))) ++bad;
        if (!close(cos_rev(t), static_cast<double>(static_cast<float>(cosl(two_pi * f))))) ++bad;
        const long double tn = tanl(two_pi * f);
        if (fabsl(tn) < 100.0L) {
            const double got = TanRev(t).value, want = static_cast<double>(static_cast<float>(tn));
#ifdef WF_FORTH_MATH_FLOAT
            if (std::fabs(got - want) > 1e-4 * std::fmax(1.0, std::fabs(want))) ++bad;
#else
            if (std::fabs(got - want) > 2e-6 * std::fmax(1.0, std::fabs(want))) ++bad;
#endif
        }
        const float u = static_cast<float>(unit(rng));
        if (!close(AsinRev(u).value, static_cast<double>(static_cast<float>(asinl(u) / two_pi)))) ++bad;
        if (!close(AcosRev(u).value, static_cast<double>(static_cast<float>(acosl(u) / two_pi)))) ++bad;
        const float w = static_cast<float>(wide(rng)), w2 = static_cast<float>(wide(rng));
        if (!close(AtanRev(w).value, static_cast<double>(static_cast<float>(atanl(w) / two_pi)))) ++bad;
        if (!close(Atan2Rev(w, w2).value, static_cast<double>(static_cast<float>(atan2l(w, w2) / two_pi)))) ++bad;
        const float p = static_cast<float>(pos(rng));
        if (!close(Sqrt(p).value, static_cast<double>(static_cast<float>(sqrtl(p))))) ++bad;
    }
    CHECK(bad == 0);
    if (bad) std::fprintf(stderr, "%d of 800000 random results out of tolerance\n", bad);

    // 8. the second plan's words: rounding rules, signs, the bit words' edges and every domain edge
    CHECK(Round(2.5).value == 3.0f && Round(-2.5).value == -3.0f && Round(0.5).value == 1.0f);           // ties away from zero
    CHECK(RoundEven(2.5).value == 2.0f && RoundEven(3.5).value == 4.0f && RoundEven(-2.5).value == -2.0f); // ties to even
    CHECK(same_bits(Ceil(-0.5).value, -0.0f) && same_bits(Trunc(-0.7).value, -0.0f));                     // the sign of zero kept
    CHECK(Floor(-0.5).value == -1.0f && Floor(16777215).value == 16777215.0f);
    CHECK(Fmod(-7, 3).value == -1.0f && Fmod(7, -3).value == 1.0f && !Fmod(1, 0).ok() && !Fmod(1, -0.0).ok());
    CHECK(CopySign(2, -0.0).value == -2.0f && CopySign(-2, 0).value == 2.0f);
    {   // one rounding: (1 + 2^-12)^2 + 1e-24 is a tie in float after a double rounding, and not before it
        const Real big = static_cast<Real>(1.0 + 1.0 / 4096.0);
        CHECK(same_bits(Fma(big, big, static_cast<Real>(1e-24f)).value, 1.0f + 1.0f / 2048.0f + 1.0f / 8388608.0f));
    }
    CHECK(!Fma(3e38f, 10, 0).ok() && !Fma(INFINITY, 0, 1).ok());
    CHECK(Popcount(16777215).value == 24.0f && Popcount(16777216).value == 1.0f && Popcount(0).value == 0.0f);
    CHECK(Clz(0).value == 32.0f && Ctz(0).value == 32.0f && Clz(1).value == 31.0f && Ctz(16777216).value == 24.0f);
    CHECK(!Popcount(-1).ok() && !Popcount(0.5).ok() && !Clz(16777218).ok() && !Ctz(1e30f).ok() && !Popcount(NAN).ok());
    CHECK(!Pow(-8, static_cast<Real>(1.0 / 3.0)).ok() && Pow(-2, 3).value == -8.0f && !Pow(0, -1).ok() && Pow(0, 0).value == 1.0f);
    CHECK(!Pow(10, 39).ok() && Pow(10, 38).ok());                      // 1e39 does not fit a float cell
    CHECK(!Ln(0).ok() && !Ln(-0.0).ok() && !Ln(-1).ok() && !Log2(0).ok() && !Log10(-1e-30f).ok());
    CHECK(!Log1p(-1).ok() && Log1p(static_cast<Real>(-0.99999994f)).ok());
    CHECK(!Acosh(static_cast<Real>(0.99999994f)).ok() && Acosh(1).value == 0.0f);
    CHECK(!Atanh(1).ok() && !Atanh(-1).ok() && Atanh(static_cast<Real>(0.99999994f)).ok());
    CHECK(!Exp(89).ok() && Exp(88).ok() && Exp(-1e30f).value == 0.0f && !Exp2(128).ok() && Exp2(127).ok());
    CHECK(!Sinh(-1e30f).ok() && !Cosh(1e30f).ok() && Tanh(1e30f).value == 1.0f && !Hypot(3e38f, 3e38f).ok());
    CHECK(!Exp(NAN).ok() && !Cbrt(INFINITY).ok() && !Tanh(-INFINITY).ok() && !Floor(NAN).ok() && !CopySign(1, NAN).ok());
    CHECK(Expm1(static_cast<Real>(1e-7f)).value != 0.0f && Log1p(static_cast<Real>(1e-7f)).value != 0.0f);   // their reason to exist
    CHECK(Cbrt(-27).value == -3.0f && Hypot(3, 4).value == 5.0f && Exp2(10).value == 1024.0f && Log2(1024).value == 10.0f);

    // 9. 100 000 random arguments of each new word: groups A and B exact, group C within one float ulp of long double
#ifdef WF_FORTH_MATH_FLOAT
    constexpr double kUlps = 2.0;      // float libm (Real = float): its own error plus the cell's rounding
#else
    constexpr double kUlps = 1.0;
#endif
    std::mt19937 rng2(20261126);
    std::uniform_real_distribution<double> hundred(-100.0, 100.0), ten(-10.0, 10.0), unit01(0.0, 1.0);
    auto logu = [&](double lo, double hi) { return std::exp(std::log(lo) + unit01(rng2) * (std::log(hi) - std::log(lo))); };
    int bad2 = 0, refused2 = 0;
    auto exact1 = [&](const char* w, const Result& r, long double want) {
        const float wf = static_cast<float>(want);
        if (!r.ok() || !same_bits(r.value, wf)) { if (bad2 < 10) std::fprintf(stderr, "%s: got %.9g want %.9g\n", w, (double)r.value, (double)wf); ++bad2; }
    };
    auto libm1 = [&](const char* w, const Result& r, long double want, double arg) {
        const float wf = static_cast<float>(want);
        if (!std::isfinite(wf)) { if (r.ok()) ++bad2; else ++refused2; return; }     // must refuse what does not fit
        if (!r.ok() || !within_ulp(r.value, wf, kUlps)) {
            if (bad2 < 10) std::fprintf(stderr, "%s(%.9g): got %.9g want %.9g\n", w, arg, (double)r.value, (double)wf);
            ++bad2;
        }
    };
    for (int i = 0; i < 100000; ++i) {
        const float x = static_cast<float>(hundred(rng2)), y = static_cast<float>(ten(rng2)), z = static_cast<float>(ten(rng2));
        exact1("floor", Floor(x), floorl(x));
        exact1("ceil", Ceil(x), ceill(x));
        exact1("trunc", Trunc(x), truncl(x));
        exact1("round", Round(x), roundl(x));
        exact1("roundeven", RoundEven(x), nearbyintl(x));
        exact1("fma", Fma(x, y, z), fmal(x, y, z));
        exact1("copysign", CopySign(x, y), copysignl(x, y));
        if (y != 0) exact1("fmod", Fmod(x, y), fmodl(x, y));
        const unsigned n = static_cast<unsigned>(unit01(rng2) * 16777217.0);
        int pc = 0, lz = 32, tz = 32;
        for (int b = 0; b < 32; ++b) if (n >> b & 1u) { ++pc; lz = 31 - b; }
        for (int b = 31; b >= 0; --b) if (n >> b & 1u) tz = b;
        exact1("popcount", Popcount(static_cast<Real>(n)), pc);
        exact1("clz", Clz(static_cast<Real>(n)), lz);
        exact1("ctz", Ctz(static_cast<Real>(n)), tz);

        const float e = static_cast<float>(hundred(rng2) * 0.9);     // -90 to 90: crosses exp's overflow at 88.7
        libm1("exp", Exp(e), expl(e), e);
        libm1("expm1", Expm1(e), expm1l(e), e);
        const float tiny = static_cast<float>(ten(rng2) * 1e-6);
        libm1("expm1", Expm1(tiny), expm1l(tiny), tiny);
        libm1("exp2", Exp2(e * 1.5f), exp2l(e * 1.5f), e * 1.5f);
        libm1("sinh", Sinh(e), sinhl(e), e);
        libm1("cosh", Cosh(e), coshl(e), e);
        libm1("tanh", Tanh(y), tanhl(y), y);
        const float p = static_cast<float>(logu(1e-6, 1e6)), q = static_cast<float>(hundred(rng2) * 0.2);
        libm1("pow", Pow(p, q), powl(p, q), p);
        libm1("ln", Ln(p), logl(p), p);
        libm1("log2", Log2(p), log2l(p), p);
        libm1("log10", Log10(p), log10l(p), p);
        const float l1 = static_cast<float>(logu(1e-6, 1e3) - 1.0);
        libm1("log1p", Log1p(l1), log1pl(l1), l1);
        libm1("cbrt", Cbrt(x * p), cbrtl(static_cast<float>(x * p)), x * p);
        libm1("hypot", Hypot(x, y), hypotl(x, y), x);
        libm1("asinh", Asinh(x * p), asinhl(static_cast<float>(x * p)), x * p);
        const float a1 = static_cast<float>(1.0 + logu(1e-6, 1e4));
        libm1("acosh", Acosh(a1), acoshl(a1), a1);
        const float t1 = static_cast<float>(unit01(rng2) * 1.9998 - 0.9999);
        libm1("atanh", Atanh(t1), atanhl(t1), t1);
    }
    CHECK(bad2 == 0);
    CHECK(refused2 > 0);       // the exp overflow was crossed, and refused
    if (bad2) std::fprintf(stderr, "%d random results of the second plan's words out of tolerance\n", bad2);

    if (failures) {
        std::fprintf(stderr, "forth_math_test (%s): %d of %d checks failed\n", kMode, failures, checks);
        return 1;
    }
    std::printf("forth_math_test (%s Real): OK, %d checks, %zu shared vectors across %d words\n", kMode, checks, sizeof(kCases) / sizeof(kCases[0]), words);
    return 0;
}
