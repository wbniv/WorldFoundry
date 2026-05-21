// ws_client.cc — see ws_client.h.
// Plan: docs/plans/2026-05-21-realtime-coediting.md Phase 1

#include "ws_client.h"

#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netdb.h>
#include <sys/socket.h>
#include <unistd.h>
#include <cstring>
#include <random>

namespace wfedit {

// ── Base64 (for Sec-WebSocket-Key) ───────────────────────────────────────────

static const char kB64Chars[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

static std::string base64Encode(const uint8_t* data, size_t len) {
    std::string out;
    out.reserve((len + 2) / 3 * 4);
    for (size_t i = 0; i < len; i += 3) {
        uint32_t v = static_cast<uint32_t>(data[i]) << 16;
        if (i + 1 < len) v |= static_cast<uint32_t>(data[i + 1]) << 8;
        if (i + 2 < len) v |= static_cast<uint32_t>(data[i + 2]);
        out += kB64Chars[(v >> 18) & 63];
        out += kB64Chars[(v >> 12) & 63];
        out += (i + 1 < len) ? kB64Chars[(v >> 6) & 63] : '=';
        out += (i + 2 < len) ? kB64Chars[v & 63] : '=';
    }
    return out;
}

// ── URL parsing ───────────────────────────────────────────────────────────────

struct ParsedUrl {
    std::string host;
    std::string port;
    std::string path;
    bool ok = false;
};

static ParsedUrl parseWsUrl(const char* url) {
    ParsedUrl r;
    std::string s(url);
    if (s.size() < 5 || s.substr(0, 5) != "ws://") return r;
    s = s.substr(5);

    auto slash = s.find('/');
    std::string hostport = (slash == std::string::npos) ? s : s.substr(0, slash);
    r.path = (slash == std::string::npos) ? "/" : s.substr(slash);

    auto colon = hostport.rfind(':');
    r.host = (colon == std::string::npos) ? hostport : hostport.substr(0, colon);
    r.port = (colon == std::string::npos) ? "80" : hostport.substr(colon + 1);
    r.ok = !r.host.empty();
    return r;
}

// ── connect ───────────────────────────────────────────────────────────────────

bool WsClient::connect(const char* url) {
    disconnect();

    ParsedUrl pu = parseWsUrl(url);
    if (!pu.ok) return false;

    // Resolve hostname.
    struct addrinfo hints{}, *res = nullptr;
    hints.ai_family   = AF_INET;
    hints.ai_socktype = SOCK_STREAM;
    if (getaddrinfo(pu.host.c_str(), pu.port.c_str(), &hints, &res) != 0) return false;

    _fd = ::socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if (_fd < 0) { freeaddrinfo(res); return false; }

    if (::connect(_fd, res->ai_addr, res->ai_addrlen) != 0) {
        freeaddrinfo(res);
        ::close(_fd); _fd = -1;
        return false;
    }
    freeaddrinfo(res);

    // WebSocket handshake — send HTTP upgrade request.
    uint8_t key[16];
    std::mt19937 rng(std::random_device{}());
    std::uniform_int_distribution<int> dist(0, 255);
    for (auto& b : key) b = static_cast<uint8_t>(dist(rng));
    std::string keyB64 = base64Encode(key, 16);

    std::string hostport = pu.host + ":" + pu.port;
    std::string req =
        "GET " + pu.path + " HTTP/1.1\r\n"
        "Host: " + hostport + "\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Key: " + keyB64 + "\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n";

    ssize_t sent = ::send(_fd, req.c_str(), req.size(), MSG_NOSIGNAL);
    if (sent < 0 || static_cast<size_t>(sent) != req.size()) {
        ::close(_fd); _fd = -1; return false;
    }

    // Read HTTP response until \r\n\r\n.
    char buf[4096];
    size_t total = 0;
    bool found = false;
    while (total < sizeof(buf) - 1 && !found) {
        ssize_t n = ::recv(_fd, buf + total, sizeof(buf) - 1 - total, 0);
        if (n <= 0) { ::close(_fd); _fd = -1; return false; }
        total += static_cast<size_t>(n);
        buf[total] = '\0';
        found = (strstr(buf, "\r\n\r\n") != nullptr);
    }

    if (!strstr(buf, "101")) { ::close(_fd); _fd = -1; return false; }

    // Switch to non-blocking.
    int flags = fcntl(_fd, F_GETFL, 0);
    fcntl(_fd, F_SETFL, flags | O_NONBLOCK);
    return true;
}

// ── disconnect ────────────────────────────────────────────────────────────────

void WsClient::disconnect() {
    if (_fd >= 0) {
        ::close(_fd);
        _fd = -1;
        _recv_buf.clear();
    }
}

// ── send ──────────────────────────────────────────────────────────────────────

bool WsClient::send(const uint8_t* data, size_t len) {
    if (_fd < 0) return false;

    // Build WebSocket frame header (client→server: masked, binary opcode 0x02).
    uint8_t header[10];
    size_t hdrLen = 0;
    header[hdrLen++] = 0x82;  // FIN=1, opcode=2 (binary)

    if (len <= 125) {
        header[hdrLen++] = 0x80 | static_cast<uint8_t>(len);
    } else if (len <= 65535) {
        header[hdrLen++] = 0x80 | 126;
        header[hdrLen++] = static_cast<uint8_t>((len >> 8) & 0xff);
        header[hdrLen++] = static_cast<uint8_t>(len & 0xff);
    } else {
        header[hdrLen++] = 0x80 | 127;
        for (int i = 7; i >= 0; --i)
            header[hdrLen++] = static_cast<uint8_t>((len >> (i * 8)) & 0xff);
    }

    // 4-byte masking key (random).
    uint8_t mask[4];
    {
        std::mt19937 rng(std::random_device{}());
        std::uniform_int_distribution<int> dist(0, 255);
        for (auto& b : mask) b = static_cast<uint8_t>(dist(rng));
    }
    header[hdrLen++] = mask[0];
    header[hdrLen++] = mask[1];
    header[hdrLen++] = mask[2];
    header[hdrLen++] = mask[3];

    // Masked payload.
    std::vector<uint8_t> masked(len);
    for (size_t i = 0; i < len; ++i)
        masked[i] = data[i] ^ mask[i & 3];

    // Send header then payload.
    if (::send(_fd, header, hdrLen, MSG_NOSIGNAL) < 0) {
        disconnect(); return false;
    }
    if (len > 0 && ::send(_fd, masked.data(), masked.size(), MSG_NOSIGNAL) < 0) {
        disconnect(); return false;
    }
    return true;
}

// ── poll ──────────────────────────────────────────────────────────────────────
// Non-blocking: reads whatever is available into _recv_buf, then tries to
// parse one complete frame.  Server→client frames are NOT masked per RFC 6455.

bool WsClient::poll(std::vector<uint8_t>& out) {
    if (_fd < 0) return false;

    // Read available bytes (non-blocking).
    uint8_t tmp[4096];
    ssize_t n;
    while ((n = ::recv(_fd, tmp, sizeof(tmp), MSG_DONTWAIT)) > 0) {
        _recv_buf.insert(_recv_buf.end(), tmp, tmp + n);
    }
    if (n == 0) {
        // Peer closed connection.
        disconnect();
        return false;
    }
    // EAGAIN/EWOULDBLOCK is expected on non-blocking sockets.

    // Try to parse one frame from _recv_buf.
    if (_recv_buf.size() < 2) return false;

    const uint8_t b0 = _recv_buf[0];
    const uint8_t b1 = _recv_buf[1];
    // bool fin = (b0 & 0x80) != 0;  // we ignore FIN for now (no fragmentation)
    const int opcode = b0 & 0x0f;
    const bool masked = (b1 & 0x80) != 0;  // server→client should be unmasked

    // Payload length.
    uint64_t payloadLen = b1 & 0x7f;
    size_t headerEnd = 2;

    if (payloadLen == 126) {
        if (_recv_buf.size() < 4) return false;
        payloadLen = (static_cast<uint64_t>(_recv_buf[2]) << 8) | _recv_buf[3];
        headerEnd = 4;
    } else if (payloadLen == 127) {
        if (_recv_buf.size() < 10) return false;
        payloadLen = 0;
        for (int i = 0; i < 8; ++i)
            payloadLen = (payloadLen << 8) | _recv_buf[2 + i];
        headerEnd = 10;
    }

    size_t maskOffset = headerEnd;
    if (masked) headerEnd += 4;

    size_t frameEnd = headerEnd + static_cast<size_t>(payloadLen);
    if (_recv_buf.size() < frameEnd) return false;

    // Handle ping — reply with pong and consume the frame.
    if (opcode == 0x09) {
        std::vector<uint8_t> pong(payloadLen + 2);
        pong[0] = 0x8a;  // FIN=1, opcode=10 (pong)
        pong[1] = static_cast<uint8_t>(payloadLen);
        memcpy(pong.data() + 2, _recv_buf.data() + headerEnd, static_cast<size_t>(payloadLen));
        ::send(_fd, pong.data(), pong.size(), MSG_NOSIGNAL);
        _recv_buf.erase(_recv_buf.begin(), _recv_buf.begin() + static_cast<ptrdiff_t>(frameEnd));
        return false;  // no data frame; caller will poll again next iteration
    }

    // Close frame.
    if (opcode == 0x08) {
        disconnect();
        return false;
    }

    // For binary (0x02) or continuation (0x00) frames, extract payload.
    const uint8_t* payload = _recv_buf.data() + headerEnd;
    out.resize(static_cast<size_t>(payloadLen));
    if (masked) {
        const uint8_t* mk = _recv_buf.data() + maskOffset;
        for (size_t i = 0; i < static_cast<size_t>(payloadLen); ++i)
            out[i] = payload[i] ^ mk[i & 3];
    } else {
        memcpy(out.data(), payload, static_cast<size_t>(payloadLen));
    }

    _recv_buf.erase(_recv_buf.begin(), _recv_buf.begin() + static_cast<ptrdiff_t>(frameEnd));
    return true;
}

}  // namespace wfedit
