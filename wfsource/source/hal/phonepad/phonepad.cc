//=============================================================================
// hal/phonepad/phonepad.cc: the phone as a gamepad, the server half (portable)
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// See phonepad.h for the protocol. Plain POSIX sockets, non-blocking, polled
// once per frame. No allocation-heavy parsing: requests are capped at 4 KB
// and WebSocket frames at 64 bytes, and every byte is read one at a time
// (no unaligned multi-byte loads; the Chromecast HD is 32-bit ARM).
//=============================================================================

#include "phonepad.h"

#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <sys/socket.h>
#include <unistd.h>

#include <cstdarg>
#include <cstdio>
#include <cstring>

namespace phonepad
{

namespace
{

// ---- SHA-1 (FIPS 180-1), only for the WebSocket handshake -------------------

struct Sha1
{
    uint32_t h[5];
    uint8_t  block[64];
    uint64_t length = 0;
    size_t   used   = 0;

    Sha1() { h[0] = 0x67452301u; h[1] = 0xEFCDAB89u; h[2] = 0x98BADCFEu; h[3] = 0x10325476u; h[4] = 0xC3D2E1F0u; }

    static uint32_t Rol(uint32_t v, int n) { return (v << n) | (v >> (32 - n)); }

    void Compress()
    {
        uint32_t w[80];
        for (int i = 0; i < 16; ++i)
            w[i] = (uint32_t(block[4 * i]) << 24) | (uint32_t(block[4 * i + 1]) << 16)
                 | (uint32_t(block[4 * i + 2]) << 8) | uint32_t(block[4 * i + 3]);
        for (int i = 16; i < 80; ++i)
            w[i] = Rol(w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16], 1);
        uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4];
        for (int i = 0; i < 80; ++i)
        {
            uint32_t f, k;
            if (i < 20)      { f = (b & c) | (~b & d);           k = 0x5A827999u; }
            else if (i < 40) { f = b ^ c ^ d;                    k = 0x6ED9EBA1u; }
            else if (i < 60) { f = (b & c) | (b & d) | (c & d);  k = 0x8F1BBCDCu; }
            else             { f = b ^ c ^ d;                    k = 0xCA62C1D6u; }
            const uint32_t t = Rol(a, 5) + f + e + k + w[i];
            e = d; d = c; c = Rol(b, 30); b = a; a = t;
        }
        h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e;
    }

    void Update(const uint8_t* p, size_t n)
    {
        length += uint64_t(n) * 8;
        for (size_t i = 0; i < n; ++i)
        {
            block[used++] = p[i];
            if (used == 64) { Compress(); used = 0; }
        }
    }

    void Final(uint8_t out[20])
    {
        const uint64_t bits = length;
        const uint8_t pad80 = 0x80, zero = 0;
        Update(&pad80, 1);
        while (used != 56) Update(&zero, 1);
        uint8_t len[8];
        for (int i = 0; i < 8; ++i) len[i] = uint8_t(bits >> (56 - 8 * i));
        Update(len, 8);
        for (int i = 0; i < 5; ++i)
            for (int j = 0; j < 4; ++j)
                out[4 * i + j] = uint8_t(h[i] >> (24 - 8 * j));
    }
};

