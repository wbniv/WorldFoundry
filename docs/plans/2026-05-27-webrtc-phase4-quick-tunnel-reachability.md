# Plan — WebRTC Phase 4: quick-tunnel reachability ("share a link" calling)

**Date:** 2026-05-27
**Status:** Planned (not started)
**Estimated effort:** ~2–3 days — *average-programmer scale* (cloudflared fetch ~0.25 day; `task quick-tunnel` plumbing ~0.5 day; in-editor Host UX + subprocess/scrape ~1–1.5 days; central-host default + docs ~0.5 day)
**Parent:** Phase 4 of [docs/plans/2026-05-26-internet-voice-video-webrtc.md](2026-05-26-internet-voice-video-webrtc.md)
**Builds on:** [Phase 3 — generic TURN client](2026-05-27-webrtc-phase3-turn-generic-client.md) (done)

## Context

`wf-edit` now does encrypted WebRTC voice/video over the internet (Phases 1–3): media is
DTLS-SRTP P2P with a TURN fallback, and signaling rides a `wss://` relay. But **reaching** a
collaborator still needs someone to manually stand up the `wf-relay` signaling server
([`wftools/wf_collab/src/bin/relay.rs`](../../wftools/wf_collab/src/bin/relay.rs), `0.0.0.0:9900`)
on a publicly-routable host and share its URL. For a 2-person team that's friction; for a quick
demo it's a blocker.

Phase 4 closes that gap with a **quick-tunnel demo mode**: the host clicks once, the editor spawns
a [Cloudflare quick tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/)
(`cloudflared tunnel --url http://localhost:9900`) that publishes the local relay at an ephemeral
`https://<rand>.trycloudflare.com`, and hands back a shareable `wfedit+s://<rand>.trycloudflare.com/r/<room>`
link. The joiner pastes the link — which the editor already parses to `wss://…` + room
([`ParseWfeditUrl`](../../engine/wf_edit/main.cc), `main.cc:180`) — and they're connected, zero infra.

