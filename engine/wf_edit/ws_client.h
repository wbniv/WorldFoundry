// ws_client.h — minimal WebSocket (ws://) client for the co-editing relay.
//
// Operates on a single TCP socket; all I/O is non-blocking after connect.
// Supports binary frames only (no text, no TLS in v1).
//
// Plan: docs/plans/2026-05-21-realtime-coediting.md Phase 1

#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace wfedit {

class WsClient {
public:
    WsClient() = default;
    ~WsClient() { disconnect(); }

    WsClient(const WsClient&) = delete;
    WsClient& operator=(const WsClient&) = delete;

    // Connect and perform WebSocket handshake. url must be "ws://host:port/path"
    // or "ws://host/path" (port defaults to 80). Blocks until connected.
    // Returns false on failure; connected() is then false.
    bool connect(const char* url);

    // Close the socket.
    void disconnect();

    bool connected() const { return _fd >= 0; }

    // Send a binary WebSocket frame (client→server frames are masked per RFC 6455).
    // Returns false on send error (socket will need reconnect).
    bool send(const uint8_t* data, size_t len);

    // Non-blocking receive. Appends one complete frame's payload to `out` and
    // returns true.  Returns false if no complete frame is available yet (or on
    // error — check connected() to distinguish).
    bool poll(std::vector<uint8_t>& out);

private:
    int _fd = -1;
    std::vector<uint8_t> _recv_buf;  // partial frame accumulator

    // WebSocket frame parser state.
    bool readExact(uint8_t* dst, size_t n);
};

}  // namespace wfedit
