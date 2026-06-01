// engine/wf_edit/voice_track.cc — Voice chat: mic → Opus → WebRTC → speaker.
//
// miniaudio is already compiled into the engine (miniaudio_impl.cc defines
// MINIAUDIO_IMPLEMENTATION). Include the header here for declarations only.

#include "voice_track.h"
#include "collab_session.h"   // PeerInfo

#include <miniaudio/miniaudio.h>
#include <opus/opus.h>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
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
    // WF_COLLAB_VOICE_DEBUG: per-second send/receive media stats to stderr.
    // Resolved once here so the hot paths only test a bool.
    if (const char* p = std::getenv("WF_COLLAB_VOICE_DEBUG"); p && *p)
        voice_debug_ = true;

    // Create Opus encoder (48 kHz mono, VOIP preset).
    int err = 0;
    encoder_ = opus_encoder_create(48000, 1, OPUS_APPLICATION_VOIP, &err);
    if (err != OPUS_OK || !encoder_) {
        std::fprintf(stderr, "voice: opus_encoder_create failed: %d\n", err);
        return false;
    }
    opus_encoder_ctl(encoder_, OPUS_SET_BITRATE(32000));
    opus_encoder_ctl(encoder_, OPUS_SET_COMPLEXITY(5));

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

    std::printf("voice: started (WebRTC transport)\n");
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
    if (encoder_) { opus_encoder_destroy(encoder_); encoder_ = nullptr; }

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

    // Add decoders for new peers.
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
    }

    // Remove decoders for departed peers.
    for (auto it = peer_audio_.begin(); it != peer_audio_.end(); ) {
        bool found = false;
        for (const auto& pi : peers) if (pi.peer_id == it->first) { found = true; break; }
        if (!found) {
            opus_decoder_destroy(it->second->decoder);
            delete it->second;
            it = peer_audio_.erase(it);
        } else {
            ++it;
        }
    }
}

void VoiceChat::SetSendCallback(std::function<void(const uint8_t*, int)> cb)
{
    std::lock_guard<std::mutex> lk(send_cb_mu_);
    send_cb_ = std::move(cb);
}

void VoiceChat::OnRemoteOpus(const std::string& peer_id,
                              const uint8_t* opus, int len)
{
    std::lock_guard<std::mutex> lk(peers_mu_);
    auto ait = peer_audio_.find(peer_id);
    if (ait == peer_audio_.end()) return;
    PeerAudio* pa = ait->second;
    if (!pa || !pa->decoder) return;

    float pcm[960]{};
    int samples = opus_decode_float(pa->decoder, opus, len, pcm, 960, 0);
    if (samples <= 0) return;

    float rms = 0.f;
    for (int s = 0; s < samples; ++s) rms += pcm[s] * pcm[s];
    pa->level = std::sqrt(rms / static_cast<float>(samples));

    if (voice_debug_) {
        pa->recv_count++;
        if (pa->level > pa->recv_peak) pa->recv_peak = pa->level;
        // ~1 s at 20 ms/frame. Confirms media is arriving FROM this peer.
        if (pa->recv_count % 50 == 0) {
            std::fprintf(stderr, "voice-dbg: recv peer=%s packets=%llu peak=%.3f\n",
                         peer_id.c_str(),
                         static_cast<unsigned long long>(pa->recv_count),
                         pa->recv_peak);
            pa->recv_peak = 0.f;
        }
    }

    std::lock_guard<std::mutex> rlk(pa->ring_mu);
    for (int s = 0; s < samples; ++s) {
        pa->ring[pa->ring_write] = pcm[s];
        pa->ring_write = (pa->ring_write + 1) % PeerAudio::kRingSize;
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
    int encoded = opus_encode_float(encoder_, pcm, frame_samples,
                                    enc_buf_, static_cast<int>(sizeof(enc_buf_)));
    if (encoded <= 0) return;

    if (voice_debug_) {
        float rms = 0.f;
        for (int s = 0; s < frame_samples; ++s) rms += pcm[s] * pcm[s];
        float lvl = std::sqrt(rms / static_cast<float>(frame_samples));
        if (lvl > send_peak_) send_peak_ = lvl;
        send_count_++;
        // ~1 s at 20 ms/frame. Confirms the mic is capturing + Opus is sending.
        if (send_count_ % 50 == 0) {
            std::fprintf(stderr, "voice-dbg: send packets=%llu peak=%.3f bytes=%d\n",
                         static_cast<unsigned long long>(send_count_),
                         send_peak_, encoded);
            send_peak_ = 0.f;
        }
    }

    std::lock_guard<std::mutex> lk(send_cb_mu_);
    if (send_cb_) send_cb_(enc_buf_, encoded);
}

} // namespace wfedit
