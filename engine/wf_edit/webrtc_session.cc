// engine/wf_edit/webrtc_session.cc — see webrtc_session.h.
// Plan: docs/plans/2026-05-26-internet-voice-video-webrtc.md Phase 2

// nlohmann/json before WF engine headers (same memory.hp macro issue as main.cc)
#include <nlohmann/json.hpp>

#include "webrtc_session.h"
#include "voice_track.h"
#include "video_track.h"

#include <rtc/rtc.hpp>

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <utility>

namespace wfedit {

// ── RTP helpers ──────────────────────────────────────────────────────────────

static rtc::binary MakeAudioRtp(uint16_t seq, uint32_t ts, uint32_t ssrc,
                                 const uint8_t* opus, int len)
{
    rtc::binary pkt(static_cast<size_t>(12 + len));
    std::byte*  p = pkt.data();
    p[0]  = std::byte{0x80};                                    // V=2
    p[1]  = std::byte{111};                                     // PT=111, no marker
    p[2]  = std::byte{static_cast<uint8_t>(seq >> 8)};
    p[3]  = std::byte{static_cast<uint8_t>(seq & 0xff)};
    p[4]  = std::byte{static_cast<uint8_t>(ts >> 24)};
    p[5]  = std::byte{static_cast<uint8_t>((ts >> 16) & 0xff)};
    p[6]  = std::byte{static_cast<uint8_t>((ts >>  8) & 0xff)};
    p[7]  = std::byte{static_cast<uint8_t>(ts & 0xff)};
    p[8]  = std::byte{static_cast<uint8_t>(ssrc >> 24)};
    p[9]  = std::byte{static_cast<uint8_t>((ssrc >> 16) & 0xff)};
    p[10] = std::byte{static_cast<uint8_t>((ssrc >>  8) & 0xff)};
    p[11] = std::byte{static_cast<uint8_t>(ssrc & 0xff)};
    std::memcpy(p + 12, opus, static_cast<size_t>(len));
    return pkt;
}

// Build one VP8 RTP packet fragment.
// descriptor: 0x10 = start-of-partition (S=1), 0x00 = continuation.
static rtc::binary MakeVideoRtp(uint16_t seq, uint32_t ts, uint32_t ssrc,
                                 bool marker, uint8_t descriptor,
                                 const uint8_t* vp8, int len)
{
    rtc::binary pkt(static_cast<size_t>(13 + len));
    std::byte*  p = pkt.data();
    p[0]  = std::byte{0x80};
    p[1]  = std::byte{static_cast<uint8_t>(marker ? (0x80 | 96) : 96)};
    p[2]  = std::byte{static_cast<uint8_t>(seq >> 8)};
    p[3]  = std::byte{static_cast<uint8_t>(seq & 0xff)};
    p[4]  = std::byte{static_cast<uint8_t>(ts >> 24)};
    p[5]  = std::byte{static_cast<uint8_t>((ts >> 16) & 0xff)};
    p[6]  = std::byte{static_cast<uint8_t>((ts >>  8) & 0xff)};
    p[7]  = std::byte{static_cast<uint8_t>(ts & 0xff)};
    p[8]  = std::byte{static_cast<uint8_t>(ssrc >> 24)};
    p[9]  = std::byte{static_cast<uint8_t>((ssrc >> 16) & 0xff)};
    p[10] = std::byte{static_cast<uint8_t>((ssrc >>  8) & 0xff)};
    p[11] = std::byte{static_cast<uint8_t>(ssrc & 0xff)};
    p[12] = std::byte{descriptor};   // VP8 payload descriptor (RFC 7741 §4.2)
    std::memcpy(p + 13, vp8, static_cast<size_t>(len));
    return pkt;
}

// ── RTCP PLI helpers ─────────────────────────────────────────────────────────

// Build a 12-byte RTCP Picture Loss Indication (RFC 4585 §6.3.1): PSFB (PT=206),
// FMT=1. libdatachannel's Track::outgoing auto-tags an outbound packet as RTCP
// when IsRtcp() matches (no media handler installed) and sends it over SRTCP, so
// a hand-rolled PLI binary fed to Track::send "just works".
std::vector<std::byte> WebrtcSession::MakePliPacket(uint32_t sender_ssrc,
                                                    uint32_t media_ssrc)
{
    std::vector<std::byte> pkt(12);
    std::byte* p = pkt.data();
    p[0]  = std::byte{0x81};   // V=2, P=0, FMT=1 (PLI)
    p[1]  = std::byte{206};    // PT=206 (PSFB)
    p[2]  = std::byte{0x00};   // length = 2 (3 32-bit words minus 1)
    p[3]  = std::byte{0x02};
    p[4]  = std::byte{static_cast<uint8_t>(sender_ssrc >> 24)};
    p[5]  = std::byte{static_cast<uint8_t>((sender_ssrc >> 16) & 0xff)};
    p[6]  = std::byte{static_cast<uint8_t>((sender_ssrc >>  8) & 0xff)};
    p[7]  = std::byte{static_cast<uint8_t>(sender_ssrc & 0xff)};
    p[8]  = std::byte{static_cast<uint8_t>(media_ssrc >> 24)};
    p[9]  = std::byte{static_cast<uint8_t>((media_ssrc >> 16) & 0xff)};
    p[10] = std::byte{static_cast<uint8_t>((media_ssrc >>  8) & 0xff)};
    p[11] = std::byte{static_cast<uint8_t>(media_ssrc & 0xff)};
    return pkt;
}

bool WebrtcSession::IsPliPacket(const std::byte* data, size_t len,
                                uint32_t* out_media_ssrc)
{
    if (!data || len < 12) return false;
    // For RTCP, byte 1 is the full 8-bit packet type (no RTP marker bit) — do not
    // mask with 0x7f (that's IsRtcp's 64..95 range heuristic, not the exact PT).
    const uint8_t pt  = static_cast<uint8_t>(data[1]);          // packet type (206=PSFB)
    const uint8_t fmt = static_cast<uint8_t>(data[0]) & 0x1f;   // feedback msg type
    if (pt != 206 || (fmt != 1 && fmt != 4)) return false;       // PLI(1) or FIR(4)
    if (out_media_ssrc) {
        *out_media_ssrc =
            (static_cast<uint32_t>(static_cast<uint8_t>(data[8]))  << 24) |
            (static_cast<uint32_t>(static_cast<uint8_t>(data[9]))  << 16) |
            (static_cast<uint32_t>(static_cast<uint8_t>(data[10])) <<  8) |
            (static_cast<uint32_t>(static_cast<uint8_t>(data[11])));
    }
    return true;
}

// ── PeerState ────────────────────────────────────────────────────────────────

struct WebrtcSession::PeerState {
    std::string peer_id;
    std::shared_ptr<rtc::PeerConnection> pc;
    std::shared_ptr<rtc::Track> audio_track;
    std::shared_ptr<rtc::Track> video_track;
    std::atomic<bool> connected{false};
    bool is_offerer = false;

