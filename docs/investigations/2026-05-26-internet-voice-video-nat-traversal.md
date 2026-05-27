# Internet (WAN) Voice + Video for `wf-edit` — NAT Traversal & Hosting Analysis

**Date:** 2026-05-26
**Status:** Investigation — decision pending
**Author:** Claude (Opus 4.7)
**Context:** `wf-edit`'s voice/video calling ships LAN-only today
([plan](../plans/2026-05-21-voice-video-collab.md)). The user wants it to work
**over the internet**. This doc analyzes the options end-to-end and recommends one.

---

## TL;DR

- **Recommendation: real WebRTC via [libdatachannel](https://github.com/paullouisageneau/libdatachannel) (C++).**
  It gives ICE + STUN + **TURN** + DTLS-SRTP encryption in one vendored C++ library,
  reuses our existing Opus/VP8 codecs as RTP media tracks, and is exactly the stack the
  [original v1 design](../plans/2026-05-21-voice-video-collab.md#architecture-overview)
  named before we cut it for the LAN-only raw-UDP shortcut. Signaling rides the relay we
  already have. ~75–85 % of calls connect peer-to-peer (no media server); a small
  self-hosted TURN covers the rest and can be deferred.

- **Do you have to stand up a server?** **Yes — exactly one small always-on box, the
  *signaling* relay.** You already need it; it's `wf-relay`, just made publicly reachable.
  It carries only tiny text (SDP/ICE) + your existing CRDT sync — kilobytes, not media.
  STUN is **free public infrastructure** (Google's `stun.l.google.com:19302`) — you host
  nothing. TURN (the only piece that relays actual media) is **optional**, needed only for
  the ~15–25 % of networks behind symmetric/carrier-grade NAT, and can be added later.

- **Can one of the editor machines be the relay?** **Yes — *if and only if* that machine
  is reachable from the public internet** (public IP, a forwarded port, or a tunnel such as
  the free Cloudflare Tunnel you already have the tooling for). A machine behind a home
  router NAT generally is **not** reachable, which is the entire reason NAT traversal
  exists. See [§ Hosting reality](#hosting-reality) — this is the key practical question.

- **Hard requirement: all network traffic must be encrypted.** This is settled, not a
  trade-off. It (a) makes Option A's built-in DTLS-SRTP a feature rather than overhead,
  (b) **rules out Option B** (cleartext media) entirely, and (c) makes moving the relay to
  `wss://` (TLS) **mandatory** — it's plaintext `ws://` today. See
  [§ Encryption (hard requirement)](#encryption-hard-requirement).

---

## Why LAN-only can't reach the internet

The current design ([`collab_session.cc`](../../engine/wf_edit/collab_session.cc),
[`voice_track.cc`](../../engine/wf_edit/voice_track.cc),
[`video_track.cc`](../../engine/wf_edit/video_track.cc)) has two hard LAN dependencies:

1. **Discovery is multicast.** Peers find each other via a UDP multicast beacon on
   `239.255.42.99:9877` with **TTL = 1** — link-local only. Multicast is not routed across
   the internet, full stop.
2. **Media is raw UDP to a LAN IP.** Each peer reads the *other peer's private LAN address*
   from the beacon and `sendto()`s Opus/VP8 straight there. A private address
   (`192.168.x.x`) is meaningless and unreachable from across the internet, and even if it
   weren't, the peer's NAT/firewall would drop unsolicited inbound UDP.

So WAN support means solving two separate problems: **(a) how do two editors that can't see
each other find each other**, and **(b) how does media actually flow between them through
NATs/firewalls.** They have different answers.

---

## The building blocks

| Block | What it does | Who provides it |
|---|---|---|
| **Signaling** | Exchanges "how to reach me" info (SDP, ICE candidates) between peers before media flows. Tiny text. | **Our relay** — `wf-relay` already fans out per-room messages; add one channel byte. **Mandatory, must be public.** |
| **STUN** | Each peer asks a public server "what's my public IP:port as you see it?" (its *server-reflexive* candidate), so peers can try a direct path. | **Free public** (`stun.l.google.com:19302`). Host nothing. |
| **Hole-punching / ICE** | Both peers fire UDP at each other's candidates simultaneously; NATs open symmetric pinholes; a working pair is selected. Succeeds for most NATs. | The WebRTC library (libdatachannel's libjuice) or hand-rolled. |
| **TURN** | When hole-punching fails (symmetric/CGNAT, ~15–25 % of networks per Chrome UMA data), a public relay forwards the media. This box carries real bandwidth. | **Self-hosted coturn** (optional, deferrable). |
| **Media transport + encryption** | Carries the Opus/VP8 RTP packets, encrypted. | DTLS-SRTP (free with libdatachannel) — or cleartext if hand-rolled. |
| **Codecs** | Opus (voice), VP8 (video). | **Already done** — `libopus` + `libvpx`, reused unchanged. |

The decision is really about **block (b)**: full WebRTC, hand-rolled hole-punch, or
server-relayed media. Signaling-over-the-relay is common to all three.

---

## Encryption (hard requirement)

**All network traffic must be encrypted.** This is a project constraint, not a preference,
and it shapes the options:

| Traffic | Today | Under the requirement |
|---|---|---|
| Media (Opus/VP8) | cleartext raw UDP (LAN) | **DTLS-SRTP** — built into Option A (libdatachannel); end-to-end between peers |
| Relay: CRDT sync / presence / chat | **plaintext `ws://`** | **`wss://` (TLS)** — mandatory; easiest via Cloudflare Tunnel / reverse-proxy TLS termination |
| Signaling (SDP/ICE) | n/a (new) | rides the same `wss://` relay |
| TURN control | n/a | optionally **TURNS** (TURN-over-TLS, port 443) |

Two consequences worth stating plainly:

1. **End-to-end through TURN.** In Option A the DTLS-SRTP session is negotiated *between the
   two editors*. A TURN relay (yours) only forwards the already-encrypted SRTP packets — it
   **cannot decrypt the media**. So even fully-relayed calls keep your server out of the
   plaintext path. (This also matters for the [hosted-tier idea](#commercial-angle): you can
   sell relayed minutes without being able to surveil them.)
2. **Option B is eliminated.** Hand-rolled raw-UDP Opus/VP8 has no encryption story short of
   re-implementing DTLS-SRTP — at which point you've rebuilt Option A badly.

### LAN exemption — considered, rejected

One could exempt same-LAN calls from encryption (keep today's cleartext raw-UDP path) on the
theory that re-encrypting local traffic isn't worth it. **Rejected — and it actually *costs*
more, mostly on testing grounds:**

- **WebRTC already is the LAN path.** ICE selects the **host (LAN) candidate pair** for
  same-LAN peers, so a LAN call under Option A is direct P2P over the LAN — encrypted, no
  TURN, no relayed media. The encrypted path covers LAN for free; no separate code.
- **A cleartext-LAN exemption means keeping two transports** (raw-UDP *and* WebRTC) and two
  discovery paths (multicast *and* relay) → roughly **double the test matrix**, plus a
  "which path am I on / why is this call cleartext?" failure mode. Since the concern is test
  effort, the single encrypted path is strictly cheaper. Going all-WebRTC *removes* the old
  raw-UDP code rather than preserving it.
- **The only thing the exemption buys is zero-relay offline-LAN** (an isolated network with
  no reachable signaling server). Even that doesn't require dropping encryption: add
  **multicast *signaling*** (SDP/ICE over multicast, à la the original Phase-1 design) while
  media stays DTLS-SRTP. A small, separate, deferrable feature — not an encryption hole.

---

## Hosting reality

This section answers the two questions directly.

### "Do I have to stand up a relay server?"

**Yes — one, and it's small.** Two editors on different networks have no way to discover
each other without a neutral rendezvous point. That's the *signaling* relay = our existing
`wf-relay`, which today only listens on `ws://localhost:9900`. To work over the internet it
must be:

- **Publicly reachable** — a host with a public IP or a tunnel.
- **Always-on** — it must be up when *anyone* wants to start a call, so it can't live inside
  a participant's editor session that comes and goes.
- **Tiny** — it relays SDP/ICE text + CRDT updates. A free-tier VM, a $4/mo VPS, or a
  Cloudflare Worker/Tunnel-fronted box all suffice. It is **not** a media server in the
  recommended design.

You need this **regardless of which option you pick** (even the simplest, because discovery
always needs a rendezvous).

### "Can one of the editor machines be the relay?"

**Yes, conditionally.** `wf-relay` is just a binary; any machine can run it alongside the
editor. The catch is **reachability**:

- **On a LAN** — trivially yes; both machines can already reach each other (this is the
  current multicast story, no relay needed at all).
- **Over the internet** — the relay-hosting machine must be reachable *from the other
  peer's network*. A machine behind a typical home router (NAT) is **not** publicly
  reachable by default. Options to make it so:
  - **Port-forward** a port on the router to that machine (manual, fragile, exposes a home
    box).
  - **A tunnel** — e.g. **Cloudflare Tunnel** (free; you already have the Cloudflare
    tooling and skills), Tailscale, or ngrok. This is the clean way to expose a home
    machine without port-forwarding, and it gives you `wss://` (TLS) for free.

- **The chicken-and-egg:** the peer who *can't* host (behind a locked-down NAT) is precisely
  the one who most needs the relay. So "host it on a participant machine" only works if at
  least **one** specific, known participant has a public path — and that participant must be
  online for anyone to connect. For ad-hoc collaboration that's brittle.

**Bottom line:** for occasional use among a known pair where one of you can run a Cloudflare
Tunnel, hosting the relay on that editor machine is **fine and free**. For anything more
durable, a tiny dedicated always-on box is worth the few dollars and removes the "is Will's
desktop on?" dependency. Either way it's a *signaling* box — cheap and low-bandwidth.

> Note on TURN: a TURN server has the **same reachability requirement** (both peers must
> reach it) and additionally carries **media bandwidth**, so hosting it on a home editor
> machine is doubly awkward. If you add TURN, put it on the same small public box (coturn
> alongside the relay).

---

## Relay reachability & tunnel automation

How does the signaling relay become publicly reachable, and can we automate that for end
users? Three models, in increasing zero-touch-ness for the end user:

### 1. Central host (best for the paid tier)

We run **one** relay, once, behind a tunnel/cert *we* control (`wss://relay.wfedit.org`).
**End users automate nothing** — the editor ships with the URL (or it's set per workspace).
One cert, one stable URL, no per-user Cloudflare account. Strictly simpler than per-user
tunnels, and it's what the [hosted tier](#commercial-angle) implies.

### 2. Self-host + quick tunnel (best for zero-config / ad-hoc)

When a user wants to be the relay, the editor shells out to **Cloudflare's quick tunnel**:

```
cloudflared tunnel --url http://localhost:<relay-port>
# → prints  https://<random>.trycloudflare.com
```

The editor scrapes that URL and auto-fills it as the room's `wss://` relay address —
**no Cloudflare account, no domain, no config.** This is a genuine "click → start call →
share this link" feature, fully automatable end to end. Caveats: the hostname is
**ephemeral** (new each launch), it's **rate-limited**, Cloudflare's TOS frames quick
tunnels as **dev/testing, not production**, and it tunnels **HTTP/WS only** (see the limit
below). `cloudflared` is a ~35 MB binary → **fetch-and-verify (SHA256), not vendored** (per
the project's no-giant-vendor rule).

### 3. Self-host + named tunnel (durable, but needs the user's CF account)

A persistent hostname requires the **user's own** Cloudflare account + a zone + an API
token. The zone/token/DNS dance is scriptable — the `cloudflare-domain-setup` and
`cloudflare-static-site` skills already automate exactly this — but the user must authorize
their account once; it can't be silent.

### The limit that decides the shape: tunnels carry HTTP/WS only

A Cloudflare Tunnel makes the **`wss://` signaling relay** reachable **and terminates TLS for
free** (satisfying the [encryption requirement](#encryption-hard-requirement) on that hop).
It does **not** carry the WebRTC **UDP media** path (P2P or TURN). So tunnel automation solves
*signaling reachability + relay TLS* — and nothing about media. For the media fallback:

- **[Cloudflare Calls](https://developers.cloudflare.com/calls/)** — managed TURN. Worth a
  hard look: it could cover the symmetric-NAT fallback as a service, so we'd self-host **only
  the tiny signaling relay** and never run coturn.
- **Self-hosted coturn** — needs a real reachable public IP (a tunnel won't do), on the same
  small box as the relay.

**Recommendation:** build the **quick-tunnel auto-spawn** as the zero-config/demo mode (it's
cheap and delightful), but treat **central hosting** as the real answer for durable use, and
**evaluate Cloudflare Calls** so the only thing anyone self-hosts is the signaling relay.

---

## Candidate architectures

### Option A — Real WebRTC via libdatachannel (C++)  ★ recommended

Vendor [libdatachannel](https://github.com/paullouisageneau/libdatachannel) (C++17, the
stack the original design named). It provides a complete `PeerConnection`: ICE (RFC 8445)
with STUN + **TURN** via its bundled libjuice, DTLS-SRTP encrypted media transport, and an
RTP API — **with no built-in codecs**, which is exactly what we want because we keep Opus +
libvpx and feed them in as RTP tracks.

```
Editor A  ──ICE / DTLS-SRTP (P2P, encrypted)──  Editor B
   │   STUN: public · TURN: ours (fallback)        │
   └──── SDP + ICE candidates over wf-relay ───────┘   ← new CH_SIGNAL byte
```

- **Media path:** P2P for ~75–85 % of network pairs (no media server); TURN relays the rest.
- **Encryption:** DTLS-SRTP, free and mandatory in WebRTC. Webcam/voice never cross the
  internet in cleartext.
- **Reuse:** capture (miniaudio, V4L2), Opus/VP8 encode/decode, the GL-texture upload, the
  Collaborators panel UI — **all unchanged**. We swap only the *transport*: instead of
  `sendto()` raw UDP, we hand encoded frames to a libdatachannel track; instead of
  `recvfrom()`, we receive via the track callback.
- **Integration shape:** matches the project's vendored-C/C++ pattern (libjuice/libsrtp as
  submodules, `add_subdirectory`, `target_link_libraries(wf_edit PRIVATE datachannel-static)`),
  no Corrosion/C-ABI boundary needed.
- **Cost:** the new work is RTP-packetizing Opus (RFC 7587) and VP8 (RFC 7741), driving the
  PeerConnection state machine, trickling ICE over signaling, and debugging real-NAT
  connectivity.

### Option A′ — Real WebRTC via Rust (str0m / webrtc-rs) — *considered, not recommended*

Tempting because of our Corrosion/yffi Rust pattern, but the research changes the picture:
- **[str0m](https://github.com/algesten/str0m)** is elegant and lock-free (sans-IO), but it
  is an **ICE agent + RTP engine, not a full client** — it has **no built-in TURN client**
  and does no socket I/O. You'd hand-build TURN allocation and all socket plumbing yourself,
  i.e. *more* work for the symmetric-NAT fallback, not less.
- **[webrtc-rs](https://webrtc.rs/)** (`webrtc` crate, the Pion port) *does* have STUN/TURN/
  ICE/DTLS/SRTP, but it's async-tokio and heavier to embed in the editor's synchronous frame
  loop, and a C-ABI binding would be substantial.

Net: for *this* C++ editor, libdatachannel is the lower-friction "real WebRTC."

#### Why "partial" on the roadmap — and what would close the gap

The **documented roadmap** is the [original v1 design](../plans/2026-05-21-voice-video-collab.md):
a **libdatachannel** WebRTC stack — ICE + DTLS-SRTP + RTP, Opus (PT 111) / VP8 (PT 96), STUN
for remote peers (`WF_COLLAB_STUN`), with TURN implied for full remote reach. Option A *is*
that stack (→ ✅). A′ reaches the same *capabilities* with a different library, so it's
"partial." The gap depends on which Rust lib:

**To reach the roadmap with A′ = str0m**, still to implement:
1. **TURN client** — str0m *uses* relay candidates but doesn't allocate them; you'd build the
   TURN allocation (or pull a separate TURN-client crate) for symmetric/CGNAT peers.
2. **Sans-IO driver** — UDP sockets, timers, the run loop and packet pump (libdatachannel
   bundles all of this).
3. **STUN srflx gathering** — app-driven binding request to a public STUN server to obtain
   your server-reflexive candidate to hand to str0m.
4. **C-ABI binding** (Rust → the C++ editor) via Corrosion, à la `yffi`.
   *(ICE pairing, DTLS, SRTP, RTP, Opus/VP8-as-media: str0m already provides.)*

**To reach the roadmap with A′ = webrtc-rs**, still to implement:
1. **C-ABI binding** (Rust → C++).
2. **Async-runtime bridge** — drive the tokio runtime from the editor's synchronous frame
   loop.
   *(No capability gap — STUN/TURN/ICE/DTLS/SRTP are all present.)*

**The inverse — what we'd drop from the roadmap to accept A′ = str0m as-is** (skip the extra
TURN/IO work): drop **TURN / symmetric-NAT & CGNAT support**, i.e. relax "works behind every
NAT" to "works behind cone NATs only" (~75–85 % of peers; the hardest ~15–25 % fail). That's
the single roadmap capability shed; encryption, ICE hole-punch, codecs, and the panel UI all
remain. (With webrtc-rs you drop *nothing* capability-wise — you just absorb the Rust/async
binding overhead.)

This is precisely why **A is ✅ and A′ is partial**: libdatachannel bundles the I/O + STUN +
TURN + DTLS-SRTP that the roadmap named, in one C++ library the editor links directly — no
binding layer, no capability to backfill.

### Option B — Hand-rolled ICE-lite hole-punch over the existing raw-UDP path  ✗ ruled out (encryption)

Keep `voice_track`/`video_track`'s raw Opus/VP8 wire format. Replace the multicast beacon
with: a tiny STUN client (one binding request) to learn each peer's public address →
exchange candidates over the relay → both peers UDP-hole-punch → lock the working path →
stream the existing packets.

- **Pro:** smallest diff; reuses the media code as-is.
- **Con (fatal):** media is **unencrypted** over the public internet — this alone violates
  the [all-traffic-encrypted requirement](#encryption-hard-requirement) and **rules the
  option out**. (Even setting that aside: no clean fallback — symmetric/CGNAT peers, the
  ~15–25 %, simply fail unless we *also* build a TURN-equivalent relay. It re-implements a
  worse version of what libdatachannel gives for free.)

### Option C — Server-relayed media (SFU-lite)

No NAT traversal at all: each editor opens an *outbound* connection to a public relay and
sends Opus/VP8 to it; the relay fans media out to the other room members. Outbound works
through virtually any firewall.

```
Editor A ──▶  RELAY  ──▶ Editor B
         ◀──        ◀──
   (all Opus/VP8 flows through the server)
```

- **Pro:** **100 % connectivity**, zero NAT complexity, no STUN/TURN, no ICE. Simplest
  networking by far.
- **Con:** the relay carries **all** media for **all** calls (bandwidth, latency via the
  detour, and your server *sees* the media). The existing WebSocket/TCP relay is poor for
  real-time media (head-of-line blocking + retransmits add latency), so this means adding a
  **UDP media-forwarding mode** to the relay (or a small companion UDP relay binary) — a
  bounded but real piece of Rust. **Encryption is mandatory here too** and is *not* free in
  this option: a server-relayed media path means adding DTLS/SRTP (or DTLS-over-UDP) to the
  media legs yourself — which is precisely the encryption layer libdatachannel hands you for
  nothing in Option A. And the server sees ciphertext only if you do that work correctly.
- **When it wins (scale-dependent):** for a *2-person team*, relaying one or two A/V streams
  is trivially cheap, so "always connects, never debug a NAT" can feel worth it. But that
  appeal **inverts as you grow** — server-relayed media means 100 % of every call's bandwidth
  flows through your fleet, a linear cost center and a scaling bottleneck precisely when a
  business wants marginal cost per call to stay near zero. See
  [§ Scale: indie → internet-scale](#scale-indie-team--internet-scale-saas).

> **C collapses into A.** The "always-relayed, encrypted" goal does *not* require building a
> bespoke relay or hand-wiring DTLS-SRTP. Reusing libdatachannel's encryption means standing
> up a full WebRTC `PeerConnection` (which brings ICE), and then forcing
> **`iceTransportPolicy = relay`** routes all media through a relay while keeping DTLS-SRTP
> end-to-end. **That relay is just a TURN server** (coturn / Cloudflare Calls). So
> "server-relayed" is **a runtime flag on Option A + a TURN server**, not a separate build —
> there is no standalone Option C worth implementing. Running it forced-on by default is
> almost never desirable (it pushes 100 % of calls through your TURN box when ~80 % could go
> direct and free); its narrow real uses are **IP-address privacy** (hides peers' IPs behind
> the relay — matters only if strangers call each other, not for a known team) and
> **testing the TURN path** without needing a symmetric NAT to reproduce.

---

## Decision matrix

| Criterion | **A: libdatachannel** ★ | A′: Rust WebRTC | B: ICE-lite hand-roll | C: Server-relayed |
|---|---|---|---|---|
| Connects behind most NATs | ✅ ~80 % P2P + TURN | ✅ (more DIY) | ⚠️ ~80 %, no fallback | ✅ 100 % |
| Symmetric/CGNAT/mobile | ✅ via TURN | ⚠️ build TURN client | ❌ fails | ✅ |
| Encrypted media (e2e, **required**) | ✅ DTLS-SRTP (free) | ✅ (free) | ❌ impossible | ✅ DTLS-SRTP (**must build**) |
| Media-server bandwidth | none (P2P) / TURN only | same | none | **all media** |
| Privacy (server sees media content) | **no** † | **no** † | n/a | **no** ‡ |
| Reuses our codecs/capture/UI | ✅ | ✅ | ✅ most | ✅ |
| New dependency | C++ lib (vendored) | Rust crate (Corrosion) | none | none |
| Servers to operate | relay + (opt) TURN | relay + TURN | relay + DIY relay | **media relay** |
| Latency | best (direct) | best | best | +detour |
| Effort (avg programmer) | **~1.5–2.5 wk** + ~1 day TURN | ~2.5–3.5 wk | ~1 wk (but a dead-end) | **~3.5–4.5 wk** (3–5 d relay + 2–3 wk DTLS-SRTP) §|
| Matches documented roadmap | ✅ (v1 design) | partial | ✗ | ✗ |

> **Option B is ruled out** by the [all-traffic-encrypted requirement](#encryption-hard-requirement)
> (cleartext media). The matrix keeps it for completeness only.
>
> † **TURN does *not* see the media** in Options A/A′. DTLS-SRTP keys are negotiated
> end-to-end between the two editors; a TURN relay forwards only the **encrypted** SRTP and
> cannot decrypt it. It does see *metadata* — that a call exists, the peers' IPs, packet
> sizes/timing — which the signaling relay sees too.
>
> ‡ **Option C also keeps media out of the server — because e2e encryption is mandatory.**
> C must run DTLS-SRTP between the two editors and have the relay forward ciphertext only
> (same posture as TURN), so the server never sees content. Its real cost vs. A is the §
> estimate below, and the relay is still **always in the media path** — it sees all the
> metadata and carries all the bandwidth (the rows above), for 100 % of calls rather than the
> ~20 % TURN fallback.
>
> § **The "+ DTLS-SRTP" estimate (~2–3 wk).** Compliant e2e for C means wiring
> OpenSSL/MbedTLS **DTLS** + **libsrtp** yourself (you don't hand-roll crypto primitives, but
> you do build the layer): the DTLS handshake over the relayed transport, RFC 5764 keying
> (`use_srtp` extension + key export), libsrtp protect/unprotect with SSRC/replay/ROC
> handling, then **security testing** — the expensive part, and exactly the testing burden
> this work is trying to avoid. That is the *bulk of A's whole effort*, because DTLS-SRTP is
> what libdatachannel gives A for free. **So under the encryption requirement C is the most
> expensive option, not the cheapest** (~3.5–4.5 wk total vs. A's ~1.5–2.5 wk), while
> delivering less. The cheap version of C — terminate TLS *at the relay* (hop-by-hop) — lets
> the server read plaintext and **violates the requirement**. Net: if you want server-relayed
> media you'd use libdatachannel or buy **Cloudflare Calls** rather than build this — both of
> which return you to the WebRTC stack.

---

## Scale: indie team → internet-scale SaaS

The right lens is the **whole spectrum** — from a 2-person team making a game up to a full
internet business providing this as a service — not just today's small scale. Several axes
behave very differently at the two ends, and the recommendation should hold across both:

| Axis | 2-person team | Internet-scale SaaS |
|---|---|---|
| **Media topology** | full-mesh P2P (each peer ↔ each peer) is fine for ≤ ~4 participants | mesh is O(n²) uploads per peer → breaks down; need an **SFU** (each peer sends one upstream, server fans out) |
| **Server media cost** | negligible | the deciding factor — **P2P keeps it ~flat** (only signaling + ~20 % TURN); forced-relay/SFU is **linear in calls × bitrate** |
| **Signaling relay** | one tiny process | needs horizontal sharding + a pub/sub backplane (Redis-style); the current single `Mutex<HashMap>` relay won't scale as-is |
| **TURN** | one coturn, or skip | regional TURN fleet (or Cloudflare Calls), and **provider egress price dominates COGS** (Hetzner/Cloudflare ≫ AWS — see [§ Commercial angle](#commercial-angle)) |
| **Reach** | "works for us two" | must work behind *every* NAT/CGNAT/corporate firewall → TURN-over-TLS/443 non-negotiable |

**This makes the recommendation *stronger*, not weaker.** Option A (P2P WebRTC) is the only
choice whose server cost stays near-flat as the user base grows — most media never touches
your infrastructure — which is exactly the property a business wants. The options that route
all media through a server (bespoke Option C, or forced-relay) look harmless for two people
but become the dominant cost and the scaling bottleneck at the high end.

**One nuance flips with scale: the SFU.** Full-mesh P2P is right for small rooms, but
many-participant rooms (large collab sessions, or a commercial multi-user tier) need a
**server-side SFU**. That is exactly where **str0m** — dismissed earlier as a *client* lib
because it lacks a TURN client — becomes the natural choice: it is sans-IO and
purpose-built as an SFU. So the likely long-arc architecture is **libdatachannel client +
mesh now**, adding a **str0m SFU** server-side when room sizes or scale demand it. The client
work done for Option A is the same either way (a WebRTC endpoint speaks to a peer or to an
SFU identically), so starting with A does **not** paint us into a corner.

---

## Recommendation

**Adopt Option A (libdatachannel).** It is the only option that is simultaneously
*encrypted*, *P2P-efficient*, and *robust behind hard NATs*, and it reuses everything we
already built except the transport swap. It's also the stack the original design intended,
so we're completing the documented roadmap rather than inventing a parallel one.

**Option C (server-relayed) is *not* the cheap shortcut it first looks like.** The
encryption requirement erases its only advantage: a compliant C must build e2e DTLS-SRTP
(~2–3 wk, see §), pushing it to ~3.5–4.5 wk total — *more* than A — while delivering less
(no P2P, server in the path for 100 % of calls). It only makes sense if you positively want
"always relayed, never debug a NAT" as the permanent topology *and* you outsource the crypto
to **Cloudflare Calls** (managed WebRTC/TURN) rather than building it — at which point you're
back on the WebRTC stack anyway. A's TURN fallback is conceptually the same media-relaying
box, just used for the ~20 % that need it.

**Option B is off the table** — cleartext media violates the encryption requirement, and it
has no symmetric-NAT fallback regardless.

### Suggested phasing for Option A

1. **Make the relay public + add signaling.** Deploy `wf-relay` behind `wss://` (TLS) — a
   tiny always-on box or a Cloudflare Tunnel off a known machine. Add `CH_SIGNAL = 0x05`
   (targeted fanout: payload carries a `to` peer-id). Drive the Collaborators **roster from
   the relay's existing `CH_PRESENCE` fanout** instead of the LAN multicast beacon — this
   alone is what makes peers *discoverable* over the internet, and PRESENCE already carries
   peer identity. *(~2–3 days incl. deploy.)*
2. **Swap the media transport to libdatachannel.** Vendor it; add a `WebrtcSession` (one
   `PeerConnection` per peer) that offers/answers + trickles ICE over `CH_SIGNAL`, with
   public STUN configured. Retarget `voice_track`/`video_track` send/recv from raw UDP to
   libdatachannel tracks (RTP-packetize Opus + VP8). This yields encrypted P2P calls for the
   ~80 % of networks that hole-punch. *(~1.5–2 wk, the core work.)*
3. **Add TURN for the hard cases (deferrable).** Stand up coturn on the same public box,
   wire `WF_COLLAB_TURN` into the ICE config. *(~0.5–1 day ops.)*

Keep the LAN multicast path as a zero-config fast path when both peers are local; the relay
path is the WAN path. The two coexist.

### Infra cost summary

| Piece | Host | Cost | Required? |
|---|---|---|---|
| Signaling relay (`wf-relay`, `wss://`) | tiny VPS / free-tier VM / **Cloudflare Tunnel off an editor box** | ~$0–4/mo | **Yes (all options)** |
| STUN | public (Google) | $0 | Yes (A) |
| TURN (coturn) | same small box | bandwidth only, when used | Optional, deferrable |
| Media relay (Option C only) | a real always-on box w/ bandwidth | ~free for 2 people, **linear cost center at scale** | Only if C |

---

## Commercial angle

There's a real revenue idea adjacent to TURN, but **not** the obvious one. Reselling cloud
bandwidth at a markup is a thin, commoditized play — and AWS is the worst supplier for it,
since egress is its own highest-margin product:

| Provider | Egress | Cost / relayed call-hr (~0.5 GB) |
|---|---|---|
| AWS | ~$0.09/GB | ~$0.045 |
| Hetzner / OVH | ~$0.001/GB (€1/TB) | ~$0.0005 |
| Cloudflare (Calls / Tunnel) | ~free–trivial | ~$0 |

Only ~15–25 % of calls touch TURN at all, and each relayed hour costs fractions of a cent on
a sane host — so "mark up AWS egress" nets pennies on a fraction of traffic while competing
against Twilio/Xirsys/Metered and near-free Cloudflare Calls. Don't build a business on it.

**The model that works is the hosted *service*, with TURN bundled as a cost line, not sold
à la carte:**

- **Free tier:** LAN / bring-your-own-relay (Cloudflare Tunnel off your own box).
- **Paid tier:** hosted rooms = signaling relay + persistence + TURN-included + N seats +
  (later) auth/SSO/BYOK.

Margin comes from the managed experience, not relayed megabytes. This already has a paper
trail in the project: the **v2 BYOK relay tier** (TODO § Collaborative Editor — the relay
`wrap()` KMS-encryption seam) and the **community relay `wfedit.org`** named in the
[collaborative editor design doc](2026-05-18-collaborative-level-editor-design.md). TURN slots
into that tier. Two nice properties: (1) the same TURN box you stand up for the *feature* is
the one you later meter for the *tier*; (2) because media is DTLS-SRTP end-to-end (see
[§ Encryption](#encryption-hard-requirement)), you can sell relayed minutes **without being
able to surveil them** — a genuine privacy selling point. If you do meter infra, host on
egress-cheap providers (Hetzner/OVH/Cloudflare), never AWS.

## What gets reused vs. rewritten (Option A)

- **Reused unchanged:** miniaudio mic/speaker, V4L2 capture, Opus encode/decode, VP8
  encode/decode, YUYV→I420→RGB conversion, GL-texture upload, the Collaborators panel
  (`collab_panel.cc`), the relay's room/fanout/presence machinery, `ws_client`.
- **Rewritten:** the *transport* inside `voice_track.cc`/`video_track.cc` (raw UDP →
  libdatachannel tracks); `collab_session` discovery (multicast-only → relay-presence over
  WAN, multicast retained for LAN).
- **New:** `webrtc_session.{h,cc}` (libdatachannel `PeerConnection` per peer + signaling
  glue); `CH_SIGNAL` in `relay.rs`; libdatachannel + libjuice + libsrtp vendored in CMake;
  relay public-deploy + (optional) coturn config.

## Risks / open questions

- **Real-NAT debugging is the time sink**, not the code — ICE/DTLS bring-up across actual
  home/mobile networks always surprises. Budget for it.
- **`wss://` (TLS) on the relay is mandatory** (the all-traffic-encrypted requirement, not
  just a browser/strict-network nicety); easiest via a Cloudflare Tunnel or a reverse proxy
  with a cert.
- **TLS dependency for libdatachannel** (OpenSSL/GnuTLS/MbedTLS) adds a build dep on the
  Linux editor — acceptable (editor is Linux-only, not shipped to mobile).
- **Targeted vs. broadcast signaling:** for small rooms, fanout + client-side filtering is
  fine; a `to`-field keeps it clean as rooms grow.

---

## Sources

- [libdatachannel (GitHub)](https://github.com/paullouisageneau/libdatachannel) — ICE/STUN/TURN via libjuice, DTLS-SRTP media transport, C API, no built-in codecs.
- [str0m (GitHub)](https://github.com/algesten/str0m) / [docs.rs](https://docs.rs/str0m) — sans-IO ICE agent + RTP; no built-in TURN client.
- [webrtc.rs](https://webrtc.rs/) and [Announcing rtc 0.3.0 (2026-01)](https://webrtc.rs/blog/2026/01/04/announcing-rtc-v0.3.0.html) — full STUN/TURN/ICE/DTLS/SRTP Rust stacks.
- [BlogGeek.me — WebRTC TURN](https://bloggeek.me/webrtcglossary/turn/) and [Chrome UMA analysis] — ~15–25 % of sessions require TURN; CGNAT/mobile are ~always symmetric.
- [Did I choose the right WebRTC stack? (webrtc-developers.com)](https://www.webrtc-developers.com/did-i-choose-the-right-webrtc-stack/) — stack comparison.
- Internal: [voice/video plan](../plans/2026-05-21-voice-video-collab.md), [realtime co-editing plan](../plans/2026-05-21-realtime-coediting.md), [`relay.rs`](../../wftools/wf_collab/src/bin/relay.rs), [`collab_session.h`](../../engine/wf_edit/collab_session.h), [`voice_track.h`](../../engine/wf_edit/voice_track.h), [`video_track.h`](../../engine/wf_edit/video_track.h).
</content>
</invoke>
