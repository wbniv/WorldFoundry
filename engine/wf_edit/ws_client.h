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

#if defined(__EMSCRIPTEN__)
#include <deque>
#include <emscripten/websocket.h>   // EMSCRIPTEN_WEBSOCKET_T + event types (browser backend)
#endif

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

#if defined(__EMSCRIPTEN__)
    bool connected() const;   // browser readyState == OPEN (ws_client_emscripten.cc)
#else
    bool connected() const { return _fd >= 0; }
#endif

    // Send a binary WebSocket frame (client→server frames are masked per RFC 6455).
    // Returns false on send error (socket will need reconnect).
    bool send(const uint8_t* data, size_t len);

    // Non-blocking receive. Appends one complete frame's payload to `out` and
    // returns true.  Returns false if no complete frame is available yet (or on
    // error — check connected() to distinguish).
    bool poll(std::vector<uint8_t>& out);

private:
    ConnectError _last_error = ConnectError::NoError;  // why the last connect() failed

#if defined(__EMSCRIPTEN__)
    // Browser WebSocket backend (ws_client_emscripten.cc). The browser performs
    // TLS + RFC 6455 framing; onmessage delivers complete binary frames, which we
    // queue here and hand out one-per-poll(). connect() is async — onopen flips
    // _ws_state to Open, which connected() reports. Same channel-tag wire protocol
    // as the native client, so a browser peer interoperates in the same relay room.
    enum class WsState { Closed, Connecting, Open, Error };
    EMSCRIPTEN_WEBSOCKET_T           _ws_socket = 0;     // 0 = none
    WsState                          _ws_state  = WsState::Closed;
    std::deque<std::vector<uint8_t>> _ws_incoming;       // complete binary frames

    // Static C-ABI callbacks (registered with userData = this).
    static EM_BOOL onOpen   (int, const EmscriptenWebSocketOpenEvent*,    void*);
    static EM_BOOL onMessage(int, const EmscriptenWebSocketMessageEvent*, void*);
    static EM_BOOL onError  (int, const EmscriptenWebSocketErrorEvent*,   void*);
    static EM_BOOL onClose  (int, const EmscriptenWebSocketCloseEvent*,   void*);
#else
    int _fd = -1;
    std::vector<uint8_t> _recv_buf;  // partial frame accumulator
    bool  _tls     = false;
    void* _ssl     = nullptr;    // SSL* (OpenSSL) — non-null when TLS active
    void* _ssl_ctx = nullptr;    // SSL_CTX*

    bool readExact(uint8_t* dst, size_t n);
    ssize_t tls_send(const void* buf, size_t len);
    ssize_t tls_recv(void* buf, size_t len);
#endif
};

}  // namespace wfedit
