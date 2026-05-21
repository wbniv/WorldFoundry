#pragma once
// engine/wf_edit/collab_session.h — UDP multicast peer discovery for the
// collaborative editor's voice+video call session. Each editor instance
// broadcasts a heartbeat beacon every 2 s on a multicast group; peers collect
// each other's addresses and A/V ports from those beacons.
//
// Multicast group: 239.255.42.99  port: 9877
// Beacon format (newline-terminated, pipe-delimited):
//   WFEDIT|<room_id>|<peer_id>|<display_name>|<audio_port>|<video_port>

#include <string>
#include <vector>
#include <cstdint>

namespace wfedit {

struct PeerInfo {
    std::string peer_id;
    std::string display_name;
    std::string address;      // dotted-decimal IPv4
    uint16_t    audio_port = 0;
    uint16_t    video_port = 0;
    double      last_seen  = 0.0;  // from clock_gettime(CLOCK_MONOTONIC)
};

class CollabSession {
public:
    CollabSession();
    ~CollabSession();

    // Join the multicast group and start broadcasting. audio_port/video_port
    // are the UDP ports this peer listens on for incoming A/V traffic.
    // Returns false if socket setup fails.
    bool Start(const std::string& room_id, const std::string& display_name,
               uint16_t audio_port, uint16_t video_port);
    void Stop();

    // Call once per frame from the editor loop. Drains the receive buffer,
    // updates the peer list, evicts stale peers (last_seen > 8 s ago).
    void Tick(double now_sec);

    const std::vector<PeerInfo>& Peers()     const { return peers_; }
    const std::string&           OurPeerId() const { return our_peer_id_; }
    bool                         Active()    const { return recv_fd_ >= 0; }

private:
    void SendBeacon(double now_sec);
    void ParseBeacon(const char* buf, int len,
                     const std::string& sender_ip, double now_sec);

    int          send_fd_   = -1;
    int          recv_fd_   = -1;
    std::string  room_id_;
    std::string  our_peer_id_;
    std::string  display_name_;
    uint16_t     audio_port_ = 0;
    uint16_t     video_port_ = 0;
    double       last_beacon_ = -99.0;

    std::vector<PeerInfo> peers_;
};

// Returns a monotonic seconds value (wraps ~136 years after boot).
double MonoNow();

} // namespace wfedit
