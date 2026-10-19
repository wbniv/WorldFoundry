// engine/wf_edit/collab_session.cc
#include "collab_session.h"

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <algorithm>
#include <random>
#include <sstream>

namespace wfedit {

static constexpr const char* kMcastGroup = "239.255.42.99";
static constexpr uint16_t    kMcastPort  = 9877;
static constexpr double      kBeaconInterval = 2.0;
static constexpr double      kStaleSec       = 8.0;

double MonoNow()
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return static_cast<double>(ts.tv_sec) +
           static_cast<double>(ts.tv_nsec) * 1e-9;
}

static std::string MakePeerId()
{
    std::mt19937_64 rng(std::random_device{}());
    std::uniform_int_distribution<uint64_t> d;
    uint64_t hi = d(rng), lo = d(rng);
    char buf[33];
    std::snprintf(buf, sizeof(buf), "%016llx%016llx",
                  (unsigned long long)hi, (unsigned long long)lo);
    return buf;
}

CollabSession::CollabSession() = default;

CollabSession::~CollabSession()
{
    Stop();
}

bool CollabSession::Start(const std::string& room_id,
                          const std::string& display_name,
                          const std::string& peer_id,
                          uint16_t audio_port,
                          uint16_t video_port)
{
    room_id_      = room_id;
    display_name_ = display_name;
    audio_port_   = audio_port;
    video_port_   = video_port;
    // Use the identity peer_id so multicast beacons and relay PRESENCE both
    // use the same ID. MakePeerId() (random per session) broke dedup: the same
    // physical host appeared twice in the merged peer list (once via relay with
    // identity UUID, once via multicast with a random UUID), VP8 was tagged with
    // the relay UUID which got evicted after 8 s, and the peer showed no video.
    our_peer_id_  = peer_id.empty() ? MakePeerId() : peer_id;

    // Send socket (multicast output).
    send_fd_ = socket(AF_INET, SOCK_DGRAM, 0);
    if (send_fd_ < 0) {
        std::perror("collab: send socket");
        return false;
    }
    unsigned char ttl = 1;
    setsockopt(send_fd_, IPPROTO_IP, IP_MULTICAST_TTL, &ttl, sizeof(ttl));

    // Receive socket: bind to the multicast port on INADDR_ANY, join group.
    recv_fd_ = socket(AF_INET, SOCK_DGRAM, 0);
    if (recv_fd_ < 0) {
        std::perror("collab: recv socket");
        close(send_fd_); send_fd_ = -1;
        return false;
    }
    int reuse = 1;
    setsockopt(recv_fd_, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));

    struct sockaddr_in bind_addr{};
    bind_addr.sin_family      = AF_INET;
    bind_addr.sin_port        = htons(kMcastPort);
    bind_addr.sin_addr.s_addr = INADDR_ANY;
    if (bind(recv_fd_, reinterpret_cast<sockaddr*>(&bind_addr),
             sizeof(bind_addr)) < 0) {
        std::perror("collab: bind recv");
        close(recv_fd_); recv_fd_ = -1;
        close(send_fd_); send_fd_ = -1;
        return false;
    }

    struct ip_mreq mreq{};
    inet_pton(AF_INET, kMcastGroup, &mreq.imr_multiaddr);
    mreq.imr_interface.s_addr = INADDR_ANY;
    if (setsockopt(recv_fd_, IPPROTO_IP, IP_ADD_MEMBERSHIP,
                   &mreq, sizeof(mreq)) < 0) {
        std::perror("collab: join mcast");
        // Non-fatal on some restricted VMs — continue without multicast recv.
    }

    // Non-blocking recv so Tick() doesn't stall.
    struct timeval tv{ 0, 0 };
    setsockopt(recv_fd_, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

    std::printf("collab: started room=%s peer=%s audio=%u video=%u\n",
                room_id_.c_str(), our_peer_id_.c_str(), audio_port_, video_port_);
    return true;
}

void CollabSession::Stop()
{
    if (recv_fd_ >= 0) { close(recv_fd_); recv_fd_ = -1; }
    if (send_fd_ >= 0) { close(send_fd_); send_fd_ = -1; }
    peers_.clear();
    merged_dirty_ = true;
}

void CollabSession::SetRelayPeers(const std::vector<PeerInfo>& relay_peers)
{
    relay_peers_  = relay_peers;
    merged_dirty_ = true;
}