std::string Base64(const uint8_t* p, size_t n)
{
    static const char kAlphabet[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string s;
    for (size_t i = 0; i < n; i += 3)
    {
        const uint32_t v = (uint32_t(p[i]) << 16) | (i + 1 < n ? uint32_t(p[i + 1]) << 8 : 0)
                         | (i + 2 < n ? uint32_t(p[i + 2]) : 0);
        s += kAlphabet[(v >> 18) & 63];
        s += kAlphabet[(v >> 12) & 63];
        s += i + 1 < n ? kAlphabet[(v >> 6) & 63] : '=';
        s += i + 2 < n ? kAlphabet[v & 63] : '=';
    }
    return s;
}

bool SetNonBlocking(int fd)
{
    const int fl = fcntl(fd, F_GETFL, 0);
    if (fl < 0 || fcntl(fd, F_SETFL, fl | O_NONBLOCK) < 0) return false;
    fcntl(fd, F_SETFD, FD_CLOEXEC);
    return true;
}

std::string Lower(std::string s)
{
    for (char& ch : s)
        if (ch >= 'A' && ch <= 'Z') ch = char(ch - 'A' + 'a');
    return s;
}

std::string Trim(const std::string& s)
{
    size_t a = 0, b = s.size();
    while (a < b && (s[a] == ' ' || s[a] == '\t')) ++a;
    while (b > a && (s[b - 1] == ' ' || s[b - 1] == '\t')) --b;
    return s.substr(a, b - a);
}

// The value of query parameter `name` in "a=1&k=2", or "" if absent.
std::string QueryParam(const std::string& query, const char* name)
{
    const size_t nlen = std::strlen(name);
    size_t pos = 0;
    while (pos <= query.size())
    {
        size_t amp = query.find('&', pos);
        if (amp == std::string::npos) amp = query.size();
        const std::string kv = query.substr(pos, amp - pos);
        if (kv.size() > nlen && kv.compare(0, nlen, name) == 0 && kv[nlen] == '=')
            return kv.substr(nlen + 1);
        pos = amp + 1;
    }
    return std::string();
}

bool HeaderHasToken(const std::string& value, const char* token)
{
    const std::string v = Lower(value);
    size_t pos = 0;
    while (pos <= v.size())
    {
        size_t comma = v.find(',', pos);
        if (comma == std::string::npos) comma = v.size();
        if (Trim(v.substr(pos, comma - pos)) == token) return true;
        pos = comma + 1;
    }
    return false;
}

// Shown for GET / with no PIN (someone typed the bare address) and, with the
// warning line, for a wrong PIN. It never carries game input.
const char kPinFormHead[] =
    "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
    "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
    "<title>World Foundry controller</title><style>"
    "body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;"
    "background:#0d1117;color:#e6edf3;font:18px/1.5 system-ui,sans-serif}"
    "form{text-align:center;padding:24px}input{font:28px monospace;width:7em;text-align:center;"
    "letter-spacing:.2em;padding:6px;border-radius:8px;border:1px solid #3a4a63;background:#05080d;color:#e6edf3}"
    "button{font-size:20px;margin-left:8px;padding:8px 16px;border-radius:8px;border:0;background:#56d364;color:#0d1117}"
    ".bad{color:#ff7b72}</style></head><body><form method=\"get\" action=\"/\">";
const char kPinFormTail[] =
    "<p>Enter the PIN shown on the TV</p>"
    "<input name=\"k\" inputmode=\"numeric\" pattern=\"[0-9]{6}\" maxlength=\"6\" autofocus>"
    "<button>Go</button></form></body></html>";

}  // namespace

// ---- helpers ------------------------------------------------------------------

std::string WebSocketAccept(const std::string& key)
{
    static const char kGuid[] = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";
    Sha1 sha;
    sha.Update(reinterpret_cast<const uint8_t*>(key.data()), key.size());
    sha.Update(reinterpret_cast<const uint8_t*>(kGuid), sizeof(kGuid) - 1);
    uint8_t digest[20];
    sha.Final(digest);
    return Base64(digest, sizeof(digest));
}

bool ParseMaskFrame(const std::string& text, uint16_t* mask)
{
    if (text.size() < 3 || text.size() > 6 || text[0] != 'b' || text[1] != ':') return false;
    uint32_t v = 0;
    for (size_t i = 2; i < text.size(); ++i)
    {
        const char ch = text[i];
        uint32_t d;
        if (ch >= '0' && ch <= '9')      d = uint32_t(ch - '0');
        else if (ch >= 'a' && ch <= 'f') d = uint32_t(ch - 'a' + 10);
        else if (ch >= 'A' && ch <= 'F') d = uint32_t(ch - 'A' + 10);
        else return false;
        v = (v << 4) | d;
    }
    *mask = uint16_t(v);
    return true;
}

