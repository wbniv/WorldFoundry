// engine/wf_edit/video_track.cc — V4L2 camera → VP8 encode → UDP send, and
// UDP receive → VP8 decode → RGB pixel buffer (uploaded to GL by main thread).

#include "video_track.h"
#include "collab_session.h"

// VP8 codec
#include <vpx/vpx_encoder.h>
#include <vpx/vpx_decoder.h>
#include <vpx/vp8cx.h>
#include <vpx/vp8dx.h>

// V4L2
#include <fcntl.h>
#include <linux/videodev2.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/stat.h>

// POSIX
#include <unistd.h>

// OpenGL (for texture upload; only called from main thread)
#include <GL/gl.h>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <cerrno>

namespace wfedit {

static constexpr int kMaxFragSize = 1200;
// Packet header magic + layout (14 bytes total):
//   [4] 'WFV\0'  [4] frame_seq  [2] frag_idx  [2] frag_total
//   [1] is_keyframe  [1] reserved
static constexpr uint8_t kMagic[4] = { 'W', 'F', 'V', '\0' };
static constexpr int kHdrSize = 14;

// Key frame every 60 frames (~2 s at 30 fps).
static constexpr int kKeyframeInterval = 60;

// ─── VideoChat ───────────────────────────────────────────────────────────────

VideoChat::VideoChat() = default;

VideoChat::~VideoChat()
{
    Stop();
}

bool VideoChat::Start()
{
    running_.store(true);

    // Try to open the camera; non-fatal if absent.
    cam_enabled_.store(OpenCamera());
    if (!cam_enabled_.load()) {
        std::fprintf(stderr, "video: no camera available\n");
    }

    // Launch capture thread (incoming frames arrive via OnRemoteVP8Frame).
    cap_thread_ = std::thread(&VideoChat::CaptureThread, this);

    std::printf("video: started (WebRTC transport)\n");
    return true;
}

void VideoChat::Stop()
{
    running_.store(false);
    cam_enabled_.store(false);

    if (cap_thread_.joinable()) cap_thread_.join();

    CloseCamera();

    if (encoder_) {
        vpx_codec_destroy(encoder_);
        delete encoder_;
        encoder_ = nullptr;
    }

    std::lock_guard<std::mutex> lk(peers_mu_);
    for (auto& [id, pv] : peer_video_) {
        if (pv) {
            if (pv->decoder) { vpx_codec_destroy(pv->decoder); delete pv->decoder; }
            if (pv->gl_tex)  { glDeleteTextures(1, &pv->gl_tex); }
            delete pv;
        }
    }
    peer_video_.clear();
}

void VideoChat::SetCameraEnabled(bool on)
{
    cam_enabled_.store(on);
    if (on && cam_fd_ < 0) {
        cam_enabled_.store(OpenCamera());
    } else if (!on && cam_fd_ >= 0) {
        CloseCamera();   // release the device so the camera LED turns off
    }
}

void VideoChat::SyncPeers(const std::vector<PeerInfo>& peers)
{
    std::lock_guard<std::mutex> lk(peers_mu_);

    // Add VP8 decoders for new peers.
    for (const auto& pi : peers) {
        if (!peer_video_.count(pi.peer_id)) {
            auto* dec_ctx = new vpx_codec_ctx{};
            if (vpx_codec_dec_init(dec_ctx, vpx_codec_vp8_dx(), nullptr, 0) != VPX_CODEC_OK) {
                std::fprintf(stderr, "video: vp8 decoder init failed for peer %s\n",
                             pi.peer_id.c_str());
                delete dec_ctx;
                continue;
            }
            auto* pv = new PeerVideo{};
            pv->decoder = dec_ctx;
            peer_video_[pi.peer_id] = pv;
            std::printf("video: added peer %s\n", pi.peer_id.c_str());
        }
    }

    // Remove decoders for departed peers.
    for (auto it = peer_video_.begin(); it != peer_video_.end(); ) {
        bool found = false;
        for (const auto& pi : peers) if (pi.peer_id == it->first) { found = true; break; }
        if (!found) {
            auto* pv = it->second;
            if (pv) {
                if (pv->decoder) { vpx_codec_destroy(pv->decoder); delete pv->decoder; }
                pv->decoder = nullptr;
                delete pv;
            }
            it = peer_video_.erase(it);
        } else {
            ++it;
        }
    }
}

void VideoChat::SetSendCallback(std::function<void(const uint8_t*, int, bool)> cb)
{
    std::lock_guard<std::mutex> lk(send_cb_mu_);
    send_cb_ = std::move(cb);
}

void VideoChat::OnRemoteVP8Frame(const std::string& peer_id,
                                  const uint8_t* vp8_data, int len, bool /*is_key*/)
{
    std::lock_guard<std::mutex> lk(peers_mu_);
    auto it = peer_video_.find(peer_id);
    if (it == peer_video_.end()) {
        static int s_miss = 0;
        if (++s_miss <= 3)
            std::fprintf(stderr, "video: VP8 frame for unknown peer %s\n", peer_id.c_str());
        return;
    }
    PeerVideo* pv = it->second;
    if (!pv || !pv->decoder) return;

    static int s_recv = 0;
    if (++s_recv <= 5 || s_recv % 150 == 0)
        std::fprintf(stderr, "video: VP8 frame #%d from %s len=%d\n", s_recv, peer_id.c_str(), len);
    std::fflush(stderr);

    if (vpx_codec_decode(pv->decoder, vp8_data, static_cast<unsigned>(len),
                          nullptr, 0) != VPX_CODEC_OK) {
        std::fprintf(stderr, "video: VP8 decode failed frame #%d\n", s_recv); std::fflush(stderr);
        return;
    }

    vpx_codec_iter_t iter = nullptr;
    vpx_image_t* img;
    while ((img = vpx_codec_get_frame(pv->decoder, &iter))) {
        if (img->fmt != VPX_IMG_FMT_I420) continue;

        int src_w = static_cast<int>(img->d_w);
        int src_h = static_cast<int>(img->d_h);
        std::vector<uint8_t> i420_flat(static_cast<size_t>(src_w * src_h * 3 / 2));
        uint8_t* fY = i420_flat.data();
        uint8_t* fU = fY + src_w * src_h;
        uint8_t* fV = fU + src_w * src_h / 4;

        for (int row = 0; row < src_h; ++row)
            std::memcpy(fY + row * src_w,
                        img->planes[VPX_PLANE_Y] + row * img->stride[VPX_PLANE_Y],
                        static_cast<size_t>(src_w));
        for (int row = 0; row < src_h / 2; ++row) {
            std::memcpy(fU + row * src_w / 2,
                        img->planes[VPX_PLANE_U] + row * img->stride[VPX_PLANE_U],
                        static_cast<size_t>(src_w / 2));
            std::memcpy(fV + row * src_w / 2,
                        img->planes[VPX_PLANE_V] + row * img->stride[VPX_PLANE_V],
                        static_cast<size_t>(src_w / 2));
        }

        std::vector<uint8_t> rgb;
        rgb.resize(static_cast<size_t>(kThumbW * kThumbH * 3));
        const uint8_t* sY = i420_flat.data();
        const uint8_t* sU = sY + src_w * src_h;
        const uint8_t* sV = sU + src_w * src_h / 4;

        for (int ty = 0; ty < kThumbH; ++ty) {
            int sy = ty * src_h / kThumbH;
            for (int tx = 0; tx < kThumbW; ++tx) {
                int sx = tx * src_w / kThumbW;
                int y  = sY[sy * src_w + sx];
                int u  = sU[(sy / 2) * (src_w / 2) + sx / 2] - 128;
                int v  = sV[(sy / 2) * (src_w / 2) + sx / 2] - 128;
                int r  = y + (1402 * v) / 1000;
                int g  = y - (344  * u) / 1000 - (714 * v) / 1000;
                int b  = y + (1772 * u) / 1000;
                auto cl = [](int x) -> uint8_t {
                    return static_cast<uint8_t>(x < 0 ? 0 : x > 255 ? 255 : x);
                };
                int idx = (ty * kThumbW + tx) * 3;
                rgb[idx] = cl(r); rgb[idx+1] = cl(g); rgb[idx+2] = cl(b);
            }
        }

        std::lock_guard<std::mutex> flk(pv->frame_mu);
        pv->rgb         = std::move(rgb);
        pv->frame_dirty = true;
        static int s_img = 0;
        if (++s_img <= 3 || s_img % 150 == 0)
            std::fprintf(stderr, "video: decoded image #%d for %.8s (%dx%d → rgb %zu)\n",
                         s_img, peer_id.c_str(), src_w, src_h, pv->rgb.size());
        std::fflush(stderr);
    }
}

void VideoChat::UploadFrames()
{
    std::lock_guard<std::mutex> lk(peers_mu_);
    for (auto& [pid, pv] : peer_video_) {
        if (!pv) continue;

        // Clean up GL texture for departed peers (decoder is nullptr).
        if (!pv->decoder) {
            if (pv->gl_tex) { glDeleteTextures(1, &pv->gl_tex); pv->gl_tex = 0; }
            continue;
        }

        std::lock_guard<std::mutex> flk(pv->frame_mu);
        if (!pv->frame_dirty || pv->rgb.empty()) continue;
        pv->frame_dirty = false;

        if (!pv->gl_tex) {
            glGenTextures(1, &pv->gl_tex);
            glBindTexture(GL_TEXTURE_2D, pv->gl_tex);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, kThumbW, kThumbH, 0,
                         GL_RGB, GL_UNSIGNED_BYTE, pv->rgb.data());
            GLint fbo = 0;
            glGetIntegerv(GL_FRAMEBUFFER_BINDING, &fbo);
            GLenum err = glGetError();
            // Log top-left 3 pixels to verify non-black content.
            std::fprintf(stderr, "video: GL texture %u for %.8s fbo=%d err=%u "
                         "px[0]=(%d,%d,%d) px[1]=(%d,%d,%d) px[2]=(%d,%d,%d)\n",
                         pv->gl_tex, pid.c_str(), fbo, err,
                         pv->rgb[0], pv->rgb[1], pv->rgb[2],
                         pv->rgb[3], pv->rgb[4], pv->rgb[5],
                         pv->rgb[6], pv->rgb[7], pv->rgb[8]);
            std::fflush(stderr);
        } else {
            glBindTexture(GL_TEXTURE_2D, pv->gl_tex);
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, kThumbW, kThumbH,
                            GL_RGB, GL_UNSIGNED_BYTE, pv->rgb.data());
        }
    }
    glBindTexture(GL_TEXTURE_2D, 0);

    // Self-preview.
    std::lock_guard<std::mutex> slk(self_mu_);
    if (self_dirty_ && !self_preview_pending_.empty()) {
        self_preview_ = self_preview_pending_;
        self_dirty_   = false;
    }
}

