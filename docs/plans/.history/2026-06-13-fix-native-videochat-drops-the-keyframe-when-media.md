| Date | Change |
|------|--------|
| [2026-06-13](https://github.com/wbniv/WorldFoundry/commit/1c7aeafd) | fix(wf-edit): lazy-create per-peer video decoder so a keyframe that beats presence isn't dropped |

<!--history-meta v1
1c7aeafd	author	Will Norris
1c7aeafd	added	208
1c7aeafd	deleted	0
1c7aeafd	files	1
1c7aeafd	body	VideoChat::OnRemoteVP8Frame dropped frames for a peer not yet in peer_video_,\nbut the per-peer VP8 decoder was created only by the presence-driven SyncPeers.\nA PeerConnection — and its inbound media — can be created ahead of presence by\nWebrtcSession::OnSignal (GetOrCreate on an inbound offer, "create PeerState if we\nreceive an offer before SyncPeers fires"), so media beats the decoder. When the\ndropped frame was the initial keyframe and the sender was a browser (one keyframe,\nthen relies on RTCP PLI), the decoder stayed waiting_for_keyframe forever → blank\nremote video. Native↔native self-healed in ~1 s via the periodic keyframe but\nstill flickered blank. Audio tolerated the same race (each Opus packet is\nindependently decodable).\n\nFix: lazy-create the decoder on first media via a shared EnsurePeer helper used by\nboth SyncPeers (presence) and OnRemoteVP8Frame (media); mirrored in\nVoiceChat::OnRemoteOpus for symmetry. Safe against the SyncPeers reap loop: media\nonly flows for a peer whose PeerConnection survived WebrtcSession::SyncPeers — i.e.\na peer in the same roster that drives reaping — so a media-producing peer is never\nreaped. Thread-safe: vpx_codec_dec_init already runs on the network thread today\nvia ResetDecoder, and both lazy-create paths hold the existing peers_mu_.\n\nRegression test (WF_EDIT_VIDEO_RACE_TEST / ctest wf_edit_video_race): encodes a\nreal VP8 keyframe with libvpx and feeds it to an unregistered peer, asserting it\ndecodes (new GL-free PeerHasFrame probe), with a delta-frame negative control and\nan Opus mirror. Verified FAIL on the pre-fix drop, PASS after.\n\nRTCP PLI (TODO.md) stays separate — it covers genuinely lost keyframes for an\nalready-registered waiting peer, not this decoder-creation race.\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
-->
