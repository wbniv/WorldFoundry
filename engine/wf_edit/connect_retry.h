// connect_retry.h — pure, seam-injected retry policy for the co-edit relay
// connect.
//
// The editor's relay connect used to be a hand-rolled loop inside main()'s
// connector thread: impossible to unit-test, and it retried *every* failure
// identically (so a bad hostname burned the whole time budget for nothing).
// This header factors the loop out behind injectable seams (try_once / now /
// sleep_s / aborted) so it is deterministically testable with a fake clock and
// a scripted connector, and adds a ConnectError taxonomy so definitive failures
// (NXDOMAIN, a 4xx upgrade) fail fast while transient ones (530/502/refused/
// timeout, a warming Cloudflare tunnel) retry until the budget runs out.
//
// Dependency-free on purpose (only <atomic>/<algorithm>): the test links nothing
// and ws_client.h includes it just for the enum.
//
// Plan: docs/plans/2026-06-01-implement-the-relay-connect-critique-s-recommendat.md

#pragma once

#include <atomic>
#include <algorithm>

namespace wfedit {

// Why a connect attempt failed. Drives the fail-fast-vs-retry decision below;
// also surfaced by WsClient::lastError() so the connector can classify.
// NB: do NOT name a value `None` — X11's <X.h> defines `#define None 0L`, which
// would macro-mangle this enum in any GL/X11 TU (e.g. wf-edit's main.cc).
enum class ConnectError {
    NoError,         // success / no error
    DnsFatal,        // getaddrinfo EAI_NONAME/EAI_NODATA/EAI_FAIL — bad host, never resolves
    DnsTemporary,    // getaddrinfo EAI_AGAIN — resolver busy, worth a retry
    Refused,         // ECONNREFUSED — relay/tunnel not listening yet
    Unreachable,     // ENETUNREACH/EHOSTUNREACH — network still settling
    Timeout,         // ETIMEDOUT / recv timeout — slow path, retry
    HttpServerError, // 5xx incl. Cloudflare 530/502 — quick-tunnel warming, retry
    HttpClientError, // any other non-101 status (4xx/3xx) — definitive rejection, fail fast
    UpgradeFailed,   // peer closed mid-upgrade (recv<=0) — transient, retry
    Tls,             // TLS handshake failed — edge not ready, retry
    Other,           // malformed URL, socket()/send() error — not worth retrying
};

// True for failures that a retry could plausibly clear (a warming tunnel, a
// network coming up). DnsFatal / HttpClientError / Other are definitive — the
// same attempt will keep failing, so we stop immediately instead of waiting out
// the whole budget.
inline bool IsRetryable(ConnectError e) {
    switch (e) {
        case ConnectError::DnsTemporary:
        case ConnectError::Refused:
        case ConnectError::Unreachable:
        case ConnectError::Timeout:
        case ConnectError::HttpServerError:
        case ConnectError::UpgradeFailed:
        case ConnectError::Tls:
            return true;
        case ConnectError::NoError:
        case ConnectError::DnsFatal:
        case ConnectError::HttpClientError:
        case ConnectError::Other:
        default:
            return false;
    }
}

// One connect attempt's result: did it connect, and if not, why.
struct ConnectAttempt { bool ok; ConnectError err; };

// The retry loop's verdict, plus how many attempts it took (the test asserts on
// `attempts` to prove fail-fast didn't burn the budget).
struct ConnectOutcome { bool ok; ConnectError err; int attempts; };

// Run the connect with backoff + fail-fast classification. All side-effecting
// behaviour is injected so the policy itself is pure:
//   try_once() -> ConnectAttempt   perform one blocking connect attempt
//   now()      -> double seconds   monotonic clock (glfwGetTime in production)
//   sleep_s(s)                     sleep for s seconds (nanosleep in production)
//   aborted()  -> bool             user asked to cancel (window close / shutdown)
//   attempt_out                    optional live attempt counter for the UI
//
// `budget` is the wall-clock ceiling in seconds; budget <= 0 means *unlimited*
// (retry transient failures forever — used by mid-session reconnect, which
// bounds itself with the aborted() seam instead).
template <class TryFn, class NowFn, class SleepFn, class AbortFn>
ConnectOutcome RunConnectWithRetry(double budget, TryFn try_once, NowFn now,
                                   SleepFn sleep_s, AbortFn aborted,
                                   std::atomic<int>* attempt_out = nullptr) {
    const double t0 = now();
    for (int attempt = 0; ; ++attempt) {
        if (attempt_out) attempt_out->store(attempt + 1);
        if (aborted()) return { false, ConnectError::NoError, attempt };

        const ConnectAttempt r = try_once();
        if (r.ok)                return { true,  ConnectError::NoError,  attempt + 1 };
        if (!IsRetryable(r.err)) return { false, r.err,               attempt + 1 };  // fail fast
        if (budget > 0.0 && now() - t0 >= budget)
                                 return { false, r.err,               attempt + 1 };  // budget spent
        if (aborted())           return { false, r.err,               attempt + 1 };

        sleep_s(std::min(3.0, 1.0 + 0.5 * attempt));   // backoff: 1.0, 1.5, …, 3.0 s (capped)
    }
}

}  // namespace wfedit
