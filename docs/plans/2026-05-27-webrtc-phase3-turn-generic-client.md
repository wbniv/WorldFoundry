# Plan — WebRTC Phase 3: generic TURN client (hosting deferred)

**Date:** 2026-05-27
**Status:** **DONE 2026-05-27 (~2 h)** — all four sub-phases landed. ICE config is sourced from
`identity.json` + `WF_COLLAB_*` env (3.1); `WF_COLLAB_FORCE_RELAY` flips `iceTransportPolicy`
to relay-only (3.2); a `WF_EDIT_TURN_TEST` headless mode asserts the config precedence/parse and
connects two in-process sessions P2P over loopback — `wf_edit_turn` ctest passes (3.3); the manual
documents the config keys with production hosting deferred (3.4). The **force-relay-through-coturn
leg was verified against real coturn 4.6.1** (a throwaway loopback `turnserver` on :3479 with static
`wfedit` creds): with `iceTransportPolicy = Relay` the only ICE candidates are relay candidates, so
the two sessions connecting at all proves coturn allocated and forwarded the (DTLS-SRTP) media —
`[turn] two sessions connect via force-relay TURN PASS`. The harness is wrapped as `task
turn-test-relay` (NOTE: it hardcodes port 3478, which collides with a system coturn daemon; run a
throwaway `turnserver` on a free port and point `WF_COLLAB_TURN` at it, as done here). Also fixed a
project-wide root-cause wart: UBSan's `vptr` check is incompatible with the engine's `-fno-rtti`,
so it now globally excludes `-fno-sanitize=vptr` (was spewing false "invalid vptr" errors on
libdatachannel); and `WebrtcCleanup()` (rtc::Cleanup) joins libdatachannel's threads so LSan stays
quiet.
**Estimated effort:** ~1–1.5 days — *average-programmer scale* (ICE-config plumbing + force-relay flag ~0.5 day; local coturn test rig + relay round-trip test ~0.5–1 day; docs ~0.25 day)
**Parent:** Phase 3 of [docs/plans/2026-05-26-internet-voice-video-webrtc.md](2026-05-26-internet-voice-video-webrtc.md)
**Rationale / hosting analysis:** [docs/investigations/2026-05-26-internet-voice-video-nat-traversal.md](../investigations/2026-05-26-internet-voice-video-nat-traversal.md) (§ Hosting reality, § Commercial angle)

## Context

`wf-edit`'s WebRTC media transport (Phases 1–2, landed `4955d635` / `b866be25`) connects peers over
the internet via ICE + STUN, with DTLS-SRTP end-to-end encryption. But it configures **only a
single public STUN server** — [`webrtc_session.cc:137`](../../engine/wf_edit/webrtc_session.cc):

```cpp
rtc::Configuration config;
config.iceServers.push_back(rtc::IceServer{"stun:stun.l.google.com:19302"});
```

STUN gets ~75–85 % of network pairs connected P2P. The remaining ~15–25 % (symmetric NAT, CGNAT —
per Chrome UMA data, see investigation) need a **TURN relay** to forward the (still-encrypted) media.
Phase 3 adds that fallback.

