// ws_client.cc — see ws_client.h.
// Plans: docs/plans/2026-05-21-realtime-coediting.md Phase 1
//        docs/plans/2026-05-26-internet-voice-video-webrtc.md Phase 1 (wss://)

#include "ws_client.h"

#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netdb.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>
#include <cstdio>
#include <cstring>
#include <random>

#include <openssl/ssl.h>
#include <openssl/err.h>

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
    bool tls = false;
    bool ok  = false;
};

static ParsedUrl parseWsUrl(const char* url) {
    ParsedUrl r;
    std::string s(url);

    if (s.size() >= 6 && s.substr(0, 6) == "wss://") {
        r.tls = true;
        s = s.substr(6);
    } else if (s.size() >= 5 && s.substr(0, 5) == "ws://") {
        r.tls = false;
        s = s.substr(5);
    } else {
        return r;
    }

    auto slash = s.find('/');
    std::string hostport = (slash == std::string::npos) ? s : s.substr(0, slash);
    r.path = (slash == std::string::npos) ? "/" : s.substr(slash);

    auto colon = hostport.rfind(':');
    r.host = (colon == std::string::npos) ? hostport : hostport.substr(0, colon);
    r.port = (colon == std::string::npos) ? (r.tls ? "443" : "80")
                                           : hostport.substr(colon + 1);
    r.ok = !r.host.empty();
    return r;
}

// ── TLS helpers (thin wrappers so send/poll stay generic) ────────────────────

ssize_t WsClient::tls_send(const void* buf, size_t len) {
    return SSL_write(static_cast<SSL*>(_ssl), buf, static_cast<int>(len));
}

ssize_t WsClient::tls_recv(void* buf, size_t len) {
    SSL* ssl = static_cast<SSL*>(_ssl);
    int n = SSL_read(ssl, buf, static_cast<int>(len));
    if (n <= 0) {
        int err = SSL_get_error(ssl, n);
        if (err == SSL_ERROR_WANT_READ || err == SSL_ERROR_WANT_WRITE) {
            errno = EAGAIN;
        } else {
            errno = EIO;
        }
    }
    return n;
}

// ── connect ───────────────────────────────────────────────────────────────────

