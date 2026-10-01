//=============================================================================
// hal/phonepad/host/phonepad_host.cc: the phone-controller server on Linux
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// A test host for tests/test_phone_controller*.py: runs phonepad::Server the
// way the Android glue does (Poll every few ms), and reports on stdout:
//
//   LISTEN <port>              after every successful start
//   MASK 0x<hex>               every time the phone's mask changes
//   EVENT connected|lost|replaced|wrongpin
//   LOG phonepad: ...          the server's own log lines
//
// stdin takes one command per line:
//   pause | resume             Stop() / Start() as APP_CMD_PAUSE / RESUME do
//   state                      prints "STATE mask=0x.. phone=0|1 running=0|1"
//   pin                        prints "PIN <six fresh digits>"
//   private <a.b.c.d>          prints "PRIVATE 0|1"
//   ov-endpoint <url> <host:port> <pin>   the TV overlay (phonepad_overlay.h), on a
//   ov-event connected|lost <ms>          fake clock so the tests control time:
//   ov-back <ms>               prints "BACK 0|1" (consumed or not)
//   ov-state <ms>              prints "OVSTATE panel=0|1 toast=<text>"
//   ov-rects <w> <h> <ms>      prints "RECTS <n> changed=0|1" then n lines
//                              "R x0 y0 x1 y1 rrggbbaa"
//   qr <text>                  prints "QR <size>" then size rows of 0/1
//   quit
//
//   phonepad_host --pin 123456 --page controller.html --layout layout.json
//                 [--bind 127.0.0.1] [--port 0] [--timeout-ms 1000]
//=============================================================================

#include "../phonepad.h"
#include "../phonepad_overlay.h"

#include <arpa/inet.h>
#include <poll.h>
#include <time.h>
#include <unistd.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

namespace
{

int64_t NowMs()
{
    timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return int64_t(ts.tv_sec) * 1000 + ts.tv_nsec / 1000000;
}

void LogLine(const char* line)
{
    std::printf("LOG %s\n", line);
    std::fflush(stdout);
}

bool ReadFile(const char* path, std::string* out)
{
    std::ifstream f(path, std::ios::binary);
    if (!f) return false;
    std::ostringstream ss;
    ss << f.rdbuf();
    *out = ss.str();
    return true;
}

int Usage(int rc)
{
    std::fprintf(rc ? stderr : stdout,
                 "usage: phonepad_host --pin NNNNNN --page FILE --layout FILE "
                 "[--bind A.B.C.D] [--port N] [--timeout-ms N]\n");
    return rc;
}

}  // namespace

