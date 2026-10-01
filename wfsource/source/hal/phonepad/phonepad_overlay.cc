//=============================================================================
// hal/phonepad/phonepad_overlay.cc: the TV side of the phone controller (portable)
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// See phonepad_overlay.h. Layout is designed on a 1920x1080 canvas (mockup 3
// at 3x) and scaled to the surface.
//=============================================================================

#include "phonepad_overlay.h"
#include "phonepad.h"

#include <cstdio>
#include <cstring>

#if defined(__GNUC__)
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-function"
#pragma GCC diagnostic ignored "-Wsign-compare"
#pragma GCC diagnostic ignored "-Wcast-align"
#endif
#include "../../../../engine/vendor/stb_easy_font.h"
#if defined(__GNUC__)
#pragma GCC diagnostic pop
#endif

namespace phonepad
{

namespace
{

// Mockup 3's palette.
constexpr uint32_t kDim      = 0x000000AAu;
constexpr uint32_t kPanel    = 0x111826EEu;
constexpr uint32_t kLine     = 0x3A4A63FFu;
constexpr uint32_t kTitle    = 0xE6EDF3FFu;
constexpr uint32_t kText     = 0xC9D4E3FFu;
constexpr uint32_t kCode     = 0x9FB3CCFFu;
constexpr uint32_t kCodeBg   = 0x05080DFFu;
constexpr uint32_t kOk       = 0x56D364FFu;
constexpr uint32_t kWarn     = 0xFFB454FFu;
constexpr uint32_t kFoot     = 0x8B98A9FFu;
constexpr uint32_t kToastBg  = 0x000000BBu;

// stb_easy_font writes floats through a char*, so the buffer must be float
// aligned (an unaligned VFP store faults on 32-bit ARM). 16 bytes per vertex,
// 4 vertices per quad, ~270 bytes per character: room for ~240 characters.
float gTextBuf[16384];

struct Painter
{
    std::vector<PhonepadRect>* out;
    float s;   // canvas units -> pixels

