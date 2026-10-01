//=============================================================================
// hal/phonepad/phonepad.h: the phone as a gamepad, the server half (portable)
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// The TV app serves a one-page web controller over the local Wi-Fi; the phone
// opens it (QR code or typed URL), then streams a button mask over a
// WebSocket. Plan: docs/plans/2026-09-30-aquarium-chromecast.md, Phase E.
//
// Portable POSIX C++ with no engine dependency, so the same file builds into
// the Android app and into the Linux test host (host/phonepad_host.cc) that
// tests/test_phone_controller.py drives with a headless client.
//
// Single-threaded and non-blocking: the owner calls Poll() once per frame
// from the game thread (Android: WFAndroidPumpEvents). The engine samples
// input once per frame anyway, so a network thread would buy at most one
// frame of latency at the price of locks and a thread lifecycle tied to
// pause/resume.
//
// Protocol (all text, so a bug is readable in a log):
//   GET /               no k: a PIN form; right k: the controller page;
//                       wrong k: 403 and the form again
//   GET /layout.json?k= the per-app layout (this app's buttons and bits)
//   GET /ws?k=          WebSocket upgrade (RFC 6455)
//   phone -> TV  "b:<1-4 hex>"   the 16-bit EJ_BUTTONF_* mask, on every change
//                                and as a 250 ms heartbeat
//                "t:<1-15 digits>" a page timestamp, echoed back unchanged
//                "<a-z>:<printable>" any other type: ignored (forward
//                                compatible), still counts as a heartbeat
//   TV -> phone  "t:<same digits>"  the echo
//                close 4001 "replaced"  a newer phone took over
//                close 4002 "timeout"   no frame for timeoutMs
// Safety: every button is released when the phone's connection ends for any
// reason (timeout, close, protocol error, replaced, Stop). Malformed and
// oversized frames close the connection. The PIN is checked on the page, the
// layout and the WebSocket; wrong guesses are rate limited; peers outside the
// private IPv4 ranges are refused.
//=============================================================================

#ifndef HAL_PHONEPAD_PHONEPAD_H
#define HAL_PHONEPAD_PHONEPAD_H

#include <cstdint>
#include <string>
#include <vector>

namespace phonepad
{

constexpr uint16_t kDefaultPort      = 8765;   // the port in mockup 3's URL
constexpr int      kTimeoutMs        = 1000;   // release everything after 1 s of silence
constexpr int      kHttpTimeoutMs    = 5000;   // a request must arrive within 5 s of connect
constexpr size_t   kMaxRequestBytes  = 4096;   // request line + headers
constexpr size_t   kMaxFramePayload  = 64;     // largest legal frame is "t:" + 15 digits
constexpr int      kMaxConnections   = 8;      // pending HTTP + the one phone
constexpr int      kWrongPinPerWindow = 5;     // wrong PINs allowed per window ...
constexpr int      kWrongPinWindowMs = 1000;   // ... before every PIN check fails (429)

// Event bits returned by Server::TakeEvents().
enum : uint32_t
{
    kEvPhoneConnected = 1u << 0,   // a phone's WebSocket opened (including a replacement)
    kEvPhoneLost      = 1u << 1,   // the active phone's connection ended (timeout, close, error)
    kEvPhoneReplaced  = 1u << 2,   // a newer phone took over from an older one
    kEvWrongPin       = 1u << 3,
};

struct Config
{
    uint32_t    bindAddr  = 0;          // IPv4, host byte order; 0x7f000001 = loopback
    uint16_t    port      = kDefaultPort; // 0 = any free port (tests)
    int         portTries = 10;         // port, port+1, ... if busy
    std::string pin;                    // six digits
    std::string pageHtml;               // the controller page (assets/controller.html)
    std::string layoutJson;             // the per-app layout (assets/layout.json)
    int         timeoutMs = kTimeoutMs;
};

typedef void (*LogFn)(const char* line);

class Server
{
public:
    Server();
    ~Server();

    // Listen. False (and a log line) if no port could be bound.
    bool Start(const Config& cfg);
    // Close the listener and every connection; the mask drops to 0.
    void Stop();
    bool Running() const { return listenFd_ >= 0; }
    uint16_t Port() const { return port_; }

    // Accept, read, answer, time out. Never blocks. Returns the phone's
    // current button mask (0 when no phone is connected).
    uint16_t Poll(int64_t nowMs);

    uint16_t Mask() const { return mask_; }
    bool     PhoneConnected() const { return phoneFd_ >= 0; }
    // Event bits (kEv*) since the last call.
    uint32_t TakeEvents() { uint32_t e = events_; events_ = 0; return e; }

    void SetLog(LogFn fn) { log_ = fn; }

private:
    struct Conn
    {
        int         fd        = -1;
        bool        ws        = false;
        bool        closing   = false;  // flush out, half-close, then close
        bool        shut      = false;  // SHUT_WR done
        int64_t     closingMs = 0;      // when closing was first seen (1 s drain deadline)
        int64_t     openedMs  = 0;
        int64_t     lastRxMs  = 0;
        std::string peer;
        std::string in;
        std::string out;
    };

    void Accept(int64_t nowMs);
    void ReadConn(Conn& c, int64_t nowMs);
    void HandleHttp(Conn& c, int64_t nowMs);
    void HandleFrames(Conn& c, int64_t nowMs);
    void HandleText(Conn& c, const std::string& text, int64_t nowMs);
    void FlushConn(Conn& c);
    void CloseConn(Conn& c, const char* why);
    void FailWs(Conn& c, uint16_t code, const char* why);
    void SendFrame(Conn& c, uint8_t opcode, const std::string& payload);
    void SendClose(Conn& c, uint16_t code, const char* reason);
    void Respond(Conn& c, int status, const char* statusText, const char* contentType, const std::string& body);
    bool PinOk(const std::string& k, const Conn& c, int64_t nowMs, int* status);
    void SetPhoneMask(uint16_t m);
    void Log(const char* fmt, ...);

    Config            cfg_;
    int               listenFd_ = -1;
    uint16_t          port_     = 0;
    int               phoneFd_  = -1;    // the active phone's fd, or -1
    uint16_t          mask_     = 0;
    uint32_t          events_   = 0;
    int64_t           pinWindowStartMs_ = 0;
    int               pinWrongInWindow_ = 0;
    std::vector<Conn> conns_;
    LogFn             log_ = nullptr;
};

// ---- helpers (public so the tests and the platform glue can use them) -------

// Six random decimal digits from /dev/urandom (uniform, rejection sampled).
std::string MakePin();

// The IPv4 address this device would use to reach the network (a UDP
// "connect" that sends nothing), host byte order. False if there is no route.
bool DiscoverLanAddress(uint32_t* addr);

// 10/8, 172.16/12, 192.168/16, 169.254/16 and 127/8 (host byte order).
bool IsPrivateIPv4(uint32_t addr);

std::string FormatIPv4(uint32_t addr);

// "http://192.168.4.38:8765/?k=482913"
std::string ControllerUrl(uint32_t addr, uint16_t port, const std::string& pin);

// RFC 6455 Sec-WebSocket-Accept for a client key.
std::string WebSocketAccept(const std::string& key);

// Parse a phone frame "b:<1-4 hex>"; false if malformed.
bool ParseMaskFrame(const std::string& text, uint16_t* mask);

}  // namespace phonepad

#endif  // HAL_PHONEPAD_PHONEPAD_H
