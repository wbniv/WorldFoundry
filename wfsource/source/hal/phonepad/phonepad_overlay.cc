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
#include "../remote_back_arrow.h"
#include "phonepad_logo.h"   // generated: scripts/gen-qr-logo.py

#include <cmath>
#include <cstdio>
#include <cstring>

#include "../../../../engine/vendor/qrcodegen-3c6d0b3c/qrcodegen.h"   // Nayuki, MIT

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

// The UI font's variants (game/ui_font.hp): SemiBold 46 for the title and the
// address, Regular 36 for everything else.
constexpr wfui::Variant kTitleFont = wfui::Title, kBodyFont = wfui::Body;

struct Painter
{
    std::vector<PhonepadRect>* out;
    std::vector<bitmaptext::Quad>* glyphs;
    float s;        // canvas units -> pixels
    float ox, oy;   // where the canvas starts on the surface (Build offsets the rectangles at the end)

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
    // Draws text with its left edge at x and its middle (the capitals' middle)
    // at cy. Returns the x where the next text would start.
    float Text(float x, float cy, wfui::Variant v, uint32_t rgba, const char* text)
    {
        const char* arrow = std::strstr(text, remoteui::kBackArrow);
        if (arrow) {
            const std::string prefix(text, size_t(arrow - text));
            x = Text(x, cy, v, rgba, prefix.c_str());
            remoteui::BackArrowMiddle(*this, x, cy, v, rgba);
            return Text(x + remoteui::BackArrowAdvance(v), cy, v, rgba, arrow + 3);
        }
        wfui::Transform t;
        t.s = s; t.ox = ox; t.oy = oy;
        return x + wfui::TextBytes(*glyphs, x, cy, v, rgba, text, std::strlen(text), wfui::Middle, wfui::Left, t);
    }
    static float Width(const char* text, wfui::Variant v)
    {
        const char* arrow = std::strstr(text, remoteui::kBackArrow);
        if (arrow) {
            const std::string prefix(text, size_t(arrow - text));
            return Width(prefix.c_str(), v) + remoteui::BackArrowAdvance(v) + Width(arrow + 3, v);
        }
        return wfui::Width(v, text, std::strlen(text));
    }
};

}  // namespace

int ParseLogoMode(const char* s)
{
    if (std::strcmp(s, "planet") == 0) return kLogoPlanet;
    if (std::strcmp(s, "full") == 0)   return kLogoFull;
    if (std::strcmp(s, "none") == 0)   return kLogoNone;
    return -1;
}

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

bool Overlay::EncodeQr(const std::string& text, std::vector<uint8_t>* modules, int* size)
{
    modules->clear();
    *size = 0;
    // Version 10 (57 x 57) at ECC H holds 119 bytes: far more than
    // "http://255.255.255.255:65535/?k=123456" (38). Static: ~1.8 KB, no heap.
    static uint8_t qr[qrcodegen_BUFFER_LEN_FOR_VERSION(10)];
    static uint8_t tmp[qrcodegen_BUFFER_LEN_FOR_VERSION(10)];
    // ECC H (about 30 % of each block repairable), so the logo over the centre leaves most of the
    // correction budget for a camera's own misreads. A typical URL is then version 4 (33 x 33).
    if (!qrcodegen_encodeText(text.c_str(), tmp, qr, qrcodegen_Ecc_HIGH, 1, 10, qrcodegen_Mask_AUTO, true))
        return false;
    const int n = qrcodegen_getSize(qr);
    modules->resize(size_t(n) * size_t(n));
    for (int y = 0; y < n; ++y)
        for (int x = 0; x < n; ++x)
            (*modules)[size_t(y) * size_t(n) + size_t(x)] = qrcodegen_getModule(qr, x, y) ? 1 : 0;
    *size = n;
    return true;
}

