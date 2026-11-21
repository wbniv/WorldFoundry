// forth_math_zforth.hpp: the zForth side of the trigonometry words (stack effects and aborts).
//
// Plan: docs/plans/2026-11-21-forth-trig-words.md. scripting_zforth.cc calls HandleSyscall from its
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
};
constexpr int kFirstCustom = 73;
constexpr int kLastCustom = 81;

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

inline void Push(zf_ctx* ctx, const Result& r, int custom, double arg)
{
    if (!r.ok()) Refuse(ctx, custom, r.why, arg);
    zf_push(ctx, static_cast<zf_cell>(r.value));
}

// Handles custom syscalls 73 to 81. Returns false for any other number.
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
    }
    return true;
}

}  // namespace forthmath
}  // namespace wf

#endif
