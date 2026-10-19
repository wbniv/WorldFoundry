#pragma once
// engine/wf_edit/webrtc_session.h — WebRTC PeerConnection per remote peer.
//
// One WebrtcSession is shared by the editor; it manages one rtc::PeerConnection
// per discovered peer. Media: Opus RTP (PT=111, RFC 7587) + VP8 RTP (PT=96,
// RFC 7741). Transport: ICE + DTLS-SRTP (encrypted end-to-end; relay/TURN see
// only ciphertext). Signaling: SDP + trickle ICE via CH_SIGNAL on the relay.
//
// Thread safety: SyncPeers/OnSignal/DrainSignaling are main-thread only.
// SendOpus/SendVP8 are called from the miniaudio/V4L2 capture threads via
// VoiceChat/VideoChat send callbacks — both are guarded by peers_mu_ / rtp_mu_.
//
// Plan: docs/plans/2026-05-26-internet-voice-video-webrtc.md Phase 2

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <utility>
#include <vector>

namespace rtc { class PeerConnection; class Track; }

namespace wfedit {

class VoiceChat;
class VideoChat;

// ICE/TURN configuration for every PeerConnection this session creates.
// Defaults come from identity.json (passed to the constructor); the WF_COLLAB_*
// environment variables override per-field at construction time (see
// ResolveIceConfig in webrtc_session.cc). Plan:
// docs/plans/2026-05-27-webrtc-phase3-turn-generic-client.md
struct IceConfig {
    // STUN server URL. Empty disables STUN; default is Google's public STUN.
    std::string stun_url = "stun:stun.l.google.com:19302";
    // TURN relay (Phase 3). turn_host empty = no TURN (STUN-only, the default).
    // Credentials are plain strings here; whether they are static or minted by
    // an ephemeral-credential service lives behind this struct (deferred).
    std::string turn_host;            // host only (port is separate)
    uint16_t    turn_port = 3478;     // 5349 is the conventional TURNS port
    std::string turn_user;
    std::string turn_pass;
    bool        turn_tls   = false;   // true → RelayType::TurnTls (TURN-over-TLS)
    // Force ICE to use ONLY relay candidates (TransportPolicy::Relay). Off by
    // default; used to prove the TURN path without a real symmetric NAT.
    bool        force_relay = false;
};

// Resolve identity.json defaults + WF_COLLAB_* environment overrides into the
// effective IceConfig (env wins per-field). The single source of the env
// precedence; exposed for the headless WF_EDIT_TURN_TEST.
IceConfig ResolveIceConfig(IceConfig defaults);

// Join libdatachannel's global threads and free its globals (wraps rtc::Cleanup).
// Call once after all WebrtcSessions are destroyed and before process exit so
// LeakSanitizer doesn't flag the framework's otherwise-persistent globals. No
// rtc object may be created afterwards without a fresh Preload.
void WebrtcCleanup();

class WebrtcSession {
public:
    // Constructor wires the send callbacks on vc/vd so that encoded media is
    // routed through WebRTC rather than raw UDP. Keeps pointers but does NOT
    // take ownership. `ice` supplies the STUN/TURN defaults (env overrides).
    explicit WebrtcSession(VoiceChat* vc, VideoChat* vd, IceConfig ice = {});
    ~WebrtcSession();

    // Update the set of known peers. Adds PeerConnections for new peers
    // (lower peer_id = offerer); tears down connections for departed peers.
    // Call once per frame from the main thread.
    void SyncPeers(const std::vector<std::string>& peer_ids,
                   const std::string& our_peer_id);

    // Process a CH_SIGNAL frame received from the relay.
    // `from_peer`   — sender's peer_id (parsed from JSON "from" field by caller)
    // `json_payload` — full JSON string (offer / answer / candidate)
    void OnSignal(const std::string& from_peer, const std::string& json_payload);

    // Drain queued outgoing signaling messages (SDP + trickle ICE).
    // Returns pairs of {to_peer_id, json_payload} ready to be sent via relay.
    std::vector<std::pair<std::string,std::string>> DrainSignaling();

    // Number of peers whose PeerConnection has reached the ICE Connected state.
    // Thread-safe; used by the headless TURN test to confirm connectivity.
    size_t ConnectedPeerCount();

    // Send an RTCP Picture Loss Indication to a peer, asking it to emit an
    // immediate keyframe (fast video recovery instead of the ~1 s periodic
    // keyframe). No-op if the peer isn't connected or we haven't learned its
    // video SSRC yet. Main-thread only.
    void SendPli(const std::string& peer_id);

    // RTCP PLI wire helpers (RFC 4585 §6.3.1). Pure + public so the headless
    // test can exercise them without a live connection. MakePliPacket builds the
    // 12-byte PSFB/PLI (sender_ssrc = ours, media_ssrc = the stream we want a
    // keyframe for); IsPliPacket recognises a PLI (FMT=1) or FIR (FMT=4) and
    // optionally returns the media-source SSRC. rtc::binary is std::vector<byte>,
    // so MakePliPacket's result feeds Track::send directly.
    static std::vector<std::byte> MakePliPacket(uint32_t sender_ssrc, uint32_t media_ssrc);
    static bool IsPliPacket(const std::byte* data, size_t len,
                            uint32_t* out_media_ssrc = nullptr);

private:
    struct PeerState;
    using PeerStatePtr = std::shared_ptr<PeerState>;

    PeerStatePtr GetOrCreate(const std::string& peer_id, bool is_offerer);
    void         TearDown(const std::string& peer_id);
    void         QueueSignal(const std::string& to, const std::string& json);

    // Called from VoiceChat/VideoChat send callbacks (capture/encode threads).
    void SendOpus(const uint8_t* opus, int opus_len);
    void SendVP8 (const uint8_t* vp8,  int vp8_len, bool keyframe);

    VoiceChat*  vc_ = nullptr;
    VideoChat*  vd_ = nullptr;
    std::string our_peer_id_;
    IceConfig   ice_;   // resolved (identity.json defaults + env overrides)
    bool        video_debug_ = false;  // WF_COLLAB_VIDEO_DEBUG: log PLI send/recv

    std::mutex  peers_mu_;
    std::map<std::string, PeerStatePtr> peers_;

    std::mutex  sig_mu_;
    std::vector<std::pair<std::string,std::string>> pending_signals_;

    // RTP state shared across peers (one sequence/timestamp stream per codec).
    std::mutex  rtp_mu_;
    uint16_t    audio_seq_  = 0;
    uint32_t    audio_ts_   = 0;
    uint32_t    audio_ssrc_ = 0;
    uint16_t    video_seq_  = 0;
    uint32_t    video_ts_   = 0;
    uint32_t    video_ssrc_ = 0;
};

} // namespace wfedit
