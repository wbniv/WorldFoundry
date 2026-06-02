# Plan — Implement the relay-connect critique's recommendations

## Context

The [2026-06-01 relay-connect critique](../investigations/2026-06-01-resilient-retry-plan-critique.md)
is a self-post-mortem of the "resilient retry" plan shipped in `17b1fda4`. It
found the retry centerpiece to be the weakest part of the work and listed six
recommendations. The user has chosen the **full set including mid-session
reconnect**. This plan implements every recommendation that is codeable here:

| # | Recommendation | This plan |
|---|----------------|-----------|
| ③ | Fix the close-button bug (the one outright defect) | **Phase 1** |
| ② / ④-class | Trim joiner budget 45→15 s + classify failures (NXDOMAIN/4xx fail fast) | **Phase 1** |
| ⑧ | Name the magic numbers | **Phase 1** |
| ⑤(reconnect) | Mid-session reconnect after a relay drop | **Phase 2** |
| ⑦ | Fault-injection regression test for the connector loop | **Phase 3** |
| ① / ⑥(verify) | Keep Fix 1 but correct its over-claimed verification | **Phase 4** (doc) |
| named-tunnel | Adopt the named tunnel for durable hosting | **Phase 4** (follow-up doc only — live-verification needs the user's Cloudflare account, can't be CI'd) |

**Not changed:** Fix 1 itself (host loopback connect, `kRelayPort`,
`connect_url`/`ctx_relay_url` split) is architecturally correct and stays as-is —
only its *verification wording* is corrected.

The throughline of the design: the existing connect logic is an inline lambda in
`main()` that's impossible to unit-test and collapses every failure to `bool`.
We extract a **pure, seam-injected retry policy** (`connect_retry.h`) and teach
`WsClient` to report *why* a connect failed. That single refactor makes the
close-button fix, the failure classification, the reconnect loop, and the test
all fall out cleanly.

## Phase 0 — Mirror this plan into the repo

Per project convention (plans live in `docs/plans/` and are rendered), the first
action is to copy this plan to
`docs/plans/2026-06-01-relay-connect-critique-remediation.md`, then
`task md -- docs/plans/2026-06-01-relay-connect-critique-remediation.md` and
xdg-open the HTML. Commit it with Phase 1's code.

## Phase 1 — Connect policy + failure classification + budget trim + close-button (②③⑧)

### 1a. New header `engine/wf_edit/connect_retry.h` (dependency-free, header-only)

```cpp
#pragma once
#include <atomic>
#include <algorithm>
namespace wfedit {

enum class ConnectError {
    None,
    DnsFatal,        // getaddrinfo EAI_NONAME/EAI_NODATA/EAI_FAIL — bad host, fail fast
    DnsTemporary,    // EAI_AGAIN — resolver busy, retry
    Refused,         // ECONNREFUSED — retry (relay/tunnel not up yet)
    Unreachable,     // ENETUNREACH/EHOSTUNREACH — retry (network settling)
    Timeout,         // ETIMEDOUT / recv timeout — retry
    HttpServerError, // 5xx incl. Cloudflare 530/502 — retry (tunnel warming)
    HttpClientError, // any other non-101 status (4xx/3xx) — definitive, fail fast
    UpgradeFailed,   // peer closed mid-upgrade (recv<=0) — retry
    Tls,             // TLS handshake failed — retry (edge not ready)
    Other,           // malformed URL, socket()/send() error — fail fast
};

inline bool IsRetryable(ConnectError e) {
    switch (e) {
        case ConnectError::DnsTemporary: case ConnectError::Refused:
        case ConnectError::Unreachable:  case ConnectError::Timeout:
        case ConnectError::HttpServerError: case ConnectError::UpgradeFailed:
        case ConnectError::Tls:
            return true;
        default:                          // DnsFatal, HttpClientError, Other, None
            return false;
    }
}

struct ConnectAttempt { bool ok; ConnectError err; };
struct ConnectOutcome { bool ok; ConnectError err; int attempts; };

// Pure retry policy. Seams (try_once/now/sleep_s/aborted) are injected so the
// loop is unit-testable with a fake clock and a scripted connector.
//   budget <= 0  ⇒ unlimited (retry transient failures until ok/fail-fast/abort)
template <class TryFn, class NowFn, class SleepFn, class AbortFn>
ConnectOutcome RunConnectWithRetry(double budget, TryFn try_once, NowFn now,
                                   SleepFn sleep_s, AbortFn aborted,
                                   std::atomic<int>* attempt_out = nullptr) {
    const double t0 = now();
    for (int attempt = 0; ; ++attempt) {
        if (attempt_out) attempt_out->store(attempt + 1);
        if (aborted()) return { false, ConnectError::None, attempt };
        const ConnectAttempt r = try_once();
        if (r.ok)               return { true,  ConnectError::None, attempt + 1 };
        if (!IsRetryable(r.err))return { false, r.err, attempt + 1 };   // fail fast
        if (budget > 0 && now() - t0 >= budget)
                                return { false, r.err, attempt + 1 };   // budget spent
        if (aborted())          return { false, r.err, attempt + 1 };
        sleep_s(std::min(3.0, 1.0 + 0.5 * attempt));                    // 1.0,1.5,…,3.0 s
    }
}
}  // namespace wfedit
```

### 1b. Teach `WsClient` to report the failure cause

- `ws_client.h`: `#include "connect_retry.h"`; add private `ConnectError _last_error = ConnectError::None;` and public `ConnectError lastError() const { return _last_error; }`.
- `ws_client.cc` `connect()` — set `_last_error` at each existing failure return (keep the stderr logging — see memory: keep instrumentation):
  - `parseWsUrl` fail → `Other`.
  - Capture `int gai = getaddrinfo(...)`; on non-zero → `gai == EAI_AGAIN ? DnsTemporary : DnsFatal`.
  - `::connect()` loop exhausted (`_fd < 0`) → map last `errno`: `ECONNREFUSED→Refused`, `ETIMEDOUT→Timeout`, `ENETUNREACH/EHOSTUNREACH→Unreachable`, else `Other`.
  - TLS failures (lines 134/137/140) → `Tls`.
  - upgrade `recv<=0` (line 182) → `UpgradeFailed`.
  - **Status parse (replace the `strstr(buf, "101")` at line 191)** — parse the real status line so a stray "101" in a header can't false-match and so we can classify: `int code=0; std::sscanf(buf, "HTTP/%*d.%*d %d", &code);` then `code==101`→continue; `code/100==5`→`HttpServerError`; else→`HttpClientError`. (Fixes a latent `strstr`-anywhere bug too.)
  - On success → `_last_error = None`.
- *(Optional hardening, fold in here)* set `SO_RCVTIMEO` (~5 s) on the socket before the upgrade read and use a non-blocking `::connect` + `select` with a ~5 s cap, so one black-hole attempt can't eat the whole budget or stall the abort-join. Clearly labelled; cuttable if the user considers it scope creep.

### 1c. Rewire the initial connector + fix the close button (`main.cc` ~3088–3121)

- Add near `kRelayPort` (line 94): `static constexpr double kHostConnectBudgetSec = 8.0;` and `static constexpr double kJoinerConnectBudgetSec = 15.0;` (was 45 — ⑧ + ②). Replace the inaccurate "15–30 s warm-up" comment block (3095–3100) with the critique's finding (530 we saw meant *down*; 15 s covers a plausible warm-up without punishing a dead host; fail-fast handles definitive errors) and a link to the critique doc.
- Add `std::atomic<bool> cabort{false};` alongside `cstate`/`cattempt`.
- Replace the hand-rolled `for` loop in the connector thread with `RunConnectWithRetry`:
  ```cpp
  const double budget = host_tunnel ? kHostConnectBudgetSec : kJoinerConnectBudgetSec;
  auto outcome = RunConnectWithRetry(budget,
      [&]{ const bool ok = ctx.relay_client.connect(connect_url.c_str());
           return wfedit::ConnectAttempt{ ok, ok ? wfedit::ConnectError::None
                                                  : ctx.relay_client.lastError() }; },
      []{ return glfwGetTime(); },
      [](double s){ const struct timespec ts{(time_t)s,(long)((s-(long)s)*1e9)}; nanosleep(&ts,nullptr); },
      [&]{ return cabort.load(); }, &cattempt);
  cstate.store(outcome.ok ? 1 : 2);
  ```
- **Close-button fix (③):** guard the pump loop and act on the close flag:
  ```cpp
  while (cstate.load() == 0 && !glfwWindowShouldClose(win)) pump(m.c_str());
  if (cstate.load() == 0) cabort.store(true);   // user clicked X → tell connector to bail
  connector.join();                              // safe: connector also checks cabort
  if (glfwWindowShouldClose(win)) { /* clean teardown + */ return 0; }  // launch cancelled
  ```
  This stops the spin the instant the window's X is clicked (the defect), tells the connector to abort at its next seam, joins it, and exits cleanly. (The modal is an ImGui window with no close button, so `glfwWindowShouldClose` can only be the real window's X.)

