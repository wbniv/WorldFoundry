// ws_client.h — minimal WebSocket client for the co-editing relay.
//
// Supports ws:// (plain TCP) and wss:// (OpenSSL TLS).
// Operates on a single socket; all I/O is non-blocking after connect.
// Supports binary frames only (no text frames).
//
// Plans: docs/plans/2026-05-21-realtime-coediting.md Phase 1
//        docs/plans/2026-05-26-internet-voice-video-webrtc.md Phase 1

#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include "connect_retry.h"   // ConnectError

namespace wfedit {

class WsClient {
public:
    WsClient() = default;
    ~WsClient() { disconnect(); }

    WsClient(const WsClient&) = delete;
    WsClient& operator=(const WsClient&) = delete;

    // Connect and perform WebSocket handshake.
    // url: "ws://host[:port]/path" (port default 80) or
    //      "wss://host[:port]/path" (port default 443, TLS via OpenSSL).
    // Blocks until connected. Returns false on failure.
    bool connect(const char* url);

    // Why the last connect() failed (None after a success). Lets the connector
    // fail fast on definitive errors (NXDOMAIN, 4xx) instead of retrying them.
    ConnectError lastError() const { return _last_error; }

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
    ConnectError _last_error = ConnectError::NoError;  // why the last connect() failed
    std::vector<uint8_t> _recv_buf;  // partial frame accumulator
    bool  _tls     = false;
    void* _ssl     = nullptr;    // SSL* (OpenSSL) — non-null when TLS active
    void* _ssl_ctx = nullptr;    // SSL_CTX*

    bool readExact(uint8_t* dst, size_t n);
    ssize_t tls_send(const void* buf, size_t len);
    ssize_t tls_recv(void* buf, size_t len);
};

}  // namespace wfedit
