// webrtc_web.cc — browser-WebRTC implementation of WebrtcSession / VoiceChat /
// VideoChat for the WASM editor (wf_edit_web).
//
// The native editor (webrtc_session.cc + voice_track.cc + video_track.cc) owns the
// whole media pipeline via libdatachannel + Opus + libvpx + V4L2 + miniaudio. The
// browser already has all of that natively (RTCPeerConnection, getUserMedia, Opus/
// VP8, DTLS-SRTP, ICE/STUN/TURN), so here the same C++ interfaces become thin shims
// over a per-peer JS RTCPeerConnection. main.cc's integration block is unchanged;
// the SDP/ICE JSON wire + the lower-peer-id-offers rule are identical to native, so a
// browser peer and a native wf-edit peer interoperate in the same relay room.
//
// Bridge model (no --js-library; all EM_JS, self-contained):
//   C++ → JS : EM_JS functions below drive a lazily-created globalThis.__WFRTC state
//              object (a peer map + an outbox of pending signals).
//   JS → C++ : NO reentrant callback — outgoing SDP/ICE land in __WFRTC.outbox, and
//              WebrtcSession::DrainSignaling() polls it once per frame via
//              wfwebrtc_take_signals() (a JSON-array string the caller frees). This
//              fits main.cc's existing per-frame DrainSignaling() drain exactly.
//
// Plan: docs/plans/2026-06-13-web-editor-audio-video.md (Phase 1 = signaling + connect).

#if defined(__EMSCRIPTEN__)

#include "webrtc_session.h"
#include "voice_track.h"
#include "video_track.h"

#include <emscripten.h>
#include <nlohmann/json.hpp>

#include <cstdlib>
#include <cstring>
#include <string>

// ── C++ → JS bridge (EM_JS) ─────────────────────────────────────────────────

// Record our peer_id (stamped as the "from" field on outgoing signals) + the ICE
// server config (JSON) every RTCPeerConnection is built with. Also installs the
// shared makePeer() helper on the state object (so create_peer + the lazy answerer
// path in on_signal use identical PC wiring — EM_JS blocks can only share code via
// globalThis). SyncPeers calls this from frame 1, long before any network round-trip
// could deliver a remote offer, so makePeer is always present by the time on_signal runs.
EM_JS(void, wfwebrtc_set_self, (const char* self_p, const char* ice_json_p), {
    var S = (globalThis.__WFRTC ||= { peers:{}, outbox:[], self:'', ice:{}, mic:null, cam:null });
    S.self = UTF8ToString(self_p);
    try { S.ice = JSON.parse(UTF8ToString(ice_json_p)); } catch (e) { S.ice = {}; }

    if (!S.makePeer) {
        S.makePeer = function (pid, isOfferer) {
            if (S.peers[pid]) return S.peers[pid];
            var pc = new RTCPeerConnection(S.ice);
            var P = S.peers[pid] = { pc: pc, connected: false, audioEl: null, videoEl: null,
                                     audioTx: null, videoTx: null };
            // Up-front audio+video transceivers so the media m-lines exist from the
            // first offer (matches native's "tracks present at PC creation" SDP → no
            // renegotiation, codec-compatible with libdatachannel). Local tracks are
            // attached later via replaceTrack when the user enables mic/cam.
            try {
                P.audioTx = pc.addTransceiver('audio', { direction: 'sendrecv' });
                P.videoTx = pc.addTransceiver('video', { direction: 'sendrecv' });
            } catch (e) { console.error('webrtc(web): addTransceiver', e); }
            try {
                if (S.mic && P.audioTx) P.audioTx.sender.replaceTrack(S.mic.getAudioTracks()[0] || null);
                if (S.cam && P.videoTx) P.videoTx.sender.replaceTrack(S.cam.getVideoTracks()[0] || null);
            } catch (e) {}

            pc.onicecandidate = function (ev) {
                if (ev.candidate) {
                    S.outbox.push({ to: pid, json: JSON.stringify({
                        type: 'candidate', candidate: ev.candidate.candidate,
                        sdpMid: ev.candidate.sdpMid || '', from: S.self }) });
                }
            };
            pc.onconnectionstatechange = function () {
                P.connected = (pc.connectionState === 'connected');
                console.log('webrtc(web): peer ' + pid.substring(0,8) + ' ' + pc.connectionState);
            };
            pc.ontrack = function (ev) {
                console.log('webrtc(web): ontrack ' + ev.track.kind + ' from ' + pid.substring(0,8));
                if (globalThis.__wfrtcAttachTrack) globalThis.__wfrtcAttachTrack(pid, ev);
            };
            if (isOfferer) {
                pc.createOffer().then(function (off) { return pc.setLocalDescription(off); })
                  .then(function () {
                      S.outbox.push({ to: pid, json: JSON.stringify({
                          type: 'offer', sdp: pc.localDescription.sdp, from: S.self }) });
                  }).catch(function (e) { console.error('webrtc(web): createOffer', e); });
            }
            return P;
        };
    }
});

