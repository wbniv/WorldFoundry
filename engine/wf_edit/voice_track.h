#pragma once
// engine/wf_edit/voice_track.h — Mic capture → Opus encode → UDP send, and
// UDP recv → Opus decode → speaker, for in-editor voice chat.
//
// VoiceChat owns one miniaudio capture device (microphone) and one playback
// device (speaker), plus one OpusEncoder and a map of OpusDecoder (one per
// peer, keyed by peer_id). Audio is 48 kHz mono, 20 ms frames.
//
// Packet wire format (UDP, variable length):
//   [4 bytes big-endian seq] [N bytes Opus payload]

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
};

class VoiceChat {
public:
    VoiceChat();
    ~VoiceChat();

    // Bind the receive socket (on an ephemeral port chosen by the OS) and
    // start the capture device. Returns false if Opus init or socket creation
    // fails. Call ListenPort() after a successful Start() to learn the port.
    bool Start();
    void Stop();

    uint16_t ListenPort() const { return listen_port_; }

    // Mute/unmute the microphone capture.
    void SetMuted(bool muted);
    bool IsMuted() const { return muted_; }

    // Update peer list (called from main thread each frame). Creates decoders
    // for new peers, removes decoders for departed peers.
    void SyncPeers(const std::vector<PeerInfo>& peers);

    // Drain the receive socket and decode incoming Opus packets. Call once
    // per frame from the main thread (non-blocking, safe alongside the capture
    // callback which runs on a miniaudio thread).
    void Tick();

    // UI: per-peer audio level (0..1). Thread-safe.
    float PeerLevel(const std::string& peer_id);

    // Called from the miniaudio device callback. Public so the static
    // DeviceCallback helper in voice_track.cc can reach them.
    void OnCapture(const float* pcm, unsigned int frames);
    void OnPlayback(float* out, unsigned int frames);

private:
    void EncodeAndSend(const float* pcm, int frame_samples);

    bool     muted_       = true;
    int      recv_fd_     = -1;
    int      send_fd_     = -1;
    uint32_t seq_         = 0;
    uint16_t listen_port_ = 0;

    OpusEncoder* encoder_ = nullptr;

    // Peer table: peer_id -> state. Protected by peers_mu_.
    std::mutex                        peers_mu_;
    std::map<std::string, PeerAudio*> peer_audio_;

    // Peer addresses for sending: peer_id -> (ip, port).
    struct PeerAddr { std::string ip; uint16_t port; };
    std::map<std::string, PeerAddr> peer_addrs_;

    // miniaudio device handles (opaque; stored as void* to avoid including
    // miniaudio.h in this header — the implementation includes it).
    void* capture_dev_  = nullptr;
    void* playback_dev_ = nullptr;

    // Encode scratch buffer (Opus max frame = 1275 bytes).
    uint8_t enc_buf_[4 + 1275]{};

    // Accumulate PCM frames until we have a full 20 ms frame (960 samples at
    // 48 kHz). The capture callback may deliver variable-size chunks.
    float    accum_[960]{};
    int      accum_n_ = 0;
};

} // namespace wfedit
