# Two-machine voice/video + internet/VPN verification — run sheet

**Goal:** close the two things headless tests *cannot* verify for multi-peer
WebRTC, in one cross-machine session:

1. **W3/W4 — real media flow.** Opus actually encoded from a mic on one machine
   and decoded on the other (the loopback ctest and the headless 3-peer smoke
   have no mic, so they can only prove the *transport*, not the *media*).
2. **Internet + NAT/VPN traversal.** STUN hole-punching across real NAT, and the
   **TURN-relay fallback** when at least one peer is on a VPN that blocks direct
   P2P. Loopback never touches this path.

This complements — does not replace — the verified pieces:
[`wf_edit_mesh` ctest](../engine/wf_edit/main.cc) (loopback mesh) and the live
3-peer smoke ([`tests/screenshot_three_peer_b2.sh`](../tests/screenshot_three_peer_b2.sh),
relay-path mesh). See [the multi-peer plan](plans/2026-05-31-multi-peer-voice-video-mesh.md).

---

## Prerequisites

| Machine | Needs |
|---------|-------|
| **Host** (computer 1) | `wf-edit` built; `cloudflared` fetched once (`task fetch-cloudflared`); a **working mic** |
| **Joiner** (computer 2) | `wf-edit` built; a **working mic**; this is the one to put **on the VPN** |
| Both | `WF_COLLAB_VOICE_DEBUG=1` in the environment (added 2026-05-31 — per-second stderr media stats; see below) |

> A mic on **both** machines is what makes this a W3/W4 test. If only one has a
> mic, you still verify one-direction media + traversal, which is most of the value.

