// collab_stub_web.cc — no-op implementations of the editor's media/discovery
// classes for the browser/WASM build (wf_edit_web).
//
// v1 of the web editor ships co-edit + presence + text chat over the relay
// (CRDT CH_SYNC + CH_PRESENCE + CH_CHAT, all in main.cc + ws_client). It does
// NOT ship voice/video, and the browser has no UDP multicast. So the four
// classes whose real implementations depend on native-only libs —
//   collab_session.cc  (UDP multicast peer discovery)
//   voice_track.cc      (miniaudio capture + Opus)
//   video_track.cc      (V4L2 capture + libvpx)
//   webrtc_session.cc   (libdatachannel ICE/DTLS-SRTP)
// — are replaced by these stubs in the web target. main.cc keeps calling them
// unchanged; the calls just no-op. Presence is the one exception: the relay
// roster set via CollabSession::SetRelayPeers is returned by Peers(), so the
// Collaborators panel still shows web peers (multicast is simply absent).
//
// See docs/plans/2026-06-12-wf-edit-in-the-browser.md (Phase 1/3).

#if defined(__EMSCRIPTEN__)

#include "collab_session.h"
#include "voice_track.h"
#include "video_track.h"
#include "webrtc_session.h"

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

// ── VoiceChat ───────────────────────────────────────────────────────────────
VoiceChat::VoiceChat() = default;
VoiceChat::~VoiceChat() = default;
bool VoiceChat::Start() { return false; }   // no mic/Opus on web in v1
void VoiceChat::Stop() {}
void VoiceChat::SetSendCallback(std::function<void(const uint8_t*, int)> cb) { send_cb_ = std::move(cb); }
void VoiceChat::OnRemoteOpus(const std::string&, const uint8_t*, int) {}
void VoiceChat::SetMuted(bool muted) { muted_ = muted; }
void VoiceChat::SyncPeers(const std::vector<PeerInfo>&) {}
float VoiceChat::PeerLevel(const std::string&) { return 0.f; }
void VoiceChat::OnCapture(const float*, unsigned int) {}
void VoiceChat::OnPlayback(float*, unsigned int) {}

// ── VideoChat ───────────────────────────────────────────────────────────────
VideoChat::VideoChat() = default;
VideoChat::~VideoChat() = default;
bool VideoChat::Start() { return false; }   // no camera/VP8 on web in v1
void VideoChat::Stop() {}
void VideoChat::SetSendCallback(std::function<void(const uint8_t*, int, bool)> cb) { send_cb_ = std::move(cb); }
void VideoChat::OnRemoteVP8Frame(const std::string&, const uint8_t*, int, bool) {}
void VideoChat::SetCameraEnabled(bool on) { cam_enabled_.store(on); }
void VideoChat::SyncPeers(const std::vector<PeerInfo>&) {}
void VideoChat::UploadFrames() {}
unsigned int VideoChat::PeerTexture(const std::string&) { return 0; }

// ── WebrtcSession (+ free functions) ─────────────────────────────────────────
IceConfig ResolveIceConfig(IceConfig defaults) { return defaults; }
void WebrtcCleanup() {}

WebrtcSession::WebrtcSession(VoiceChat* vc, VideoChat* vd, IceConfig ice)
    : vc_(vc), vd_(vd), ice_(std::move(ice)) {}
WebrtcSession::~WebrtcSession() = default;
void WebrtcSession::SyncPeers(const std::vector<std::string>&, const std::string& our_peer_id) {
    our_peer_id_ = our_peer_id;
}
void WebrtcSession::OnSignal(const std::string&, const std::string&) {}
std::vector<std::pair<std::string, std::string>> WebrtcSession::DrainSignaling() { return {}; }
size_t WebrtcSession::ConnectedPeerCount() { return 0; }

} // namespace wfedit

#endif // __EMSCRIPTEN__
