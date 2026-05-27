# Plan: Internet (WAN) Voice + Video for `wf-edit` via WebRTC

**Status:** Planned (not started)
**Estimated effort:** ~1.5–2.5 wk core (Phases 1–2) + ~1 day TURN (Phase 3) + ~2–3 days demo polish (Phase 4) — *average-programmer scale*
**Investigation / rationale:** [docs/investigations/2026-05-26-internet-voice-video-nat-traversal.md](../investigations/2026-05-26-internet-voice-video-nat-traversal.md)
**Supersedes (for WAN):** the v2 remote-peer goal of [docs/plans/2026-05-21-voice-video-collab.md](2026-05-21-voice-video-collab.md) (LAN, as-shipped)

## Context

`wf-edit`'s voice/video calling ships **LAN-only**: peers find each other via a multicast
beacon (`239.255.42.99:9877`, TTL=1) and send raw, **unencrypted** Opus/VP8 UDP straight to
each other's private LAN address — none of which routes or is reachable over the internet.
The user wants it to work **over the internet**, with **all network traffic encrypted** (hard
requirement, [[project_wf_edit_collab_encryption_required]]), and the design must hold across
the **full scale spectrum** — a 2-person game team up to an internet-scale service
([[feedback_consider_full_scale_spectrum]]).