bool Overlay::LogoPlate(int n, int mode, int* x0, int* y0, int* pw, int* ph)
{
    *x0 = *y0 = *pw = *ph = 0;
    // Version 1 is too small (a centred plate would reach the format bits beside the finders) and
    // cannot hold the URL at ECC H anyway; versions 7 and up have an alignment pattern in the very
    // centre. The URL is version 4 or 5 in practice. tests/test_phone_qr.py checks versions 2 to 6.
    if (mode == kLogoNone || n < 25 || n >= 45) return false;
    auto oddBelow = [](float v) { int k = int(v); return (k % 2) ? k : k - 1; };
    if (mode == kLogoPlanet)
    {
        *pw = *ph = oddBelow(0.22f * float(n));                 // 7 of 33: 4.5 % of the modules
    }
    else
    {
        // The whole logo is taller than wide: 9 x 11 of 33 (9.1 % of the modules), narrowed until
        // the plate is at most 10 % of the code.
        for (*pw = oddBelow(0.28f * float(n)); *pw >= 3; *pw -= 2)
        {
            const int hh = int(float(*pw) * float(logo::kFullH) / float(logo::kFullW) + 0.5f);
            *ph = (hh % 2) ? hh : hh - 1;
            if (10 * *pw * *ph <= n * n) break;
        }
    }
    if (*pw < 3 || *ph < 3) return false;
    *x0 = (n - *pw) / 2;                                         // n and the plate are odd: exactly centred
    *y0 = (n - *ph) / 2;
    return true;
}

