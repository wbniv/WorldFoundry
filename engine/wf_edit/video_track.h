#pragma once
// engine/wf_edit/video_track.h — V4L2 camera capture → VP8 encode → UDP, and
// UDP receive → VP8 decode → OpenGL texture, for in-editor video chat.
//
// VideoChat owns a background capture thread (V4L2 → encode → UDP send) and a
// receive thread (UDP recv → reassemble → decode). Decoded frames are stored as
// RGB pixel buffers; the main thread uploads them to GL textures each frame.
//
// Capture resolution: 320×240 (YUYV), scaled to 160×120 for thumbnails.
// Fragment size: 1200 bytes (stays under Ethernet MTU).
// Wire packet header (14 bytes):
//   [4 bytes: 'WFV\0'] [4 bytes: frame_seq] [2 bytes: frag_idx]
//   [2 bytes: frag_total] [1 byte: is_keyframe] [1 byte: reserved]

#include <string>
#include <vector>
#include <map>
#include <mutex>
#include <thread>
#include <atomic>
#include <cstdint>
#include <cstddef>

struct vpx_codec_ctx;

namespace wfedit {

struct PeerInfo;  // from collab_session.h

static constexpr int kThumbW = 160;
static constexpr int kThumbH = 120;

// Reassembly buffer for one in-flight VP8 frame.
struct FrameAssembly {
    uint32_t             frame_seq  = 0;
    uint16_t             total_frags = 0;
    bool                 is_keyframe = false;
    std::vector<uint8_t> data;        // accumulated VP8 bitstream bytes
    uint16_t             frags_seen  = 0;
};

// Per-peer received video state.
struct PeerVideo {
    vpx_codec_ctx*   decoder    = nullptr;
    FrameAssembly    assembly;

    // Latest decoded frame as RGB (160×120). Protected by frame_mu.
    std::vector<uint8_t> rgb;    // 160*120*3 bytes, or empty if no frame yet
    std::mutex           frame_mu;
    bool                 frame_dirty = false;  // new frame since last GL upload

    // GL texture (0 = not yet created). Main-thread only.
    unsigned int gl_tex = 0;

    // Audio level display (0..1) — updated by VoiceChat, read here for layout.
    float audio_level = 0.f;
};

class VideoChat {
public:
    VideoChat();
    ~VideoChat();

    // Bind the receive socket on an OS-assigned ephemeral port, and open
    // /dev/video0 for capture (non-fatal if absent). Returns false only if the
    // socket setup fails. Call ListenPort() after a successful Start().
    bool Start();
    void Stop();

    uint16_t ListenPort() const { return listen_port_; }

    void SetCameraEnabled(bool on);
    bool IsCameraEnabled() const { return cam_enabled_.load(); }

    // Update peer list from CollabSession. Thread-safe.
    void SyncPeers(const std::vector<PeerInfo>& peers);

    // Call from the main (GL) thread each frame. Uploads any new decoded frames
    // to GL textures. Returns the list of peers with updated textures.
    void UploadFrames();

    // GL texture handle for the given peer (0 if no frame received yet).
    // Main-thread only.
    unsigned int PeerTexture(const std::string& peer_id);

    // RGB pixel buffer for self-preview (may be empty). Main-thread only.
    const std::vector<uint8_t>& SelfPreview() const { return self_preview_; }

private:
    void CaptureThread();
    void RecvThread();

    bool OpenCamera();
    void CloseCamera();
    bool GrabFrame(std::vector<uint8_t>& yuyv_out);
    void YuyvToI420(const uint8_t* yuyv, int w, int h,
                    std::vector<uint8_t>& i420_out);
    void I420ToRgb160x120(const uint8_t* i420, int src_w, int src_h,
                          std::vector<uint8_t>& rgb_out);

    void EncodeAndSend(const std::vector<uint8_t>& i420, bool force_keyframe);
    void HandleRecvPacket(const uint8_t* buf, int len,
                          const std::string& sender_ip);

    std::atomic<bool> cam_enabled_{false};
    std::atomic<bool> running_{false};

    int      cam_fd_      = -1;
    int      recv_fd_     = -1;
    int      send_fd_     = -1;
    uint16_t listen_port_ = 0;

    int cap_w_   = 320;
    int cap_h_   = 240;

    // V4L2 mmap buffers.
    struct MmapBuf { void* start; size_t length; };
    std::vector<MmapBuf> mmap_bufs_;

    vpx_codec_ctx* encoder_ = nullptr;
    uint32_t       frame_seq_ = 0;
    int            frames_since_key_ = 0;

    std::thread cap_thread_;
    std::thread recv_thread_;

    std::mutex                        peers_mu_;
    std::map<std::string, PeerVideo*> peer_video_;

    struct PeerAddr { std::string ip; uint16_t port; };
    std::map<std::string, PeerAddr> peer_addrs_;

    // Self-preview: latest captured frame scaled to 160×120 RGB.
    std::vector<uint8_t> self_preview_;  // main-thread only
    std::vector<uint8_t> self_preview_pending_;
    std::mutex           self_mu_;
    bool                 self_dirty_ = false;
};

} // namespace wfedit