bool WsClient::connect(const char* url) {
    disconnect();
    _last_error = ConnectError::NoError;

    ParsedUrl pu = parseWsUrl(url);
    if (!pu.ok) { _last_error = ConnectError::Other; return false; }

    // Resolve hostname. AF_UNSPEC so we accept IPv4 *or* IPv6 — a public relay /
    // Cloudflare quick-tunnel host can answer AAAA-only, and the old AF_INET
    // forced IPv4-only (connect failed on such hosts). Try each result until one
    // connects (the first family may not be routable on a given network).
    struct addrinfo hints{}, *res = nullptr;
    hints.ai_family   = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    const int gai = getaddrinfo(pu.host.c_str(), pu.port.c_str(), &hints, &res);
    if (gai != 0) {
        // EAI_AGAIN = resolver temporarily busy (worth a retry); everything else
        // (NXDOMAIN/EAI_NONAME, EAI_NODATA, EAI_FAIL) is a bad host → fail fast.
        _last_error = (gai == EAI_AGAIN) ? ConnectError::DnsTemporary
                                         : ConnectError::DnsFatal;
        std::fprintf(stderr, "ws: getaddrinfo(%s:%s) failed: %s\n",
                     pu.host.c_str(), pu.port.c_str(), gai_strerror(gai));
        return false;
    }

    // Try each address with a non-blocking connect + select so a black-hole host
    // (e.g. unreachable IPv6) doesn't block indefinitely. 5 s per address matches
    // the SO_RCVTIMEO/SO_SNDTIMEO set below; the retry budget above handles the
    // overall cap so individual attempts stay snappy.
    _fd = -1;
    int connect_errno = 0;
    for (struct addrinfo* rp = res; rp; rp = rp->ai_next) {
        const int fd = ::socket(rp->ai_family, rp->ai_socktype, rp->ai_protocol);
        if (fd < 0) { connect_errno = errno; continue; }
        // Make non-blocking for the connect() call only.
        const int flags = ::fcntl(fd, F_GETFL, 0);
        ::fcntl(fd, F_SETFL, flags | O_NONBLOCK);
        const int rc = ::connect(fd, rp->ai_addr, rp->ai_addrlen);
        if (rc == 0 || errno == EINPROGRESS) {
            fd_set wfds; FD_ZERO(&wfds); FD_SET(fd, &wfds);
            struct timeval tv{ 5, 0 };
            const int sel = ::select(fd + 1, nullptr, &wfds, nullptr, &tv);
            if (sel > 0) {
                int err = 0; socklen_t len = sizeof(err);
                ::getsockopt(fd, SOL_SOCKET, SO_ERROR, &err, &len);
                if (err == 0) {
                    ::fcntl(fd, F_SETFL, flags);   // restore blocking
                    _fd = fd; break;
                }
                connect_errno = err;
            } else {
                connect_errno = (sel == 0) ? ETIMEDOUT : errno;
            }
        } else {
            connect_errno = errno;
        }
        std::fprintf(stderr, "ws: connect(fam=%d) to %s:%s failed: %s\n",
                     rp->ai_family, pu.host.c_str(), pu.port.c_str(), std::strerror(connect_errno));
        ::close(fd);
    }
    freeaddrinfo(res);
    if (_fd < 0) {
        switch (connect_errno) {
            case ECONNREFUSED:               _last_error = ConnectError::Refused;     break;
            case ETIMEDOUT:                  _last_error = ConnectError::Timeout;     break;
            case ENETUNREACH: case EHOSTUNREACH:
                                             _last_error = ConnectError::Unreachable; break;
            default:                         _last_error = ConnectError::Other;       break;
        }
        return false;
    }

    // Bound blocking I/O so one slow/half-open peer can't hang an attempt past
    // the retry budget (and so the abort-join after a window close stays snappy).
    // Covers the plain-TCP recv/send and, since OpenSSL drives this fd, the TLS
    // handshake's reads too. (A non-blocking ::connect with a select() cap — to
    // bound the SYN wait to a black-hole host — is a noted follow-up.)
    {
        const struct timeval to{ 5, 0 };   // 5 s
        setsockopt(_fd, SOL_SOCKET, SO_RCVTIMEO, &to, sizeof(to));
        setsockopt(_fd, SOL_SOCKET, SO_SNDTIMEO, &to, sizeof(to));
    }

    // TLS handshake for wss://. A handshake failure against a warming Cloudflare
    // edge is transient, so classify as Tls (retryable) at every exit.
    _tls = pu.tls;
    if (_tls) {
        SSL_CTX* ctx = SSL_CTX_new(TLS_client_method());
        if (!ctx) { _last_error = ConnectError::Tls; ::close(_fd); _fd = -1; return false; }
        SSL_CTX_set_verify(ctx, SSL_VERIFY_NONE, nullptr);
        SSL* ssl = SSL_new(ctx);
        if (!ssl) { _last_error = ConnectError::Tls; SSL_CTX_free(ctx); ::close(_fd); _fd = -1; return false; }
        SSL_set_fd(ssl, _fd);
        SSL_set_tlsext_host_name(ssl, pu.host.c_str());
        if (SSL_connect(ssl) != 1) {
            _last_error = ConnectError::Tls;
            std::fprintf(stderr, "ws: TLS handshake to %s failed\n", pu.host.c_str());
            SSL_free(ssl); SSL_CTX_free(ctx);
            ::close(_fd); _fd = -1; return false;
        }
        _ssl     = ssl;
        _ssl_ctx = ctx;
    }

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

    auto raw_send = [&](const char* p, size_t n) -> bool {
        if (_tls) return tls_send(p, n) == static_cast<ssize_t>(n);
        return ::send(_fd, p, n, MSG_NOSIGNAL) == static_cast<ssize_t>(n);
    };
    if (!raw_send(req.c_str(), req.size())) {
        disconnect(); return false;
    }

    // Read HTTP response until \r\n\r\n.
    char buf[4096];
    size_t total = 0;
    bool found = false;
    while (total < sizeof(buf) - 1 && !found) {
        ssize_t n;
        if (_tls) n = tls_recv(buf + total, sizeof(buf) - 1 - total);
        else      n = ::recv(_fd, buf + total, sizeof(buf) - 1 - total, 0);
        if (n <= 0) {
            // Peer closed (or recv timed out) before the full upgrade response —
            // common while a quick tunnel is still coming up. Retryable.
            _last_error = ConnectError::UpgradeFailed;
            std::fprintf(stderr, "ws: upgrade read failed (recv=%zd) from %s\n", n, pu.host.c_str());
            disconnect(); return false;
        }
        total += static_cast<size_t>(n);
        buf[total] = '\0';
        found = (strstr(buf, "\r\n\r\n") != nullptr);
    }

    // Parse the real status line ("HTTP/1.1 <code> <reason>") rather than
    // strstr'ing for "101" — a header value could contain "101" and false-match.
    // 101 = success; 5xx (Cloudflare 530/502, gateway warming) is retryable;
    // any other non-101 status is a definitive rejection → fail fast.
    int code = 0;
    std::sscanf(buf, "HTTP/%*d.%*d %d", &code);
    if (code != 101) {
        _last_error = (code / 100 == 5) ? ConnectError::HttpServerError
                                        : ConnectError::HttpClientError;
        char status[80] = {0};
        std::snprintf(status, sizeof(status), "%.*s", 60, buf);   // first line of the response
        std::fprintf(stderr, "ws: WS upgrade not accepted by %s — response: %s\n", pu.host.c_str(), status);
        disconnect(); return false;
    }

    // Handshake done — drop the handshake recv/send timeout so the long-lived
    // socket keeps its original semantics (the timeout was only there to bound
    // the connect/upgrade phase for retry-budget and abort responsiveness).
    {
        const struct timeval none{ 0, 0 };
        setsockopt(_fd, SOL_SOCKET, SO_RCVTIMEO, &none, sizeof(none));
        setsockopt(_fd, SOL_SOCKET, SO_SNDTIMEO, &none, sizeof(none));
    }

    // Switch to non-blocking (plain TCP only; TLS layer handles its own buffering).
    if (!_tls) {
        int flags = fcntl(_fd, F_GETFL, 0);
        fcntl(_fd, F_SETFL, flags | O_NONBLOCK);
    }
    return true;
}

