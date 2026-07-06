// collab_stub_web.cc — browser/WASM peer-discovery shim for wf_edit_web.
//
// The browser has no UDP multicast, so CollabSession's multicast peer discovery
// (collab_session.cc) is replaced here by a relay-only stub: Start() records the
// identity, and presence flows entirely through the relay (SetRelayPeers / Peers).
// main.cc keeps calling it unchanged.
//
// The A/V classes (VoiceChat / VideoChat / WebrtcSession) used to be stubbed here
// too; they now have REAL browser-WebRTC implementations in webrtc_web.cc (the
// browser's RTCPeerConnection replaces libdatachannel/Opus/libvpx/V4L2). This TU
// is discovery-only. See docs/plans/2026-06-13-web-editor-audio-video.md.

#if defined(__EMSCRIPTEN__)

#include "collab_session.h"

#include <chrono>

namespace wfedit {

// ── MonoNow (used by main.cc's presence cadence) ────────────────────────────
double MonoNow() {
    using namespace std::chrono;
    return duration<double>(steady_clock::now().time_since_epoch()).count();
}

// ── CollabSession ───────────────────────────────────────────────────────────
// No multicast in the browser. Start() records identity so OurPeerId() works;
// presence flows entirely through the relay (SetRelayPeers / Peers).
CollabSession::CollabSession() = default;
CollabSession::~CollabSession() = default;

bool CollabSession::Start(const std::string& room_id, const std::string& display_name,
                          const std::string& peer_id,
                          uint16_t audio_port, uint16_t video_port) {
    room_id_      = room_id;
    display_name_ = display_name;
    our_peer_id_  = peer_id;
    audio_port_   = audio_port;
    video_port_   = video_port;
    return true;   // "started" — relay presence will populate Peers()
}

void CollabSession::Stop() {}
void CollabSession::Tick(double /*now_sec*/) {}

void CollabSession::SetRelayPeers(const std::vector<PeerInfo>& relay_peers) {
    relay_peers_  = relay_peers;
    merged_dirty_ = true;
}

const std::vector<PeerInfo>& CollabSession::Peers() const {
    // Web: relay peers are the only peers (no multicast).
    return relay_peers_;
}

} // namespace wfedit

#endif // __EMSCRIPTEN__
