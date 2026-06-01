# Plan — wf-edit Host-a-call: opt-in named tunnel (rate-limit-free, stable hostname)

**Date:** 2026-05-30
**Status:** **DONE 2026-05-30 (`03dc866c`)** — `tunnel_token` + `tunnel_hostname` slots on `WfeditIdentity` (env wins, same precedence as TURN), `StartQuickTunnelProcs` branches on token+hostname → `cloudflared tunnel run --token …` (no scrape), loading loop pre-seeds the host so it skips the *Establishing* phase, share link unchanged in shape. Quick-tunnel regression verified (no token → `starting quick tunnel` → `relay connected wss://…trycloudflare.com`). One-time setup added to the manual. Named-tunnel live verification needs a real CF account (manual smoke test only — cannot be CI'd).
**Parent:** Phase 3 of [docs/plans/2026-05-27-quick-tunnel-vpn-robustness.md](2026-05-27-quick-tunnel-vpn-robustness.md)

## Context

Account-less Cloudflare quick tunnels are inherently rate-limited (Cloudflare per-IP throttling)
and produce an ephemeral `*.trycloudflare.com` hostname that changes every session. That's fine for
demos and one-off pair sessions; it's painful for **durable / team use**: rate-limit failures show
up at the worst time, and there's no stable invite link you can pre-share or bookmark.

Phase 3 adds an **opt-in authenticated Cloudflare named tunnel** so a host can pre-configure
`cloudflared` once and then host calls with a stable hostname (`wf.<their-domain>`), no scraping,
no quota throttling. The zero-config quick-tunnel path stays the default — Phase 3 is a switch you
flip when you have a Cloudflare account and want durable hosting.

The decision space dovetails with the still-deferred **central relay / hosting** choice from
Phase 4 — both are flavours of "use real infrastructure for the signalling path." The named tunnel
is the easiest entry point (lives on the host machine, no separate relay server to operate).

## Goal / Non-goals

**Goal:** when a host sets `tunnel_token` + `tunnel_hostname` (in `identity.json` or env), **Host a
call** uses their named tunnel instead of a quick tunnel — same invite-link UX, but rate-limit-free
and with a stable hostname. With no token set, behaviour is exactly today's quick tunnel.

**Non-goals:**
- Automating the one-time Cloudflare account/DNS setup. Documented, not scripted.
- A central / managed relay (separate decision).
- Sharing one named tunnel across multiple host editors (one tunnel = one host).

## Design

### Config (mirrors the existing `turn_*` / `relay_default` slots)

Two new fields on `WfeditIdentity` (in `engine/wf_edit/main.cc`):
- `std::string tunnel_token;` — the long-lived CF tunnel token.
- `std::string tunnel_hostname;` — the host's chosen hostname (e.g. `wf.alice.example`), which
  their Cloudflare DNS already CNAMEs to the tunnel.

Env overrides (env wins per-field, same precedence as TURN config):
- `WF_COLLAB_TUNNEL_TOKEN`
- `WF_COLLAB_TUNNEL_HOSTNAME`

Both must be set for the named-tunnel path to engage; either alone → fall back to quick tunnel.

### `StartQuickTunnelProcs` — branch on token presence

In `engine/wf_edit/main.cc` (the `StartQuickTunnelProcs` helper at `~:801`), add a branch up front:

```cpp
if (!token.empty() && !hostname.empty()) {
    // Named tunnel: cloudflared knows the tunnel ID + origin from the token's
    // ingress config; no `--url` and no URL to scrape. The relay still runs on
    // a free local port; the named tunnel's ingress in the CF dashboard must
    // route the hostname to http://localhost:<port>.
    execl(cf, cf, "tunnel", "run", "--token", token.c_str(), (char*)nullptr);
} else {
    // Existing quick-tunnel path (unchanged).
    execl(cf, cf, "tunnel", "--protocol", "http2", "--url", url.c_str(), (char*)nullptr);
}
```

Return the hostname to the caller (named-tunnel path) so the loading loop knows the host
immediately and can skip URL scraping.

### Loading loop (the `tunnel_pending` block)

- Named-tunnel path: `host` is known from config the instant the loop starts (no `PollTunnelUrl`).
  Still wait for cloudflared's `Registered tunnel connection` log line + the DNS propagation grace
  + the `HostResolves` check — same gates as today. The user's DNS is pre-configured, so resolve is
  typically near-instant, but the gate stays the safety net.
- Phase text becomes *"Starting named tunnel… → Registering… → Resolving…"* (subset of the
  existing phases — the "Establishing secure tunnel" scrape phase is skipped).

### Share-link modal

Unchanged shape, just a different hostname:
`wfedit+s://wf.alice.example/r/<room>`. The existing `ParseWfeditUrl` already handles arbitrary
hosts, so the joiner side needs no changes.

### Failure / migration

- Named tunnel registration fails (bad token, wrong ingress, etc.) → surface cloudflared's log tail
  (already in place from Phase 2's failure dump). Don't silently fall back to quick tunnel — the
  user opted into named, so the failure should be loud.
- Empty/invalid config → quick tunnel (today's behaviour).

## One-time setup (manual doc — included in `wf-edit-manual.md`)

The host does this once per machine; the joiner needs nothing extra:

1. Cloudflare Zero Trust dashboard → **Access → Tunnels → Create a tunnel** (free tier; pick a
   name like `wf-host`).
2. Save the connector **token** somewhere safe (long random string).
3. In the tunnel's **Public Hostname** tab, add a route: hostname `wf.<your-domain>`,
   service `http://localhost:9900` (the wf-relay port). Cloudflare auto-creates the DNS CNAME.
4. On the host machine, put the token + hostname in `~/.config/wf-edit/identity.json`:
   ```json
   { "tunnel_token": "<paste>", "tunnel_hostname": "wf.your-domain" }
   ```
   (or set `WF_COLLAB_TUNNEL_TOKEN` / `WF_COLLAB_TUNNEL_HOSTNAME` for a single run).

Document the trade vs. quick tunnel: named tunnel = rate-limit-free + stable hostname, costs you a
Cloudflare account + a domain you control + one-time DNS setup.

## Verification

- **Config plumbing:** `WF_EDIT_TURN_TEST`-style unit: set the env, call `ResolveTunnelConfig`,
  assert env-overrides-identity. (Same throttling-and-headless pattern as
  [`engine/wf_edit/webrtc_session.h`](../../engine/wf_edit/webrtc_session.h) `IceConfig` already
  has — reuse the pattern.)
- **Quick-tunnel regression:** with no token, `task quick-tunnel` and Host-a-call still work
  unchanged (the new branch never engages).
- **Named tunnel live:** with a real `tunnel_token` + `tunnel_hostname` configured, Host a call
  registers the named tunnel, the loading loop skips the URL scrape, the share-link modal shows
  `wfedit+s://<hostname>/r/<room>`, and a joiner connects. Cannot be CI'd (needs a real CF
  account); document the manual smoke procedure.

## Notes

- Sizing: ~0.5–1 day implementation (config + branch + loading-loop tweak + docs), *average-
  programmer scale*. Per-machine CF setup is documentation, not code.
- Keep the quick-tunnel path as the unambiguous default — no surprise behaviour change for anyone
  not opting in.
- The same `tunnel_token` could later drive a central-relay flavour (one named tunnel routed at a
  fixed VPS) — design with that dovetail in mind, don't hardcode "host's own machine."
