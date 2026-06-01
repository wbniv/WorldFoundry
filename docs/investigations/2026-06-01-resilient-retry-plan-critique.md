# Investigation — Critique of the relay-connect "resilient retry" plan

**Date:** 2026-06-01
**Subject:** [`docs/plans/2026-06-01-relay-connect-localhost-and-resilient-retry.md`](../plans/2026-06-01-relay-connect-localhost-and-resilient-retry.md)
**Shipped in:** [`17b1fda4`](https://github.com/wbniv/WorldFoundry/commit/17b1fda4) (Fix 1 + Fix 2), with [`9d90496d`](https://github.com/wbniv/WorldFoundry/commit/9d90496d) (connection indicator), [`d46c7cda`](https://github.com/wbniv/WorldFoundry/commit/d46c7cda) (static ASan), [`b0e04eee`](https://github.com/wbniv/WorldFoundry/commit/b0e04eee) (`build-wf-edit-fast`)
**Prompted by:** a long live two-machine debugging session on 2026-06-01 whose findings undercut the plan's premise.

## Why this doc

The plan was written *early* in the session, before we had the real evidence. By the end of the session we'd established the actual failure modes — and several of them are not what the plan assumed. This is the honest post-mortem: what the evidence really showed, what in the plan holds up, and what doesn't. The plan's author and the critic are the same agent; this is deliberately self-critical.

## TL;DR verdict

- **Fix 1 (host connects to its own relay over `ws://127.0.0.1:kRelayPort`): keep.** Architecturally correct regardless of whether it measurably changed behavior. Low risk.
- **Fix 2 (time-budget + backoff "resilient retry", host 8 s / joiner 45 s): questionable.** Built on a premise (quick-tunnel "warm-up 530 window") we never actually confirmed; ships a real close-button regression; makes the *common* failure (dead tunnel) slower; retries fatal errors pointlessly; targets startup when the recurring failure was mid-session drop; and is **largely mooted by the named tunnel** (which has no warm-up window).
- **The plan over-claims its own verification** (steps 1–2 PASS).
- The genuinely valuable artifact from the whole effort was the **connection indicator**, not the retry.

## Empirical findings from the session (the evidence base)

All via the vendored raw-WS probe ([`wftools/wf_collab/probe_relay.py`](../../wftools/wf_collab/probe_relay.py)) and `gdb`/`/proc` against live editors.

1. **Host self-join works.** Across three sessions the host editor held steady ~9–10 Hz presence in its own room (e.g. 307 frames / 35 s, then 498 / 55 s). It was *absent* in the earliest sessions — so something changed — **but the host ran on a different machine, on a binary this agent never built**, so the improvement cannot be causally attributed to Fix 1.
2. **Joiner connect works when the tunnel is up.** A real terminal launch printed `wf-edit: relay connected wss://…`. A raw Python WS client connected first-try (`101` + SYNC) whenever the tunnel served.
3. **`530` meant the tunnel was *down*, not warming up.** In the `studio-8907` run the editor logged `530 ×4`; an immediate `curl` returned **530 six-for-six**. The connector was gone, not mid-warm-up.
4. **OOM, not connect failure, killed several joiners.** The Debug **ASan** editor (~700 MB RSS ×2) on a **16 GB** machine (2×8 GB SODIMM; OS sees ~14.4 GB after iGPU reservation — *not* 32 GB, no missing stick) with swap exhausted → the OOM killer SIGKILLed the editor mid-startup (`Killed` right after `collab room … started`). `/proc/vmstat` `oom_kill` confirmed. Fixed by the non-ASan `build-wf-edit-fast`.
5. **An apparent "hang" was a Mesa/XWayland render stall, not collab.** A `gdb` backtrace of a "Not Responding" joiner showed the **main thread blocked in `Display::RenderBegin` (`wfsource/source/gfx/gl/display.cc:796` `glClear`) → Mesa `loader_dri3_get_buffers` → `xcb_wait_for_special_event` → `poll`** — DRI3 back-buffer acquisition stalling under XWayland (Wayland session, `DISPLAY=:0`). It *eventually* resolves; it is unrelated to the relay/connect/WebRTC code. (My intermediate "WebRTC SDP-offer deadlock" hypothesis was **wrong** — the backtrace killed it.)

The throughline: **every joiner failure we saw was an environment issue (OOM, XWayland, dead tunnel), never the connect logic per se.**

## What holds up in the plan

- **Fix 1** — the host should never reach its own loopback relay by round-tripping through the public Cloudflare edge. Connecting via `ws://127.0.0.1:kRelayPort` is the right design and removes a real fragility (and the warm-up race for the *host's own* join). Correct even though we couldn't isolate its causal effect.
- **`kRelayPort` constant** — good DRY; replaced two magic `9900`s.
- **`connect_url` vs `ctx_relay_url` split** — connecting target differs from the public address used for the share link + recent-rooms; clean.
- **The connection indicator** (sibling commit) — the actually-valuable outcome; makes a failed/absent connection *visible*, which was the original "I can't tell if it connected" problem.

## Substantive critiques (severity-tagged)

**① [High] Fix 2's premise is unconfirmed.** The plan justifies the 45 s budget with a "quick tunnels 530 for 15–30 s after the URL appears" warm-up window. Our evidence (finding 3) shows the `530`s were a *down* tunnel, and the successful runs connected on attempt 1 against an *up* tunnel. We **never observed the warm-up window** the retry is designed to ride out. The "15–30 s" figure is asserted, not measured.

**② [High] The long budget penalizes the common failure.** The failure we hit *repeatedly* was a dead/dropped tunnel. Old behavior: fail in ~8 s. New behavior: the user watches "Connecting… (attempt N)" for **45 s** before giving up. We slowed the real case to (maybe) help a hypothetical one. The plan's "Risks" hand-waves this as "Acceptable"; the session says otherwise.

**③ [High] The connect-wait loop ignores the close button — a real regression.**
```cpp
while (cstate.load() == 0) {
    const std::string m = connecting_msg + "  (attempt " + std::to_string(cattempt.load()) + ")";
    pump(m.c_str());                 // pump() runs glfwPollEvents (sets the close flag)…
}                                    // …but nothing checks glfwWindowShouldClose(win)
```
The close flag is *set* by `pump()` but never acted on, so **for up to 45 s the window cannot be closed** — which presents as exactly the "Not Responding" freeze that dogged the session. At the old 8 s this was a blip; at 45 s it's a "can't kill this window" bug. Fix: `while (cstate.load()==0 && !glfwWindowShouldClose(win)) pump(...);` and treat a close as abort.

**④ [Med] All failures are retried identically.** The plan deliberately doesn't classify ("the time budget makes the distinction unnecessary"). But a well-formed URL with a bad host → `getaddrinfo` NXDOMAIN → `connect()` returns false → **retried the full budget for nothing**. Only `530`/`502`/`ECONNREFUSED`/timeout are worth retrying; DNS-NXDOMAIN and definitive non-101 HTTP should fail fast. (Malformed `wfedit://` URLs *are* already short-circuited — `ParseWfeditUrl` fails at arg-parse time so the connect block never runs — but post-parse resolution failures are not.)

**⑤ [Med] Wrong layer: the recurring failure was mid-session drop.** Fix 2 is startup-only ("reconnect-after-drop is a separate plan"). But tunnels died *mid-session* repeatedly; a connected joiner whose tunnel dies just goes 🔴 and sits there with no reconnect. A small reconnect-on-drop would have helped this session more than the startup retry did.

**⑥ [Med] Verification over-claims.**
- Fix 1's "PASS" infers host self-join works *because of* the localhost change, but the host ran a binary we never built and we never saw `relay connected ws://127.0.0.1:9900` in a host log. Presence in the room is real; the *causal attribution* is not. Should read "observed; causal effect unconfirmed."
- Fix 2's retry path was **never exercised end-to-end** — every run connected on attempt 1 or died (OOM/stall) before the budget mattered.

**⑦ [Low] No regression test for the connector loop.** Per our own regression-guard rule, there's no test that fault-injects a failing `connect()` and asserts backoff + budget + fatal-fast. Achievable with a stub `WsClient`.

**⑧ [Low] Magic numbers unexplained.** 8 s / 45 s / backoff `min(3, 1+0.5·n)` are reasonable but unmotivated by data.

## The reframe the named tunnel forces

[`docs/plans/2026-05-30-quick-tunnel-named-tunnel.md`](../plans/2026-05-30-quick-tunnel-named-tunnel.md) (DONE, [`03dc866c`](https://github.com/wbniv/WorldFoundry/commit/03dc866c)) gives an opt-in **stable, pre-resolved, always-up hostname** (`tunnel_token` + `tunnel_hostname` → `cloudflared tunnel run --token`). A named tunnel has **no warm-up `530` window** — so for the durable/team path you actually want, **Fix 2's entire rationale evaporates.** The resilient retry was hardening the *throwaway* quick-tunnel path while the real fix (named tunnel) was already implemented and unused. Effort was misallocated.

## Recommended changes

1. **Trim Fix 2:** joiner budget ~15 s (covers a real warm-up, doesn't punish a dead host for 45 s); **classify failures** (④) so NXDOMAIN/4xx fail fast.
2. **Fix the close-button bug** (③) — the one outright defect. Break the wait loop on `glfwWindowShouldClose` and abort the launch cleanly.
3. **Keep Fix 1**, but **correct its verification** to "observed, not causally isolated."
4. **Add mid-session reconnect** (⑤) as the higher-value follow-up; this matches the failure we actually saw.
5. **Adopt the named tunnel** for durable hosting; treat the quick-tunnel retry as best-effort, not a centerpiece.
6. Add a **fault-injection test** for the connector loop (⑦).

## Status

Shipped and standing: connection indicator, `kRelayPort`, Fix 1, static-linked ASan, `build-wf-edit-fast`. Verified working: **host self-join** (observed) and **joiner connect over `wss://`** (observed `relay connected`). Open / recommended above: trim Fix 2, fix the close-button loop, mid-session reconnect, named-tunnel adoption, connector test. None of the open items block normal use; they improve a path the named tunnel will mostly supersede.