unsigned int VideoChat::PeerTexture(const std::string& peer_id)
{
    std::lock_guard<std::mutex> lk(peers_mu_);
    auto it = peer_video_.find(peer_id);
    return it != peer_video_.end() ? it->second->gl_tex : 0u;
}

// ─── Camera (V4L2) ──────────────────────────────────────────────────────────

bool VideoChat::OpenCamera()
{
    cam_fd_ = open("/dev/video0", O_RDWR | O_NONBLOCK);
    if (cam_fd_ < 0) {
        std::fprintf(stderr, "video: cannot open /dev/video0: %s\n",
                     std::strerror(errno));
        return false;
    }

    // Set format: YUYV 320×240.
    struct v4l2_format fmt{};
    fmt.type                = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    fmt.fmt.pix.width       = static_cast<unsigned>(cap_w_);
    fmt.fmt.pix.height      = static_cast<unsigned>(cap_h_);
    fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_YUYV;
    fmt.fmt.pix.field       = V4L2_FIELD_ANY;
    if (ioctl(cam_fd_, VIDIOC_S_FMT, &fmt) < 0) {
        std::perror("video: VIDIOC_S_FMT");
        close(cam_fd_); cam_fd_ = -1;
        return false;
    }
    cap_w_ = static_cast<int>(fmt.fmt.pix.width);
    cap_h_ = static_cast<int>(fmt.fmt.pix.height);

    // Request mmap buffers.
    struct v4l2_requestbuffers req{};
    req.count  = 4;
    req.type   = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    req.memory = V4L2_MEMORY_MMAP;
    if (ioctl(cam_fd_, VIDIOC_REQBUFS, &req) < 0) {
        std::perror("video: VIDIOC_REQBUFS");
        close(cam_fd_); cam_fd_ = -1;
        return false;
    }

    mmap_bufs_.resize(req.count);
    for (unsigned i = 0; i < req.count; ++i) {
        struct v4l2_buffer buf{};
        buf.type   = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        buf.memory = V4L2_MEMORY_MMAP;
        buf.index  = i;
        ioctl(cam_fd_, VIDIOC_QUERYBUF, &buf);
        mmap_bufs_[i].length = buf.length;
        mmap_bufs_[i].start  = mmap(nullptr, buf.length,
                                    PROT_READ | PROT_WRITE,
                                    MAP_SHARED, cam_fd_, buf.m.offset);
        // Queue the buffer.
        ioctl(cam_fd_, VIDIOC_QBUF, &buf);
    }

    // Start streaming.
    enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    if (ioctl(cam_fd_, VIDIOC_STREAMON, &type) < 0) {
        std::perror("video: VIDIOC_STREAMON");
        CloseCamera();
        return false;
    }

    // VP8 encoder.
    encoder_ = new vpx_codec_ctx{};
    vpx_codec_enc_cfg_t cfg{};
    vpx_codec_enc_config_default(vpx_codec_vp8_cx(), &cfg, 0);
    cfg.g_w          = static_cast<unsigned>(cap_w_);
    cfg.g_h          = static_cast<unsigned>(cap_h_);
    cfg.rc_target_bitrate = 500;   // kbps
    cfg.g_timebase.num   = 1;
    cfg.g_timebase.den   = 30;
    cfg.g_threads        = 2;
    if (vpx_codec_enc_init(encoder_, vpx_codec_vp8_cx(), &cfg, 0) != VPX_CODEC_OK) {
        std::fprintf(stderr, "video: vp8 encoder init failed\n");
        delete encoder_; encoder_ = nullptr;
        CloseCamera();
        return false;
    }

    std::printf("video: camera %dx%d YUYV\n", cap_w_, cap_h_);
    return true;
}