// ── disconnect ────────────────────────────────────────────────────────────────

void WsClient::disconnect() {
    if (_ssl) {
        SSL_shutdown(static_cast<SSL*>(_ssl));
        SSL_free(static_cast<SSL*>(_ssl));
        _ssl = nullptr;
    }
    if (_ssl_ctx) {
        SSL_CTX_free(static_cast<SSL_CTX*>(_ssl_ctx));
        _ssl_ctx = nullptr;
    }
    if (_fd >= 0) {
        ::close(_fd);
        _fd = -1;
        _recv_buf.clear();
        _tls = false;
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
    auto do_send = [&](const void* p, size_t n) -> bool {
        if (_tls) return tls_send(p, n) == static_cast<ssize_t>(n);
        return ::send(_fd, p, n, MSG_NOSIGNAL) == static_cast<ssize_t>(n);
    };
    if (!do_send(header, hdrLen)) { disconnect(); return false; }
    if (len > 0 && !do_send(masked.data(), masked.size())) { disconnect(); return false; }
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
    while (true) {
        if (_tls) {
            n = tls_recv(tmp, sizeof(tmp));
        } else {
            n = ::recv(_fd, tmp, sizeof(tmp), MSG_DONTWAIT);
        }
        if (n <= 0) break;
        _recv_buf.insert(_recv_buf.end(), tmp, tmp + n);
    }
    if (n == 0) {
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
        if (_tls) tls_send(pong.data(), pong.size());
        else      ::send(_fd, pong.data(), pong.size(), MSG_NOSIGNAL);
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