The investigation selected **Option A: real WebRTC via [libdatachannel](https://github.com/paullouisageneau/libdatachannel)**
— it bundles ICE + STUN + TURN (via libjuice) + DTLS-SRTP encryption in one C++ library,
reuses our existing Opus/VP8 codecs as RTP tracks, keeps server cost ~flat as usage grows
(P2P for ~80 % of pairs), and is the stack the original design named. We keep one transport
(no LAN cleartext exemption — ICE selects the LAN host-candidate pair locally, so the
encrypted path *is* the LAN path).

## Goal / Non-goals

**Goal:** encrypted P2P voice+video between editor instances on different networks, signaled
over the existing relay, with a TURN fallback for hard NATs.

**Non-goals (this plan):** server-side SFU for large rooms (deferred — `str0m`, see § Deferred);
adaptive bitrate / simulcast / RTCP-driven congestion control; mobile (editor is Linux-only,
`WF_ENABLE_EDITOR AND NOT ANDROID AND NOT IOS`).

## Architecture

```
Editor A  ──ICE / DTLS-SRTP (P2P, encrypted)──  Editor B
   │   STUN: public · TURN: ours (~20 % fallback)  │
   └──── SDP + trickle ICE over wss:// relay ───────┘   ← new CH_SIGNAL channel
        (roster from relay CH_PRESENCE; multicast kept as LAN fast-path)
```

- **Media:** libdatachannel `PeerConnection` per peer; Opus/VP8 fed as RTP media tracks;
  DTLS-SRTP end-to-end (relay/TURN only ever see ciphertext).
- **Signaling + roster:** the existing `wf-relay`, made public over `wss://`, carrying a new
  `CH_SIGNAL` channel; the Collaborators roster is driven by the relay's existing
  `CH_PRESENCE` fanout over WAN (multicast retained for zero-config LAN).

## Phases

### Phase 1 — Signaling over the relay + public/encrypted relay

Makes peers *discoverable* over the internet and satisfies the encryption rule on signaling.

- **`wftools/wf_collab/src/bin/relay.rs`:** add `CH_SIGNAL = 0x05`. Prefer **targeted**
  routing — payload `[to_peer_id\0 sdp/ice-json]`, relay sends only to `to` (fall back to
  `fanout` if `to` empty). Passthrough like `CH_PRESENCE`/`CH_CHAT`; relay never parses media.
- **`engine/wf_edit/ws_client.{h,cc}`:** add **`wss://` (TLS) support** (OpenSSL) — the relay
  endpoint must be TLS. Today it's `ws://` only ("No TLS in v1"). Either native TLS in the
  client or document a `cloudflared`/reverse-proxy that terminates TLS — but the client must
  speak `wss://` to a public endpoint.
- **`engine/wf_edit/collab_session.{h,cc}` + `main.cc`:** when connected to a relay, build the
  Collaborators roster from relay `CH_PRESENCE` (peer id/name already carried) instead of the
  LAN multicast beacon. Keep multicast as the LAN fast-path (no behavioral change on LAN).
- **Deploy:** stand up `wf-relay` publicly over `wss://` — tiny VM / VPS, or Cloudflare Tunnel
  off a known box. Document in [docs/dev-setup.md](../dev-setup.md).
- **Verify:** two editors pointed at the public `wss://` relay (different networks, or
  simulated) appear in each other's roster; signaling messages round-trip.

### Phase 2 — WebRTC media transport (libdatachannel) — *the core*

- **Vendor** libdatachannel + libjuice + libsrtp as a CMake subdirectory (build from source;
  **fetch-and-verify by SHA256, not committed** if large — [[feedback_no_giant_vendor]]).
  Link into `wf_edit` (`target_link_libraries(wf_edit PRIVATE datachannel-static …)`), gated
  with the editor (`WF_ENABLE_EDITOR AND NOT ANDROID AND NOT IOS`). Add the TLS dep to
  [docs/dev-setup.md](../dev-setup.md).
- **New `engine/wf_edit/webrtc_session.{h,cc}`:** one `rtc::PeerConnection` per peer;
  create/handle offer/answer; **trickle ICE over `CH_SIGNAL`**; configure public STUN; DTLS
  handshake. Owns the per-peer audio + video tracks.
- **Retarget `voice_track.{h,cc}` / `video_track.{h,cc}`:** replace the raw-UDP
  `sendto`/`recvfrom` transport with libdatachannel tracks — RTP-packetize **Opus (RFC 7587,
  PT 111)** and **VP8 (RFC 7741, PT 96)** on send; receive via the track callback. **Reuse
  unchanged:** miniaudio capture/playback, V4L2 capture, Opus/VP8 encode/decode, YUYV→I420→RGB,
  GL-texture upload, `collab_panel.cc`. Delete the raw-UDP media path (single transport).
- **`main.cc`:** instantiate `WebrtcSession` per discovered peer; route `CH_SIGNAL` in
  `CollabDrain`; tear down on peer-leave / window-close.
- **Verify:** encrypted P2P call between two editors — LAN proves the host-candidate path; a
  real cross-NAT test proves WAN hole-punch. **Capture screenshots** of both Collaborators
  panels with live video ([[feedback_screenshots_for_proof]]).

### Phase 3 — TURN fallback (deferrable)

For the ~15–25 % of peers behind symmetric/CGNAT.

- Stand up **coturn** on the same public box (TURN-over-TLS/443 for restrictive firewalls),
  **or** evaluate **[Cloudflare Calls](https://developers.cloudflare.com/calls/)** as managed
  TURN (then we self-host only the signaling relay). Wire `WF_COLLAB_TURN` + credentials into
  the libdatachannel ICE config.
- **Verify:** force `iceTransportPolicy = relay` to exercise the TURN path without needing a
  symmetric NAT to reproduce against (this flag is also the only "server-relayed" mode we'd
  ever want — see investigation § Option C).

### Phase 4 — Reachability UX (deferrable)

- **Quick-tunnel demo mode:** auto-spawn `cloudflared tunnel --url http://localhost:<port>`,
  scrape the `*.trycloudflare.com` URL, auto-fill it as the room's relay address — zero-config
  "click → share link" calling. Fetch-and-verify `cloudflared` (~35 MB). Caveats: ephemeral
  URL, rate-limited, WS-only (signaling, not media).
- **Central-host default:** ship a default `wss://` relay URL for durable use.

## Critical files

| File | Change |
|------|--------|
| `wftools/wf_collab/src/bin/relay.rs` | New `CH_SIGNAL` channel (targeted routing) |
| `engine/wf_edit/ws_client.{h,cc}` | `wss://` (TLS) client support |
| `engine/wf_edit/webrtc_session.{h,cc}` | **New** — libdatachannel `PeerConnection` per peer + signaling glue |
| `engine/wf_edit/voice_track.{h,cc}` | Transport swap: raw UDP → Opus RTP track |
| `engine/wf_edit/video_track.{h,cc}` | Transport swap: raw UDP → VP8 RTP track |
| `engine/wf_edit/collab_session.{h,cc}` | Roster from relay presence (WAN); multicast = LAN fast-path |
| `engine/wf_edit/main.cc` | Wire `WebrtcSession` into the frame loop; `CH_SIGNAL` routing |
| `CMakeLists.txt` | Vendor + link libdatachannel/libjuice/libsrtp; TLS dep |
| `docs/dev-setup.md` | New build deps (TLS lib); relay deploy notes |

## Verification

1. `wfcrdt_wrapper_test` + relay still green; new signaling round-trip covered by a small test.
2. Two-instance harness (extend the existing `WF_EDIT_REMOTE_TEST` pattern) over a `wss://`
   relay: roster, offer/answer, DTLS connect, one media frame each way.
3. Manual cross-NAT call (two networks) → encrypted P2P; force-relay flag → TURN path.
4. **Screenshots** of both Collaborators panels with live video, per phase.

## Deferred / future (scale)

- **Server-side SFU (`str0m`)** for many-participant rooms / internet-scale fan-out — mesh
  P2P is fine ≤ ~4 peers; the client work here is identical whether a peer talks to another
  peer or to an SFU, so this is additive, not a rewrite ([[feedback_consider_full_scale_spectrum]]).
- **Multicast *signaling*** for zero-relay offline-LAN (media stays DTLS-SRTP).
- Adaptive bitrate / simulcast / RTCP feedback at scale.
- Horizontally-shard the signaling relay (pub/sub backplane) when one process isn't enough.

## Risks

- **Real-NAT debugging is the time sink** (ICE/DTLS bring-up across real networks), not the code.
- **`ws_client` TLS** is new work and on the critical path for the encryption requirement.
- **libdatachannel TLS dependency** (OpenSSL/GnuTLS/MbedTLS) adds a Linux editor build dep — acceptable (editor never ships to mobile).

## Sources

- Investigation: [docs/investigations/2026-05-26-internet-voice-video-nat-traversal.md](../investigations/2026-05-26-internet-voice-video-nat-traversal.md)
- v1 (LAN, as-shipped): [docs/plans/2026-05-21-voice-video-collab.md](2026-05-21-voice-video-collab.md)
- [libdatachannel](https://github.com/paullouisageneau/libdatachannel), [Cloudflare Calls](https://developers.cloudflare.com/calls/), [str0m](https://github.com/algesten/str0m)