**Why this is safe under the encryption requirement** ([[project_wf_edit_collab_encryption_required]]):
signaling to the tunnel is `wss://` (TLS to Cloudflare's edge); the edge→relay hop is **loopback**
(`http://localhost:9900`, never on the wire); and media stays DTLS-SRTP P2P/TURN, *not* through the
tunnel (a quick tunnel is WS-only anyway). So nothing cleartext crosses a network.

## Goal / Non-goals

**Goal:** a host running `wf-edit` can start a call and get a single shareable link that a remote
collaborator (different network, behind NAT) opens to join — no manually-hosted relay, no router
config — with all signaling encrypted.

**Non-goals (deferred):**
- A **durable central relay** (the `wss://` default host) — same deferred hosting decision as TURN
  (self-host vs managed); quick tunnels are ephemeral + rate-limited, fine for demos/small teams,
  not a always-on service. A config slot is added (Phase 4.4) but ships empty.
- Bundling/committing the `cloudflared` binary (~35 MB) — fetched + SHA256-verified on demand
  ([[feedback_no_giant_vendor]]), never committed.
- Authenticated/named Cloudflare tunnels (require a CF account + token) — quick tunnels are anonymous.

## Phases

### Phase 4.1 — cloudflared acquisition (fetch + verify)
Add a `fetch-cloudflared` task (and wire it into `dev-setup-editor`) that downloads the pinned
`cloudflared` release for the host arch over HTTPS, checks it against a committed SHA256, `chmod +x`,
and drops it at a known path (`build-editor/tools/cloudflared`). Idempotent (skip if the checksum
already matches). No commit of the binary.

### Phase 4.2 — `task quick-tunnel` (plumbing, independently useful)
A task that: builds `wf-relay` (dep), starts it on `:9900`, spawns
`cloudflared tunnel --url http://localhost:9900`, **scrapes** the `https://<rand>.trycloudflare.com`
line from cloudflared's stderr banner, and prints both the raw `wss://<rand>.trycloudflare.com`
relay and a ready-to-share `wfedit+s://<rand>.trycloudflare.com/r/<room>` link (room defaulted /
overridable). Robust cleanup of *both* children by unique marker — reusing the hard lesson from
`turn-test-relay` (go-task's shell gives neither the real `&` pid nor reliable EXIT traps, so tear
down with `pkill -f` on a unique arg, which excludes its own pid). This task is the orchestration
contract the in-editor button wraps.

### Phase 4.3 — in-editor "Host a call (quick tunnel)" UX
A Collaborators-panel / File-menu action that runs the same orchestration as child processes
(`wf-relay` + `cloudflared`), reads cloudflared's stdout/stderr to capture the URL, then joins its
own room via the tunnel and shows a **copyable share link** in a modal. Implementation mirrors the
existing process-spawn patterns (`WF_OT_run_level`-style spawn; the `execvp` re-exec already used by
File→Open at `main.cc`): pick a room, spawn relay+cloudflared, scrape URL, re-exec
`wf-edit --relay=wss://<rand>.trycloudflare.com --room=<room>` (preserving the level), and surface
the `wfedit+s://…` link with a "Copy" button + persist it to `recent_rooms`. A non-blocking status
("starting tunnel…/ ready") while cloudflared comes up (~2–5 s).

### Phase 4.4 — central-host default relay (config slot, ships empty)
A `relay_default` key in `~/.config/wf-edit/identity.json` + `WF_COLLAB_RELAY_DEFAULT` env (env
overrides), used by "Join" when no link/relay is given. Defaults empty (no central host yet) with a
clear "no relay configured — use Host a call, or set a relay" message. Documents the path to a
durable relay without committing to hosting it.

## Verification
- **4.1:** `task fetch-cloudflared` lands the binary, checksum matches, `cloudflared --version` runs;
  re-running is a no-op.
- **4.2:** `task quick-tunnel` prints a `*.trycloudflare.com` URL + the `wfedit+s://` share link, and
  on exit leaves no stray `wf-relay`/`cloudflared` (port 9900 free). *(Needs outbound network to
  Cloudflare; if the sandbox blocks it, the URL-scrape regex is unit-checked against a captured
  cloudflared banner and the live run is left to the user.)*
- **4.3:** headless `--screenshot` of the share-link modal (the mockup below); a real two-machine
  join is a manual step (needs two networks). The re-exec arg construction is asserted in a small
  headless check.
- **Encryption invariant:** confirm the joiner connects over `wss://` (TLS), not `ws://` — the
  `wfedit+s://` scheme forces it; a `ws://` quick-tunnel link is rejected with a clear message.

## Share-link modal (mockup)

```
┌─ Host a call ──────────────────────────────────┐
│ Tunnel ready — share this link to invite:       │
│                                                 │
│  wfedit+s://quiet-frog-1234.trycloudflare.com/  │
│           r/studio-1            [ Copy ]        │
│                                                 │
│ ⓘ Ephemeral link (this session only). Media is  │
│   end-to-end encrypted; signaling over wss://.  │
│                                   [ Done ]      │
└─────────────────────────────────────────────────┘
```

## Risks / notes
- **Ephemeral + rate-limited:** trycloudflare URLs die when `cloudflared` exits and are
  rate-limited — fine for demos/small teams, not production (that's the deferred central host).
- **Scrape fragility:** the URL is parsed from cloudflared's human banner (no machine-readable flag
  for quick tunnels). Pin a regex (`https://[a-z0-9-]+\.trycloudflare\.com`) and fail loudly with the
  captured output if it changes.
- **Subprocess lifecycle:** the editor must reap `cloudflared` + `wf-relay` on quit/peer-leave;
  track pids and kill on teardown (and a unique-marker `pkill` backstop), per the `turn-test-relay`
  cleanup lesson.