std::string MakePin()
{
    const int fd = open("/dev/urandom", O_RDONLY | O_CLOEXEC);
    if (fd < 0) return std::string();
    std::string pin;
    // 4294000000 = 4294 * 10^6, the largest multiple of 10^6 below 2^32:
    // rejecting values at or above it makes every PIN equally likely.
    for (int attempt = 0; attempt < 16 && pin.empty(); ++attempt)
    {
        uint8_t b[4];
        size_t got = 0;
        while (got < sizeof(b))
        {
            const ssize_t n = read(fd, b + got, sizeof(b) - got);
            if (n <= 0) { if (n < 0 && errno == EINTR) continue; close(fd); return std::string(); }
            got += size_t(n);
        }
        const uint32_t v = (uint32_t(b[0]) << 24) | (uint32_t(b[1]) << 16) | (uint32_t(b[2]) << 8) | b[3];
        if (v >= 4294000000u) continue;
        char buf[8];
        std::snprintf(buf, sizeof(buf), "%06u", unsigned(v % 1000000u));
        pin = buf;
    }
    close(fd);
    return pin;
}

bool DiscoverLanAddress(uint32_t* addr)
{
    // connect() on a UDP socket only picks a route and a source address; no
    // packet is sent. 8.8.8.8 stands for "anywhere off this subnet".
    const int fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) return false;
    sockaddr_in to;
    std::memset(&to, 0, sizeof(to));
    to.sin_family      = AF_INET;
    to.sin_port        = htons(53);
    to.sin_addr.s_addr = htonl(0x08080808u);
    bool ok = false;
    if (connect(fd, reinterpret_cast<sockaddr*>(&to), sizeof(to)) == 0)
    {
        sockaddr_in me;
        socklen_t len = sizeof(me);
        if (getsockname(fd, reinterpret_cast<sockaddr*>(&me), &len) == 0 && me.sin_addr.s_addr != 0)
        {
            *addr = ntohl(me.sin_addr.s_addr);
            ok = true;
        }
    }
    close(fd);
    return ok;
}

bool IsPrivateIPv4(uint32_t a)
{
    return (a >> 24) == 10
        || (a >> 20) == ((172u << 4) | 1u)          // 172.16.0.0/12
        || (a >> 16) == ((192u << 8) | 168u)        // 192.168.0.0/16
        || (a >> 16) == ((169u << 8) | 254u)        // 169.254.0.0/16 link-local
        || (a >> 24) == 127;                        // loopback (the Linux test host)
}

std::string FormatIPv4(uint32_t a)
{
    char buf[20];
    std::snprintf(buf, sizeof(buf), "%u.%u.%u.%u", unsigned(a >> 24), unsigned((a >> 16) & 255),
                  unsigned((a >> 8) & 255), unsigned(a & 255));
    return buf;
}

std::string ControllerUrl(uint32_t addr, uint16_t port, const std::string& pin)
{
    char buf[64];
    std::snprintf(buf, sizeof(buf), "http://%s:%u/?k=%s", FormatIPv4(addr).c_str(), unsigned(port), pin.c_str());
    return buf;
}

// ---- Server -------------------------------------------------------------------

Server::Server() {}
Server::~Server() { Stop(); }

void Server::Log(const char* fmt, ...)
{
    if (!log_) return;
    char buf[300];
    std::memcpy(buf, "phonepad: ", 10);
    va_list ap;
    va_start(ap, fmt);
    std::vsnprintf(buf + 10, sizeof(buf) - 10, fmt, ap);
    va_end(ap);
    log_(buf);
}

