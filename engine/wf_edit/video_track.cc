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

// Networking
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
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
    // UDP receive socket — bind to port 0 for an OS-assigned ephemeral port.
    recv_fd_ = socket(AF_INET, SOCK_DGRAM, 0);
    if (recv_fd_ < 0) { std::perror("video: recv socket"); return false; }

    struct sockaddr_in addr{};
    addr.sin_family      = AF_INET;
    addr.sin_port        = 0;   // ephemeral
    addr.sin_addr.s_addr = INADDR_ANY;
    if (bind(recv_fd_, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0) {
        std::perror("video: bind"); close(recv_fd_); recv_fd_ = -1; return false;
    }
    socklen_t alen = sizeof(addr);
    getsockname(recv_fd_, reinterpret_cast<sockaddr*>(&addr), &alen);
    listen_port_ = ntohs(addr.sin_port);

    // UDP send socket.
    send_fd_ = socket(AF_INET, SOCK_DGRAM, 0);
    if (send_fd_ < 0) { std::perror("video: send socket"); return false; }

    running_.store(true);

    // Try to open the camera; non-fatal if absent.
    cam_enabled_.store(OpenCamera());
    if (!cam_enabled_.load()) {
        std::fprintf(stderr, "video: no camera available, video-only receive\n");
    }

    // Launch capture + receive threads.
    cap_thread_  = std::thread(&VideoChat::CaptureThread, this);
    recv_thread_ = std::thread(&VideoChat::RecvThread, this);

    std::printf("video: started on UDP port %u\n", listen_port_);
    return true;
}

void VideoChat::Stop()
{
    running_.store(false);
    cam_enabled_.store(false);

    if (cap_thread_.joinable())  cap_thread_.join();
    if (recv_thread_.joinable()) recv_thread_.join();

    CloseCamera();

    if (recv_fd_ >= 0) { close(recv_fd_); recv_fd_ = -1; }
    if (send_fd_ >= 0) { close(send_fd_); send_fd_ = -1; }

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
    }
}

