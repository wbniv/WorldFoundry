| Date | Change |
|------|--------|
| [2026-06-13](https://github.com/wbniv/WorldFoundry/commit/b7316645) | feat(wf-edit/web): A/V Phase 2 — voice (getUserMedia mic, bidirectional) |
| [2026-06-13](https://github.com/wbniv/WorldFoundry/commit/f872e3ae) | docs(wf-edit/web): plan voice+video (A/V) over browser WebRTC + TODO entry |

<!--history-meta v1
b7316645	author	Will Norris
b7316645	added	15
b7316645	deleted	4
b7316645	files	1
b7316645	body	webrtc_web.cc: wfwebrtc_set_mic acquires getUserMedia({audio}) and replaceTrack's it\ninto each peer's audio transceiver sender (no renegotiation); remote ontrack audio →\na hidden autoplay <audio>. Two correctness fixes for bidirectional flow:\n  - only the OFFERER pre-adds transceivers; the answerer adopts the ones\n    setRemoteDescription(offer) creates (pre-adding on both sides mis-aligns m-lines);\n  - the answerer forces its transceivers to sendrecv BEFORE createAnswer, so the answer\n    advertises send-capability even though the local mic isn't attached until unmute —\n    without this the answer is recvonly and that peer could never send (one-way audio).\n  A shared S.attachLocal(P) replaceTrack helper is used by makePeer (offerer), the\n  answerer path, and set_mic.\n\nmain.cc: a web-only WF_COLLAB_AV_AUTOSTART=1 test hook turns mic+cam on once the first\npeer connects (drives the real SetMuted/SetCameraEnabled path without a panel click;\npermission auto-granted under --use-fake-ui-for-media-stream).\n\nVerified web↔web (two headless-Chrome, fake mic): both peers negotiate\nsendrecv/sendrecv, log "ontrack audio", and getStats shows inbound audio RTP bytes > 0\nin BOTH directions. web↔native audio deferred to a Phase-4 spot-check (native\naudio-device dependent; Phase-1 already proved the SDP/ICE interop).\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
f872e3ae	author	Will Norris
f872e3ae	added	135
f872e3ae	deleted	0
f872e3ae	files	1
f872e3ae	body	Feature branch 2026-web-av off 2026-new-level. Bring back the A/V deferred from web\neditor v1: browser-native RTCPeerConnection (no libdatachannel/Opus/libvpx/V4L2 port),\nthe web WebrtcSession/VoiceChat/VideoChat become thin shims over a JS shim, reusing the\nshared relay CH_SIGNAL path so web↔native interoperates. 4 phases, headless fake-media\n+ CDP verification web↔web and web↔native.\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
-->
