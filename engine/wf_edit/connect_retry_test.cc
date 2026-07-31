// connect_retry_test.cc — fault-injection regression test for the relay connect
// retry policy (connect_retry.h). Standalone, header-only, no GL / no sockets:
// the policy's seams (try_once / now / sleep_s / aborted) are injected, so we
// drive it with a scripted connector and a fake clock and assert on the outcome.
//
// This is the regression guard the 2026-06-01 critique (⑦) asked for: it pins
// down (a) transient failures retry until success, (b) definitive failures
// (NXDOMAIN / 4xx) FAIL FAST — attempts==1, not "burn the whole budget", (c) a
// finite budget is honoured, and (d) abort (window-close / shutdown) exits the
// loop promptly.
//
// Build: add_executable(connect_retry_test ...) + add_test (CMakeLists.txt),
// also run by `task build-editor`. Returns 0 on all-pass, 1 on any failure.

#include "connect_retry.h"

#include <atomic>
#include <cstdio>
#include <vector>

using wfedit::ConnectAttempt;
using wfedit::ConnectError;
using wfedit::ConnectOutcome;
using wfedit::IsRetryable;
using wfedit::RunConnectWithRetry;

#define CHECK(cond, msg)                                                       \
    do {                                                                       \
        if (!(cond)) {                                                         \
            std::fprintf(stderr, "connect_retry_test: FAIL %s (%s:%d)\n",      \
                         (msg), __FILE__, __LINE__);                           \
            return 1;                                                          \
        }                                                                      \
    } while (0)

namespace {

// A deterministic driver: a fake monotonic clock advanced by the injected
// sleep_s (so backoff is instant in the test), plus a scripted sequence of
// ConnectAttempt results that try_once pops one at a time. Once the script is
// exhausted it repeats its last entry forever (models "keeps failing the same
// way") so the budget / abort paths terminate the loop, not the script.
struct Driver {
    double clock = 0.0;
    std::vector<ConnectAttempt> script;
    int calls = 0;