    // The remote sender's video SSRC, learned from inbound RTP — the media
    // source a PLI we send must name. 0 until the first VP8 packet arrives.
    std::atomic<uint32_t> remote_video_ssrc{0};

    // VP8 reassembly buffer (receive side; guarded by vp8_mu).
    std::mutex           vp8_mu;
    std::vector<uint8_t> vp8_accum;
};

// ── ICE / TURN configuration (Phase 3) ────────────────────────────────────────

// Apply WF_COLLAB_* env overrides on top of the identity.json defaults. Env
// wins per-field so a single run can be pointed at a test TURN server without
// editing identity.json. WF_COLLAB_TURN is "host" or "host:port".
IceConfig ResolveIceConfig(IceConfig cfg)
{
    auto env = [](const char* k) -> const char* {
        const char* v = std::getenv(k);
        return (v && *v) ? v : nullptr;
    };
    if (const char* s = env("WF_COLLAB_STUN"))      cfg.stun_url  = s;
    if (const char* t = env("WF_COLLAB_TURN")) {
        std::string hp = t;
        const auto colon = hp.rfind(':');
        if (colon != std::string::npos && colon + 1 < hp.size()) {
            const std::string port_s = hp.substr(colon + 1);
            const bool numeric = port_s.find_first_not_of("0123456789") == std::string::npos;
            if (numeric) {
                const int p = std::atoi(port_s.c_str());
                if (p > 0 && p <= 65535) {
                    cfg.turn_port = static_cast<uint16_t>(p);
                    hp = hp.substr(0, colon);
                }
            }
        }
        cfg.turn_host = hp;
    }
    if (const char* u = env("WF_COLLAB_TURN_USER")) cfg.turn_user = u;
    if (const char* p = env("WF_COLLAB_TURN_PASS")) cfg.turn_pass = p;
    if (env("WF_COLLAB_TURN_TLS"))    cfg.turn_tls    = true;
    if (env("WF_COLLAB_FORCE_RELAY")) cfg.force_relay = true;
    return cfg;
}

// Translate our plain IceConfig into a libdatachannel rtc::Configuration. The
// DTLS-SRTP media encryption is independent of this — a TURN relay only ever
// forwards ciphertext, so force_relay does not weaken end-to-end encryption.
static rtc::Configuration BuildRtcConfig(const IceConfig& ice)
{
    rtc::Configuration config;
    if (!ice.stun_url.empty())
        config.iceServers.emplace_back(ice.stun_url);
    if (!ice.turn_host.empty()) {
        config.iceServers.emplace_back(
            ice.turn_host, ice.turn_port, ice.turn_user, ice.turn_pass,
            ice.turn_tls ? rtc::IceServer::RelayType::TurnTls
                         : rtc::IceServer::RelayType::TurnUdp);
    }
    if (ice.force_relay)
        config.iceTransportPolicy = rtc::TransportPolicy::Relay;
    return config;
}

// ── WebrtcSession ─────────────────────────────────────────────────────────────

WebrtcSession::WebrtcSession(VoiceChat* vc, VideoChat* vd, IceConfig ice)
    : vc_(vc), vd_(vd), ice_(ResolveIceConfig(std::move(ice)))
{
    if (const char* p = std::getenv("WF_COLLAB_VIDEO_DEBUG"); p && *p)
        video_debug_ = true;

    if (!ice_.turn_host.empty()) {
        std::printf("wf-edit: WebRTC TURN relay %s:%u (%s)%s\n",
                    ice_.turn_host.c_str(), ice_.turn_port,
                    ice_.turn_tls ? "turns/tls" : "turn/udp",
                    ice_.force_relay ? " [force-relay]" : "");
    } else if (ice_.force_relay) {
        std::printf("wf-edit: WebRTC force-relay set but no TURN configured — "
                    "connections will fail (no relay candidate).\n");
    }

    // Random SSRC values.
    std::mt19937 rng(std::random_device{}());
    std::uniform_int_distribution<uint32_t> d;
    audio_ssrc_ = d(rng);
    video_ssrc_ = d(rng);

    // Wire send callbacks so VoiceChat/VideoChat route encoded media through us.
    if (vc_) {
        vc_->SetSendCallback([this](const uint8_t* opus, int len) {
            SendOpus(opus, len);
        });
    }
    if (vd_) {
        vd_->SetSendCallback([this](const uint8_t* vp8, int len, bool key) {
            SendVP8(vp8, len, key);
        });
    }
}

WebrtcSession::~WebrtcSession()
{
    // Disconnect callbacks before tearing down peer connections.
    if (vc_) vc_->SetSendCallback(nullptr);
    if (vd_) vd_->SetSendCallback(nullptr);

    std::lock_guard<std::mutex> lk(peers_mu_);
    for (auto& [id, state] : peers_) {
        if (state->pc) state->pc->close();
        state->audio_track.reset();
        state->video_track.reset();
        state->pc.reset();
    }
    peers_.clear();
}

// ── GetOrCreate ───────────────────────────────────────────────────────────────

WebrtcSession::PeerStatePtr
WebrtcSession::GetOrCreate(const std::string& peer_id, bool is_offerer)
{
    // Caller holds peers_mu_.
    auto it = peers_.find(peer_id);
    if (it != peers_.end()) return it->second;

    auto state = std::make_shared<PeerState>();
    state->peer_id   = peer_id;
    state->is_offerer = is_offerer;

    rtc::Configuration config = BuildRtcConfig(ice_);

    state->pc = std::make_shared<rtc::PeerConnection>(config);

    // Capture by value so callbacks don't dangle on WebrtcSession lifetime.
    std::string to = peer_id;
    std::weak_ptr<PeerState> weak = state;

    state->pc->onLocalDescription([this, to](rtc::Description desc) {
        using json = nlohmann::json;
        json j;
        j["type"] = desc.typeString();
        j["sdp"]  = std::string(desc);
        j["from"] = our_peer_id_;
        QueueSignal(to, j.dump());
    });

    state->pc->onLocalCandidate([this, to](rtc::Candidate cand) {
        using json = nlohmann::json;
        json j;
        j["type"]      = "candidate";
        j["candidate"] = std::string(cand);
        j["sdpMid"]    = cand.mid();
        j["from"]      = our_peer_id_;
        QueueSignal(to, j.dump());
    });

    state->pc->onStateChange([weak, peer_id](rtc::PeerConnection::State s) {
        const char* sname = s == rtc::PeerConnection::State::Connected    ? "Connected"
                          : s == rtc::PeerConnection::State::Connecting   ? "Connecting"
                          : s == rtc::PeerConnection::State::Disconnected ? "Disconnected"
                          : s == rtc::PeerConnection::State::Failed       ? "Failed"
                          : s == rtc::PeerConnection::State::Closed       ? "Closed"
                          : "New";
        std::fprintf(stderr, "webrtc: state %s for peer %.8s\n", sname, peer_id.c_str());
        std::fflush(stderr);
        if (s == rtc::PeerConnection::State::Connected) {
            if (auto sp = weak.lock()) sp->connected.store(true);
        } else if (s == rtc::PeerConnection::State::Failed ||
                   s == rtc::PeerConnection::State::Closed) {
            if (auto sp = weak.lock()) sp->connected.store(false);
        }
    });

    // Audio track — Opus PT=111. SendRecv (not the libdatachannel default
    // SendOnly): a SendOnly track refuses incoming RTP, so onMessage never
    // fires on the receiving peer and no media flows.
    // addSSRC advertises the SSRC we actually send with (audio_ssrc_) in the
    // SDP — without it, the receiver can't demux our hand-rolled RTP (unknown
    // SSRC) to this track and silently drops every packet.
    {
        rtc::Description::Audio audio("audio", rtc::Description::Direction::SendRecv);
        audio.addOpusCodec(111);
        audio.addSSRC(audio_ssrc_, "wf-audio");
        state->audio_track = state->pc->addTrack(audio);
    }
    if (state->audio_track) {
        std::string pid = peer_id;
        state->audio_track->onMessage([this, pid](rtc::message_variant data) {
            auto* bin = std::get_if<rtc::binary>(&data);
            if (!bin) return;
            if (rtc::IsRtcp(*bin)) return;   // ignore RTCP (SR/RR/…) on the audio track
            if (bin->size() <= 12) return;
            // Strip 12-byte RTP header; pass raw Opus to VoiceChat.
            const uint8_t* opus =
                reinterpret_cast<const uint8_t*>(bin->data()) + 12;
            int len = static_cast<int>(bin->size()) - 12;
            if (vc_) vc_->OnRemoteOpus(pid, opus, len);
        });
    }

    // Video track — VP8 PT=96. SendRecv (see audio note above) so the
    // receiving peer's track actually delivers incoming RTP to onMessage.
    // addSSRC: advertise video_ssrc_ in the SDP so the peer can demux it.
    {
        rtc::Description::Video video("video", rtc::Description::Direction::SendRecv);
        video.addVP8Codec(96);
        video.addSSRC(video_ssrc_, "wf-video");
        state->video_track = state->pc->addTrack(video);
    }
    if (state->video_track) {
        std::string pid = peer_id;
        state->video_track->onMessage([this, pid, weak](rtc::message_variant data) {
            auto* bin = std::get_if<rtc::binary>(&data);
            if (!bin) return;
            if (rtc::IsRtcp(*bin)) {
                // Honor a Picture Loss Indication / Full Intra Request from the
                // receiver: ask our encoder for an immediate keyframe. Other RTCP
                // (SR/RR/SDES/BYE) is ignored. dispatchMedia can fan compound RTCP
                // to either track, so this must run before any RTP field access.
                if (vd_ && IsPliPacket(bin->data(), bin->size())) {
                    if (video_debug_)
                        std::fprintf(stderr, "video: PLI from peer %.8s — forcing keyframe\n",
                                     pid.c_str());
                    vd_->RequestKeyframe();
                }
                return;
            }
            if (bin->size() <= 13) return;  // header(12) + descriptor(1)
            const uint8_t* rtp = reinterpret_cast<const uint8_t*>(bin->data());
            bool marker = (rtp[1] & 0x80) != 0;           // RTP marker bit
            bool start  = (rtp[12] & 0x10) != 0;          // VP8 S bit
            const uint8_t* payload = rtp + 13;
            int payload_len = static_cast<int>(bin->size()) - 13;

            auto sp = weak.lock();
            if (!sp) return;
            // Learn the sender's video SSRC (RTP header bytes 8-11) so a PLI we
            // send back can name the right media source.
            uint32_t rssrc = (static_cast<uint32_t>(rtp[8])  << 24) |
                             (static_cast<uint32_t>(rtp[9])  << 16) |
                             (static_cast<uint32_t>(rtp[10]) <<  8) |
                             (static_cast<uint32_t>(rtp[11]));
            if (rssrc) sp->remote_video_ssrc.store(rssrc, std::memory_order_relaxed);
            std::lock_guard<std::mutex> lk(sp->vp8_mu);
            if (start) sp->vp8_accum.clear();
            sp->vp8_accum.insert(sp->vp8_accum.end(), payload, payload + payload_len);
            if (marker && !sp->vp8_accum.empty()) {
                if (vd_) {
                    vd_->OnRemoteVP8Frame(pid,
                        sp->vp8_accum.data(),
                        static_cast<int>(sp->vp8_accum.size()),
                        start);
                }
                sp->vp8_accum.clear();
            }
        });
    }

    if (is_offerer) {
        state->pc->setLocalDescription();
    }

    peers_[peer_id] = state;
    std::printf("webrtc: connected to peer %s (offerer=%d)\n",
                peer_id.c_str(), is_offerer);
    return state;
}

void WebrtcSession::TearDown(const std::string& peer_id)
{
    // Caller holds peers_mu_.
    auto it = peers_.find(peer_id);
    if (it == peers_.end()) return;
    auto& state = it->second;
    if (state->pc) state->pc->close();
    state->audio_track.reset();
    state->video_track.reset();
    state->pc.reset();
    peers_.erase(it);
    std::printf("webrtc: disconnected peer %s\n", peer_id.c_str());
}

void WebrtcSession::QueueSignal(const std::string& to, const std::string& json)
{
    std::lock_guard<std::mutex> lk(sig_mu_);
    pending_signals_.emplace_back(to, json);
}

// ── SyncPeers ─────────────────────────────────────────────────────────────────

void WebrtcSession::SyncPeers(const std::vector<std::string>& peer_ids,
                               const std::string& our_peer_id)
{
    our_peer_id_ = our_peer_id;

    std::lock_guard<std::mutex> lk(peers_mu_);

    // Add connections for new peers (lower peer_id is offerer).
    for (const auto& pid : peer_ids) {
        if (pid == our_peer_id) continue;
        if (!peers_.count(pid)) {
            bool is_offerer = (our_peer_id < pid);
            GetOrCreate(pid, is_offerer);
        }
    }

    // Tear down connections for departed peers.
    std::vector<std::string> to_remove;
    for (const auto& [pid, _] : peers_) {
        bool found = std::find(peer_ids.begin(), peer_ids.end(), pid) != peer_ids.end();
        if (!found) to_remove.push_back(pid);
    }
    for (const auto& pid : to_remove) TearDown(pid);
}

// ── OnSignal ─────────────────────────────────────────────────────────────────

void WebrtcSession::OnSignal(const std::string& from_peer,
                              const std::string& json_payload)
{
    try {
        using json = nlohmann::json;
        json j = json::parse(json_payload);
        const std::string type = j.value("type", "");

        std::lock_guard<std::mutex> lk(peers_mu_);
        // Answerer: create PeerState if we receive an offer before SyncPeers fires.
        bool is_offerer = (our_peer_id_ < from_peer);
        auto state = GetOrCreate(from_peer, is_offerer);
        if (!state->pc) return;

        if (type == "offer" || type == "answer") {
            std::string sdp = j.value("sdp", "");
            if (sdp.empty()) return;
            state->pc->setRemoteDescription(rtc::Description(sdp, type));
            if (type == "offer" && !is_offerer) {
                // Generate answer.
                state->pc->setLocalDescription();
            }
        } else if (type == "candidate") {
            std::string cand   = j.value("candidate", "");
            std::string sdpMid = j.value("sdpMid", "");
            if (!cand.empty())
                state->pc->addRemoteCandidate(rtc::Candidate(cand, sdpMid));
        }
    } catch (const std::exception& e) {
        // Don't silently swallow malformed signaling (bad JSON / SDP / ICE) —
        // a dropped signal that's invisible makes connection failures un-debuggable.
        std::fprintf(stderr, "webrtc: dropped malformed signal from %.8s: %s\n",
                     from_peer.c_str(), e.what());
    } catch (...) {
        std::fprintf(stderr, "webrtc: dropped malformed signal from %.8s (non-std throw)\n",
                     from_peer.c_str());
    }
}

// ── DrainSignaling ────────────────────────────────────────────────────────────

std::vector<std::pair<std::string,std::string>> WebrtcSession::DrainSignaling()
{
    std::lock_guard<std::mutex> lk(sig_mu_);
    return std::exchange(pending_signals_, {});
}

size_t WebrtcSession::ConnectedPeerCount()
{
    std::lock_guard<std::mutex> lk(peers_mu_);
    size_t n = 0;
    for (auto& [id, st] : peers_) { (void)id; if (st->connected.load()) ++n; }
    return n;
}

void WebrtcCleanup()
{
    rtc::Cleanup().wait();
}

// ── SendOpus ─────────────────────────────────────────────────────────────────

void WebrtcSession::SendOpus(const uint8_t* opus, int opus_len)
{
    uint16_t seq; uint32_t ts, ssrc;
    {
        std::lock_guard<std::mutex> lk(rtp_mu_);
        seq  = audio_seq_++;
        ts   = audio_ts_; audio_ts_ += 960;  // 20 ms @ 48 kHz
        ssrc = audio_ssrc_;
    }

    auto pkt = MakeAudioRtp(seq, ts, ssrc, opus, opus_len);

    std::lock_guard<std::mutex> lk(peers_mu_);
    for (auto& [pid, state] : peers_) {
        if (state->audio_track && state->connected.load()) {
            try { state->audio_track->send(pkt); } catch (...) {}
        }
    }
}

// ── SendVP8 ──────────────────────────────────────────────────────────────────

void WebrtcSession::SendVP8(const uint8_t* vp8, int vp8_len, bool /*keyframe*/)
{
    static constexpr int kMaxPayload = 1200;  // below Ethernet MTU

    uint32_t ts, ssrc;
    {
        std::lock_guard<std::mutex> lk(rtp_mu_);
        ts   = video_ts_; video_ts_ += 3000;  // 90 kHz / 30 fps
        ssrc = video_ssrc_;
    }

    int offset = 0;
    bool first = true;
    while (offset < vp8_len) {
        int chunk = std::min(kMaxPayload, vp8_len - offset);
        bool last = (offset + chunk >= vp8_len);

        uint16_t seq;
        {
            std::lock_guard<std::mutex> lk(rtp_mu_);
            seq = video_seq_++;
        }

        // VP8 payload descriptor: S=1 for first packet (RFC 7741 §4.2).
        uint8_t desc = first ? 0x10 : 0x00;
        auto pkt = MakeVideoRtp(seq, ts, ssrc, last, desc, vp8 + offset, chunk);

        {
            std::lock_guard<std::mutex> lk(peers_mu_);
            for (auto& [pid, state] : peers_) {
                if (state->video_track && state->connected.load()) {
                    try { state->video_track->send(pkt); } catch (const std::exception& e) {
                        std::fprintf(stderr, "webrtc: VP8 send threw: %s\n", e.what());
                    }
                }
            }
        }

        offset += chunk;
        first = false;
    }
}

// ── SendPli ──────────────────────────────────────────────────────────────────

void WebrtcSession::SendPli(const std::string& peer_id)
{
    uint32_t sender;
    { std::lock_guard<std::mutex> lk(rtp_mu_); sender = video_ssrc_; }

    std::lock_guard<std::mutex> lk(peers_mu_);
    auto it = peers_.find(peer_id);
    if (it == peers_.end()) return;
    auto& st = it->second;
    if (!st->connected.load() || !st->video_track) return;
    uint32_t media = st->remote_video_ssrc.load(std::memory_order_relaxed);
    if (!media) return;   // haven't seen this peer's video yet — nothing to PLI

    try {
        st->video_track->send(MakePliPacket(sender, media));
        if (video_debug_)
            std::fprintf(stderr, "video: PLI -> peer %.8s (media ssrc %08x)\n",
                         peer_id.c_str(), media);
    } catch (const std::exception& e) {
        std::fprintf(stderr, "webrtc: PLI send threw: %s\n", e.what());
    }
}

} // namespace wfedit
