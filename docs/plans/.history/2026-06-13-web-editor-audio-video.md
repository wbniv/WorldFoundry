| Date | Change |
|------|--------|
| [2026-06-13](https://github.com/wbniv/WorldFoundry/commit/f872e3ae) | docs(wf-edit/web): plan voice+video (A/V) over browser WebRTC + TODO entry |

<!--history-meta v1
f872e3ae	author	Will Norris
f872e3ae	added	135
f872e3ae	deleted	0
f872e3ae	files	1
f872e3ae	body	Feature branch 2026-web-av off 2026-new-level. Bring back the A/V deferred from web\neditor v1: browser-native RTCPeerConnection (no libdatachannel/Opus/libvpx/V4L2 port),\nthe web WebrtcSession/VoiceChat/VideoChat become thin shims over a JS shim, reusing the\nshared relay CH_SIGNAL path so web↔native interoperates. 4 phases, headless fake-media\n+ CDP verification web↔web and web↔native.\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
-->
