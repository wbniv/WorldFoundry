#pragma once
// engine/wf_edit/video_track.h — V4L2 camera → VP8 encode → WebRTC RTP, and
// WebRTC RTP → VP8 decode → OpenGL texture, for in-editor video chat.
//
// VideoChat owns a background capture thread (V4L2 → encode → send_cb).
// Incoming VP8 is delivered via OnRemoteVP8Frame (called by WebrtcSession from
// its track receive callback). Decoded frames are stored as RGB pixel buffers;
// the main thread uploads them to GL textures each frame.
//
// Capture resolution: 320×240 (YUYV), scaled to 160×120 for thumbnails.

#include <functional>
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

    // When true the decoder was reset after an error; discard frames until the
    // next VP8 keyframe resyncs the decoder reference-frame state.
    bool waiting_for_keyframe = true;

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

    // Open /dev/video0 for capture (non-fatal if absent). Never fails due to
    // network — media is now routed via WebRTC.
    bool Start();
    void Stop();

    // Always 0; port is no longer advertised (media routed via WebRTC).
    uint16_t ListenPort() const { return 0; }

    // Set the outgoing send callback. Called from the V4L2 capture thread with
    // a complete VP8 frame (no RTP header). Pass nullptr to disable sending.
    void SetSendCallback(std::function<void(const uint8_t*, int, bool)> cb);

    // Deliver an incoming VP8 frame from the named peer. Called by
    // WebrtcSession from its track receive callback (any thread).
    void OnRemoteVP8Frame(const std::string& peer_id,
                          const uint8_t* vp8, int len, bool is_key);

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

    // True if a decoded frame is pending upload for this peer (GL-free probe;
    // mirrors VoiceChat::PeerLevel). Used by the headless video-race test.
    bool PeerHasFrame(const std::string& peer_id);

    // RGB pixel buffer for self-preview (may be empty). Main-thread only.
    const std::vector<uint8_t>& SelfPreview() const { return self_preview_; }

private:
    void CaptureThread();

    bool OpenCamera();
    void CloseCamera();
    bool GrabFrame(std::vector<uint8_t>& yuyv_out);
    void YuyvToI420(const uint8_t* yuyv, int w, int h,
                    std::vector<uint8_t>& i420_out);
    void I420ToRgb160x120(const uint8_t* i420, int src_w, int src_h,
                          std::vector<uint8_t>& rgb_out);

    void EncodeAndSend(const std::vector<uint8_t>& i420, bool force_keyframe);

    // Return the PeerVideo for peer_id, creating its VP8 decoder on first use.
    // Caller MUST hold peers_mu_. nullptr only if decoder init fails. Shared by
    // SyncPeers (presence-driven) and OnRemoteVP8Frame (media that beats the
    // roster — the decoder-creation race; distinct from the lost-keyframe PLI
    // work in TODO.md).
    PeerVideo* EnsurePeer(const std::string& peer_id);

    std::atomic<bool> cam_enabled_{false};
    std::atomic<bool> running_{false};

    int      cam_fd_ = -1;

    int cap_w_   = 320;
    int cap_h_   = 240;

    // V4L2 mmap buffers.
    struct MmapBuf { void* start; size_t length; };
    std::vector<MmapBuf> mmap_bufs_;

    vpx_codec_ctx* encoder_ = nullptr;
    uint32_t       frame_seq_ = 0;
    int            frames_since_key_ = 0;

    // Outgoing send callback (set by WebrtcSession). Thread-safe via send_cb_mu_.
    std::mutex                                         send_cb_mu_;
    std::function<void(const uint8_t*, int, bool)>    send_cb_;

    std::thread cap_thread_;

    std::mutex                        peers_mu_;
    std::map<std::string, PeerVideo*> peer_video_;

    // Self-preview: latest captured frame scaled to 160×120 RGB.
    std::vector<uint8_t> self_preview_;  // main-thread only
    std::vector<uint8_t> self_preview_pending_;
    std::mutex           self_mu_;
    bool                 self_dirty_ = false;
};

} // namespace wfedit