bool Server::Start(const Config& cfg)
{
    Stop();
    if (cfg.pin.size() != 6 || cfg.pin.find_first_not_of("0123456789") != std::string::npos)
    {
        Log("refusing to start: the PIN must be six digits");
        return false;
    }
    cfg_ = cfg;
    const int tries = cfg.port == 0 ? 1 : (cfg.portTries > 0 ? cfg.portTries : 1);
    for (int i = 0; i < tries; ++i)
    {
        const int fd = socket(AF_INET, SOCK_STREAM, 0);
        if (fd < 0) { Log("socket: %s", std::strerror(errno)); return false; }
        const int one = 1;
        setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
        sockaddr_in a;
        std::memset(&a, 0, sizeof(a));
        a.sin_family      = AF_INET;
        a.sin_port        = htons(uint16_t(cfg.port == 0 ? 0 : cfg.port + i));
        a.sin_addr.s_addr = htonl(cfg.bindAddr);
        if (bind(fd, reinterpret_cast<sockaddr*>(&a), sizeof(a)) == 0 && listen(fd, kMaxConnections) == 0
            && SetNonBlocking(fd))
        {
            socklen_t len = sizeof(a);
            getsockname(fd, reinterpret_cast<sockaddr*>(&a), &len);
            listenFd_ = fd;
            port_     = ntohs(a.sin_port);
            Log("listening on %s:%u", FormatIPv4(cfg.bindAddr).c_str(), unsigned(port_));
            return true;
        }
        Log("bind %s:%u: %s", FormatIPv4(cfg.bindAddr).c_str(), unsigned(cfg.port + i), std::strerror(errno));
        close(fd);
    }
    return false;
}

void Server::Stop()
{
    for (Conn& c : conns_)
        if (c.fd >= 0) close(c.fd);
    conns_.clear();
    if (phoneFd_ >= 0) events_ |= kEvPhoneLost;
    phoneFd_ = -1;
    SetPhoneMask(0);
    if (listenFd_ >= 0)
    {
        close(listenFd_);
        listenFd_ = -1;
        Log("stopped");
    }
}

void Server::SetPhoneMask(uint16_t m)
{
    mask_ = m;
}

uint16_t Server::Poll(int64_t nowMs)
{
    if (listenFd_ < 0) return 0;
    Accept(nowMs);

    // Index loop: HandleHttp may push nothing, but CloseConn only marks fd = -1.
    for (size_t i = 0; i < conns_.size(); ++i)
    {
        Conn& c = conns_[i];
        if (c.fd < 0) continue;
        ReadConn(c, nowMs);
    }

    for (Conn& c : conns_)
    {
        if (c.fd < 0) continue;
        if (c.closing)
        {
            if (c.closingMs == 0) c.closingMs = nowMs;
            if (nowMs - c.closingMs > 1000) CloseConn(c, nullptr);   // drain deadline
        }
        else if (c.ws)
        {
            if (c.fd == phoneFd_ && nowMs - c.lastRxMs > cfg_.timeoutMs)
            {
                Log("phone %s timed out (no frame for %d ms): every button released", c.peer.c_str(), cfg_.timeoutMs);
                SendClose(c, 4002, "timeout");
                phoneFd_ = -1;
                SetPhoneMask(0);
                events_ |= kEvPhoneLost;
                c.closing  = true;
            }
        }
        else if (nowMs - c.openedMs > kHttpTimeoutMs)
        {
            char why[96];
            std::snprintf(why, sizeof(why), "no complete request within 5 s (%u bytes received)", unsigned(c.in.size()));
            CloseConn(c, why);
        }
    }

    for (Conn& c : conns_)
        if (c.fd >= 0) FlushConn(c);

    size_t w = 0;
    for (size_t r = 0; r < conns_.size(); ++r)
        if (conns_[r].fd >= 0)
        {
            if (w != r) conns_[w] = std::move(conns_[r]);
            ++w;
        }
    conns_.resize(w);
    return mask_;
}