    void Rect(float x0, float y0, float x1, float y1, uint32_t rgba)
    {
        out->push_back({x0 * s, y0 * s, x1 * s, y1 * s, rgba});
    }
    void Frame(float x0, float y0, float x1, float y1, float t, uint32_t rgba)
    {
        Rect(x0, y0, x1, y0 + t, rgba);
        Rect(x0, y1 - t, x1, y1, rgba);
        Rect(x0, y0 + t, x0 + t, y1 - t, rgba);
        Rect(x1 - t, y0 + t, x1, y1 - t, rgba);
    }
    // Draws ASCII text at (x, y) (top of the caps), `scale` canvas units per
    // font pixel. Returns the x where the next text would start.
    float Text(float x, float y, float scale, uint32_t rgba, const char* text)
    {
        char clean[160];
        size_t n = 0;
        for (const char* p = text; *p && n + 1 < sizeof(clean); ++p)
            clean[n++] = (*p >= 32 && *p <= 126) ? *p : '?';   // the font covers 32..126 only
        clean[n] = '\0';
        stb_easy_font_spacing(-0.5f);   // the font's 1-pixel gap looks loose when scaled up
        const int quads = stb_easy_font_print(0.0f, 0.0f, clean, nullptr, gTextBuf, int(sizeof(gTextBuf)));
        for (int q = 0; q < quads; ++q)
        {
            const float* v = gTextBuf + q * 16;    // 4 vertices x (x, y, z, rgba)
            float minx = v[0], maxx = v[0], miny = v[1], maxy = v[1];
            for (int k = 1; k < 4; ++k)
            {
                const float vx = v[k * 4], vy = v[k * 4 + 1];
                if (vx < minx) minx = vx;
                if (vx > maxx) maxx = vx;
                if (vy < miny) miny = vy;
                if (vy > maxy) maxy = vy;
            }
            Rect(x + minx * scale, y + miny * scale, x + maxx * scale, y + maxy * scale, rgba);
        }
        return x + float(stb_easy_font_width(clean)) * scale;
    }
    static float Width(const char* text, float scale)
    {
        char clean[160];
        size_t n = 0;
        for (const char* p = text; *p && n + 1 < sizeof(clean); ++p)
            clean[n++] = (*p >= 32 && *p <= 126) ? *p : '?';
        clean[n] = '\0';
        stb_easy_font_spacing(-0.5f);
        return float(stb_easy_font_width(clean)) * scale;
    }
};

}  // namespace

void Overlay::SetEndpoint(const std::string& url, const std::string& hostPort, const std::string& pin)
{
    url_      = url;
    hostPort_ = hostPort;
    pin_      = pin;
    endpoint_ = true;
}

void Overlay::ClearEndpoint()
{
    endpoint_  = false;
    connected_ = false;
    toast_     = "";
}

void Overlay::OnEvents(uint32_t ev, int64_t nowMs)
{
    if (ev & kEvPhoneLost)
    {
        connected_  = false;
        lostAt_     = nowMs;
        toast_      = "Phone lost";
        toastRgba_  = kWarn;
        toastUntil_ = nowMs + kToastMs;
    }
    if (ev & kEvPhoneConnected)     // after Lost: a replacement ends connected
    {
        connected_  = true;
        lostAt_     = -1;
        hidden_     = false;        // a phone that drops later brings the panel back
        toast_      = "Phone connected";
        toastRgba_  = kOk;
        toastUntil_ = nowMs + kToastMs;
    }
}

bool Overlay::OnBack(int64_t nowMs)
{
    if (!PanelVisible(nowMs)) return false;
    hidden_ = true;
    return true;
}

bool Overlay::PanelVisible(int64_t nowMs) const
{
    return endpoint_ && !connected_ && !hidden_ && (lostAt_ < 0 || nowMs - lostAt_ >= kPanelAfterMs);
}

const char* Overlay::Toast(int64_t nowMs) const
{
    return (endpoint_ && nowMs < toastUntil_) ? toast_ : "";
}

bool Overlay::EncodeQr(const std::string& /*text*/, std::vector<uint8_t>* modules, int* size)
{
    modules->clear();
    *size = 0;
    return false;   // the QR code is step E3
}

bool Overlay::Build(int w, int h, int64_t nowMs, std::vector<PhonepadRect>* out)
{
    const bool  panel = PanelVisible(nowMs);
    const char* toast = Toast(nowMs);
    char key[256];
    std::snprintf(key, sizeof(key), "%dx%d p%d t%s %s", w, h, panel ? 1 : 0, toast, panel ? url_.c_str() : "");
    if (lastKey_ == key) return false;
    lastKey_ = key;
    out->clear();
    if (w <= 0 || h <= 0) return true;

    // 1920x1080 canvas, scaled uniformly; the canvas is centred if the aspect differs.
    const float sx = float(w) / 1920.0f, sy = float(h) / 1080.0f;
    Painter p{out, sx < sy ? sx : sy};

    if (panel)
    {
        p.Rect(0, 0, 1920, 1080, kDim);
        p.Rect(84, 90, 1836, 990, kPanel);
        p.Frame(84, 90, 1836, 990, 3, kLine);
        p.Text(132, 132, 6.0f, kTitle, "Use your phone as the controller");

        std::vector<uint8_t> qr;
        int n = 0;
        float tx = 132;
        if (EncodeQr(url_, &qr, &n) && n > 0)
        {
            // White square with a 4-module quiet zone; dark runs merged per row.
            const float side = 560, m = side / float(n + 8), x0 = 132, y0 = 250;
            p.Rect(x0, y0, x0 + side, y0 + side, 0xFFFFFFFFu);
            for (int r = 0; r < n; ++r)
                for (int c = 0; c < n;)
                {
                    if (!qr[size_t(r) * size_t(n) + size_t(c)]) { ++c; continue; }
                    int e = c;
                    while (e < n && qr[size_t(r) * size_t(n) + size_t(e)]) ++e;
                    p.Rect(x0 + (4 + c) * m, y0 + (4 + r) * m, x0 + (4 + e) * m, y0 + (5 + r) * m, 0x0D1117FFu);
                    c = e;
                }
            tx = 760;
        }

        const float ts = 4.0f;
        p.Text(tx, 270, ts, kText, "1. Join the same Wi-Fi as this TV");
        p.Text(tx, 350, ts, kText, tx > 132 ? "2. Scan the code, or open" : "2. On your phone, open");
        const float cw = Painter::Width(hostPort_.c_str(), 5.0f);
        p.Rect(tx + 40, 418, tx + 40 + cw + 36, 418 + 64, kCodeBg);
        p.Text(tx + 58, 430, 5.0f, kCode, hostPort_.c_str());
        char pin[8] = "";
        if (pin_.size() == 6) std::snprintf(pin, sizeof(pin), "%.3s %.3s", pin_.c_str(), pin_.c_str() + 3);
        float x = p.Text(tx, 530, ts, kText, "3. Enter PIN ");
        x = p.Text(x, 530, ts, kOk, pin);
        p.Text(x, 530, ts, kText, " if asked");
        p.Rect(tx, 640, tx + 18, 658, kWarn);
        p.Text(tx + 34, 634, ts, kWarn, "Waiting for a phone...");
        p.Text(132, 930, 3.0f, kFoot, "The remote still works. Press Back to hide this.");
    }

    if (*toast)
    {
        const float ts = 4.0f, tw = Painter::Width(toast, ts);
        const float x1 = 1880, x0 = x1 - tw - 56, y0 = 40, y1 = 40 + 76;
        p.Rect(x0, y0, x1, y1, kToastBg);
        p.Frame(x0, y0, x1, y1, 3, toastRgba_);
        p.Text(x0 + 28, y0 + 22, ts, toastRgba_, toast);
    }

    // Centre the canvas on surfaces that are not 16:9.
    const float ox = (float(w) - 1920.0f * p.s) * 0.5f, oy = (float(h) - 1080.0f * p.s) * 0.5f;
    if (ox != 0.0f || oy != 0.0f)
        for (PhonepadRect& r : *out) { r.x0 += ox; r.x1 += ox; r.y0 += oy; r.y1 += oy; }
    return true;
}

}  // namespace phonepad
