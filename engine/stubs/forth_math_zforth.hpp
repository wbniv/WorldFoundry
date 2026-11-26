// forth_math_zforth.hpp: the zForth side of the math words (stack effects and aborts).
//
// Plans: docs/plans/2026-11-21-forth-trig-words.md (73 to 81) and docs/plans/2026-11-26-forth-math-words.md
// (82 to 108). scripting_zforth.cc calls HandleSyscall from its
// syscall switch and registers every word in kWords; the VM test host calls the very same code, so a
// test of the host is a test of the shipped glue. The maths itself is in forth_math.hpp.
#ifndef WF_FORTH_MATH_ZFORTH_HPP
#define WF_FORTH_MATH_ZFORTH_HPP

#include <cstdio>
#include "forth_math.hpp"
#include "zforth.h"

namespace wf {
namespace forthmath {

// The one table: the Forth word, its syscall (ZF_SYSCALL_USER + custom) and its stack effect.
// Custom 72 is the neural-forth gate, so these start at 73. docs/forth-math-words.md lists the same
// words and tests/test_forth_math_docs.py fails if the two ever differ.
struct WordInfo {
    const char* name;
    int custom;
    const char* stack_effect;
};
constexpr WordInfo kWords[] = {
    {"sin-rev",    73, "( rev -- sin )"},
    {"cos-rev",    74, "( rev -- cos )"},
    {"tan-rev",    75, "( rev -- tan )"},
    {"asin-rev",   76, "( x -- rev )"},
    {"acos-rev",   77, "( x -- rev )"},
    {"atan-rev",   78, "( x -- rev )"},
    {"atan2-rev",  79, "( y x -- rev )"},
    {"sincos-rev", 80, "( rev -- sin cos )"},
    {"sqrt",       81, "( x -- r )"},
    // A: exact
    {"floor",      82, "( x -- ⌊x⌋ )"},
    {"ceil",       83, "( x -- ⌈x⌉ )"},
    {"trunc",      84, "( x -- r )"},
    {"round",      85, "( x -- r )"},
    {"roundeven",  86, "( x -- r )"},
    {"fma",        87, "( a b c -- a·b+c )"},
    {"copysign",   88, "( x y -- r )"},
    {"fmod",       89, "( x y -- r )"},
    // B: integer bits (a whole number from 0 to 2^24)
    {"popcount",   90, "( n -- bits )"},
    {"clz",        91, "( n -- zeros )"},
    {"ctz",        92, "( n -- zeros )"},
    // C: libm
    {"exp",        93, "( x -- eˣ )"},
    {"expm1",      94, "( x -- eˣ−1 )"},
    {"exp2",       95, "( x -- 2ˣ )"},
    {"pow",        96, "( x y -- xʸ )"},
    {"ln",         97, "( x -- ln x )"},
    {"log1p",      98, "( x -- ln(1+x) )"},
    {"log2",       99, "( x -- r )"},
    {"log10",     100, "( x -- r )"},
    {"cbrt",      101, "( x -- ∛x )"},
    {"hypot",     102, "( x y -- √(x²+y²) )"},
    {"sinh",      103, "( x -- r )"},
    {"cosh",      104, "( x -- r )"},
    {"tanh",      105, "( x -- r )"},
    {"asinh",     106, "( x -- r )"},
    {"acosh",     107, "( x -- r )"},
    {"atanh",     108, "( x -- r )"},
};
constexpr int kFirstCustom = 73;
constexpr int kLastCustom = 108;

inline const char* NameOf(int custom)
{
    for (const WordInfo& w : kWords)
        if (w.custom == custom) return w.name;
    return "?";
}

// A domain error: say which word and what it was given, then abort the script's frame. zf_abort
// longjmps out of the VM, as its own division-by-zero does, and the next frame runs clean.
[[noreturn]] inline void Refuse(zf_ctx* ctx, int custom, const char* why, double arg)
{
    std::fprintf(stderr, "zforth: %s: %s (argument %.9g)\n", NameOf(custom), why, arg);
    zf_abort(ctx, ZF_ABORT_EXTERNAL);
    for (;;) {}  // zf_abort does not return; keeps [[noreturn]] honest if it ever changes
}

// The same for a word of two or three arguments: all of them go to the log, in stack order.
[[noreturn]] inline void RefuseN(zf_ctx* ctx, int custom, const char* why, const Real* args, int n)
{
    if (n == 2) std::fprintf(stderr, "zforth: %s: %s (arguments %.9g %.9g)\n", NameOf(custom), why, (double)args[0], (double)args[1]);
    else std::fprintf(stderr, "zforth: %s: %s (arguments %.9g %.9g %.9g)\n", NameOf(custom), why, (double)args[0], (double)args[1], (double)args[2]);
    zf_abort(ctx, ZF_ABORT_EXTERNAL);
    for (;;) {}
}

inline void Push(zf_ctx* ctx, const Result& r, int custom, double arg)
{
    if (!r.ok()) Refuse(ctx, custom, r.why, arg);
    zf_push(ctx, static_cast<zf_cell>(r.value));
}

// ( x -- r )
template <typename F>
inline void Unary(zf_ctx* ctx, int custom, F f)
{
    const Real a = static_cast<Real>(zf_pop(ctx));
    Push(ctx, f(a), custom, a);
}

// ( x y -- r )
template <typename F>
inline void Binary(zf_ctx* ctx, int custom, F f)
{
    Real v[2];
    v[1] = static_cast<Real>(zf_pop(ctx));
    v[0] = static_cast<Real>(zf_pop(ctx));
    const Result r = f(v[0], v[1]);
    if (!r.ok()) RefuseN(ctx, custom, r.why, v, 2);
    zf_push(ctx, static_cast<zf_cell>(r.value));
}

// Handles custom syscalls 73 to 108. Returns false for any other number.
inline bool HandleSyscall(zf_ctx* ctx, int custom)
{
    if (custom < kFirstCustom || custom > kLastCustom) return false;
    switch (custom) {
    case 73: { const Real a = static_cast<Real>(zf_pop(ctx)); Push(ctx, SinRev(a), custom, a); break; }
    case 74: { const Real a = static_cast<Real>(zf_pop(ctx)); Push(ctx, CosRev(a), custom, a); break; }
    case 75: { const Real a = static_cast<Real>(zf_pop(ctx)); Push(ctx, TanRev(a), custom, a); break; }
    case 76: { const Real a = static_cast<Real>(zf_pop(ctx)); Push(ctx, AsinRev(a), custom, a); break; }
    case 77: { const Real a = static_cast<Real>(zf_pop(ctx)); Push(ctx, AcosRev(a), custom, a); break; }
    case 78: { const Real a = static_cast<Real>(zf_pop(ctx)); Push(ctx, AtanRev(a), custom, a); break; }
    case 79: {
        const Real x = static_cast<Real>(zf_pop(ctx));
        const Real y = static_cast<Real>(zf_pop(ctx));
        const Result r = Atan2Rev(y, x);
        if (!r.ok()) Refuse(ctx, custom, r.why, std::isfinite(y) ? x : y);
        zf_push(ctx, static_cast<zf_cell>(r.value));
        break;
    }
    case 80: {
        const Real a = static_cast<Real>(zf_pop(ctx));
        const Pair p = SinCosRev(a);
        if (!p.sin.ok()) Refuse(ctx, custom, p.sin.why, a);
        zf_push(ctx, static_cast<zf_cell>(p.sin.value));
        zf_push(ctx, static_cast<zf_cell>(p.cos.value));
        break;
    }
    case 81: { const Real a = static_cast<Real>(zf_pop(ctx)); Push(ctx, Sqrt(a), custom, a); break; }
    case 82: Unary(ctx, custom, Floor); break;
    case 83: Unary(ctx, custom, Ceil); break;
    case 84: Unary(ctx, custom, Trunc); break;
    case 85: Unary(ctx, custom, Round); break;
    case 86: Unary(ctx, custom, RoundEven); break;
    case 87: {
        Real v[3];
        v[2] = static_cast<Real>(zf_pop(ctx));
        v[1] = static_cast<Real>(zf_pop(ctx));
        v[0] = static_cast<Real>(zf_pop(ctx));
        const Result r = Fma(v[0], v[1], v[2]);
        if (!r.ok()) RefuseN(ctx, custom, r.why, v, 3);
        zf_push(ctx, static_cast<zf_cell>(r.value));
        break;
    }
    case 88: Binary(ctx, custom, CopySign); break;
    case 89: Binary(ctx, custom, Fmod); break;
    case 90: Unary(ctx, custom, Popcount); break;
    case 91: Unary(ctx, custom, Clz); break;
    case 92: Unary(ctx, custom, Ctz); break;
    case 93: Unary(ctx, custom, Exp); break;
    case 94: Unary(ctx, custom, Expm1); break;
    case 95: Unary(ctx, custom, Exp2); break;
    case 96: Binary(ctx, custom, Pow); break;
    case 97: Unary(ctx, custom, Ln); break;
    case 98: Unary(ctx, custom, Log1p); break;
    case 99: Unary(ctx, custom, Log2); break;
    case 100: Unary(ctx, custom, Log10); break;
    case 101: Unary(ctx, custom, Cbrt); break;
    case 102: Binary(ctx, custom, Hypot); break;
    case 103: Unary(ctx, custom, Sinh); break;
    case 104: Unary(ctx, custom, Cosh); break;
    case 105: Unary(ctx, custom, Tanh); break;
    case 106: Unary(ctx, custom, Asinh); break;
    case 107: Unary(ctx, custom, Acosh); break;
    case 108: Unary(ctx, custom, Atanh); break;
    }
    return true;
}

}  // namespace forthmath
}  // namespace wf

#endif