void Server::Accept(int64_t nowMs)
{
    for (int n = 0; n < 16; ++n)
    {
        sockaddr_in peer;
        socklen_t len = sizeof(peer);
        const int fd = accept(listenFd_, reinterpret_cast<sockaddr*>(&peer), &len);
        if (fd < 0) return;   // EAGAIN (nothing pending) or a transient accept error
        const uint32_t pa = ntohl(peer.sin_addr.s_addr);
        if (peer.sin_family != AF_INET || !IsPrivateIPv4(pa))
        {
            Log("refused %s: not a private LAN address", FormatIPv4(pa).c_str());
            close(fd);
            continue;
        }
        if (!SetNonBlocking(fd)) { close(fd); continue; }
        const int one = 1;
        setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &one, sizeof(one));   // a 6-byte frame must not wait

        int live = 0;
        for (const Conn& c : conns_) if (c.fd >= 0) ++live;
        if (live >= kMaxConnections)
        {
            // Evict the oldest connection that is not the phone, so a few idle
            // sockets cannot lock the real phone out.
            Conn* oldest = nullptr;
            for (Conn& c : conns_)
                if (c.fd >= 0 && c.fd != phoneFd_ && (!oldest || c.openedMs < oldest->openedMs)) oldest = &c;
            if (oldest) CloseConn(*oldest, "too many connections");
            else { close(fd); continue; }
        }
        Conn c;
        c.fd       = fd;
        c.openedMs = nowMs;
        c.lastRxMs = nowMs;
        char pbuf[32];
        std::snprintf(pbuf, sizeof(pbuf), "%s:%u", FormatIPv4(pa).c_str(), unsigned(ntohs(peer.sin_port)));
        c.peer = pbuf;
        // One line per connection, so a phone whose browser connects but never completes a
        // request (or tries https:// on this port) still leaves a trace in the log.
        Log("connection from %s", c.peer.c_str());
        conns_.push_back(std::move(c));
    }
}

void Server::ReadConn(Conn& c, int64_t nowMs)
{
    char buf[2048];
    for (int n = 0; n < 4; ++n)
    {
        const ssize_t got = recv(c.fd, buf, sizeof(buf), 0);
        if (got == 0)
        {
            if (!c.closing && c.ws && c.fd == phoneFd_)
                Log("phone %s disconnected: every button released", c.peer.c_str());
            if (!c.closing && !c.ws)
                Log("%s closed the connection before a complete request (%u bytes received%s)", c.peer.c_str(),
                    unsigned(c.in.size()), c.in.empty() ? ": a browser preconnect, or it gave up" : "");
            CloseConn(c, nullptr);
            return;
        }
        if (got < 0)
        {
            if (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR) return;
            CloseConn(c, "read error");
            return;
        }
        if (c.closing) continue;   // draining: discard
        c.in.append(buf, size_t(got));
        if (!c.ws)
        {
            HandleHttp(c, nowMs);
            if (c.fd < 0 || c.closing) return;
        }
        if (c.ws)
        {
            HandleFrames(c, nowMs);
            if (c.fd < 0 || c.closing) return;
        }
    }
}

bool Server::PinOk(const std::string& k, const Conn& c, int64_t nowMs, int* status)
{
    if (nowMs - pinWindowStartMs_ >= kWrongPinWindowMs)
    {
        pinWindowStartMs_ = nowMs;
        pinWrongInWindow_ = 0;
    }
    if (pinWrongInWindow_ >= kWrongPinPerWindow)
    {
        *status = 429;
        Log("PIN check refused for %s: too many wrong PINs, wait a second", c.peer.c_str());
        return false;
    }
    // Compare every character so the time taken does not depend on where
    // the first mismatch is.
    unsigned diff = unsigned(k.size() ^ cfg_.pin.size());
    for (size_t i = 0; i < cfg_.pin.size(); ++i)
        diff |= unsigned(uint8_t(i < k.size() ? k[i] : 0) ^ uint8_t(cfg_.pin[i]));
    if (diff == 0) return true;
    *status = 403;
    if (!k.empty())
    {
        ++pinWrongInWindow_;
        events_ |= kEvWrongPin;
        Log("wrong PIN from %s", c.peer.c_str());
    }
    return false;
}

