// The Forth math words' maths (engine/stubs/forth_math.hpp), no engine and no VM.
// Plan: docs/plans/2026-11-21-forth-trig-words.md. Built and run by `task test-forth-math`, twice:
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
    double in[2];
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

Out call(const char* word, const double* in)
{
    Out o;
    auto one = [&](const Result& r) { if (!r.ok()) o.why = r.why; else { o.n = 1; o.v[0] = r.value; } };
    const Real a = static_cast<Real>(in[0]), b = static_cast<Real>(in[1]);
    if (!std::strcmp(word, "sin-rev")) one(SinRev(a));
    else if (!std::strcmp(word, "cos-rev")) one(CosRev(a));
    else if (!std::strcmp(word, "tan-rev")) one(TanRev(a));
    else if (!std::strcmp(word, "asin-rev")) one(AsinRev(a));
    else if (!std::strcmp(word, "acos-rev")) one(AcosRev(a));
    else if (!std::strcmp(word, "atan-rev")) one(AtanRev(a));
    else if (!std::strcmp(word, "atan2-rev")) one(Atan2Rev(a, b));
    else if (!std::strcmp(word, "sqrt")) one(Sqrt(a));
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
                const bool ok = close(o.v[k], c.out[k], c.word);
                if (!ok) std::fprintf(stderr, "%s(%.9g, %.9g)[%d]: got %.9g want %.9g\n", c.word, c.in[0], c.in[1], k, (double)o.v[k], c.out[k]);
                CHECK(ok);
            }
        }
    }
    CHECK(words == 9);

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

    if (failures) {
        std::fprintf(stderr, "forth_math_test (%s): %d of %d checks failed\n", kMode, failures, checks);
        return 1;
    }
    std::printf("forth_math_test (%s Real): OK, %d checks, %zu shared vectors across %d words\n", kMode, checks, sizeof(kCases) / sizeof(kCases[0]), words);
    return 0;
}
