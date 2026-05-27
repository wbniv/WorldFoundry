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

class WebrtcSession {
public:
    // Constructor wires the send callbacks on vc/vd so that encoded media is
    // routed through WebRTC rather than raw UDP. Keeps pointers but does NOT
    // take ownership.
    explicit WebrtcSession(VoiceChat* vc, VideoChat* vd);
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