void Server::Respond(Conn& c, int status, const char* statusText, const char* contentType, const std::string& body)
{
    char head[400];
    std::snprintf(head, sizeof(head),
                  "HTTP/1.1 %d %s\r\nContent-Type: %s\r\nContent-Length: %u\r\n"
                  "Cache-Control: no-store\r\nReferrer-Policy: no-referrer\r\n"
                  "X-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n",
                  status, statusText, contentType, unsigned(body.size()));
    c.out += head;
    c.out += body;
    c.closing = true;
    c.in.clear();
}

void Server::HandleHttp(Conn& c, int64_t nowMs)
{
    const size_t end = c.in.find("\r\n\r\n");
    if (end == std::string::npos)
    {
        if (c.in.size() > kMaxRequestBytes)
            Respond(c, 431, "Request Header Fields Too Large", "text/plain", "request too large\n");
        return;
    }
    if (end + 4 > kMaxRequestBytes)
    {
        Respond(c, 431, "Request Header Fields Too Large", "text/plain", "request too large\n");
        return;
    }
    const std::string head = c.in.substr(0, end);
    std::string rest = c.in.substr(end + 4);

    size_t eol = head.find("\r\n");
    const std::string reqLine = head.substr(0, eol);
    const size_t sp1 = reqLine.find(' ');
    const size_t sp2 = sp1 == std::string::npos ? std::string::npos : reqLine.find(' ', sp1 + 1);
    if (sp2 == std::string::npos || reqLine.compare(sp2 + 1, 5, "HTTP/") != 0)
    {
        Respond(c, 400, "Bad Request", "text/plain", "bad request\n");
        return;
    }
    const std::string method = reqLine.substr(0, sp1);
    const std::string target = reqLine.substr(sp1 + 1, sp2 - sp1 - 1);
    if (method != "GET")
    {
        Respond(c, 405, "Method Not Allowed", "text/plain", "GET only\n");
        return;
    }
    const size_t q = target.find('?');
    const std::string path  = target.substr(0, q);
    const std::string query = q == std::string::npos ? std::string() : target.substr(q + 1);
    const std::string k     = QueryParam(query, "k");

    std::string upgrade, connection, wsKey, wsVersion;
    while (eol != std::string::npos)
    {
        const size_t start = eol + 2;
        eol = head.find("\r\n", start);
        const std::string line = head.substr(start, eol == std::string::npos ? std::string::npos : eol - start);
        const size_t colon = line.find(':');
        if (colon == std::string::npos) continue;
        const std::string name  = Lower(Trim(line.substr(0, colon)));
        const std::string value = Trim(line.substr(colon + 1));
        if (name == "upgrade")                    upgrade    = value;
        else if (name == "connection")            connection = value;
        else if (name == "sec-websocket-key")     wsKey      = value;
        else if (name == "sec-websocket-version") wsVersion  = value;
    }

    int status = 403;
    if (path == "/")
    {
        if (k.empty())
        {
            Respond(c, 200, "OK", "text/html; charset=utf-8", std::string(kPinFormHead) + kPinFormTail);
        }
        else if (PinOk(k, c, nowMs, &status))
        {
            Log("page served to %s", c.peer.c_str());
            Respond(c, 200, "OK", "text/html; charset=utf-8", cfg_.pageHtml);
        }
        else
        {
            const char* msg = status == 429 ? "<p class=\"bad\">Too many wrong codes. Wait a second, then try again.</p>"
                                            : "<p class=\"bad\">Wrong code. Scan the TV again.</p>";
            Respond(c, status, status == 429 ? "Too Many Requests" : "Forbidden", "text/html; charset=utf-8",
                    std::string(kPinFormHead) + msg + kPinFormTail);
        }
        return;
    }
    if (path == "/layout.json")
    {
        if (PinOk(k, c, nowMs, &status))
            Respond(c, 200, "OK", "application/json", cfg_.layoutJson);
        else
            Respond(c, status, status == 429 ? "Too Many Requests" : "Forbidden", "text/plain", "wrong PIN\n");
        return;
    }
    if (path == "/ws")
    {
        if (Lower(upgrade) != "websocket" || !HeaderHasToken(connection, "upgrade") || wsVersion != "13"
            || wsKey.size() != 24)
        {
            Respond(c, 400, "Bad Request", "text/plain", "WebSocket upgrade expected\n");
            return;
        }
        if (!PinOk(k, c, nowMs, &status))
        {
            Respond(c, status, status == 429 ? "Too Many Requests" : "Forbidden", "text/plain", "wrong PIN\n");
            return;
        }
        // Newest phone wins: the old one is told why and released.
        for (Conn& old : conns_)
        {
            if (old.fd >= 0 && old.fd == phoneFd_)
            {
                Log("phone %s replaced by %s", old.peer.c_str(), c.peer.c_str());
                SendClose(old, 4001, "replaced");
                old.closing  = true;
                events_ |= kEvPhoneReplaced;
            }
        }
        c.out += "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                 "Sec-WebSocket-Accept: " + WebSocketAccept(wsKey) + "\r\n\r\n";
        c.ws       = true;
        c.lastRxMs = nowMs;
        c.in       = rest;
        phoneFd_   = c.fd;
        SetPhoneMask(0);
        events_ |= kEvPhoneConnected;
        Log("phone connected from %s", c.peer.c_str());
        return;
    }
    if (path == "/favicon.ico")
    {
        Respond(c, 404, "Not Found", "text/plain", "");
        return;
    }
    Respond(c, 404, "Not Found", "text/plain", "not found\n");
}

