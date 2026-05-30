# Plan — wf-edit quick-tunnel: robust "Host a call" over a VPN

**Date:** 2026-05-27
**Status:** **Phases 1, 2, 2b DONE + live 2-editor verification DONE (2026-05-27 → 2026-05-30,
`94976b25` `4ffd098a`)** — the editor's relay connects over the Surfshark VPN (`relay connected
wss://…trycloudflare.com`) and the window stays responsive throughout the connect: the blocking
`relay_client.connect()` + retries + SYNC wait now run on a `std::thread` while the main thread
pumps a "Connecting to room…" frame (no WM "not responding", window stays draggable). **Verified
live** with two editors (distinct `XDG_CONFIG_HOME` → distinct `peer_id`s) joining a room over the
public `wfedit+s://…trycloudflare.com` link: mutual presence + WebRTC PeerConnection + an edit by
a third "mover" peer propagated to both editors live through the relay. Two-computer recipe added
to the wf-edit manual. **Phase 3 (named tunnel) remains.** Open follow-up: a post-connect engine
`terminate` after a long stretch of "delta too large" frames (engine timing under ASan + long
session), unrelated to the connect path.
**Parent:** [Phase 4 — quick-tunnel reachability](2026-05-27-webrtc-phase4-quick-tunnel-reachability.md)
**Builds on:** [connectivity fixes + build-stale guard](../../engine/wf_edit/main.cc) (`eecee142`)

## Context

Hosting a `wf-edit` call over a Cloudflare quick tunnel **already works over the user's Surfshark
WireGuard VPN** — proven this session: a clean `cloudflared --protocol http2` tunnel registered in
~4 s, DNS resolved, and a real WS upgrade returned `101 Switching Protocols` end-to-end while the
VPN was active. The earlier failures were **not** the VPN blocking it fundamentally:

1. cloudflared defaults to **QUIC (UDP :7844)**, which WireGuard mangles → already fixed/committed
   (`eecee142`): `--protocol http2` forces TCP, which the VPN passes (bare TCP :7844 tested OPEN).
2. **Cloudflare rate-limits account-less quick tunnels** — ~15 were spun up in rapid testing, so
   later ones (incl. one editor run) didn't get DNS published in time. Cumulative, not the VPN, and
   not flaky DNS.

The substantive fix (http2) is in. This plan closes the loop: **verify in the editor over the VPN**,
make failures **degrade gracefully** (so a throttled/blocked tunnel gives an actionable message
instead of a silent 45 s timeout), and add a **rate-limit-free named-tunnel** path for durable use.

Editor code is all in [`engine/wf_edit/main.cc`](../../engine/wf_edit/main.cc) (tunnel helpers
`StartQuickTunnelProcs`/`PollTunnelUrl`/`HostResolves`, the `tunnel_pending` loading loop, and the
relay-connect block) and [`engine/wf_edit/ws_client.cc`](../../engine/wf_edit/ws_client.cc).

## Phase 1 — Verify in the editor over the VPN

Run **Collaborate → Host a call** (`./build-editor/wf-edit --host-tunnel`) once, clean, over the
VPN, and confirm the editor's relay connects — log shows `relay connected …` (`main.cc:~2494`),
not `did not come up` / `relay connect failed`. curl already proved the tunnel path; this is the
in-editor end-to-end proof. If rate-limited, wait for the quota to cool and retry once (expected
after heavy testing, not a defect).

## Phase 2 — Degrade gracefully on slow / throttled / blocked tunnels

- **Surface cloudflared's real reason.** The loading loop prints a generic `did not come up`.
  Before unlinking `tunnel_logpath`, scan it for cloudflared's own signals (`hard_fail=true`,
  `ERROR: Allow outbound …:7844`, `429`/rate-limit, `Registered tunnel connection`) and report the
  specific cause — e.g. *"outbound :7844 blocked (VPN/firewall?)"* or *"Cloudflare rate-limited
  this quick tunnel — wait a minute and retry."* Show the latest status line in the loading panel
  via a new `PollTunnelStatus(logpath)` next to `PollTunnelUrl`.
- **Retry the relay connect.** The collab block does a single `ctx.relay_client.connect()`
  (`main.cc:~2458`). Wrap in a short retry (≈3 attempts, ~1 s apart) so a tunnel whose DNS just
  published / proxy just came ready connects on attempt 2 instead of aborting. `ws_client`'s
  per-step diagnostics (already added) keep failures legible.
