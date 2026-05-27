# Plan — wf-edit quick-tunnel: robust "Host a call" over a VPN

**Date:** 2026-05-27
**Status:** **Phase 1 DONE + Phase 2 mostly DONE (2026-05-27, `94976b25`)** — the editor's relay
now connects over the Surfshark VPN (verified: `relay connected wss://…trycloudflare.com`). Root
cause was the editor's own premature DNS probe poisoning systemd-resolved's negative cache, not the
VPN. Phase 2 landed the bulk: register-gate (no early probe) + ~4 s propagation grace + post-grace
resolve + connect retry, plus dumping cloudflared's log tail on failure (surfaces blocked-:7844 /
rate-limit reasons) and a phased loading UI. **Phase 3 (named tunnel) remains.**
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

## Notes
- `--protocol http2` (committed) is the load-bearing VPN fix — keep it the default.
- After each editor change, trust the `task build-wf-edit` `✓ wf-edit built` / `BUILD STALE`
  marker (a failed compile leaves a stale binary — see `eecee142`).