void Server::HandleFrames(Conn& c, int64_t nowMs)
{
    for (;;)
    {
        if (c.fd < 0 || c.closing) return;
        if (c.in.size() < 2) return;
        const uint8_t b0 = uint8_t(c.in[0]);
        const uint8_t b1 = uint8_t(c.in[1]);
        const bool    fin    = (b0 & 0x80) != 0;
        const uint8_t rsv    = b0 & 0x70;
        const uint8_t opcode = b0 & 0x0F;
        const bool    masked = (b1 & 0x80) != 0;
        size_t len = b1 & 0x7F;
        size_t header = 2;
        if (rsv)               { FailWs(c, 1002, "reserved bits set"); return; }
        if (!masked)           { FailWs(c, 1002, "unmasked client frame"); return; }
        if(len==127){FailWs(c,1009,"frame too big");return;}
        if(len==126){if(c.in.size()<4)return;len=size_t(uint8_t(c.in[2]))*256+uint8_t(c.in[3]);header=4;if(len<126){FailWs(c,1002,"noncanonical frame length");return;}}
        if (len > 4096 || (opcode>=8&&len>125)) { FailWs(c, 1009, "frame too big"); return; }
        if (c.in.size() < header + 4 + len) return;
        std::string payload(len, '\0');
        for (size_t i = 0; i < len; ++i)
            payload[i] = char(uint8_t(c.in[header+4+i]) ^ uint8_t(c.in[header+(i&3)]));
        c.in.erase(0, header+4+len);

        if (!fin || opcode == 0) { FailWs(c, 1002, "fragmented frames are not accepted"); return; }
        switch (opcode)
        {
            case 1:
                for (char ch : payload)
                    if (uint8_t(ch) < 0x20 || uint8_t(ch) > 0x7E) { FailWs(c, 1007, "non-printable text"); return; }
                HandleText(c, payload, nowMs);
                break;
            case 2:
                FailWs(c, 1003, "binary frames are not accepted");
                return;
            case 8:
                if (c.fd == phoneFd_)
                {
                    Log("phone %s closed the connection: every button released", c.peer.c_str());
                    phoneFd_ = -1;
                    SetPhoneMask(0);
                    events_ |= kEvPhoneLost;
                }
                SendClose(c, 1000, "");
                c.closing = true;
                return;
            case 9:
                c.lastRxMs = nowMs;
                SendFrame(c, 0xA, payload);
                break;
            case 10:
                c.lastRxMs = nowMs;
                break;
            default:
                FailWs(c, 1002, "unknown opcode");
                return;
        }
    }
}

