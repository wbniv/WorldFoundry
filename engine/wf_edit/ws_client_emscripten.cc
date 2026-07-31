// ws_client_emscripten.cc — browser WebSocket backend for the relay transport,
// behind the same wfedit::WsClient interface as the native ws_client.cc (POSIX
// sockets + OpenSSL). The browser performs TLS + RFC 6455 framing; we exchange
// the relay's binary channel frames ([channel-byte][payload]) unchanged, so a
// web client interoperates with native clients in the same relay room.
//
// The native connect() blocks until connected and poll() reassembles RFC 6455
// frames. The browser WebSocket API is async + event-callback, and can't block on
// the single-threaded main loop, so the contract shifts:
//   - connect()  begins an async connect (onopen flips state to Open) and returns
//                true = "initiated" (NOT "connected"). The caller drives a
//                poll-in-loop state machine off connected() (see main.cc web path).
//   - connected() reports onopen state.
//   - onmessage  delivers a COMPLETE binary message (the browser did the framing),
//                queued here; poll() hands out one per call.
// See docs/plans/2026-06-12-wf-edit-in-the-browser.md (Phase 2).

#if defined(__EMSCRIPTEN__)

#include "ws_client.h"

#include <cstdio>
#include <cstring>

namespace wfedit {

// ── async event callbacks (userData == the WsClient) ─────────────────────────

EM_BOOL WsClient::onOpen(int, const EmscriptenWebSocketOpenEvent*, void* userData) {
    auto* c = static_cast<WsClient*>(userData);
    c->_ws_state  = WsState::Open;
    c->_last_error = ConnectError::NoError;
    return EM_TRUE;
}

EM_BOOL WsClient::onMessage(int, const EmscriptenWebSocketMessageEvent* e, void* userData) {
    auto* c = static_cast<WsClient*>(userData);
    // Relay frames are binary. (Text frames, if any, are ignored — the protocol
    // is binary-only.) e->data/numBytes is one complete WebSocket message.
    if (!e->isText && e->numBytes > 0 && e->data)
        c->_ws_incoming.emplace_back(e->data, e->data + e->numBytes);
    return EM_TRUE;
}

EM_BOOL WsClient::onError(int, const EmscriptenWebSocketErrorEvent*, void* userData) {
    auto* c = static_cast<WsClient*>(userData);
    c->_ws_state  = WsState::Error;
    // The browser hides the cause (mixed-content / DNS / TLS / refused all surface
    // as a generic error event), so we can't classify finely — mark non-fatal-ish
    // so the caller's retry policy may try again.
    if (c->_last_error == ConnectError::NoError)
        c->_last_error = ConnectError::Other;
    return EM_TRUE;
}

EM_BOOL WsClient::onClose(int, const EmscriptenWebSocketCloseEvent* e, void* userData) {
    auto* c = static_cast<WsClient*>(userData);
    c->_ws_state = WsState::Closed;
    // wasClean=false before any open ⇒ the connect itself failed.
    if (!e->wasClean && c->_last_error == ConnectError::NoError)
        c->_last_error = ConnectError::UpgradeFailed;
    return EM_TRUE;
}

// ── WsClient interface ───────────────────────────────────────────────────────

bool WsClient::connect(const char* url) {
    if (!emscripten_websocket_is_supported()) {
        _last_error = ConnectError::Other;
        return false;
    }
    disconnect();   // drop any prior socket

    EmscriptenWebSocketCreateAttributes attr;
    emscripten_websocket_init_create_attributes(&attr);
    attr.url      = url;            // ws:// or wss:// — the browser handles TLS
    attr.protocols = nullptr;       // relay accepts no subprotocol (matches native)
    attr.createOnMainThread = EM_TRUE;

    EMSCRIPTEN_WEBSOCKET_T s = emscripten_websocket_new(&attr);
    if (s <= 0) {
        _last_error = ConnectError::Other;
        return false;
    }
    _ws_socket = s;
    _ws_state  = WsState::Connecting;
    _last_error = ConnectError::NoError;

    emscripten_websocket_set_onopen_callback   (s, this, &WsClient::onOpen);
    emscripten_websocket_set_onmessage_callback(s, this, &WsClient::onMessage);
    emscripten_websocket_set_onerror_callback  (s, this, &WsClient::onError);
    emscripten_websocket_set_onclose_callback  (s, this, &WsClient::onClose);

    return true;   // "connect initiated" — poll connected() for the open state
}

bool WsClient::connected() const {
    return _ws_state == WsState::Open;
}

void WsClient::disconnect() {
    if (_ws_socket > 0) {
        emscripten_websocket_close(_ws_socket, 1000, "client closing");
        emscripten_websocket_delete(_ws_socket);
    }
    _ws_socket = 0;
    _ws_state  = WsState::Closed;
    _ws_incoming.clear();
}

bool WsClient::send(const uint8_t* data, size_t len) {
    if (_ws_state != WsState::Open || _ws_socket <= 0) return false;
    return emscripten_websocket_send_binary(
               _ws_socket, const_cast<uint8_t*>(data),
               static_cast<uint32_t>(len)) == EMSCRIPTEN_RESULT_SUCCESS;
}

bool WsClient::poll(std::vector<uint8_t>& out) {
    if (_ws_incoming.empty()) return false;
    out = std::move(_ws_incoming.front());
    _ws_incoming.pop_front();
    return true;
}

} // namespace wfedit

#endif // __EMSCRIPTEN__