If you want to *force* the TURN path (prove the relay specifically rather than
relying on STUN), you also need a reachable **TURN server** and its creds — see
[Forcing TURN](#forcing-the-turn-relay-path) below. Without that, the call will
still connect (P2P or STUN), but you won't have isolated the relay leg.

---

## The run

### 1. Host (computer 1)

```bash
WF_COLLAB_VOICE_DEBUG=1 ./build-editor/wf-edit --host-tunnel wflevels/cd.iff
# Wait ~10–20 s for "Establishing secure tunnel…" to resolve, then copy the
# printed link:   wfedit+s://<random>.trycloudflare.com/r/<room>
```

In the editor: **Collaborate → Host a call** if you didn't pass `--host-tunnel`.
Then **un-mute the mic** (the toggle in the call panel — capture starts muted by
default).

### 2. Joiner (computer 2, on the VPN)

```bash
# Bring up the VPN first (WireGuard/Surfshark/etc.), then:
WF_COLLAB_VOICE_DEBUG=1 ./build-editor/wf-edit --url='wfedit+s://<random>.trycloudflare.com/r/<room>' wflevels/cd.iff
```

Un-mute the mic here too. Talk on each end.

---

## What success looks like

### Connection (W1, over the real internet)

Each machine's **stderr** should show, in order:

```
voice: started (WebRTC transport)
video: started (WebRTC transport)
wf-edit: relay connected wss://<...>.trycloudflare.com  room=<room>
collab: new peer <id> ...
voice: added peer <id>
webrtc: connected to peer <id> (offerer=…)
```

- ✅ **`webrtc: connected to peer`** for the other peer = ICE/DTLS succeeded over
  the internet (through the VPN). This is the internet-traversal proof.
- ❌ **No `ma_device_init capture failed`** — if you see that, the mic didn't open
  and W3/W4 can't be tested on that machine (fix the mic / audio permissions).

### Media actually flowing (W3/W4 — the new part)

With `WF_COLLAB_VOICE_DEBUG=1`, each machine prints ~once per second while audio
moves (50 Opus frames × 20 ms ≈ 1 s):

```
voice-dbg: send packets=50 peak=0.182 bytes=87      # YOUR mic → Opus, leaving this box
voice-dbg: recv peer=<id> packets=50 peak=0.164     # THEIR Opus → decoded here
```

- ✅ **`send packets=` climbing with `peak>0` when you talk** = your mic is
  capturing and Opus is encoding+sending (W3).
- ✅ **`recv peer=<id> packets=` climbing with `peak>0` when *they* talk** = their
  media arrived and decoded on your machine (W4). `peak≈0` while silent, jumping
  when they speak, is the unambiguous signal.
- The same numbers drive the **on-screen audio-level meter** under each peer's
  tile in the Collab panel ([`collab_panel.cc:131`](../engine/wf_edit/collab_panel.cc)),
  so the bouncing meter is the visual equivalent.

### Capture the proof

Per [`feedback_verification_mp4_recordings`], record a short **MP4** of the Collab
panel with the audio meters bouncing as each person talks, and drop it in
[`tests/recordings/`](../tests/recordings/) (e.g. `multi_machine_voice.mp4`).
Also save both machines' `voice-dbg:` stderr — the `send`/`recv` packet counts
are the grep-able, non-visual record.

---

## Forcing the TURN-relay path

By default ICE will use the *best* path it finds — often direct P2P or a STUN
server-reflexive candidate — so a plain successful call does **not** prove TURN
works. To isolate the relay leg (the ~15–25 % of real-world peer pairs that STUN
can't punch — symmetric NAT/CGNAT, some VPNs):

**Stand up the TURN server** — on a machine both peers can reach (a host with a
public IP, or one on the same LAN as the others; **not** the VPN'd box):

```bash
task turn-serve     # runs coturn from config/turnserver-wfedit.conf,
                    # then prints the exact WF_COLLAB_* env to paste on the clients
```

`task turn-serve` auto-detects the host's reachable IPv4 and prints a ready-to-paste
block. Open **UDP 3478 and 49300–49400** on that host's firewall. If the TURN host is
itself behind NAT (home router), forward those ports and set `external-ip=<public-ip>`
in [`config/turnserver-wfedit.conf`](../config/turnserver-wfedit.conf) so it advertises
a reachable relay candidate. (Static creds `wfedit:wfeditpass` are for this throwaway
test only — see the security note atop the config.)

**On the VPN machine**, before launching, paste what `turn-serve` printed:

```bash
export WF_COLLAB_TURN='<turn-host-ip>:3478'
export WF_COLLAB_TURN_USER='wfedit'
export WF_COLLAB_TURN_PASS='wfeditpass'
export WF_COLLAB_FORCE_RELAY=1                   # pins ICE to relay-only
WF_COLLAB_VOICE_DEBUG=1 ./build-editor/wf-edit --url='<link>'
```

With `WF_COLLAB_FORCE_RELAY=1`, the call succeeds **only** if media traverses the
TURN server — so a working call + flowing `voice-dbg:` counters is direct proof
the relay path carries DTLS-SRTP media. (This mirrors what the headless
`WF_EDIT_TURN_TEST` does against a local coturn, but now over the real internet.)

No TURN server yet? `task turn-serve` (coturn, validated against 4.6.1) stands one
up from [`config/turnserver-wfedit.conf`](../config/turnserver-wfedit.conf). If you
skip it entirely, the traversal test still has value (STUN handles most NATs); just
note in the result that the **relay fallback was not exercised** — don't claim it.

---

## If it doesn't connect

| Symptom | Likely cause |
|---------|-------------|
| Tunnel never resolves (`Establishing…` forever) | cloudflared blocked on :7844, or rate-limited — see the dumped cloudflared log; try a [named tunnel](wf-edit-manual.md#named-tunnel--durable-rate-limit-free-stable-hostname) |
| `relay connected` but no `webrtc: connected to peer` | ICE failed — both behind hard NAT with no TURN. Configure TURN (above). |
| `webrtc: connected` but no `voice-dbg: recv` | media not flowing despite transport up — check the *sender* un-muted + their `send packets=` is climbing |
| `ma_device_init capture failed` | no mic / audio permission on that machine |

See also [`docs/wf-edit-manual.md` § Two computers](wf-edit-manual.md#two-computers)
for the base recipe and the VPN/`--protocol http2` notes.
