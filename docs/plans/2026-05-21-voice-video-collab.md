# Plan: Voice + Video Calling in wf-edit

**Status:** Done — implemented and building (~3 h)  
**Estimated effort:** ~3–4 days

> The "Architecture Overview" and "Phases" below capture the **original design intent**
> (a libdatachannel/WebRTC stack). The shipped v1 **diverged** — see § As shipped for what
> actually landed, which is authoritative.

## As shipped (reconciled 2026-05-21)

The implementation is **simpler than the WebRTC design** below: it dropped
[libdatachannel](https://github.com/paullouisageneau/libdatachannel) / DTLS-SRTP / ICE /
STUN entirely in favour of **raw UDP** on the LAN. This is fine for the LAN-only v1 target;
remote peers (which were what STUN/relay bought) are explicitly v2.

| Aspect | Designed (below) | **As shipped** |
|---|---|---|
| Transport | libdatachannel (ICE/DTLS-SRTP/RTP) | **raw UDP sockets** ([voice_track.cc](../../engine/wf_edit/voice_track.cc), [video_track.cc](../../engine/wf_edit/video_track.cc)) |
| Peer discovery | multicast SDP offer/answer | **multicast heartbeat beacon** `WFEDIT\|room\|peer\|name\|audio_port\|video_port` every 2 s on `239.255.42.99:9877` ([collab_session.cc](../../engine/wf_edit/collab_session.cc)) |
| Ports | RTP payload types over one connection | **ephemeral OS-assigned** audio + video UDP ports (so multiple instances share a host); the room beacon advertises them — replaced the earlier hardcoded 19400/19401 (`a9600ab1`) |
| Audio | Opus over libdatachannel | **Opus direct** (48 kHz mono, 20 ms, VOIP preset, 32 kbps) over UDP, miniaudio capture/playback |
| Video | VP8 over libdatachannel | **VP8 (libvpx) direct** over UDP, fragmented with a `WFV\0` header to fit the MTU; V4L2 capture; decoded → GL texture |
| Display name | per-user | fixed to **"Editor"** in v1 ([main.cc](../../engine/wf_edit/main.cc)) |
| STUN / remote peers | `WF_COLLAB_STUN` env | **not implemented** (LAN multicast only) |

### As-shipped Collaborators panel ([collab_panel.cc](../../engine/wf_edit/collab_panel.cc))

```
┌─ Collaborators ─────────────────────────────┐
│ Room: studio-1                              │
│ You      (live)                             │   ← self-preview state
│  [ Mute mic ]   [ Cam off ]                 │   ← toggles
│ ─────────────────────────────────────────  │
│  ┌──────────┐  ┌──────────┐                │
│  │ [video]  │  │   (B)    │   ← initials    │
│  │ Alice    │  │  Bob     │     avatar      │
│  │ ████░░░░ │  │ ░░░░░░░░ │   ← level meter │
│  └──────────┘  └──────────┘                │
│  No peers? Share the room ID to invite.     │
└─────────────────────────────────────────────┘
```

Differs from the Phase-4 mockup: a real **self-preview** row ("You"), the toggles are
labelled **Mute mic / Cam off** (no "Leave call" — closing the window leaves), and an
empty room prints "Share the room ID above to invite collaborators." Usage is documented
in the [editor user manual § Collaboration](../wf-edit-manual.md#collaboration-voice--video).

**Screenshot** ([feedback_screenshots_for_proof](/home/will/.claude/projects/-home-will-WorldFoundry/memory/feedback_screenshots_for_proof.md)): captured with **two `wf-edit` instances in the same room** (`--room=demo-266485`) on one host — multicast discovery over loopback works (each logs `collab: new peer … (Editor)`). Neither instance has a camera, so the peer renders as a coloured initials avatar (**E**) rather than a video thumbnail; the toggles read *Unmute mic* / *Cam on* (both off):

![Collaborators panel — a second editor instance discovered as the "Editor" peer in the same room](../../tests/screenshots/wfedit_collab.png)

> A video-thumbnail capture (peers with live cameras) still needs a host with `/dev/video0`
> — the discovery + panel + avatar-fallback path is proven here; the VP8 video path is
> exercised by the same code but not yet shown with a real camera frame.

## Context

wf-edit is a collaborative CRDT-based level editor (ImGui/GLFW/OpenGL). Multiple editors
share a room identified by a UUID; the CRDT doc syncs changes via Y.Doc state vectors.
Collaborators currently have no in-tool communication channel. The goal is to add
Zoom/Skype-style voice+video calling so collaborators see and hear each other inside the
editor without switching apps.

## Architecture Overview

```
Editor A                           Editor B
┌─────────────────┐                ┌─────────────────┐
│ Mic → Opus enc  │──RTP audio──▶  │ Opus dec → spkr │
│ Cam → VP8 enc   │──RTP video──▶  │ VP8 dec → panel │
│ libdatachannel  │◀──DTLS-SRTP──▶ │ libdatachannel  │
│   ICE / STUN    │                │   ICE / STUN    │
└─────────────────┘                └─────────────────┘
        │ signaling (SDP/ICE)              │
        └──────────── UDP mcast ───────────┘
                  (same room-id)
```

**Transport** *(designed — superseded by raw UDP at ship; see § As shipped)*:
[libdatachannel](https://github.com/paullouisageneau/libdatachannel) — lightweight
C++ WebRTC that handles ICE, DTLS-SRTP, RTP. LAN-only v1 (UDP multicast signaling); remote
peers add a public STUN server in v2.

**Audio codec**: libopus (system `libopus-dev`)  
**Video codec**: libvpx VP8 (system `libvpx-dev`)  
**Camera capture**: Linux V4L2 kernel API (no extra lib)  
**Mic capture**: miniaudio capture mode (already vendored at `engine/vendor/miniaudio-0.11.25/`)

## Phases

### Phase 1 — Signaling & peer discovery

**New files:**
- `engine/wf_edit/collab_session.h/cc` — `CollabSession` class

**What it does:**
- Joins a UDP multicast group keyed on room-id (derived from `--room <uuid>` arg or displayed as a shareable URL)
- Broadcasts presence heartbeat (`{room, peer-id, display-name, sdp-offer}`) every 2 s
- On receiving a foreign peer's offer, creates a libdatachannel `PeerConnection`, sends SDP answer back via multicast
- ICE candidates exchanged the same way

**CMake changes:**
- Vendor libdatachannel under `engine/vendor/libdatachannel/` (CMake subdirectory, ~5 MB source)
- `target_link_libraries(wf_edit PRIVATE datachannel-static)`
- `pkg_check_modules(OPUS REQUIRED opus)` + `pkg_check_modules(VPX REQUIRED vpx)`
- V4L2: no extra lib (Linux kernel headers)

**Prereqs** (document in dev-setup):
```
apt install libopus-dev libvpx-dev
```

### Phase 2 — Voice (audio)

**New files:**
- `engine/wf_edit/voice_track.h/cc` — `VoiceTrack` class (one per peer + one for self)

**Capture side (self):**
- Open miniaudio device in `ma_device_type_capture` mode, 48 kHz mono
- Feed PCM frames into `OpusEncoder` (20 ms frames, VOIP preset)
- Send encoded packets via libdatachannel audio track (RTP, OPUS payload type 111)

**Receive side (per peer):**
- Pull RTP packets from libdatachannel audio track
- `OpusDecoder` → PCM → miniaudio `ma_device_type_playback` (stereo mix, no spatial for v1)

**UI additions:**
- Mic toggle button (mute/unmute) in Collaborators panel
- Per-peer audio level meter (RMS of last 20 ms frame, ImGui progress bar)

### Phase 3 — Video

**New files:**
- `engine/wf_edit/video_track.h/cc` — `VideoTrack` class

**Capture side (self):**
- Open `/dev/video0` via V4L2 (`VIDIOC_S_FMT` → YUYV 640×480 30 fps)
- Convert YUYV → I420 (inline, no lib needed)
- Feed into `vpx_codec_encode()` (VP8, libvpx) at target 500 kbps
- Send VP8 RTP packets via libdatachannel video track (payload type 96)

**Receive side (per peer):**
- Decode VP8 RTP via `vpx_codec_decode()` → I420 frame
- Upload I420 → OpenGL texture (GLSL shader converts I420→RGB on GPU, reusing editor's existing GL context)
- Texture ID stored on `PeerState`; rendered via `ImGui::Image()`

### Phase 4 — Collaborators panel UI

**New file:** `engine/wf_edit/collab_panel.h/cc`

```
┌─ Collaborators ────────────────────────────┐
│  ┌──────────┐  ┌──────────┐               │
│  │ [video]  │  │ [video]  │               │
│  │ Alice    │  │  Bob     │               │
│  │ 🔊 ████░ │  │  🔇      │               │
│  └──────────┘  └──────────┘               │
│  [Mute mic]  [Cam off]   [Leave call]     │
└────────────────────────────────────────────┘
```

Thumbnails: 160×90 px. Toggled from View menu.  
Fallback when no camera: initials avatar (colored per display-name hash).  
Fallback when no mic: video-only.

### Phase 5 — Integration & polish

- Wire `--room <uuid>` arg; display room URL in title bar for easy sharing
- `WF_COLLAB_STUN=stun.l.google.com:19302` env var enables remote-peer support
- Disconnect gracefully on GLFW window-close callback (already in `main.cc:~line 580`)

## Critical files to modify

| File | Change |
|------|--------|
| `engine/wf_edit/main.cc` | Add `CollabSession` init/tick in frame loop; View→Collaborators menu item |
| `CMakeLists.txt` | Add libdatachannel subdirectory, Opus + VPX pkg-config |
| `engine/wf_edit/collab_panel.h/cc` | New — Collaborators ImGui panel |
| `engine/wf_edit/collab_session.h/cc` | New — peer discovery + UDP multicast signaling |
| `engine/wf_edit/voice_track.h/cc` | New — miniaudio capture + Opus RTP |
| `engine/wf_edit/video_track.h/cc` | New — V4L2 capture + VP8 RTP |

## Verification

1. `apt install libopus-dev libvpx-dev`
2. `task build`
3. Launch two editor instances with the same room-id:
   ```
   ./wf-edit --level qbert_practice.lev --room a1b2c3
   ./wf-edit --level qbert_practice.lev --room a1b2c3
   ```
4. Open Collaborators panel in both — verify each shows the other's video thumbnail
5. Speak into mic — verify audio is audible in the second instance
6. Mute self — verify peer sees the muted indicator
7. Test with no `/dev/video0` — verify audio-only fallback with initials avatar
8. Screenshot both Collaborators panels as proof
