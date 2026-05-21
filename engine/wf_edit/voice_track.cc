// engine/wf_edit/voice_track.cc — Voice chat: mic → Opus → UDP → speaker.
//
// miniaudio is already compiled into the engine (miniaudio_impl.cc defines
// MINIAUDIO_IMPLEMENTATION). Include the header here for declarations only.

#include "voice_track.h"
#include "collab_session.h"   // PeerInfo

#include <miniaudio/miniaudio.h>
#include <opus/opus.h>

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>

namespace wfedit {

// We store ma_device as void* in the header to avoid pulling in miniaudio.h
// there. Wrap both devices in a small POD struct allocated on the heap.
struct VoiceDevices {
    ma_device capture;
    ma_device playback;
};

// ─── Capture handler ────────────────────────────────────────────────────────

void VoiceChat::OnCapture(const float* pcm, unsigned int frames)
{
    if (muted_) return;

    // Accumulate into 960-sample frames (20 ms @ 48 kHz).
    unsigned int in_pos = 0;
    while (in_pos < frames) {
        int space = 960 - accum_n_;
        int take  = static_cast<int>(frames - in_pos);
        if (take > space) take = space;
        std::memcpy(accum_ + accum_n_, pcm + in_pos,
                    static_cast<size_t>(take) * sizeof(float));
        accum_n_ += take;
        in_pos   += static_cast<unsigned>(take);
        if (accum_n_ == 960) {
            EncodeAndSend(accum_, 960);
            accum_n_ = 0;
        }
    }
}

// ─── Playback callback ──────────────────────────────────────────────────────

void VoiceChat::OnPlayback(float* out, unsigned int frames)
{
    // Mix all peer ring buffers into the output.
    std::memset(out, 0, frames * sizeof(float));
    std::lock_guard<std::mutex> lk(peers_mu_);
    for (auto& [id, pa] : peer_audio_) {
        if (!pa) continue;
        std::lock_guard<std::mutex> plk(pa->ring_mu);
        for (unsigned int i = 0; i < frames; ++i) {
            int avail = (pa->ring_write - pa->ring_read + PeerAudio::kRingSize)
                        % PeerAudio::kRingSize;
            if (avail == 0) break;
            out[i] += pa->ring[pa->ring_read];
            pa->ring_read = (pa->ring_read + 1) % PeerAudio::kRingSize;
        }
    }
}

// ─── Device callbacks (miniaudio style) ─────────────────────────────────────

static void DeviceCallback(ma_device* dev, void* output,
                           const void* input, ma_uint32 frames)
{
    VoiceChat* vc = static_cast<VoiceChat*>(dev->pUserData);
    if (!vc) return;
    if (dev->type == ma_device_type_capture) {
        vc->OnCapture(static_cast<const float*>(input), frames);
    } else if (dev->type == ma_device_type_playback) {
        vc->OnPlayback(static_cast<float*>(output), frames);
    }
}

// ─── VoiceChat ───────────────────────────────────────────────────────────────

VoiceChat::VoiceChat() = default;

VoiceChat::~VoiceChat()
{
    Stop();
}

bool VoiceChat::Start()
{
    // Create Opus encoder (48 kHz mono, VOIP preset).
    int err = 0;
    encoder_ = opus_encoder_create(48000, 1, OPUS_APPLICATION_VOIP, &err);
    if (err != OPUS_OK || !encoder_) {
        std::fprintf(stderr, "voice: opus_encoder_create failed: %d\n", err);
        return false;
    }
    opus_encoder_ctl(encoder_, OPUS_SET_BITRATE(32000));
    opus_encoder_ctl(encoder_, OPUS_SET_COMPLEXITY(5));

    // UDP receive socket — bind to port 0 so the OS assigns an ephemeral port.
    recv_fd_ = socket(AF_INET, SOCK_DGRAM, 0);
    if (recv_fd_ < 0) { std::perror("voice: recv socket"); return false; }

    struct sockaddr_in addr{};
    addr.sin_family      = AF_INET;
    addr.sin_port        = 0;   // ephemeral
    addr.sin_addr.s_addr = INADDR_ANY;
    if (bind(recv_fd_, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0) {
        std::perror("voice: bind"); close(recv_fd_); recv_fd_ = -1; return false;
    }
    socklen_t alen = sizeof(addr);
    getsockname(recv_fd_, reinterpret_cast<sockaddr*>(&addr), &alen);
    listen_port_ = ntohs(addr.sin_port);

    // UDP send socket.
    send_fd_ = socket(AF_INET, SOCK_DGRAM, 0);
    if (send_fd_ < 0) { std::perror("voice: send socket"); return false; }

    // miniaudio capture device (mic).
    auto* vd = new VoiceDevices{};
    capture_dev_ = vd;

    ma_device_config cap_cfg = ma_device_config_init(ma_device_type_capture);
    cap_cfg.capture.format   = ma_format_f32;
    cap_cfg.capture.channels = 1;
    cap_cfg.sampleRate       = 48000;
    cap_cfg.dataCallback     = DeviceCallback;
    cap_cfg.pUserData        = this;

    if (ma_device_init(nullptr, &cap_cfg, &vd->capture) != MA_SUCCESS) {
        std::fprintf(stderr, "voice: ma_device_init capture failed\n");
        // Non-fatal — audio-only receive still works; no mic is available.
        delete vd;
        capture_dev_ = nullptr;
    } else if (!muted_) {
        ma_device_start(&vd->capture);
    }

    // miniaudio playback device (speaker for incoming voice).
    ma_device_config play_cfg = ma_device_config_init(ma_device_type_playback);
    play_cfg.playback.format   = ma_format_f32;
    play_cfg.playback.channels = 1;
    play_cfg.sampleRate        = 48000;
    play_cfg.dataCallback      = DeviceCallback;
    play_cfg.pUserData         = this;

    auto* pd = new VoiceDevices{};
    playback_dev_ = pd;
    if (ma_device_init(nullptr, &play_cfg, &pd->playback) != MA_SUCCESS) {
        std::fprintf(stderr, "voice: ma_device_init playback failed\n");
        delete pd; playback_dev_ = nullptr;
    } else {
        ma_device_start(&pd->playback);
    }

    std::printf("voice: started on UDP port %u\n", listen_port_);
    return true;
}

void VoiceChat::Stop()
{
    if (capture_dev_) {
        auto* vd = static_cast<VoiceDevices*>(capture_dev_);
        ma_device_uninit(&vd->capture);
        delete vd;
        capture_dev_ = nullptr;
    }
    if (playback_dev_) {
        auto* vd = static_cast<VoiceDevices*>(playback_dev_);
        ma_device_uninit(&vd->playback);
        delete vd;
        playback_dev_ = nullptr;
    }
    if (recv_fd_ >= 0) { close(recv_fd_); recv_fd_ = -1; }
    if (send_fd_ >= 0) { close(send_fd_); send_fd_ = -1; }
    if (encoder_)  { opus_encoder_destroy(encoder_); encoder_ = nullptr; }

    std::lock_guard<std::mutex> lk(peers_mu_);
    for (auto& [id, pa] : peer_audio_) {
        if (pa) { opus_decoder_destroy(pa->decoder); delete pa; }
    }
    peer_audio_.clear();
}

void VoiceChat::SetMuted(bool muted)
{
    muted_ = muted;
    if (!capture_dev_) return;
    auto* vd = static_cast<VoiceDevices*>(capture_dev_);
    if (muted) {
        ma_device_stop(&vd->capture);
    } else {
        ma_device_start(&vd->capture);
    }
}

void VoiceChat::SyncPeers(const std::vector<PeerInfo>& peers)
{
    std::lock_guard<std::mutex> lk(peers_mu_);

    // Add new peers.
    for (const auto& pi : peers) {
        if (!peer_audio_.count(pi.peer_id)) {
            int err = 0;
            OpusDecoder* dec = opus_decoder_create(48000, 1, &err);
            if (err != OPUS_OK) continue;
            auto* pa = new PeerAudio{};
            pa->decoder = dec;
            peer_audio_[pi.peer_id] = pa;
            std::printf("voice: added peer %s\n", pi.peer_id.c_str());
        }
        peer_addrs_[pi.peer_id] = { pi.address, pi.audio_port };
    }

    // Remove departed peers.
    for (auto it = peer_audio_.begin(); it != peer_audio_.end(); ) {
        bool found = false;
        for (const auto& pi : peers) if (pi.peer_id == it->first) { found = true; break; }
        if (!found) {
            opus_decoder_destroy(it->second->decoder);
            delete it->second;
            peer_addrs_.erase(it->first);
            it = peer_audio_.erase(it);
        } else {
            ++it;
        }
    }
}

float VoiceChat::PeerLevel(const std::string& peer_id)
{
    std::lock_guard<std::mutex> lk(peers_mu_);
    auto it = peer_audio_.find(peer_id);
    return it != peer_audio_.end() ? it->second->level : 0.f;
}

void VoiceChat::EncodeAndSend(const float* pcm, int frame_samples)
{
    // Wire format: [4-byte big-endian seq][Opus payload]
    uint32_t s = htonl(seq_++);
    std::memcpy(enc_buf_, &s, 4);

    int encoded = opus_encode_float(encoder_, pcm, frame_samples,
                                    enc_buf_ + 4, static_cast<int>(sizeof(enc_buf_)) - 4);
    if (encoded <= 0) return;

    std::lock_guard<std::mutex> lk(peers_mu_);
    for (auto& [peer_id, addr] : peer_addrs_) {
        struct sockaddr_in dest{};
        dest.sin_family = AF_INET;
        dest.sin_port   = htons(addr.port);
        inet_pton(AF_INET, addr.ip.c_str(), &dest.sin_addr);
        sendto(send_fd_, enc_buf_, static_cast<size_t>(4 + encoded), 0,
               reinterpret_cast<sockaddr*>(&dest), sizeof(dest));
    }
}

// Drain the receive socket and decode incoming Opus packets into peer ring
// buffers. Non-blocking; safe to call from the main thread each frame.
void VoiceChat::Tick()
{
    if (recv_fd_ < 0) return;

    static uint8_t recv_buf[4 + 1500];
    struct sockaddr_in src{};
    socklen_t src_len = sizeof(src);

    for (int i = 0; i < 32; ++i) {
        int n = recvfrom(recv_fd_, recv_buf, sizeof(recv_buf), MSG_DONTWAIT,
                         reinterpret_cast<sockaddr*>(&src), &src_len);
        if (n <= 4) break;

        const uint8_t* opus_data = recv_buf + 4;
        int opus_len = n - 4;

        char sender_ip[INET_ADDRSTRLEN]{};
        inet_ntop(AF_INET, &src.sin_addr, sender_ip, sizeof(sender_ip));
        uint16_t sender_port = ntohs(src.sin_port);

        std::lock_guard<std::mutex> lk(peers_mu_);
        for (auto& [pid, pa] : peer_audio_) {
            auto ait = peer_addrs_.find(pid);
            if (ait == peer_addrs_.end()) continue;
            if (ait->second.ip != sender_ip ||
                ait->second.port != sender_port) continue;

            float pcm[960]{};
            int samples = opus_decode_float(pa->decoder, opus_data, opus_len,
                                            pcm, 960, 0);
            if (samples <= 0) continue;

            float rms = 0.f;
            for (int s = 0; s < samples; ++s) rms += pcm[s] * pcm[s];
            pa->level = std::sqrt(rms / static_cast<float>(samples));

            std::lock_guard<std::mutex> rlk(pa->ring_mu);
            for (int s = 0; s < samples; ++s) {
                pa->ring[pa->ring_write] = pcm[s];
                pa->ring_write = (pa->ring_write + 1) % PeerAudio::kRingSize;
            }
        }
    }
}

} // namespace wfedit