int main(int argc, char** argv)
{
    phonepad::Config cfg;
    cfg.bindAddr = 0x7f000001u;
    cfg.port     = 0;
    for (int i = 1; i < argc; ++i)
    {
        const std::string a = argv[i];
        const char* v = i + 1 < argc ? argv[i + 1] : nullptr;
        if (a == "-h" || a == "--help") return Usage(0);
        if (!v) return Usage(2);
        if (a == "--pin")             cfg.pin = v;
        else if (a == "--page")       { if (!ReadFile(v, &cfg.pageHtml))   { std::fprintf(stderr, "cannot read %s\n", v); return 2; } }
        else if (a == "--layout")     { if (!ReadFile(v, &cfg.layoutJson)) { std::fprintf(stderr, "cannot read %s\n", v); return 2; } }
        else if (a == "--bind")       { in_addr ia; if (inet_pton(AF_INET, v, &ia) != 1) return Usage(2); cfg.bindAddr = ntohl(ia.s_addr); }
        else if (a == "--port")       cfg.port = uint16_t(std::atoi(v));
        else if (a == "--timeout-ms") cfg.timeoutMs = std::atoi(v);
        else return Usage(2);
        ++i;
    }

    phonepad::Server server;
    server.SetLog(LogLine);
    if (!server.Start(cfg)) { std::printf("START-FAILED\n"); return 1; }
    // Resume rebinds the same port, as the app does with its fixed 8765, so an open page can reconnect.
    cfg.port      = server.Port();
    cfg.portTries = 1;
    std::printf("LISTEN %u\n", unsigned(server.Port()));
    std::fflush(stdout);

    uint16_t last = 0;
    std::string line;
    phonepad::Overlay overlay;
    std::vector<PhonepadRect> rects;
    for (;;)
    {
        pollfd p = { STDIN_FILENO, POLLIN, 0 };
        if (poll(&p, 1, 2) > 0)
        {
            char buf[256];
            const ssize_t n = read(STDIN_FILENO, buf, sizeof(buf));
            if (n <= 0) break;   // stdin closed: the test is done
            line.append(buf, size_t(n));
        }
        size_t nl;
        while ((nl = line.find('\n')) != std::string::npos)
        {
            const std::string cmd = line.substr(0, nl);
            line.erase(0, nl + 1);
            if (cmd == "quit") return 0;
            if (cmd == "pause")  { server.Stop(); std::printf("PAUSED\n"); }
            else if (cmd == "resume")
            {
                if (server.Start(cfg)) std::printf("LISTEN %u\n", unsigned(server.Port()));
                else                   std::printf("START-FAILED\n");
            }
            else if (cmd == "state")
                std::printf("STATE mask=0x%04x phone=%d running=%d\n", unsigned(server.Mask()),
                            server.PhoneConnected() ? 1 : 0, server.Running() ? 1 : 0);
            else if (cmd == "pin")
                std::printf("PIN %s\n", phonepad::MakePin().c_str());
            else if (cmd.compare(0, 8, "private ") == 0)
            {
                in_addr ia;
                const bool ok = inet_pton(AF_INET, cmd.c_str() + 8, &ia) == 1;
                std::printf("PRIVATE %d\n", ok && phonepad::IsPrivateIPv4(ntohl(ia.s_addr)) ? 1 : 0);
            }
            else if (cmd.compare(0, 12, "ov-endpoint ") == 0)
            {
                char url[128], hp[64], pin[16];
                if (std::sscanf(cmd.c_str() + 12, "%127s %63s %15s", url, hp, pin) == 3)
                    overlay.SetEndpoint(url, hp, pin);
            }
            else if (cmd.compare(0, 9, "ov-event ") == 0)
            {
                char what[32];
                long long t = 0;
                if (std::sscanf(cmd.c_str() + 9, "%31s %lld", what, &t) == 2)
                    overlay.OnEvents(std::strcmp(what, "connected") == 0 ? phonepad::kEvPhoneConnected
                                     : std::strcmp(what, "lost") == 0 ? phonepad::kEvPhoneLost : 0u, t);
            }
            else if (cmd.compare(0, 8, "ov-back ") == 0)
                std::printf("BACK %d\n", overlay.OnBack(std::atoll(cmd.c_str() + 8)) ? 1 : 0);
            else if (cmd.compare(0, 9, "ov-state ") == 0)
            {
                const long long t = std::atoll(cmd.c_str() + 9);
                std::printf("OVSTATE panel=%d toast=%s\n", overlay.PanelVisible(t) ? 1 : 0, overlay.Toast(t));
            }
            else if (cmd.compare(0, 9, "ov-rects ") == 0)
            {
                int w = 0, h = 0;
                long long t = 0;
                if (std::sscanf(cmd.c_str() + 9, "%d %d %lld", &w, &h, &t) == 3)
                {
                    const bool changed = overlay.Build(w, h, t, &rects);
                    std::printf("RECTS %u changed=%d\n", unsigned(rects.size()), changed ? 1 : 0);
                    for (const PhonepadRect& r : rects)
                        std::printf("R %.2f %.2f %.2f %.2f %08x\n", r.x0, r.y0, r.x1, r.y1, unsigned(r.rgba));
                }
            }
            else if (cmd.compare(0, 3, "qr ") == 0)
            {
                std::vector<uint8_t> m;
                int n = 0;
                if (!phonepad::Overlay::EncodeQr(cmd.substr(3), &m, &n)) n = 0;
                std::printf("QR %d\n", n);
                for (int r = 0; r < n; ++r)
                {
                    for (int c = 0; c < n; ++c) std::putchar(m[size_t(r) * size_t(n) + size_t(c)] ? '1' : '0');
                    std::putchar('\n');
                }
            }
            else
                std::printf("UNKNOWN %s\n", cmd.c_str());
            std::fflush(stdout);
        }

        const uint16_t m = server.Poll(NowMs());
        const uint32_t ev = server.TakeEvents();
        if (ev & phonepad::kEvWrongPin)       std::printf("EVENT wrongpin\n");
        if (ev & phonepad::kEvPhoneReplaced)  std::printf("EVENT replaced\n");
        if (ev & phonepad::kEvPhoneLost)      std::printf("EVENT lost\n");
        if (ev & phonepad::kEvPhoneConnected) std::printf("EVENT connected\n");
        if (m != last) { std::printf("MASK 0x%04x\n", unsigned(m)); last = m; }
        std::fflush(stdout);
    }
    return 0;
}