EM_JS(void, wfwebrtc_create_peer, (const char* peer_id_p, int is_offerer), {
    var S = globalThis.__WFRTC;
    if (!S || !S.makePeer) { console.error('webrtc(web): create_peer before set_self'); return; }
    S.makePeer(UTF8ToString(peer_id_p), !!is_offerer);
});

// Apply an inbound CH_SIGNAL JSON (offer/answer/candidate). Lazily creates the PC as
// answerer if an offer arrives before SyncPeers ran (mirrors native GetOrCreate-in-OnSignal).
EM_JS(void, wfwebrtc_on_signal, (const char* peer_id_p, const char* json_p), {
    var pid = UTF8ToString(peer_id_p);
    var msg; try { msg = JSON.parse(UTF8ToString(json_p)); } catch (e) { return; }
    var S = globalThis.__WFRTC;
    if (!S || !S.makePeer) { console.error('webrtc(web): on_signal before set_self'); return; }
    var P = S.peers[pid] || S.makePeer(pid, false);   // lazy answerer
    if (!P) return;
    var pc = P.pc;

    if (msg.type === 'offer' || msg.type === 'answer') {
        pc.setRemoteDescription({ type: msg.type, sdp: msg.sdp }).then(function () {
            if (msg.type === 'offer') {
                return pc.createAnswer().then(function (ans) { return pc.setLocalDescription(ans); })
                    .then(function () {
                        S.outbox.push({ to: pid, json: JSON.stringify({
                            type: 'answer', sdp: pc.localDescription.sdp, from: S.self }) });
                    });
            }
        }).catch(function (e) { console.error('webrtc(web): setRemoteDescription', e); });
    } else if (msg.type === 'candidate') {
        if (msg.candidate) {
            pc.addIceCandidate({ candidate: msg.candidate, sdpMid: msg.sdpMid })
              .catch(function (e) { console.error('webrtc(web): addIceCandidate', e); });
        }
    }
});

EM_JS(void, wfwebrtc_close_peer, (const char* peer_id_p), {
    var pid = UTF8ToString(peer_id_p);
    var S = globalThis.__WFRTC; if (!S) return;
    var P = S.peers[pid]; if (!P) return;
    try { P.pc.close(); } catch (e) {}
    if (P.audioEl) { P.audioEl.srcObject = null; P.audioEl.remove(); }
    if (P.videoEl) { P.videoEl.srcObject = null; P.videoEl.remove(); }
    delete S.peers[pid];
});

EM_JS(void, wfwebrtc_close_all, (void), {
    var S = globalThis.__WFRTC; if (!S) return;
    for (var pid in S.peers) {
        try { S.peers[pid].pc.close(); } catch (e) {}
    }
    S.peers = {}; S.outbox = [];
});

// Return the pending outgoing signals as a JSON array string [{to,json},...] (and
// clear the outbox). Caller frees the returned pointer. Empty → "[]".
EM_JS(char*, wfwebrtc_take_signals, (void), {
    var S = globalThis.__WFRTC; if (!S || !S.outbox.length) return stringToNewUTF8('[]');
    var s = JSON.stringify(S.outbox);
    S.outbox = [];
    return stringToNewUTF8(s);
});