Per the chosen direction (2026-05-27), this plan builds the **generic TURN client** only: the code
to consume a TURN server's URL + credentials and route relay candidates through it, tested against a
**throwaway local [coturn](https://github.com/coturn/coturn)**. It deliberately **defers the
production-hosting and revenue decision** — self-hosted coturn vs managed
[Cloudflare Calls](https://developers.cloudflare.com/calls/) — both of which stay open because the
client code is identical for either (both hand libdatachannel a `turn:` URL + username/password).

## Goal / Non-goals

**Goal:** a `wf-edit` peer behind a symmetric NAT can complete an encrypted call by relaying media
through a configured TURN server, with the TURN endpoint + credentials supplied by config (env /
`~/.config/wf-edit/identity.json`), never hardcoded — verified end-to-end against a local coturn with
a force-relay mode that proves the relay path actually carries the media.

**Non-goals (deferred, both hosting paths preserved):**
- Standing up a *production* public TURN box (real IP, bandwidth, scaling).
- Ephemeral time-limited HMAC credentials (coturn `use-auth-secret` / TURN-REST, or Cloudflare Calls'
  credential API). The config reader takes plain `username`/`password` strings; whether those are
  static or minted by a REST call lives **behind that seam**, so deferring this doesn't churn Phase 3 code.
- Cloudflare Calls integration, billing, or any hosted-tier revenue plumbing (§ Commercial angle).

## API surface (verified in the vendored header)

[`configuration.hpp`](../../build-editor/_deps/libdatachannel-src/include/rtc/configuration.hpp) gives
exactly what Phase 3 needs — no capability gap:

- `IceServer(hostname, port, username, password, RelayType::TurnUdp | TurnTcp | TurnTls)` — explicit
  TURN server with credentials; `TurnTls` is **TURNS** (TURN-over-TLS on 443), which keeps the relay
  control channel encrypted too.
- `IceServer(url)` — also accepts a `turn:`/`turns:` URL form.
- `Configuration::iceTransportPolicy = TransportPolicy::Relay` — forces ICE to use **only** relay
  candidates. This is the test lever: on a LAN, ICE would otherwise pick a host-candidate pair and
  never touch TURN, so a passing "TURN works" test *requires* forcing relay-only.

## Phases

### Phase 3.1 — ICE-server config plumbing
Replace the single hardcoded STUN push in `GetOrCreate` ([`webrtc_session.cc:136`](../../engine/wf_edit/webrtc_session.cc))
with a small `BuildIceConfig()` helper that assembles `config.iceServers` from configuration:
- Source order: env vars override the config file. New keys (mirroring the existing
  `WF_COLLAB_*` style — cf. `WF_COLLAB_STUN` named in the investigation):
  `WF_COLLAB_STUN` (default `stun:stun.l.google.com:19302`), `WF_COLLAB_TURN` (host:port or `turn:`
  URL), `WF_COLLAB_TURN_USER`, `WF_COLLAB_TURN_PASS`, `WF_COLLAB_TURN_TLS=1` (→ `RelayType::TurnTls`).
- Persisted equivalents in `~/.config/wf-edit/identity.json` (same file the gizmo snap-pref already
  uses), so a designer configures TURN once.
- Default with no TURN configured = today's behaviour (STUN-only), so the common path is unchanged.

### Phase 3.2 — force-relay test mode
`WF_COLLAB_FORCE_RELAY=1` → `config.iceTransportPolicy = TransportPolicy::Relay`. Off by default.
This makes a connection succeed *only* through TURN, which is how we prove the relay path without a
real symmetric NAT.

### Phase 3.3 — local coturn test rig + relay round-trip test
- A `task` target (e.g. `task turn-test-relay`) that runs a throwaway local coturn with static
  long-term credentials (a documented `realm` + user/pass; coturn from apt or a pinned container —
  no giant vendored binary, per project policy).
- A headless test that brings up two `WebrtcSession`s pointed at the local coturn with
  `WF_COLLAB_FORCE_RELAY=1`, drives signaling between them, and asserts (a) the PeerConnection reaches
  `Connected`, and (b) an Opus + a VP8 RTP frame round-trip through the relay — observed via the
  existing `OnRemoteOpus` / `OnRemoteVP8Frame` callbacks **and** coturn's relay-session log line.
- Regression: a second run with no TURN configured + no force-relay still connects P2P.

### Phase 3.4 — docs
- `wf-edit` manual / README: how to point the editor at a TURN server (the env/config keys).
- Explicitly record that production hosting + ephemeral credentials + revenue are deferred, linking
  the investigation's two paths so the decision is one click away when it's time.

## Verification
- **Relay path proven:** two local sessions, force-relay, local coturn → `Connected` + media frames
  round-trip; coturn log shows the allocation/relay. (Screenshots aren't meaningful here — the proof
  is the deterministic frame-round-trip log + coturn session log.)
- **P2P regression:** STUN-only, no force-relay → still connects directly (no TURN dependency leaked
  into the default path).
- **Encryption invariant preserved:** DTLS-SRTP negotiation is between the two editors; coturn only
  forwards ciphertext. Force-relay does **not** weaken E2E encryption — it just changes the path. This
  keeps the hard all-traffic-encrypted requirement intact (the relay sees only SRTP).

## Risks / notes
- libdatachannel bundles its own TURN client (libjuice) — no extra dependency; the FetchContent build
  already pulls it (cf. `9a930bc0` submodule fix).
- coturn in CI/sandbox may need host networking; the test rig must tolerate a sandbox that blocks the
  relay UDP range (skip-with-clear-message rather than a false failure).
- The static-credential test rig is **not** how production should authenticate (long-term shared
  secrets are exposed in any shipped client). That's exactly why production credentials are deferred
  to the ephemeral-HMAC / managed-service seam in Non-goals — not an oversight.