void VideoChat::CloseCamera()
{
    if (cam_fd_ < 0) return;
    enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    ioctl(cam_fd_, VIDIOC_STREAMOFF, &type);
    for (auto& b : mmap_bufs_) munmap(b.start, b.length);
    mmap_bufs_.clear();
    close(cam_fd_);
    cam_fd_ = -1;
}

bool VideoChat::GrabFrame(std::vector<uint8_t>& yuyv_out)
{
    struct v4l2_buffer buf{};
    buf.type   = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    buf.memory = V4L2_MEMORY_MMAP;
    if (ioctl(cam_fd_, VIDIOC_DQBUF, &buf) < 0) return false;

    const size_t sz = static_cast<size_t>(cap_w_ * cap_h_ * 2);
    yuyv_out.resize(sz);
    std::memcpy(yuyv_out.data(), mmap_bufs_[buf.index].start, sz);

    ioctl(cam_fd_, VIDIOC_QBUF, &buf);
    return true;
}

// ─── Colour-space conversion ─────────────────────────────────────────────────

// YUYV (4:2:2 packed) → I420 (4:2:0 planar).
void VideoChat::YuyvToI420(const uint8_t* yuyv, int w, int h,
                            std::vector<uint8_t>& i420_out)
{
    i420_out.resize(static_cast<size_t>(w * h * 3 / 2));
    uint8_t* Y = i420_out.data();
    uint8_t* U = Y + w * h;
    uint8_t* V = U + (w * h / 4);

    for (int row = 0; row < h; ++row) {
        for (int col = 0; col < w; col += 2) {
            int i = (row * w + col) * 2;
            Y[row * w + col]     = yuyv[i];
            Y[row * w + col + 1] = yuyv[i + 2];
            if ((row & 1) == 0) {
                int ci = (row / 2) * (w / 2) + col / 2;
                U[ci] = yuyv[i + 1];
                V[ci] = yuyv[i + 3];
            }
        }
    }
}

