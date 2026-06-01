# Relay connect: host-via-localhost + resilient joiner retry

**Date:** 2026-06-01
**Branch:** `2026-new-level`
**Component:** `engine/wf_edit/main.cc` (editor relay-connect path)
**Related:** [shipped] connection indicator in Collaborators panel ([`9d90496d`](https://github.com/wbniv/WorldFoundry/commit/9d90496d))

## Problem

Live debugging of a two-machine collab session today showed editors silently
failing to join their room while the relay + tunnel were demonstrably healthy.
Captured evidence (not hypothesis):

- A raw Python WebSocket client connects to the quick-tunnel host, completes the
  `101` upgrade, joins the room, and receives the initial `SYNC` — **the relay
  and tunnel work** when the cloudflared connector is up.
- The editor's `WsClient` against the **same** host logged:
  ```
  ws: WS upgrade not accepted by …trycloudflare.com — response: HTTP/1.1 530   (×4)
  wf-edit: relay connect failed: wss://…trycloudflare.com
  collab: started room=studio-8907 …            ← fell back to offline
  ```
- A probe sitting in the room for 25 s saw **zero** presence frames from the
  host editor — i.e. the host never joined **its own** room either.

`530` is Cloudflare error 1033 ("no tunnel connector"). A Cloudflare **quick
tunnel** keeps returning `530` for a warm-up window (commonly 15–30 s) *after*
its `*.trycloudflare.com` URL is printed and DNS resolves. The editor connect
budget is only `4 attempts × 2 s ≈ 8 s` (`main.cc:3054-3057`), so it lands
inside the 530 window, gives up, and runs offline.

## Root causes

1. **The host editor connects to its *own* relay through the public `wss://`
   tunnel** (`main.cc:2921`, `ctx_relay_url = "wss://" + host`). It spawns
   `wf-relay` on `localhost:9900` and `cloudflared`, then round-trips its own
   join out to the Cloudflare edge and back. That round-trip is pointless and
   exposes the host's self-join to the exact tunnel-warm-up race above. The host
   should be *unconditionally present* in its room — it owns the relay.

2. **The joiner's connect budget is too short for quick-tunnel warm-up.**
   `4 × 2 s` does not ride out the 530 window, and the fallback is silent
   (now visible via the shipped indicator, but the connection itself still
   fails when it shouldn't).

## Fixes

Both changes are confined to `engine/wf_edit/main.cc`. No `WsClient` API change
(its only caller is `main.cc:3056`). The relay binds `0.0.0.0:9900`
(`relay.rs:354`), so `ws://127.0.0.1:9900` is always reachable from the host.

### Fix 1 — host joins its own relay over loopback

The relay is spawned at host startup and has been listening for the entire
tunnel-resolve duration (15–30 s+) by the time we connect, so a loopback connect
is instant and cannot hit the 530 race.

Introduce a single relay-port constant and a `connect_url` distinct from the
canonical/public `ctx_relay_url`:

- **Add** near the other file-scope constants:
  ```cpp
  static constexpr int kRelayPort = 9900;   // wf-relay default (relay.rs:13); host loopback target
  ```
  Replace the two `9900` literals at `main.cc:2395` and `main.cc:2516` with
  `kRelayPort` for consistency.

- **Keep** the host resolve block (`main.cc:2920-2923`) as-is — `ctx_relay_url`
  stays the public `wss://host` (used for the share link, the recent-rooms
  entry, and the log line; those *should* show the public address).

- **Derive the connect target** just before the connector thread
  (`main.cc:~3050`):
  ```cpp
  // The host owns the relay (spawned on loopback); connect to it directly
  // rather than round-tripping through the public tunnel, which is subject to
  // the quick-tunnel warm-up 530 race. Joiners use the public URL as before.
  const std::string connect_url =
      host_tunnel ? ("ws://127.0.0.1:" + std::to_string(kRelayPort))
                  : ctx_relay_url;
  ```
  `host_tunnel` is in scope (declared `main.cc:2354`). Covers both the quick
  and named tunnel host paths (both spawn the local relay on `kRelayPort`).

- **Use `connect_url`** in the connector (`main.cc:3056`) instead of
  `ctx_relay_url`. Everything else (CONTROL join, `PushRecentRoom`, the
  `relay connected` log) continues to use `ctx_relay_url`/`room_id`.

### Fix 2 — resilient connect with a time budget + backoff

Replace the fixed `4 × 2 s` loop (`main.cc:3052-3059`) with an elapsed-time
budget and gentle backoff. Any failure (`530`, `502`, connection refused, DNS
not yet propagated) is retried until the budget expires — these are all
transient during tunnel warm-up; a genuinely bad URL simply exhausts the budget.

```cpp
std::atomic<int> cstate{0};        // 0 = connecting, 1 = ok, 2 = failed
std::atomic<int> cattempt{0};      // surfaced in the progress message
std::thread connector([&]{
    // Host connects over loopback (relay already up) → short budget.
    // Joiner must ride out the Cloudflare quick-tunnel warm-up (530 for
    // ~15–30 s after the URL appears) → generous budget.
    const double budget = host_tunnel ? 8.0 : 45.0;
    const double t0 = glfwGetTime();
    bool ok = false;
    for (int attempt = 0; !ok; ++attempt) {
        cattempt.store(attempt + 1);
        ok = ctx.relay_client.connect(connect_url.c_str());
        if (ok) break;
        if (glfwGetTime() - t0 >= budget) break;
        const double back = std::min(3.0, 1.0 + 0.5 * attempt);  // 1.0,1.5,…,3.0 s
        const struct timespec s{ (time_t)back,
                                 (long)((back - (time_t)back) * 1e9) };
        nanosleep(&s, nullptr);
    }
    cstate.store(ok ? 1 : 2);
});
```

Make the pump message show progress during a long warm-up so the user sees it's
working, not hung (`main.cc:3060`):

```cpp
// In the wait loop, rebuild the message each frame from cattempt:
while (cstate.load() == 0) {
    const std::string msg = "Connecting to room " + room_id +
                            "…  (attempt " + std::to_string(cattempt.load()) + ")";
    pump(msg.c_str());
}
```

(`pump` already takes a `const char*`; build the std::string in-loop and pass
`.c_str()`. The fixed `connecting_msg` used afterward for the SYNC wait can stay,
or be reused.)

## Non-goals

- No `WsClient` API/signature change, no reconnect-after-drop logic (the connect
  remains one-shot at startup; mid-session drop recovery is a separate plan).
- No change to the WebRTC/voice/video transport.
- No change to the relay (`relay.rs`).
- Not distinguishing 530 vs 502 vs refused programmatically — the time budget
  makes the distinction unnecessary, and `WsClient` already logs the HTTP status
  for diagnostics.

## Risks / edge cases

- **Port assumption.** If `wf-relay` ever fails to bind `9900` and the host
  proceeds anyway, the loopback connect fails fast and (Fix 2) retries for 8 s
  then falls back offline with the 🔴 indicator — strictly better than today.
- **45 s wait on a truly-bad joiner URL.** The window stays responsive (pump
  loop) and shows the attempt counter; the user can close it. Acceptable.
- **Named-tunnel host.** Still spawns the local relay on `kRelayPort`, so
  loopback applies identically.

## Verification

> Note (updated 2026-06-01): the **Debug + ASan** runtime is now **static-linked**
> into the binary ([`d46c7cda`](https://github.com/wbniv/WorldFoundry/commit/d46c7cda),
> `-static-libasan -static-libubsan`), so the editor launches directly with **no
> `LD_PRELOAD`** — the earlier "ASan runtime does not come first" abort can no
> longer occur (`readelf -d build-editor/wf-edit` shows no asan/ubsan `NEEDED`).
>
> **Partial verification run — 2026-06-01.** Steps 1–2 exercised live against a
> real two-machine session (host on a remote box, probe from this box via the
> vendored `wftools/wf_collab/probe_relay.py` raw-WS client). Steps 3–5 are **open**:
> the joiner-over-public-`wss://` path could not be cleanly tested from the tool
> shell (output buffering + `timeout`-kill + GUI-from-non-interactive-shell noise),
> and live testing ended when the editor was quit. Re-run 3–5 from a real terminal.

1. Build the editor: `task build-wf-edit` → links `build-editor/wf-edit`.

   ```
   ✓ wf-edit built → build-editor/wf-edit (14:03:52, 367085344 bytes)
   readelf -d build-editor/wf-edit | grep -iE 'asan|ubsan'  → (no matches; runtime baked in)
   ./build-editor/wf-edit --frames 20 wflevels/cd.iff:L4    → EXIT=0, no ASan ordering error, no LD_PRELOAD
   ```
   **PASS** — builds, links, launches clean with the runtime embedded.

2. **Host joins its own room over loopback.** Start a host
   (`--host-tunnel`), wait for the share link, then from a second client probe
   the room. The host's own peer must appear (presence within a few seconds of
   the share link showing). Confirm the host log prints
   `wf-edit: relay connected ws://127.0.0.1:9900 room=studio-… (peer …)`.

   ```
   # probe of host tunnel royalty-walls-…/r/studio-5664 (host on remote machine):
   GET https://royalty-walls-…/  → HTTP 502   (connector up, relay reachable)
   [probe] JOIN room=studio-5664 peer=probe-claude
   [probe] PRESENCE from peer_id='ccf9ca2c…' name='Editor (ccf9ca)'   (×307 over 35 s ≈ 9 Hz)
   [probe] SIGNAL (…)   ×7   (host opened WebRTC toward the probe)
   ===== SUMMARY ===== frames: SYNC=1 PRESENCE=307 SIGNAL=7
   OTHER peers in room studio-5664: {'ccf9ca2c…': 'Editor (ccf9ca)'}
   ```
   **PASS (host presence confirmed)** — the host editor is reliably present in its
   own room at the expected ~10 Hz, which it never was before this change (two
   prior sessions, `studio-2781` and `studio-8907`, showed an empty room). Caveat:
   the host's own `relay connected ws://127.0.0.1:9900` log line was not directly
   observed (host ran on a remote machine); presence in the room is the proof.

3. **Joiner rides out quick-tunnel warm-up.** Immediately after the host's
   share link appears (while a plain `GET https://<host>/` may still return
   `530`), launch a joiner with `--url=<share link>`. It must show
   "Connecting…  (attempt N)" climbing, then succeed with
   `wf-edit: relay connected wss://… room=studio-… (peer …)` once the tunnel
   warms up — not fail at ~8 s.

   ```
   OPEN — inconclusive from the tool shell. Two joiner launches against the live
   studio-5664 (host present, tunnel up, GET=502): the editor loaded the level
   and printed up to `collab room 'studio-5664' started` (main.cc:3005), then
   entered the relay-connect block (main.cc:3009). No `relay connected` /
   `relay connect failed` verdict was ever captured (lost to stdout buffering +
   timeout-kill mid-retry), and a concurrent probe saw NO second peer appear in
   ~28 s — i.e. the joiner had not joined within that window. Cannot distinguish
   "real WsClient-vs-quick-tunnel-wss failure" from "harness launch artifact"
   from here. NB: the raw Python probe joins the SAME public wss:// host on the
   first try (101 + SYNC + visible to the host), so the relay/tunnel are fine —
   the open question is specifically the editor's WsClient TLS/upgrade path
   against the Cloudflare edge.
   ```
   **OPEN** — re-run from a real terminal; capture the verdict line + any `ws:`
   lines. If it fails where Python succeeds, open a focused `WsClient` (TLS/SNI/
   HTTP-upgrade vs Cloudflare HTTP/2 edge) investigation.

4. **Two editors see each other.** With host + joiner both connected, each
   editor's Collaborators panel shows a 🟢 connected dot and lists the other
   peer; an edit on one appears on the other.

   ```
   OPEN — blocked on step 3 (no confirmed joiner connection yet).
   ```
   **OPEN.**

5. **Bad URL still fails cleanly.** `--url=wfedit+s://nonexistent.example/r/x`
   shows the attempt counter, exhausts the 45 s budget, logs
   `relay connect failed`, and the panel shows the 🔴 disconnected dot — no hang,
   no crash.

   ```
   OPEN — not yet exercised against the post-fix (45 s budget) build. A pre-fix
   run earlier (studio-8907, old 4×2 s budget) did log `relay connect failed`
   and fall back to offline cleanly on HTTP 530, so the fail-soft path is sound;
   the 45 s-budget timing remains to be confirmed.
   ```
   **OPEN.**

Paste raw output under each step and mark PASS/FAIL before promoting the
`[verify]` TODO item to `[x]`. Current state: **1–2 PASS, 3–5 OPEN.**