## Phase 2 — Mid-session reconnect (④)

The initial connect is single-threaded (before the engine loop). Mid-session,
the editor runs per-frame callbacks and the relay is serviced by `CollabDrain`
(main.cc:544). A drop must be handled without (a) stalling the frame loop or
(b) racing `relay_client`/`doc` between threads. Design: a background thread
owns `relay_client` **only** while reconnecting; the main thread never touches
`relay_client` during that window; the main thread re-joins the room (which
makes the relay push a fresh SYNC that the *existing* `CollabDrain` path
applies — no new doc-mutation code, no doc race).

### 2a. `EditorCtx` fields (main.cc ~354–359)

```cpp
std::string         relay_connect_url;             // loopback-or-public target, for reconnect
bool                relay_was_connected = false;    // latch: only reconnect after a real connect
std::atomic<bool>   relay_reconnecting{false};
std::atomic<int>    relay_reconnect_done{0};        // 0=running 1=ok 2=fatal 3=shutdown
std::atomic<bool>   relay_shutdown{false};          // abort seam for the reconnect thread
bool                relay_reconnect_abandoned = false; // fatal classification → stop auto-retry
std::thread         relay_reconnect_thread;
```

### 2b. Serialize relay access behind one predicate

Add `static inline bool RelayUsable(EditorCtx* c){ return c->relay_client.connected() && !c->relay_reconnecting.load(); }` and replace the `relay_client.connected()` guards at **545, 1379, 1597, 2011** with `RelayUsable(c)`; add `if (c->relay_reconnecting.load()) return;` to the `observeUpdates` send callback (3157). Result: while reconnecting, the main thread issues zero `relay_client` calls; the bg thread has exclusive ownership.