void VideoChat::SyncPeers(const std::vector<PeerInfo>& peers)
{
    std::lock_guard<std::mutex> lk(peers_mu_);

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
        peer_addrs_[pi.peer_id] = { pi.address, pi.video_port };
    }

    for (auto it = peer_video_.begin(); it != peer_video_.end(); ) {
        bool found = false;
        for (const auto& pi : peers) if (pi.peer_id == it->first) { found = true; break; }
        if (!found) {
            auto* pv = it->second;
            if (pv) {
                if (pv->decoder) { vpx_codec_destroy(pv->decoder); delete pv->decoder; }
                // GL texture deletion happens on the main thread in UploadFrames.
                // Mark it by zeroing decoder so UploadFrames skips decode but still
                // deletes the texture.
                pv->decoder = nullptr;
                delete pv;
            }
            peer_addrs_.erase(it->first);
            it = peer_video_.erase(it);
        } else {
            ++it;
        }
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
    if (!encoder_ || send_fd_ < 0) return;

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

        const uint8_t* data = static_cast<const uint8_t*>(pkt->data.frame.buf);
        size_t         size = pkt->data.frame.sz;
        bool           is_key = (pkt->data.frame.flags & VPX_FRAME_IS_KEY) != 0;

        int total_frags = static_cast<int>((size + kMaxFragSize - 1) / kMaxFragSize);
        if (total_frags == 0) total_frags = 1;

        std::lock_guard<std::mutex> lk(peers_mu_);
        for (auto& [pid, addr] : peer_addrs_) {
            struct sockaddr_in dest{};
            dest.sin_family = AF_INET;
            dest.sin_port   = htons(addr.port);
            inet_pton(AF_INET, addr.ip.c_str(), &dest.sin_addr);

            for (int fi = 0; fi < total_frags; ++fi) {
                size_t offset    = static_cast<size_t>(fi * kMaxFragSize);
                size_t frag_size = std::min(static_cast<size_t>(kMaxFragSize),
                                            size - offset);
                uint8_t pkt_buf[kHdrSize + kMaxFragSize];
                std::memcpy(pkt_buf, kMagic, 4);
                uint32_t fs32 = htonl(frame_seq_);
                std::memcpy(pkt_buf + 4, &fs32, 4);
                uint16_t fi16  = htons(static_cast<uint16_t>(fi));
                uint16_t tot16 = htons(static_cast<uint16_t>(total_frags));
                std::memcpy(pkt_buf + 8,  &fi16,  2);
                std::memcpy(pkt_buf + 10, &tot16, 2);
                pkt_buf[12] = is_key ? 1 : 0;
                pkt_buf[13] = 0;
                std::memcpy(pkt_buf + kHdrSize, data + offset, frag_size);
                sendto(send_fd_, pkt_buf,
                       static_cast<size_t>(kHdrSize) + frag_size, 0,
                       reinterpret_cast<sockaddr*>(&dest), sizeof(dest));
            }
        }
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

void VideoChat::RecvThread()
{
    // Incoming fragment reassembly keyed by (sender_ip, frame_seq).
    // Simple single-slot assembler per sender — assumes frames arrive in order.
    std::map<std::string, FrameAssembly> assemblies;

    static uint8_t buf[kHdrSize + kMaxFragSize + 64];
    struct sockaddr_in src{};
    socklen_t src_len = sizeof(src);

    while (running_.load()) {
        // Blocking recv with a short timeout so we can check running_.
        struct timeval tv{ 0, 50000 };  // 50 ms
        setsockopt(recv_fd_, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

        int n = recvfrom(recv_fd_, buf, sizeof(buf), 0,
                         reinterpret_cast<sockaddr*>(&src), &src_len);
        if (n < kHdrSize) continue;
        if (std::memcmp(buf, kMagic, 4) != 0) continue;

        uint32_t frame_seq;
        std::memcpy(&frame_seq, buf + 4, 4);
        frame_seq = ntohl(frame_seq);

        uint16_t frag_idx, frag_total;
        std::memcpy(&frag_idx,   buf + 8,  2);
        std::memcpy(&frag_total, buf + 10, 2);
        frag_idx   = ntohs(frag_idx);
        frag_total = ntohs(frag_total);

        bool is_key = buf[12] != 0;

        char sender_ip[INET_ADDRSTRLEN]{};
        inet_ntop(AF_INET, &src.sin_addr, sender_ip, sizeof(sender_ip));
        std::string key = sender_ip;

        auto& asm_ = assemblies[key];
        if (asm_.frame_seq != frame_seq || asm_.total_frags != frag_total) {
            asm_.frame_seq   = frame_seq;
            asm_.total_frags = frag_total;
            asm_.is_keyframe = is_key;
            asm_.data.clear();
            asm_.frags_seen  = 0;
        }

        int payload = n - kHdrSize;
        size_t offset = static_cast<size_t>(frag_idx) * kMaxFragSize;
        if (asm_.data.size() < offset + static_cast<size_t>(payload))
            asm_.data.resize(offset + static_cast<size_t>(payload));
        std::memcpy(asm_.data.data() + offset, buf + kHdrSize,
                    static_cast<size_t>(payload));
        ++asm_.frags_seen;

        if (asm_.frags_seen < frag_total) continue;

        // Full frame assembled — decode and store.
        HandleRecvPacket(asm_.data.data(),
                         static_cast<int>(asm_.data.size()), sender_ip);
        asm_.frags_seen = 0;
    }
}

void VideoChat::HandleRecvPacket(const uint8_t* vp8_data, int len,
                                  const std::string& sender_ip)
{
    std::lock_guard<std::mutex> lk(peers_mu_);

    PeerVideo* pv = nullptr;
    for (auto& [pid, addr] : peer_addrs_) {
        if (addr.ip == sender_ip) {
            auto it = peer_video_.find(pid);
            if (it != peer_video_.end()) pv = it->second;
            break;
        }
    }
    if (!pv || !pv->decoder) return;

    if (vpx_codec_decode(pv->decoder, vp8_data, static_cast<unsigned>(len),
                          nullptr, 0) != VPX_CODEC_OK)
        return;

    vpx_codec_iter_t iter = nullptr;
    vpx_image_t* img;
    while ((img = vpx_codec_get_frame(pv->decoder, &iter))) {
        if (img->fmt != VPX_IMG_FMT_I420) continue;

        // Convert decoded I420 to 160×120 RGB.
        std::vector<uint8_t> rgb;
        // Reassemble I420 from libvpx planes (Y, U, V may have stride padding).
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

        // Reuse VideoChat::I420ToRgb160x120 via a helper lambda.
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
                rgb[idx]     = cl(r);
                rgb[idx + 1] = cl(g);
                rgb[idx + 2] = cl(b);
            }
        }

        std::lock_guard<std::mutex> flk(pv->frame_mu);
        pv->rgb         = std::move(rgb);
        pv->frame_dirty = true;
    }
}

} // namespace wfedit
