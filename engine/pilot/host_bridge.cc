// host_bridge.cc — BridgeHost: external PilotHost over the TCP debug bridge.

#include "host_bridge.hp"

#include <arpa/inet.h>
#include <cerrno>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <netdb.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <thread>
#include <unistd.h>

namespace pilot {

// ─────────────────────────────────────────────────────────────────────────────
// Minimal JSON helpers (outbound builder + inbound key extractors).

static std::string jStr(const char* key, const std::string& val)
{
    std::string out;
    out += '"'; out += key; out += "\":\"";
    for (unsigned char c : val) {
        if (c == '"')       { out += "\\\""; }
        else if (c == '\\') { out += "\\\\"; }
        else if (c == '\n') { out += "\\n";  }
        else                { out += (char)c; }
    }
    out += '"';
    return out;
}

static std::string jNum(const char* key, double val)
{
    char buf[64];
    // Use integer form when exact, float form otherwise.
    long long iv = (long long)val;
    if ((double)iv == val)
        std::snprintf(buf, sizeof(buf), "\"%s\":%lld", key, iv);
    else
        std::snprintf(buf, sizeof(buf), "\"%s\":%g", key, val);
    return buf;
}

// Extract a string value from a flat JSON line.
// Searches for "key": then reads the quoted value.
static std::string parseStr(const std::string& line, const char* key)
{
    // Match "key": so we only hit keys, not values that happen to contain key.
    std::string needle = std::string("\"") + key + "\":";
    auto pos = line.find(needle);
    if (pos == std::string::npos) return {};
    pos += needle.size();
    // Skip spaces, then expect opening quote.
    while (pos < line.size() && (line[pos] == ' ' || line[pos] == '\t')) ++pos;
    if (pos >= line.size() || line[pos] != '"') return {};
    ++pos;  // skip opening quote
    std::string out;
    while (pos < line.size() && line[pos] != '"') {
        if (line[pos] == '\\' && pos + 1 < line.size()) {
            char esc = line[++pos];
            switch (esc) {
                case 'n':  out += '\n'; break;
                case 't':  out += '\t'; break;
                case '"':  out += '"';  break;
                case '\\': out += '\\'; break;
                default:   out += esc;  break;
            }
            ++pos;
        } else {
            out += line[pos++];
        }
    }
    return out;
}

// Extract a numeric value from a flat JSON line.
// Searches for "key": to avoid matching key names that appear inside values.
static double parseNum(const std::string& line, const char* key)
{
    std::string needle = std::string("\"") + key + "\":";
    auto pos = line.find(needle);
    if (pos == std::string::npos) return 0.0;
    pos += needle.size();
    while (pos < line.size() && (line[pos] == ' ' || line[pos] == '\t')) ++pos;
    try { return std::stod(line.c_str() + pos); } catch (...) { return 0.0; }
}

// ─────────────────────────────────────────────────────────────────────────────
// Lifecycle

BridgeHost::~BridgeHost()
{
    teardown();
    _running = false;
    if (_fd >= 0) { ::close(_fd); _fd = -1; }
    if (_reader.joinable()) _reader.join();
}

bool BridgeHost::connect(const char* host, int port, double timeoutSecs)
{
    auto deadline = std::chrono::steady_clock::now() +
                    std::chrono::duration<double>(timeoutSecs);
    while (std::chrono::steady_clock::now() < deadline) {
        int fd = ::socket(AF_INET, SOCK_STREAM, 0);
        if (fd < 0) { std::this_thread::sleep_for(std::chrono::milliseconds(200)); continue; }

        struct sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_port   = htons((uint16_t)port);
        // Try numeric first, then hostname resolution.
        if (::inet_pton(AF_INET, host, &addr.sin_addr) <= 0) {
            struct hostent* he = ::gethostbyname(host);
            if (!he) { ::close(fd); std::this_thread::sleep_for(std::chrono::milliseconds(200)); continue; }
            std::memcpy(&addr.sin_addr, he->h_addr, he->h_length);
        }
        if (::connect(fd, (struct sockaddr*)&addr, sizeof(addr)) == 0) {
            _fd = fd;
            _running = true;
            _reader = std::thread(&BridgeHost::readerThread, this);
            return true;
        }
        ::close(fd);
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }
    return false;
}

// ─────────────────────────────────────────────────────────────────────────────
// Reader thread

void BridgeHost::readerThread()
{
    char buf[4096];
    while (_running) {
        ssize_t n = ::recv(_fd, buf, sizeof(buf), 0);
        if (n <= 0) { _running = false; return; }
        std::string chunk(buf, (size_t)n);
        _readBuf += chunk;
        for (;;) {
            auto nl = _readBuf.find('\n');
            if (nl == std::string::npos) break;
            std::string line = _readBuf.substr(0, nl);
            _readBuf = _readBuf.substr(nl + 1);
            if (!line.empty()) dispatchLine(line);
        }
    }
}

void BridgeHost::dispatchLine(const std::string& line)
{
    std::lock_guard<std::mutex> lk(_lock);
    _inbox.push_back(line);
    std::string op = parseStr(line, "op");
    if (op == "mailbox") {
        int    idx = (int)parseNum(line, "idx");
        int    mbx = (int)parseNum(line, "mailbox");
        double val =       parseNum(line, "value");
        _mbValues[mbKey(idx, mbx)] = val;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Send + waitFor

void BridgeHost::send(const std::string& json)
{
    std::string line = json + "\n";
    ::send(_fd, line.c_str(), line.size(), MSG_NOSIGNAL);
}

bool BridgeHost::waitFor(const char* opName, double timeoutSecs)
{
    size_t seen;
    {
        std::lock_guard<std::mutex> lk(_lock);
        seen = _inbox.size();
    }
    auto deadline = std::chrono::steady_clock::now() +
                    std::chrono::duration<double>(timeoutSecs);
    while (std::chrono::steady_clock::now() < deadline) {
        {
            std::lock_guard<std::mutex> lk(_lock);
            while (seen < _inbox.size()) {
                if (parseStr(_inbox[seen], "op") == opName) return true;
                ++seen;
            }
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
    }
    return false;
}

// ─────────────────────────────────────────────────────────────────────────────
// PilotHost methods

void BridgeHost::Type(const std::string& text, bool newline)
{
    std::fputs(text.c_str(), stdout);
    if (newline) std::fputc('\n', stdout);
    std::fflush(stdout);
}

double BridgeHost::ReadMailbox(int actor, int mbx)
{
    int idx = route(actor, mbx);
    std::lock_guard<std::mutex> lk(_lock);
    auto it = _mbValues.find(mbKey(idx, mbx));
    return it != _mbValues.end() ? it->second : 0.0;
}

void BridgeHost::SetMailbox(int actor, int mbx, double val)
{
    int idx = route(actor, mbx);
    char buf[256];
    std::snprintf(buf, sizeof(buf),
        "{\"op\":\"set_mailbox\",%s,%s,%s}",
        jNum("idx", idx).c_str(),
        jNum("mailbox", mbx).c_str(),
        jNum("value", val).c_str());
    send(buf);
}

void BridgeHost::Watch(int actor, int mbx, bool off)
{
    int idx = route(actor, mbx);
    char buf[128];
    std::snprintf(buf, sizeof(buf),
        "{\"op\":\"%s\",%s,%s}",
        off ? "unwatch" : "watch",
        jNum("idx", idx).c_str(),
        jNum("mailbox", mbx).c_str());
    send(buf);
    if (off)
        _watched.erase({idx, mbx});
    else
        _watched.insert({idx, mbx});
}

double BridgeHost::ClockSeconds()
{
    // TIME is a global mailbox — auto-watch it at idx=1 if not yet done.
    if (!_timeWatched) {
        Watch(1, TIME_MBX, false);
        _timeWatched = true;
    }
    std::lock_guard<std::mutex> lk(_lock);
    auto it = _mbValues.find(mbKey(1, TIME_MBX));
    return it != _mbValues.end() ? it->second : 0.0;
}

bool BridgeHost::rel(RelOp o, double a, double b)
{
    switch (o) {
        case RelOp::Eq: return a == b;
        case RelOp::Ne: return a != b;
        case RelOp::Lt: return a <  b;
        case RelOp::Le: return a <= b;
        case RelOp::Gt: return a >  b;
        default:        return a >= b;
    }
}

PilotHost::AwaitState BridgeHost::CheckAwait(const AwaitReq& req, double& out)
{
    // BridgeHost BLOCKS until satisfied or timed out (no Pending).
    double limit = req.timeoutSecs > 0 ? req.timeoutSecs : 5.0;
    auto deadline = std::chrono::steady_clock::now() +
                    std::chrono::duration<double>(limit);

    if (req.kind == AwaitKind::ClockSeconds) {
        // Ensure TIME is watched.
        if (!_timeWatched) {
            Watch(1, TIME_MBX, false);
            _timeWatched = true;
        }
        while (std::chrono::steady_clock::now() < deadline) {
            double now = ReadMailbox(1, TIME_MBX);
            if (now >= req.value) { out = now; return AwaitState::Satisfied; }
            std::this_thread::sleep_for(std::chrono::milliseconds(20));
        }
        out = ReadMailbox(1, TIME_MBX);
        return AwaitState::TimedOut;
    }

    // Mailbox kind: ensure the mailbox is watched.
    int idx = route(req.actorIdx, req.mailbox);
    if (_watched.find({idx, req.mailbox}) == _watched.end()) {
        Watch(req.actorIdx, req.mailbox, false);
    }

    while (std::chrono::steady_clock::now() < deadline) {
        double cur = ReadMailbox(req.actorIdx, req.mailbox);
        if (rel(req.op, cur, req.value)) { out = cur; return AwaitState::Satisfied; }
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
    }
    out = ReadMailbox(req.actorIdx, req.mailbox);
    return AwaitState::TimedOut;
}

void BridgeHost::SetTransform(int actor, double x, double y, double z)
{
    char buf[256];
    std::snprintf(buf, sizeof(buf),
        "{\"op\":\"scene:set_transform\",%s,\"pos\":[%g,%g,%g]}",
        jNum("idx", actor).c_str(), x, y, z);
    send(buf);
}

void BridgeHost::SetProp(int actor, const std::string& key, double val)
{
    char buf[512];
    std::snprintf(buf, sizeof(buf),
        "{\"op\":\"scene:set_prop\",%s,%s,%s}",
        jNum("idx", actor).c_str(),
        jStr("key", key).c_str(),
        jNum("value", val).c_str());
    send(buf);
}

void BridgeHost::InjectInput(const std::string& slot, int bits, int held)
{
    _injected.insert(slot);
    char buf[256];
    std::snprintf(buf, sizeof(buf),
        "{\"op\":\"inject_input\",%s,%s,%s}",
        jStr("slot", slot).c_str(),
        jNum("value", bits).c_str(),
        jNum("duration_frames", held).c_str());
    send(buf);
}

void BridgeHost::Pause()
{
    send("{\"op\":\"pause\"}");
    waitFor("paused", 5.0);
}

void BridgeHost::Resume()
{
    send("{\"op\":\"resume\"}");
}

void BridgeHost::Step(int frames)
{
    char buf[64];
    std::snprintf(buf, sizeof(buf), "{\"op\":\"step\",%s}", jNum("frames", frames).c_str());
    send(buf);
    // Give the game thread time to start processing; actual completion is
    // confirmed by subsequent WM/WB awaits.
    std::this_thread::sleep_for(std::chrono::milliseconds(30 * std::min(frames, 10)));
}

bool BridgeHost::Screenshot(const std::string& name)
{
    std::string path = _screenshotsDir.empty() ? name : _screenshotsDir + name;
    char buf[512];
    std::snprintf(buf, sizeof(buf), "{\"op\":\"screenshot\",%s}", jStr("filename", path).c_str());
    send(buf);
    bool ok = waitFor("screenshot_done", 10.0);
    if (ok) _screenshots.push_back(name);
    return ok;
}

// ─────────────────────────────────────────────────────────────────────────────
// Teardown

void BridgeHost::teardown()
{
    if (_fd < 0) return;

    // Clear sticky input injections.
    for (const auto& slot : _injected) {
        char buf[256];
        std::snprintf(buf, sizeof(buf),
            "{\"op\":\"inject_input\",%s,\"value\":0,\"duration_frames\":1}",
            jStr("slot", slot).c_str());
        send(buf);
    }
    _injected.clear();

    // Unwatch all watched mailboxes.
    for (const auto& p : _watched) {
        char buf[128];
        std::snprintf(buf, sizeof(buf),
            "{\"op\":\"unwatch\",%s,%s}",
            jNum("idx", p.first).c_str(),
            jNum("mailbox", p.second).c_str());
        send(buf);
    }
    _watched.clear();

    if (_timeWatched) {
        char buf[128];
        std::snprintf(buf, sizeof(buf),
            "{\"op\":\"unwatch\",%s,%s}",
            jNum("idx", 1).c_str(),
            jNum("mailbox", TIME_MBX).c_str());
        send(buf);
        _timeWatched = false;
    }
}

} // namespace pilot
