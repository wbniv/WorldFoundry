// forth_math_host.cpp: the engine's math words (floor, sqrt, sin-rev ...) for the C test hosts.
//
// tests/species_vm.c and docs/reference/swarming-poster/zf_host.c (built with -DWF_FORTH_MATH) are C, so
// they cannot include forth_math_zforth.hpp. This file gives them its two halves through C linkage: the
// syscall dispatch and the word registration, exactly as engine/stubs/scripting_zforth.cc does both, so
// a level script that calls `floor` runs in the test host on the shipped glue.
// Build: tests/forth_math_host.py (cc for the C files, c++ for this one and the link).
// Plan: docs/plans/2026-11-26-forth-math-words.md.
#include <cstdio>
#include "forth_math_zforth.hpp"

extern "C" int wf_forth_math_sys(zf_ctx* ctx, int id)
{
    return id >= (int)ZF_SYSCALL_USER && wf::forthmath::HandleSyscall(ctx, id - (int)ZF_SYSCALL_USER);
}

extern "C" int wf_forth_math_register(zf_ctx* ctx)
{
    for (const auto& w : wf::forthmath::kWords) {
        char buf[64];
        std::snprintf(buf, sizeof buf, ": %s %d sys ;", w.name, (int)ZF_SYSCALL_USER + w.custom);
        if (zf_eval(ctx, buf) != ZF_OK) {
            std::fprintf(stderr, "forth_math_host: registering %s failed\n", w.name);
            return 1;
        }
    }
    return 0;
}