const std::vector<PeerInfo>& CollabSession::Peers() const
{
    if (!merged_dirty_) return merged_peers_;

    merged_peers_ = peers_;
    for (const auto& rp : relay_peers_) {
        bool found = false;
        for (const auto& p : merged_peers_)
            if (p.peer_id == rp.peer_id) { found = true; break; }
        if (!found) merged_peers_.push_back(rp);
    }
    merged_dirty_ = false;
    return merged_peers_;
}

void CollabSession::SendBeacon(double now_sec)
{
    if (send_fd_ < 0) return;

    char buf[512];
    int n = std::snprintf(buf, sizeof(buf),
                          "WFEDIT|%s|%s|%s|%u|%u\n",
                          room_id_.c_str(), our_peer_id_.c_str(),
                          display_name_.c_str(),
                          static_cast<unsigned>(audio_port_),
                          static_cast<unsigned>(video_port_));
    if (n <= 0) return;

    struct sockaddr_in dest{};
    dest.sin_family = AF_INET;
    dest.sin_port   = htons(kMcastPort);
    inet_pton(AF_INET, kMcastGroup, &dest.sin_addr);
    sendto(send_fd_, buf, n, 0,
           reinterpret_cast<sockaddr*>(&dest), sizeof(dest));

    last_beacon_ = now_sec;
}

void CollabSession::ParseBeacon(const char* buf, int len,
                                const std::string& sender_ip,
                                double now_sec)
{
    // Format: WFEDIT|room|peer|name|audio_port|video_port\n
    std::string line(buf, len);
    if (line.size() > 1 && line.back() == '\n')
        line.pop_back();

    auto split = [&](const std::string& s, char delim) {
        std::vector<std::string> out;
        std::istringstream ss(s);
        std::string tok;
        while (std::getline(ss, tok, delim)) out.push_back(tok);
        return out;
    };

    auto parts = split(line, '|');
    if (parts.size() != 6) return;
    if (parts[0] != "WFEDIT") return;
    if (parts[1] != room_id_) return;         // different room
    if (parts[2] == our_peer_id_) return;     // ourselves

    const std::string& peer_id = parts[2];
    uint16_t aport = static_cast<uint16_t>(std::stoul(parts[4]));
    uint16_t vport = static_cast<uint16_t>(std::stoul(parts[5]));

    for (auto& p : peers_) {
        if (p.peer_id == peer_id) {
            p.last_seen    = now_sec;
            p.address      = sender_ip;
            p.audio_port   = aport;
            p.video_port   = vport;
            p.display_name = parts[3];
            return;
        }
    }
    // New peer.
    PeerInfo np;
    np.peer_id      = peer_id;
    np.display_name = parts[3];
    np.address      = sender_ip;
    np.audio_port   = aport;
    np.video_port   = vport;
    np.last_seen    = now_sec;
    peers_.push_back(np);
    merged_dirty_ = true;
    std::printf("collab: new peer %s (%s) at %s audio=%u video=%u\n",
                peer_id.c_str(), parts[3].c_str(), sender_ip.c_str(),
                aport, vport);
}

void CollabSession::Tick(double now_sec)
{
    // Send heartbeat every kBeaconInterval seconds.
    if (now_sec - last_beacon_ >= kBeaconInterval)
        SendBeacon(now_sec);

    // Drain incoming beacons.
    if (recv_fd_ >= 0) {
        char buf[1024];
        struct sockaddr_in src{};
        socklen_t src_len = sizeof(src);
        for (int i = 0; i < 32; ++i) {
            int n = recvfrom(recv_fd_, buf, sizeof(buf) - 1, MSG_DONTWAIT,
                             reinterpret_cast<sockaddr*>(&src), &src_len);
            if (n <= 0) break;
            buf[n] = '\0';
            char ip[INET_ADDRSTRLEN]{};
            inet_ntop(AF_INET, &src.sin_addr, ip, sizeof(ip));
            ParseBeacon(buf, n, ip, now_sec);
        }
    }

    // Evict stale peers.
    size_t before = peers_.size();
    peers_.erase(
        std::remove_if(peers_.begin(), peers_.end(),
                       [&](const PeerInfo& p) {
                           return now_sec - p.last_seen > kStaleSec;
                       }),
        peers_.end());
    if (peers_.size() != before) merged_dirty_ = true;
}

} // namespace wfedit
