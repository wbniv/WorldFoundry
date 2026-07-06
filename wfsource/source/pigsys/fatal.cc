//===========================================================================*/
// fatal.cc — shared std::terminate diagnostic handler.
//
// An engine AssertMsg exits via exit(-1) (assert.cc), which runs static
// destructors. A joinable static std::thread destroyed there — or any unhandled
// exception / noexcept violation anywhere — calls std::terminate(), whose default
// prints a bare "terminate called without an active exception" that MASKS the
// real cause. Sys_InstallTerminateHandler installs a handler that dumps the actual
// cause (the active exception, or the no-exception hint) + a backtrace before
// aborting, so the failure is self-diagnosing. Call it first thing in every main().
//
// Lifted from engine/wf_edit/main.cc's TerminateHandler so wf_game and wf_edit
// share one implementation. See docs/investigations/2026-06-13-terminate-masking-audit.md.
//===========================================================================*/

#include "pigsys.hp"
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <unistd.h>      // STDERR_FILENO
#undef abort             // pigsys may macro-define abort; use the real std::abort

// backtrace() lives in <execinfo.h> on glibc + macOS/iOS, absent on wasm and on
// Android before API 33 — guard so the handler degrades to no-backtrace there.
#if !defined(__EMSCRIPTEN__) && defined(__has_include)
#  if __has_include(<execinfo.h>)
#    include <execinfo.h>
#    define WF_HAVE_BACKTRACE 1
#  endif
#endif

static const char* g_appName = "wf";

static void WfTerminateHandler()
{
    std::fprintf(stderr, "\n=== %s: std::terminate fired ===\n", g_appName);
    if (std::exception_ptr ep = std::current_exception()) {
        try {
            std::rethrow_exception(ep);
        } catch (const std::exception& e) {
            std::fprintf(stderr, "  active std::exception: %s\n", e.what());
        } catch (...) {
            std::fprintf(stderr, "  active exception: (non-std::exception)\n");
        }
    } else {
        std::fprintf(stderr, "  no active exception "
                     "(likely joinable std::thread destroyed without join, "
                     "or noexcept function throwing)\n");
    }
#if defined(WF_HAVE_BACKTRACE)
    void* frames[64];
    const int n = ::backtrace(frames, 64);
    std::fprintf(stderr, "  backtrace (%d frames):\n", n);
    ::backtrace_symbols_fd(frames, n, STDERR_FILENO);
#else
    std::fprintf(stderr, "  (no backtrace on this platform)\n");
#endif
    std::fprintf(stderr, "=== aborting ===\n");
    std::fflush(stderr);
    std::abort();
}

void Sys_InstallTerminateHandler(const char* appName)
{
    if (appName && *appName) g_appName = appName;
    std::set_terminate(WfTerminateHandler);
}