// Nearest-neighbour scale I420 src_w×src_h → 160×120, then convert to RGB.
void VideoChat::I420ToRgb160x120(const uint8_t* i420, int src_w, int src_h,
                                  std::vector<uint8_t>& rgb_out)
{
    rgb_out.resize(kThumbW * kThumbH * 3);
    const uint8_t* src_Y = i420;
    const uint8_t* src_U = src_Y + src_w * src_h;
    const uint8_t* src_V = src_U + (src_w * src_h / 4);

    for (int ty = 0; ty < kThumbH; ++ty) {
        int sy = ty * src_h / kThumbH;
        for (int tx = 0; tx < kThumbW; ++tx) {
            int sx = tx * src_w / kThumbW;

            int y = src_Y[sy * src_w + sx];
            int u = src_U[(sy / 2) * (src_w / 2) + sx / 2] - 128;
            int v = src_V[(sy / 2) * (src_w / 2) + sx / 2] - 128;

            int r = y + (1402 * v) / 1000;
            int g = y - (344  * u) / 1000 - (714 * v) / 1000;
            int b = y + (1772 * u) / 1000;

            auto clamp = [](int x) -> uint8_t {
                return static_cast<uint8_t>(x < 0 ? 0 : x > 255 ? 255 : x);
            };
            int idx = (ty * kThumbW + tx) * 3;
            rgb_out[idx]     = clamp(r);
            rgb_out[idx + 1] = clamp(g);
            rgb_out[idx + 2] = clamp(b);
        }
    }
}

