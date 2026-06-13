#pragma once
// engine/wf_edit/voice_track.h — Mic capture → Opus encode → WebRTC RTP, and
// WebRTC RTP → Opus decode → speaker, for in-editor voice chat.
//
// VoiceChat owns one miniaudio capture device (microphone) and one playback
// device (speaker), plus one OpusEncoder and a map of OpusDecoder (one per
// peer, keyed by peer_id). Audio is 48 kHz mono, 20 ms frames.
//
// Transport: raw Opus bytes delivered via SetSendCallback (WebrtcSession wraps
// them into RTP). Incoming Opus arrives via OnRemoteOpus (called by WebrtcSession
// from its track receive callback).

#include <functional>
#include <string>
#include <vector>
#include <map>
#include <mutex>
#include <cstdint>
#include <cstddef>

struct OpusEncoder;
struct OpusDecoder;

namespace wfedit {

struct PeerInfo;  // from collab_session.h

// Per-peer received audio state (decoder + PCM ring buffer for playback).
struct PeerAudio {
    OpusDecoder* decoder   = nullptr;
    uint32_t     last_seq  = 0;

    // Ring buffer for decoded PCM (float, mono, 48 kHz).
    static constexpr int kRingSize = 48000 / 10;  // 100 ms at 48 kHz
    float       ring[kRingSize]{};
    int         ring_write = 0;
    int         ring_read  = 0;
    std::mutex  ring_mu;

    // Audio level (0..1) for the UI meter, updated by decode thread.
    float level = 0.f;

    // WF_COLLAB_VOICE_DEBUG counters (received side): total decoded packets and
    // the peak level seen since the last debug print. Lets a two-machine test
    // confirm media is actually flowing from this peer, grep-able on stderr.
    uint64_t recv_count = 0;
    float    recv_peak  = 0.f;
};

class VoiceChat {
public:
    VoiceChat();
    ~VoiceChat();

    // Init Opus encoder + miniaudio devices. Returns false on Opus init failure.
    bool Start();
    void Stop();

    // Always 0; port is no longer advertised (media routed via WebRTC).
    uint16_t ListenPort() const { return 0; }

    // Set the outgoing send callback. Called from the miniaudio capture thread
    // with raw Opus bytes (no RTP header). WebrtcSession sets this at startup.
    // Pass nullptr to disable sending.
    void SetSendCallback(std::function<void(const uint8_t*, int)> cb);

    // Deliver an incoming Opus packet from the named peer. Called by
    // WebrtcSession from its track receive callback (any thread).
    void OnRemoteOpus(const std::string& peer_id, const uint8_t* opus, int len);

    // Mute/unmute the microphone capture.
    void SetMuted(bool muted);
    bool IsMuted() const { return muted_; }

    // Update peer list (called from main thread each frame). Creates decoders
    // for new peers, removes decoders for departed peers.
    void SyncPeers(const std::vector<PeerInfo>& peers);

    // No-op in WebRTC mode (incoming packets arrive via OnRemoteOpus).
    void Tick() {}

    // UI: per-peer audio level (0..1). Thread-safe.
    float PeerLevel(const std::string& peer_id);

    // Called from the miniaudio device callback. Public so the static
    // DeviceCallback helper in voice_track.cc can reach them.
    void OnCapture(const float* pcm, unsigned int frames);
    void OnPlayback(float* out, unsigned int frames);

private:
    void EncodeAndSend(const float* pcm, int frame_samples);

    // Return the PeerAudio for peer_id, creating its Opus decoder on first use.
    // Caller MUST hold peers_mu_. nullptr only if decoder create fails. Mirrors
    // VideoChat::EnsurePeer: Opus tolerated the unknown-peer drop (every packet
    // is independently decodable), but lazy-create removes the asymmetry.
    PeerAudio* EnsurePeer(const std::string& peer_id);

    bool     muted_ = true;

    OpusEncoder* encoder_ = nullptr;

    // Outgoing send callback (set by WebrtcSession). Thread-safe via send_cb_mu_.
    std::mutex                              send_cb_mu_;
    std::function<void(const uint8_t*, int)> send_cb_;

    // Peer table: peer_id -> decoder state. Protected by peers_mu_.
    std::mutex                        peers_mu_;
    std::map<std::string, PeerAudio*> peer_audio_;

    // miniaudio device handles (opaque; stored as void* to avoid including
    // miniaudio.h in this header — the implementation includes it).
    void* capture_dev_  = nullptr;
    void* playback_dev_ = nullptr;

    // Encode scratch buffer (Opus max frame = 1275 bytes).
    uint8_t enc_buf_[1275]{};

    // Accumulate PCM frames until we have a full 20 ms frame (960 samples at
    // 48 kHz). The capture callback may deliver variable-size chunks.
    float    accum_[960]{};
    int      accum_n_ = 0;

    // WF_COLLAB_VOICE_DEBUG: when the env var is set (resolved once in Start),
    // log per-second send/receive stats to stderr so a two-machine call can
    // confirm Opus is actually flowing without watching the UI meters. The
    // 20 ms frame cadence is fixed (48 kHz / 960), so every 50 frames ≈ 1 s.
    bool     voice_debug_   = false;
    uint64_t send_count_    = 0;   // total Opus frames encoded + sent
    float    send_peak_     = 0.f; // peak mic RMS since last send-debug print
};

} // namespace wfedit