- **Tune the resolve gate.** Bump the loading-loop resolve timeout 45 s → 60 s; if cloudflared
  logs `hard_fail=true`, fail fast with the blocked-egress message instead of waiting it out.
- Keep `ws_client::connect`'s step diagnostics (DNS/connect/TLS/HTTP-status) — useful permanent
  error logging.

Touches `engine/wf_edit/main.cc` only (loading loop + collab connect).

## Phase 2b — Keep the window responsive during resolve + connect  *(this is "(a)")*

The progress bar renders, but the WM still flags **"WF Editor is not responding"**: the DNS
resolve (`HostResolves`/getaddrinfo) blocks per call, and worse, the relay `connect()` + its
retries (`sleep(2)` between attempts + the 1 s SYNC wait) run **after** the loading loop with **no
rendering** — so the window freezes for several seconds (screenshot confirmed). It still connects
("Wait" → success); it's a freeze, not a hang.

Fix: move the blocking resolve + relay connect onto a **background `std::thread`** and keep the
loading loop pumping (`glfwPollEvents` + render "Connecting…") while it polls the thread's atomic
status; break + proceed when the thread reports connected/failed. The thread owns the blocking
calls; the main thread only reads an atomic and never touches `relay_client` until the thread is
done + joined (no concurrent access). All in `engine/wf_edit/main.cc` (the `tunnel_pending` loading
loop + the collab/relay-connect block at ~`:2474`). *Fallback if threading is fiddly:* pump a frame
between retries and drop the `sleep(2)` waits — but one attempt's getaddrinfo+TLS+upgrade still
blocks ~1–2 s, so the thread is the robust answer.

## Phase 3 — Rate-limit-free named tunnel (durable path)

Account-less quick tunnels are inherently throttled. Add an opt-in **authenticated Cloudflare
named tunnel** so durable/team use isn't subject to quick-tunnel limits and gets a stable hostname.

- Config: `tunnel_token` in `~/.config/wf-edit/identity.json` + `WF_COLLAB_TUNNEL_TOKEN` env
  (mirrors the existing `turn_*` / `relay_default` slots in `WfeditIdentity`).
- `StartQuickTunnelProcs`: if a token is set, run `cloudflared tunnel run --token <TOKEN>` (stable
  hostname from the user's CF config, no URL scraping); else fall back to the quick tunnel as today.
- Same decision space as the **deferred central relay / hosting** choice (self-host vs managed) —
  design to dovetail; keep opt-in (ships empty, quick tunnel stays the zero-config default). Detail
  further once Phases 1–2 land (needs a CF account + one-time named-tunnel setup — the heaviest piece).

## Verification

- **P1:** editor `--host-tunnel` over the VPN → `relay connected`; bridge a 2nd instance via the
  printed `wfedit+s://…` link if a second machine/network is handy.
- **P2:** force each mode and confirm the message — (a) leave QUIC default / block :7844 →
  "outbound :7844 blocked"; (b) hammer quick tunnels → rate-limit message; (c) slow-publishing
  tunnel still connects via the retry. `task quick-tunnel` exercises the same orchestration headless.
- **P3:** with `tunnel_token` set → named tunnel (stable hostname, no rate limit); with none → quick
  tunnel still works.
- **(b) Two editors locally, distinct identities:** launch host + joiner with separate
  `XDG_CONFIG_HOME` (`/tmp/wfedit-A`, `/tmp/wfedit-B`) so each generates its own `peer_id` (avoids
  the same-`identity.json` collision seen on one box). Confirm **both** `relay connected … room=<r>`
  with *different* peers, the host's Collaborators panel shows the joiner, and dragging an actor in
  one moves it in the other (live CRDT sync over the tunnel). *(Already confirmed both connect to
  the same room over the public link; this adds distinct identities + sync proof.)*
- **(c) Two computers (the real goal):** computer 1 `wf-edit --host-tunnel` → share the printed
  `wfedit+s://…/r/<room>` link; computer 2 (with `wf-edit` built — only the host needs `cloudflared`)
  `wf-edit --url=<link>`. Distinct identities by default → distinct collaborators. Add this recipe
  to the wf-edit manual.

## Notes
- `--protocol http2` (committed) is the load-bearing VPN fix — keep it the default.
- After each editor change, trust the `task build-wf-edit` `✓ wf-edit built` / `BUILD STALE`
  marker (a failed compile leaves a stale binary — see `eecee142`).