bool Overlay::Build(int w, int h, int64_t nowMs, std::vector<PhonepadRect>* out, std::vector<bitmaptext::Quad>* glyphs)
{
    const bool  panel = PanelVisible(nowMs);
    const char* toast = Toast(nowMs);
    char key[256];
    std::snprintf(key, sizeof(key), "%dx%d p%d l%d t%s %s", w, h, panel ? 1 : 0, logo_, toast, panel ? url_.c_str() : "");
    if (lastKey_ == key) return false;
    lastKey_ = key;
    out->clear();
    glyphs->clear();
    if (w <= 0 || h <= 0) return true;

    // 1920x1080 canvas, scaled uniformly; the canvas is centred if the aspect differs.
    const float sx = float(w) / 1920.0f, sy = float(h) / 1080.0f, s = sx < sy ? sx : sy;
    const float ox = (float(w) - 1920.0f * s) * 0.5f, oy = (float(h) - 1080.0f * s) * 0.5f;
    Painter p{out, glyphs, s, ox, oy};

    if (panel)
    {
        p.Rect(0, 0, 1920, 1080, kDim);
        p.Rect(84, 90, 1836, 990, kPanel);
        p.Frame(84, 90, 1836, 990, 3, kLine);
        p.Text(132, 153, kTitleFont, kTitle, "Use your phone as the controller");

        std::vector<uint8_t> qr;
        int n = 0;
        float tx = 132;
        if (EncodeQr(url_, &qr, &n) && n > 0)
        {
            // The full URL with this launch's PIN, black on white with a 4-module quiet zone, about
            // 600 px tall at 1080p (16 px modules for a 29-module code) so it scans from a sofa.
            // Modules are whole screen pixels and the square starts on a pixel, so every module
            // edge is sharp; dark runs are merged per row.
            const float mpx = std::floor(600.0f * p.s / float(n + 8));       // module size, pixels
            if (mpx >= 2.0f)
            {
                const float m  = mpx / p.s;                                    // ... in canvas units
                const float x0 = std::floor(132.0f * p.s) / p.s, y0 = std::floor(232.0f * p.s) / p.s;
                const float side = m * float(n + 8);
                p.Rect(x0, y0, x0 + side, y0 + side, 0xFFFFFFFFu);
                // The logo plate: whole modules in the centre left white (the code's error correction
                // stands in for them), with the logo inside a one-module white margin.
                int lx = 0, ly = 0, lw = 0, lh = 0;
                const bool logo = LogoPlate(n, logo_, &lx, &ly, &lw, &lh);
                auto inPlate = [&](int r, int c) { return logo && r >= ly && r < ly + lh && c >= lx && c < lx + lw; };
                for (int r = 0; r < n; ++r)
                    for (int c = 0; c < n;)
                    {
                        if (!qr[size_t(r) * size_t(n) + size_t(c)] || inPlate(r, c)) { ++c; continue; }
                        int e = c;
                        while (e < n && qr[size_t(r) * size_t(n) + size_t(e)] && !inPlate(r, e)) ++e;
                        p.Rect(x0 + (4 + c) * m, y0 + (4 + r) * m, x0 + (4 + e) * m, y0 + (5 + r) * m, 0x000000FFu);
                        c = e;
                    }
                if (logo)
                {
                    const bool full = logo_ == kLogoFull;
                    const int gw = full ? logo::kFullW : logo::kPlanetW, gh = full ? logo::kFullH : logo::kPlanetH;
                    const uint8_t* cells = full ? logo::kFull : logo::kPlanet;
                    const float aw = float(lw - 2) * m, ah = float(lh - 2) * m;     // inside the margin
                    const float cell = std::fmin(aw / float(gw), ah / float(gh));
                    const float gx = x0 + (4 + lx + 1) * m + (aw - cell * float(gw)) * 0.5f;
                    const float gy = y0 + (4 + ly + 1) * m + (ah - cell * float(gh)) * 0.5f;
                    for (int r = 0; r < gh; ++r)
                        for (int c = 0; c < gw;)
                        {
                            const uint8_t k = cells[r * gw + c];
                            int e = c;
                            while (e < gw && cells[r * gw + e] == k) ++e;
                            if (logo::kPalette[k] != 0xFFFFFFFFu)   // white is the plate already
                                p.Rect(gx + float(c) * cell, gy + float(r) * cell, gx + float(e) * cell,
                                       gy + float(r + 1) * cell, logo::kPalette[k]);
                            c = e;
                        }
                }
                tx = 132.0f + 600.0f + 64.0f;   // the code is at most 600 wide; text never moves with the snapping
            }
        }

        const wfui::Variant ts = kBodyFont;
        p.Text(tx, 284, ts, kText, "1. Join the same Wi-Fi as this TV");
        p.Text(tx, 364, ts, kText, tx > 132 ? "2. Scan the code, or open" : "2. On your phone, open");
        const float cw = Painter::Width(hostPort_.c_str(), kTitleFont);
        p.Rect(tx + 40, 418, tx + 40 + cw + 36, 418 + 64, kCodeBg);
        p.Text(tx + 58, 450, kTitleFont, kCode, hostPort_.c_str());
        char pin[8] = "";
        if (pin_.size() == 6) std::snprintf(pin, sizeof(pin), "%.3s %.3s", pin_.c_str(), pin_.c_str() + 3);
        float x = p.Text(tx, 544, ts, kText, "3. Enter PIN ");
        x = p.Text(x, 544, ts, kOk, pin);
        p.Text(x, 544, ts, kText, " if asked");
        p.Rect(tx, 640, tx + 18, 658, kWarn);
        p.Text(tx + 34, 649, ts, kWarn, "Waiting for a phone...");
        p.Text(132, 940, kBodyFont, kFoot, "The remote still works. Press ← to hide this.");
    }

    if (*toast)
    {
        const wfui::Variant ts = kBodyFont;
        const float tw = Painter::Width(toast, ts);
        const float x1 = 1880, x0 = x1 - tw - 56, y0 = 40, y1 = 40 + 76;
        p.Rect(x0, y0, x1, y1, kToastBg);
        p.Frame(x0, y0, x1, y1, 3, toastRgba_);
        p.Text(x0 + 28, (y0 + y1) * 0.5f, ts, toastRgba_, toast);
    }

    // Centre the canvas on surfaces that are not 16:9 (the glyphs were placed there already).
    if (ox != 0.0f || oy != 0.0f)
        for (PhonepadRect& r : *out) { r.x0 += ox; r.x1 += ox; r.y0 += oy; r.y1 += oy; }
    return true;
}

}  // namespace phonepad