    double now() { return clock; }
    void sleep(double s) { clock += s; }
    ConnectAttempt try_once() {
        const ConnectAttempt r = script[calls < (int)script.size() ? calls
                                                                    : (int)script.size() - 1];
        ++calls;
        return r;
    }
};

ConnectAttempt ok()                 { return { true,  ConnectError::NoError }; }
ConnectAttempt fail(ConnectError e) { return { false, e }; }

// 1. Transient failures (Cloudflare 530 ×3) then success → connects, 4 attempts.
int test_retry_until_success() {
    Driver d{ 0.0, { fail(ConnectError::HttpServerError),
                     fail(ConnectError::HttpServerError),
                     fail(ConnectError::HttpServerError),
                     ok() }, 0 };
    std::atomic<int> attempt{0};
    const ConnectOutcome out = RunConnectWithRetry(/*budget=*/30.0,
        [&]{ return d.try_once(); }, [&]{ return d.now(); },
        [&](double s){ d.sleep(s); }, []{ return false; }, &attempt);
    CHECK(out.ok, "should connect after transient failures");
    CHECK(out.attempts == 4, "should take exactly 4 attempts");
    CHECK(attempt.load() == 4, "attempt counter should reach 4");
    return 0;
}

// 2. NXDOMAIN → fail fast on attempt 1 (does NOT burn the budget). This is the
//    crux of critique ④: a bad host used to be retried for the whole window.
int test_dns_fatal_fails_fast() {
    Driver d{ 0.0, { fail(ConnectError::DnsFatal) }, 0 };
    const ConnectOutcome out = RunConnectWithRetry(/*budget=*/45.0,
        [&]{ return d.try_once(); }, [&]{ return d.now(); },
        [&](double s){ d.sleep(s); }, []{ return false; });
    CHECK(!out.ok, "NXDOMAIN should fail");
    CHECK(out.attempts == 1, "NXDOMAIN should fail fast (1 attempt)");
    CHECK(out.err == ConnectError::DnsFatal, "error preserved");
    CHECK(d.clock == 0.0, "must not have slept/burned the budget");
    return 0;
}

// 3. A definitive 4xx upgrade rejection → fail fast on attempt 1.
int test_http_client_error_fails_fast() {
    Driver d{ 0.0, { fail(ConnectError::HttpClientError) }, 0 };
    const ConnectOutcome out = RunConnectWithRetry(/*budget=*/45.0,
        [&]{ return d.try_once(); }, [&]{ return d.now(); },
        [&](double s){ d.sleep(s); }, []{ return false; });
    CHECK(!out.ok && out.attempts == 1, "4xx should fail fast");
    return 0;
}

// 4. A host that's always 530 + a finite budget → gives up, budget honoured,
//    attempt count bounded (doesn't loop forever).
int test_budget_honoured() {
    Driver d{ 0.0, { fail(ConnectError::HttpServerError) }, 0 };
    const ConnectOutcome out = RunConnectWithRetry(/*budget=*/10.0,
        [&]{ return d.try_once(); }, [&]{ return d.now(); },
        [&](double s){ d.sleep(s); }, []{ return false; });
    CHECK(!out.ok, "should give up when budget runs out");
    CHECK(out.err == ConnectError::HttpServerError, "last error preserved");
    CHECK(d.clock >= 10.0, "should have consumed the budget");
    CHECK(out.attempts >= 5 && out.attempts <= 12, "attempt count bounded by budget/backoff");
    return 0;
}

// 5. Abort (window close / shutdown) flips true after 2 attempts → exits
//    promptly rather than running the budget out. Models the close-button (③)
//    and the reconnect-shutdown seam.
int test_abort_exits_promptly() {
    Driver d{ 0.0, { fail(ConnectError::Refused) }, 0 };
    int aborts = 0;
    const ConnectOutcome out = RunConnectWithRetry(/*budget=*/0.0 /*unlimited*/,
        [&]{ return d.try_once(); }, [&]{ return d.now(); },
        [&](double s){ d.sleep(s); },
        [&]{ return ++aborts > 4; });   // becomes true partway through
    CHECK(!out.ok, "aborted connect should report failure");
    CHECK(out.attempts <= 3, "should stop within a couple attempts of the abort");
    return 0;
}

// 6. IsRetryable truth table — pins the fail-fast vs retry classification.
int test_is_retryable_table() {
    CHECK(IsRetryable(ConnectError::DnsTemporary),    "EAI_AGAIN retryable");
    CHECK(IsRetryable(ConnectError::Refused),         "ECONNREFUSED retryable");
    CHECK(IsRetryable(ConnectError::Unreachable),     "unreachable retryable");
    CHECK(IsRetryable(ConnectError::Timeout),         "timeout retryable");
    CHECK(IsRetryable(ConnectError::HttpServerError),  "5xx retryable");
    CHECK(IsRetryable(ConnectError::UpgradeFailed),   "upgrade-failed retryable");
    CHECK(IsRetryable(ConnectError::Tls),             "tls retryable");
    CHECK(!IsRetryable(ConnectError::DnsFatal),       "NXDOMAIN fail-fast");
    CHECK(!IsRetryable(ConnectError::HttpClientError), "4xx fail-fast");
    CHECK(!IsRetryable(ConnectError::Other),          "other fail-fast");
    CHECK(!IsRetryable(ConnectError::NoError),           "none not retryable");
    return 0;
}

}  // namespace

int main() {
    int rc = 0;
    rc |= test_retry_until_success();
    rc |= test_dns_fatal_fails_fast();
    rc |= test_http_client_error_fails_fast();
    rc |= test_budget_honoured();
    rc |= test_abort_exits_promptly();
    rc |= test_is_retryable_table();
    if (rc == 0)
        std::printf("connect_retry_test: OK (6/6 tests passed)\n");
    return rc;
}