EM_JS(int, wfwebrtc_connected_count, (void), {
    var S = globalThis.__WFRTC; if (!S) return 0;
    var n = 0;
    for (var pid in S.peers) if (S.peers[pid].connected) ++n;
    return n;
});

// Media toggles — fully implemented in Phase 2 (mic) / Phase 3 (cam). Phase 1: log only.
EM_JS(void, wfwebrtc_set_mic, (int enabled), {
    console.log('webrtc(web): set_mic ' + enabled + ' (Phase 2)');
});
EM_JS(void, wfwebrtc_set_cam, (int enabled), {
    console.log('webrtc(web): set_cam ' + enabled + ' (Phase 3)');
});
EM_JS(double, wfwebrtc_peer_level, (const char* peer_id_p), { return 0.0; });

namespace wfedit {

// ── ICE config (identity.json defaults + WF_COLLAB_* env, mirrors native) ────
IceConfig ResolveIceConfig(IceConfig cfg) {
    auto env = [](const char* k) -> const char* {
        const char* v = std::getenv(k);
        return (v && *v) ? v : nullptr;
    };
    if (const char* s = env("WF_COLLAB_STUN")) cfg.stun_url = s;
    if (const char* t = env("WF_COLLAB_TURN")) {
        std::string hp = t;
        const auto colon = hp.rfind(':');
        if (colon != std::string::npos && colon + 1 < hp.size()) {
            const std::string port_s = hp.substr(colon + 1);
            if (port_s.find_first_not_of("0123456789") == std::string::npos) {
                const int p = std::atoi(port_s.c_str());
                if (p > 0 && p <= 65535) { cfg.turn_port = static_cast<uint16_t>(p); hp = hp.substr(0, colon); }
            }
        }
        cfg.turn_host = hp;
    }
    if (const char* u = env("WF_COLLAB_TURN_USER")) cfg.turn_user = u;
    if (const char* p = env("WF_COLLAB_TURN_PASS")) cfg.turn_pass = p;
    if (env("WF_COLLAB_TURN_TLS"))    cfg.turn_tls    = true;
    if (env("WF_COLLAB_FORCE_RELAY")) cfg.force_relay = true;
    return cfg;
}

void WebrtcCleanup() {}

// Serialize an IceConfig to the RTCConfiguration JSON the browser consumes (1:1 with
// native's BuildRtcConfig).
static std::string IceConfigToJson(const IceConfig& ice) {
    using json = nlohmann::json;
    json servers = json::array();
    if (!ice.stun_url.empty())
        servers.push_back({ {"urls", ice.stun_url} });
    if (!ice.turn_host.empty()) {
        const std::string scheme = ice.turn_tls ? "turns:" : "turn:";
        const std::string transport = ice.turn_tls ? "?transport=tcp" : "?transport=udp";
        servers.push_back({
            {"urls", scheme + ice.turn_host + ":" + std::to_string(ice.turn_port) + transport},
            {"username", ice.turn_user},
            {"credential", ice.turn_pass} });
    }
    json cfg; cfg["iceServers"] = std::move(servers);
    if (ice.force_relay) cfg["iceTransportPolicy"] = "relay";
    return cfg.dump();
}

// ── WebrtcSession ────────────────────────────────────────────────────────────
WebrtcSession::WebrtcSession(VoiceChat* vc, VideoChat* vd, IceConfig ice)
    : vc_(vc), vd_(vd), ice_(std::move(ice)) {}

WebrtcSession::~WebrtcSession() { wfwebrtc_close_all(); }

void WebrtcSession::SyncPeers(const std::vector<std::string>& peer_ids,
                              const std::string& our_peer_id) {
    if (our_peer_id.empty()) return;
    if (our_peer_id_ != our_peer_id) {
        our_peer_id_ = our_peer_id;
        wfwebrtc_set_self(our_peer_id_.c_str(), IceConfigToJson(ice_).c_str());
    }
    // Add new peers (lower peer_id offers — identical rule to native).
    for (const auto& pid : peer_ids) {
        if (pid.empty() || pid == our_peer_id_) continue;
        if (peers_.find(pid) == peers_.end()) {
            peers_[pid] = nullptr;   // key-as-set; PeerState stays incomplete on web
            wfwebrtc_create_peer(pid.c_str(), our_peer_id_ < pid ? 1 : 0);
        }
    }
    // Remove departed peers.
    for (auto it = peers_.begin(); it != peers_.end();) {
        bool present = false;
        for (const auto& pid : peer_ids) if (pid == it->first) { present = true; break; }
        if (!present) { wfwebrtc_close_peer(it->first.c_str()); it = peers_.erase(it); }
        else ++it;
    }
}

void WebrtcSession::OnSignal(const std::string& from_peer, const std::string& json_payload) {
    // Track the peer so SyncPeers' diff doesn't immediately tear it down if the
    // signal beat the presence roster.
    if (!from_peer.empty() && from_peer != our_peer_id_ && peers_.find(from_peer) == peers_.end())
        peers_[from_peer] = nullptr;
    wfwebrtc_on_signal(from_peer.c_str(), json_payload.c_str());
}

std::vector<std::pair<std::string, std::string>> WebrtcSession::DrainSignaling() {
    std::vector<std::pair<std::string, std::string>> out;
    char* s = wfwebrtc_take_signals();
    if (s) {
        try {
            auto arr = nlohmann::json::parse(s);
            for (auto& e : arr) {
                out.emplace_back(e.value("to", std::string{}), e.value("json", std::string{}));
            }
        } catch (...) {}
        std::free(s);
    }
    return out;
}

size_t WebrtcSession::ConnectedPeerCount() {
    return static_cast<size_t>(wfwebrtc_connected_count());
}

// ── VoiceChat (thin shim — browser captures/encodes/transports/decodes/plays) ──
VoiceChat::VoiceChat() = default;
VoiceChat::~VoiceChat() = default;
bool VoiceChat::Start() { return true; }            // "started"; getUserMedia deferred to first unmute
void VoiceChat::Stop()  { wfwebrtc_set_mic(0); }
void VoiceChat::SetSendCallback(std::function<void(const uint8_t*, int)> cb) { send_cb_ = std::move(cb); }
void VoiceChat::OnRemoteOpus(const std::string&, const uint8_t*, int) {}   // browser <audio> plays remote
void VoiceChat::SetMuted(bool muted) { muted_ = muted; wfwebrtc_set_mic(muted ? 0 : 1); }
void VoiceChat::SyncPeers(const std::vector<PeerInfo>&) {}
float VoiceChat::PeerLevel(const std::string& peer_id) {
    return static_cast<float>(wfwebrtc_peer_level(peer_id.c_str()));
}
void VoiceChat::OnCapture(const float*, unsigned int) {}
void VoiceChat::OnPlayback(float*, unsigned int) {}

// ── VideoChat (thin shim — browser captures/encodes/decodes; <video> overlay) ──
VideoChat::VideoChat() = default;
VideoChat::~VideoChat() = default;
bool VideoChat::Start() { return true; }
void VideoChat::Stop()  { wfwebrtc_set_cam(0); }
void VideoChat::SetSendCallback(std::function<void(const uint8_t*, int, bool)> cb) { send_cb_ = std::move(cb); }
void VideoChat::OnRemoteVP8Frame(const std::string&, const uint8_t*, int, bool) {}  // browser <video> shows remote
void VideoChat::SetCameraEnabled(bool on) { cam_enabled_.store(on); wfwebrtc_set_cam(on ? 1 : 0); }
void VideoChat::SyncPeers(const std::vector<PeerInfo>&) {}
void VideoChat::UploadFrames() {}                    // Phase 3: drives the <video> overlay layout
unsigned int VideoChat::PeerTexture(const std::string&) { return 0; }   // overlay approach → no GL texture

} // namespace wfedit

#endif // __EMSCRIPTEN__