### 2c. `ServiceRelayReconnect(EditorCtx* c)` — called each frame right before `CollabDrain(c)`

```cpp
void ServiceRelayReconnect(EditorCtx* c) {
    if (c->relay_connect_url.empty() || c->relay_reconnect_abandoned) return;
    if (c->relay_reconnecting.load()) {                 // an attempt is in flight
        const int done = c->relay_reconnect_done.load();
        if (done == 0) return;
        if (c->relay_reconnect_thread.joinable()) c->relay_reconnect_thread.join();
        c->relay_reconnecting.store(false);
        if (done == 1) { SendRoomJoin(c); /* relay re-pushes SYNC; CollabDrain applies it */
                         std::printf("wf-edit: relay reconnected, re-joined room=%s\n", c->room_id.c_str()); }
        else if (done == 2) { c->relay_reconnect_abandoned = true;
                         std::fprintf(stderr, "wf-edit: relay reconnect abandoned (fatal)\n"); }
        return;
    }
    if (c->relay_was_connected && !c->relay_client.connected()) {   // genuine mid-session drop
        c->relay_reconnecting.store(true); c->relay_reconnect_done.store(0);
        c->relay_reconnect_thread = std::thread([c]{
            auto out = wfedit::RunConnectWithRetry(/*budget*/0.0 /*unlimited*/,
                [c]{ const bool ok = c->relay_client.connect(c->relay_connect_url.c_str());
                     return wfedit::ConnectAttempt{ ok, ok ? wfedit::ConnectError::None
                                                           : c->relay_client.lastError() }; },
                []{ return glfwGetTime(); },
                [](double s){ const struct timespec ts{(time_t)s,(long)((s-(long)s)*1e9)}; nanosleep(&ts,nullptr); },
                [c]{ return c->relay_shutdown.load(); });
            c->relay_reconnect_done.store(c->relay_shutdown.load() ? 3 : (out.ok ? 1 : 2));
        });
    }
}
```

- `SendRoomJoin(EditorCtx*)`: factor the existing CONTROL-join frame builder (main.cc:3124–3130) into a helper reused by both initial connect and reconnect.
- Set `c->relay_connect_url = connect_url;` and `c->relay_was_connected = true;` in the initial `cstate==1` success branch (~3123).
- **Teardown** (after `HALStart` returns, ~3217): `ctx.relay_shutdown.store(true); if (ctx.relay_reconnect_thread.joinable()) ctx.relay_reconnect_thread.join();` before `ctx` destructs.
- Update the now-stale comment in `collab_panel.cc:66` ("one-shot at startup with no reconnect").

## Phase 3 — Fault-injection regression test (⑦)

New `engine/wf_edit/connect_retry_test.cc` — standalone, header-only (`#include "connect_retry.h"`), no GL/link deps. Uses the `wfcrdt_wrapper_test.cc` `CHECK` style. A scripted `try_once` returns a fixed sequence; a fake clock is a captured `double` that the injected `sleep_s` advances (deterministic, instant). Cases:

