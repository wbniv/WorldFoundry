// ws_client_emscripten.cc — browser WebSocket backend for the relay transport,
// behind the same wfedit::WsClient interface as the native ws_client.cc (which
// uses POSIX sockets + OpenSSL). The browser performs the TLS + RFC 6455
// framing; we exchange the relay's binary channel frames (byte-0 channel tag +
// payload) unchanged, so a web client interoperates with native clients in the
// same room.
//
// PHASE 1 (this commit): no-op — the editor renders a preloaded level with no
// networking. PHASE 2 fills in the emscripten/websocket.h implementation:
// connect() begins an async connect, connected() reads the onopen state, an
// onmessage handler queues complete binary frames, and poll() drains the queue.
// See docs/plans/2026-06-12-wf-edit-in-the-browser.md (Phase 2).

#if defined(__EMSCRIPTEN__)

#include "ws_client.h"

namespace wfedit {

bool WsClient::connect(const char* /*url*/) {
    _last_error = ConnectError::Other;   // Phase 1: networking not wired yet
    return false;
}

void WsClient::disconnect() { _fd = -1; }

bool WsClient::send(const uint8_t* /*data*/, size_t /*len*/) { return false; }

bool WsClient::poll(std::vector<uint8_t>& /*out*/) { return false; }

} // namespace wfedit

#endif // __EMSCRIPTEN__
