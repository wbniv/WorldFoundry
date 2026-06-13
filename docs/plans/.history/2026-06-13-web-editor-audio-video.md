| Date | Change |
|------|--------|
| [2026-06-13](https://github.com/wbniv/WorldFoundry/commit/0392ea0e) | feat(wf-edit/web): A/V Phase 4 — video overlay positioning + robustness + mesh |
| [2026-06-13](https://github.com/wbniv/WorldFoundry/commit/2a5eee58) | feat(wf-edit/web): A/V Phase 3 — video (camera + remote <video>, bidirectional) |
| [2026-06-13](https://github.com/wbniv/WorldFoundry/commit/b7316645) | feat(wf-edit/web): A/V Phase 2 — voice (getUserMedia mic, bidirectional) |
| [2026-06-13](https://github.com/wbniv/WorldFoundry/commit/f872e3ae) | docs(wf-edit/web): plan voice+video (A/V) over browser WebRTC + TODO entry |

<!--history-meta v1
0392ea0e	author	Will Norris
0392ea0e	added	12
0392ea0e	deleted	4
0392ea0e	files	1
0392ea0e	body	- collab_panel.cc (web): each frame, position each peer's remote-video <video> and the\n  self-preview <video> over their panel-thumbnail rects (ImGui::GetCursorScreenPos +\n  kThumbW/H → wfwebrtc_layout_video/_self); ImGui screen coords map 1:1 to CSS px on\n  emscripten GLFW, so no DPR correction needed. Panel collapse/close → hide_all_video.\n- shell-edit.html: #wf-video-layer overlay container (pointer-events:none, z-index 10,\n  over the canvas) + a beforeunload that closes RTCPeerConnections so peers see the drop\n  immediately (relay presence backstops it otherwise).\n- webrtc_web.cc: wfwebrtc_hide_all_video; PC connectionState 'failed' → close + recreate\n  a fresh PC (re-derive offerer), mirroring native's re-sync.\n\nVerified web↔web: remote <video> display:block, videoWidth=320, positioned 162×122 over\nthe panel thumbnail; screenshot shows the live fake-camera tiles over the Collaborators\npanel. 3-peer full mesh: each peer connected to BOTH others and receiving media from\nboth (validates unicast to_peer_id routing).\n\nDeferred (minor, noted in plan): AnalyserNode level meters (flat meter, not broken);\nweb↔native MEDIA spot-check (connect/SDP/ICE interop already proven in Phase 1; full\nmedia interop needs native A/V hardware — a manual check).\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
2a5eee58	author	Will Norris
2a5eee58	added	9
2a5eee58	deleted	5
2a5eee58	files	1
2a5eee58	body	webrtc_web.cc: wfwebrtc_set_cam acquires getUserMedia({video:320x240}) and replaceTrack's\nit into each peer's pre-negotiated video transceiver (no renegotiation — same sendrecv\nmechanism as audio); remote ontrack video → an overlay <video> element; a mirrored\nself-preview <video>; and wfwebrtc_layout_video/_self to position the overlay elements\nover the canvas (CSS px). Elements append to #wf-video-layer (shell) or <body>.\n\nVerified web↔web (two headless-Chrome, --use-fake-device-for-media-stream): both peers\nshow inbound AND outbound VIDEO RTP bytes (getStats vin/vout > 0) and the remote\n<video>.videoWidth == 320 — bidirectional video, alongside the Phase-2 audio.\n\nThe overlay POSITIONING (driving layout_video/_self from collab_panel.cc + the\n#wf-video-layer container) is Phase 4 (UI), where the panel lives; the <video> elements\ndecode now but stay display:none until positioned.\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
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