void Server::HandleText(Conn& c, const std::string& text, int64_t nowMs)
{
    if (text.size() >= 2 && text[0] == 'b' && text[1] == ':')
    {
        uint16_t m = 0;
        if (!ParseMaskFrame(text, &m)) { FailWs(c, 1007, "malformed mask frame"); return; }
        c.lastRxMs = nowMs;
        if (c.fd == phoneFd_) SetPhoneMask(m);
        return;
    }
    if (text.size() >= 2 && text[0] == 't' && text[1] == ':')
    {
        if (text.size() < 3 || text.size() > 17 || text.find_first_not_of("0123456789", 2) != std::string::npos)
        {
            FailWs(c, 1007, "malformed timestamp frame");
            return;
        }
        c.lastRxMs = nowMs;
        SendFrame(c, 1, text);
        return;
    }
    if(text.size()>=2&&(text[0]=='p'||text[0]=='r')&&text[1]==':'){
        c.lastRxMs=nowMs;
        if(c.fd==phoneFd_&&command_)command_(text);
        return;
    }
    if (text.size() >= 2 && text[0] >= 'a' && text[0] <= 'z' && text[1] == ':')
    {
        c.lastRxMs = nowMs;   // a frame type this build does not know: ignored, still a heartbeat
        return;
    }
    FailWs(c, 1007, "unknown frame");
}

void Server::FailWs(Conn& c, uint16_t code, const char* why)
{
    Log("protocol error from %s: %s (close %u)%s", c.peer.c_str(), why, unsigned(code),
        c.fd == phoneFd_ ? ": every button released" : "");
    if (c.fd == phoneFd_)
    {
        phoneFd_ = -1;
        SetPhoneMask(0);
        events_ |= kEvPhoneLost;
    }
    SendClose(c, code, why);
    c.closing = true;
    c.in.clear();
}

void Server::SendFrame(Conn& c, uint8_t opcode, const std::string& payload)
{
    if(payload.size()>65535||(opcode>=8&&payload.size()>125))return;
    c.out += char(0x80 | opcode);
    if(payload.size()<126)c.out+=char(payload.size());
    else {c.out+=char(126);c.out+=char(payload.size()>>8);c.out+=char(payload.size()&255);}
    c.out += payload;
}

void Server::SendClose(Conn& c, uint16_t code, const char* reason)
{
    std::string p;
    p += char(code >> 8);
    p += char(code & 0xFF);
    p += std::string(reason).substr(0, 120);
    SendFrame(c, 8, p);
}

void Server::FlushConn(Conn& c)
{
    while (!c.out.empty())
    {
        const ssize_t n = send(c.fd, c.out.data(), c.out.size(), MSG_NOSIGNAL);
        if (n < 0)
        {
            if (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR) break;
            CloseConn(c, "write error");
            return;
        }
        c.out.erase(0, size_t(n));
    }
    if (c.out.size() > 256 * 1024) { CloseConn(c, "peer is not reading"); return; }
    // Done writing a final response: half-close so the peer sees the whole
    // body before the socket goes (closing with unread input would send RST).
    if (c.closing && c.out.empty() && !c.shut)
    {
        shutdown(c.fd, SHUT_WR);
        c.shut = true;
    }
}

void Server::CloseConn(Conn& c, const char* why)
{
    if (c.fd < 0) return;
    if (c.fd == phoneFd_)
    {
        phoneFd_ = -1;
        SetPhoneMask(0);
        events_ |= kEvPhoneLost;
    }
    if (why) Log("closed %s: %s", c.peer.c_str(), why);
    close(c.fd);
    c.fd = -1;
}

}  // namespace phonepad

bool phonepad::Server::SendText(const std::string& text){
 if(text.size()>65535||phoneFd_<0)return false;
 for(auto& c:conns_)if(c.fd==phoneFd_){SendFrame(c,1,text);return true;}
 return false;
}
