// Every Forth math word on a fixed set of arguments, printed as float bits, for
// tests/forth_math_agreement.py to compare between machines (PC glibc, WebAssembly, devices).
// Plan: docs/plans/2026-11-26-forth-math-words.md, Phase 3.
//
// The arguments are the shared vectors (tests/data/forth_math_vectors.inc) plus 2000 per word from
// an integer generator, so every C library sees the same inputs (std::uniform_real_distribution is
// not specified bit for bit, and libstdc++ and libc++ differ). Each line is
//   <word> <case> <bits of result 1>[,<bits of result 2>]   or   <word> <case> ERR
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

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

uint32_t bits(float f) { uint32_t u; std::memcpy(&u, &f, sizeof u); return u; }

void print(const char* word, int k, const Result& r)
{
    if (!r.ok()) std::printf("%s %d ERR\n", word, k);
    else std::printf("%s %d %08x\n", word, k, (unsigned)bits(r.value));
}

Result one(const char* w, Real a, Real b, Real c)
{
#define W(name, call) if (!std::strcmp(w, name)) return call;
    W("sin-rev", SinRev(a)) W("cos-rev", CosRev(a)) W("tan-rev", TanRev(a)) W("asin-rev", AsinRev(a))
    W("acos-rev", AcosRev(a)) W("atan-rev", AtanRev(a)) W("atan2-rev", Atan2Rev(a, b)) W("sqrt", Sqrt(a))
    W("floor", Floor(a)) W("ceil", Ceil(a)) W("trunc", Trunc(a)) W("round", Round(a)) W("roundeven", RoundEven(a))
    W("fma", Fma(a, b, c)) W("copysign", CopySign(a, b)) W("fmod", Fmod(a, b))
    W("popcount", Popcount(a)) W("clz", Clz(a)) W("ctz", Ctz(a))
    W("exp", Exp(a)) W("expm1", Expm1(a)) W("exp2", Exp2(a)) W("pow", Pow(a, b)) W("ln", Ln(a)) W("log1p", Log1p(a))
    W("log2", Log2(a)) W("log10", Log10(a)) W("cbrt", Cbrt(a)) W("hypot", Hypot(a, b)) W("sinh", Sinh(a))
    W("cosh", Cosh(a)) W("tanh", Tanh(a)) W("asinh", Asinh(a)) W("acosh", Acosh(a)) W("atanh", Atanh(a))
#undef W
    std::fprintf(stderr, "unknown word %s\n", w);
    std::abort();
}

void run(const char* w, int k, Real a, Real b, Real c)
{
    if (!std::strcmp(w, "sincos-rev")) {
        const Pair p = SinCosRev(a);
        if (!p.sin.ok()) std::printf("%s %d ERR\n", w, k);
        else std::printf("%s %d %08x,%08x\n", w, k, (unsigned)bits(p.sin.value), (unsigned)bits(p.cos.value));
        return;
    }
    print(w, k, one(w, a, b, c));
}

uint64_t state = 0x2026112600000001ull;
double unit()   // [0, 1), 53 bits, the same on every machine
{
    state = state * 6364136223846793005ull + 1442695040888963407ull;
    return static_cast<double>(state >> 11) * (1.0 / 9007199254740992.0);
}
float range(double lo, double hi) { return static_cast<float>(lo + (hi - lo) * unit()); }
float logrange(double lo, double hi) { return static_cast<float>(std::exp(std::log(lo) + (std::log(hi) - std::log(lo)) * unit())); }

}  // namespace

int main()
{
    int k = 0;
    const char* last = "";
    for (const Case& c : kCases) {
        if (std::strcmp(c.word, last)) { k = 0; last = c.word; }
        run(c.word, k++, static_cast<Real>(c.in[0]), static_cast<Real>(c.in[1]), static_cast<Real>(c.in[2]));
    }
    // random arguments, numbered from 10000 so they never collide with the vectors
    const char* words[] = {"sin-rev", "cos-rev", "tan-rev", "asin-rev", "acos-rev", "atan-rev", "atan2-rev", "sincos-rev", "sqrt",
                           "floor", "ceil", "trunc", "round", "roundeven", "fma", "copysign", "fmod", "popcount", "clz", "ctz",
                           "exp", "expm1", "exp2", "pow", "ln", "log1p", "log2", "log10", "cbrt", "hypot",
                           "sinh", "cosh", "tanh", "asinh", "acosh", "atanh"};
    for (const char* w : words) {
        for (int i = 0; i < 2000; ++i) {
            float a = range(-100, 100), b = range(-10, 10), c = range(-10, 10);
            if (!std::strcmp(w, "sin-rev") || !std::strcmp(w, "cos-rev") || !std::strcmp(w, "tan-rev") || !std::strcmp(w, "sincos-rev")) a = range(-8, 8);
            else if (!std::strcmp(w, "asin-rev") || !std::strcmp(w, "acos-rev") || !std::strcmp(w, "atanh")) a = range(-1, 1);
            else if (!std::strcmp(w, "sqrt") || !std::strcmp(w, "ln") || !std::strcmp(w, "log2") || !std::strcmp(w, "log10")) a = logrange(1e-6, 1e6);
            else if (!std::strcmp(w, "popcount") || !std::strcmp(w, "clz") || !std::strcmp(w, "ctz")) a = std::floor(range(0, 16777216));
            else if (!std::strcmp(w, "exp") || !std::strcmp(w, "expm1") || !std::strcmp(w, "sinh") || !std::strcmp(w, "cosh")) a = range(-90, 90);
            else if (!std::strcmp(w, "exp2")) a = range(-130, 130);
            else if (!std::strcmp(w, "pow")) { a = logrange(1e-6, 1e6); b = range(-20, 20); }
            else if (!std::strcmp(w, "log1p")) a = logrange(1e-6, 1e3) - 1.0f;
            else if (!std::strcmp(w, "cbrt") || !std::strcmp(w, "asinh")) a = range(-1e6, 1e6);
            else if (!std::strcmp(w, "acosh")) a = 1.0f + logrange(1e-6, 1e4);
            run(w, 10000 + i, a, b, c);
        }
    }
    return 0;
}