1. `HttpServerError ×3` then `ok` → `outcome.ok`, `attempts==4`.
2. `DnsFatal` once → `!ok`, **`attempts==1`** (failed fast, did *not* burn the budget).
3. `HttpClientError` (404) once → `!ok`, `attempts==1`.
4. `HttpServerError` forever + finite budget → `!ok`, terminates, `attempts` bounded by budget/backoff.
5. `aborted()` flips true after 2 attempts → `!ok`, exits promptly (close-button / shutdown path).
6. `IsRetryable` truth table (every enum value).

CMake (inside `if(WF_ENABLE_EDITOR)`, near line 1169):
```cmake
add_executable(connect_retry_test engine/wf_edit/connect_retry_test.cc)
target_include_directories(connect_retry_test PRIVATE ${CMAKE_SOURCE_DIR}/engine/wf_edit)
add_test(NAME wf_edit_connect_retry COMMAND connect_retry_test)
```
Add `connect_retry_test` to the `build-editor` task's `cmake --build … --target` list and run it after `wfcrdt_wrapper_test` (Taskfile.yml ~69–72) so it runs in the normal editor build flow.

## Phase 4 — Doc corrections + status sync (①/⑥-verify + ⑤ follow-up)

- **`docs/plans/2026-06-01-relay-connect-localhost-and-resilient-retry.md`:**
  - Step 2 verdict: `**PASS (host presence confirmed)**` → **`OBSERVED — host presence confirmed; loopback causal effect UNconfirmed`** (the `relay connected ws://127.0.0.1:9900` log line was never captured; host ran a binary we never built).
  - Fix 2 section + Step 3: note the retry path was **never exercised end-to-end**, and that the budget is now trimmed 45→15 s with fail-fast classification per the critique; link to this remediation plan.
  - Summary line `1–2 PASS, 3–5 OPEN` → `1 PASS; 2 OBSERVED (causal unconfirmed); Fix 2 revised per critique; 3–5 OPEN`.
- **Critique doc Status** (lines 80–82): note the remediation landed (close-button, trim+classify, reconnect, test) and link the new plan.
- **`docs/plans/2026-05-30-quick-tunnel-named-tunnel.md`:** confirm the `03dc866c`→`cc07da17` provenance fix is present (it is, per exploration); add a short **"Live-verification checklist"** the user runs against a real Cloudflare account (set `WF_COLLAB_TUNNEL_TOKEN` + `WF_COLLAB_TUNNEL_HOSTNAME`, host, join from a second machine, confirm `relay connected wss://<stable-host>` with no 530) — this is recommendation ⑤'s only remaining work and it's the user's to run.
- **`wf-status.md`:** prepend a one-sentence reverse-chron summary row + sync this plan's Status (per status conventions).
- **`TODO.md`:** update the `[verify]` line for the original relay plan to point at the revised verification + remaining open items (don't mark verified).

## Verification

1. **Build:** `task build-editor` (or `task build-wf-edit-fast` for the non-ASan editor). Confirm the binary mtime advanced: `ls -la build-editor/wf-edit` (per memory — pipe-through-grep hides failures).
2. **Automated (the core proof of ②⑥⑦):** `./cmake-build-editor/engine/wf_edit/connect_retry_test` → all CHECKs pass, including `attempts==1` on the fail-fast cases. This is the regression guard the critique asked for.
3. **Close-button (③), manual:** launch a joiner against a dead host — `./build-editor/wf-edit --url=wfedit://no-such-host.invalid:443/r/x` — and click the window's X while "Connecting… (attempt N)" is showing. The window must close *immediately* (not after 15 s). Record an mp4 (engine `-record_video` per memory) into `tests/recordings/`.
4. **Reconnect (④), manual two-instance:** host + joiner on one box over a quick tunnel; once both are 🟢, `pkill cloudflared` (or kill the relay) → both go 🔴; restart it → indicator returns 🟢 and an edit on one side appears on the other (re-SYNC worked). Screenshot the 🔴→🟢 transition (memory: screenshots are the user's only proof) + an mp4.
5. **No regression to the happy path:** a normal host/join still connects on attempt 1 and co-edits (the existing `wf_edit_*` ctests + a manual two-instance edit).

## Commit plan

One commit per phase (memory: commit after each phase; docs with the code they
describe). Phase 0's `docs/plans/` doc rides with Phase 1. Phase 4's doc edits
are their own commit. End commit messages with the required Co-Authored-By line.