// ─── Encode + send ───────────────────────────────────────────────────────────

void VideoChat::EncodeAndSend(const std::vector<uint8_t>& i420,
                               bool force_keyframe)
{
    if (!encoder_) return;

    vpx_image_t img{};
    vpx_img_wrap(&img, VPX_IMG_FMT_I420,
                 static_cast<unsigned>(cap_w_),
                 static_cast<unsigned>(cap_h_),
                 1,
                 const_cast<uint8_t*>(i420.data()));

    vpx_enc_frame_flags_t flags = 0;
    if (force_keyframe) flags |= VPX_EFLAG_FORCE_KF;

    if (vpx_codec_encode(encoder_, &img, static_cast<vpx_codec_pts_t>(frame_seq_),
                         1, flags, VPX_DL_REALTIME) != VPX_CODEC_OK)
        return;

    const vpx_codec_cx_pkt_t* pkt;
    vpx_codec_iter_t iter = nullptr;
    while ((pkt = vpx_codec_get_cx_data(encoder_, &iter))) {
        if (pkt->kind != VPX_CODEC_CX_FRAME_PKT) continue;

        const uint8_t* data  = static_cast<const uint8_t*>(pkt->data.frame.buf);
        int            size  = static_cast<int>(pkt->data.frame.sz);
        bool           is_key = (pkt->data.frame.flags & VPX_FRAME_IS_KEY) != 0;

        std::lock_guard<std::mutex> lk(send_cb_mu_);
        static int s_sent = 0;
        if (++s_sent <= 5 || s_sent % 150 == 0)
            std::fprintf(stderr, "video: VP8 send #%d len=%d key=%d cb=%s\n",
                         s_sent, size, (int)is_key, send_cb_ ? "yes" : "NO");
        std::fflush(stderr);
        if (send_cb_) send_cb_(data, size, is_key);
    }
}

// ─── Threads ─────────────────────────────────────────────────────────────────

void VideoChat::CaptureThread()
{
    std::vector<uint8_t> yuyv, i420;
    while (running_.load()) {
        if (!cam_enabled_.load() || cam_fd_ < 0) {
            usleep(100000);  // 100 ms idle
            continue;
        }

        if (!GrabFrame(yuyv)) {
            usleep(33333);  // ~30 fps wait
            continue;
        }

        YuyvToI420(yuyv.data(), cap_w_, cap_h_, i420);

        // Self-preview (scaled RGB for the UI).
        std::vector<uint8_t> rgb;
        I420ToRgb160x120(i420.data(), cap_w_, cap_h_, rgb);
        {
            std::lock_guard<std::mutex> lk(self_mu_);
            self_preview_pending_ = std::move(rgb);
            self_dirty_ = true;
        }

        bool force_key = (frames_since_key_++ >= kKeyframeInterval);
        if (force_key) frames_since_key_ = 0;

        EncodeAndSend(i420, force_key);
        ++frame_seq_;

        usleep(33333);  // ~30 fps cap
    }
}

} // namespace wfedit
