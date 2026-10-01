//=============================================================================
// hal/phonepad/phonepad_overlay.h: the TV side of the phone controller (portable)
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// What the TV shows about the phone, as a list of solid rectangles that the
// platform draws over the game (Android: gfx/gl/android_window.cc, with the
// touch HUD's shader). Mockup 3 of docs/plans/2026-09-30-aquarium-chromecast.md:
//
//   no phone yet       the panel: title, QR code, the address, the PIN,
//                      "Waiting for a phone..." and "Press Back to hide this"
//   a phone connects   the panel goes; a "Phone connected" toast for 3 s
//   the phone drops    a "Phone lost" toast at once; the panel again after 5 s
//                      if no phone has come back (buttons were already
//                      released by the server)
//   Back on the panel  hides it for this session (the remote still works)
//
// Text comes from engine/vendor/stb_easy_font.h (public domain, already used
// by gfx/gl/display.cc), the QR code from engine/vendor/qrcodegen (MIT). Both
// produce quads, so no texture or font file is needed. Pure logic plus
// geometry: the tests drive it with a fake clock on Linux.
//=============================================================================

#ifndef HAL_PHONEPAD_PHONEPAD_OVERLAY_H
#define HAL_PHONEPAD_PHONEPAD_OVERLAY_H

#include <cstdint>
#include <string>
#include <vector>

// Plain C layout so the GL side can take it across an extern "C" boundary.
// Pixels, origin top-left, +Y down; colour 0xRRGGBBAA.
struct PhonepadRect
{
    float    x0, y0, x1, y1;
    uint32_t rgba;
};

namespace phonepad
{

constexpr int kToastMs      = 3000;   // "Phone connected" / "Phone lost"

// What sits in the middle of the QR code (wf_args.txt "qr_logo=planet|full|none", default planet).
enum : int { kLogoNone = 0, kLogoPlanet = 1, kLogoFull = 2 };
int ParseLogoMode(const char* s);   // "planet" / "full" / "none"; -1 if none of them
constexpr int kPanelAfterMs = 5000;   // the panel returns this long after a drop

class Overlay
{
public:
    // The server is listening: show this URL (with the PIN) and PIN.
    void SetEndpoint(const std::string& url, const std::string& hostPort, const std::string& pin);
    // Not listening (paused, or no Wi-Fi): draw nothing.
    void ClearEndpoint();
    // Server event bits (phonepad::kEv*).
    void OnEvents(uint32_t events, int64_t nowMs);
    void SetLogo(int mode) { logo_ = mode; }
    int  Logo() const { return logo_; }
    // The plate (in modules, top-left and size) left white for the logo in an n x n code, or false
    // when there is none (mode none, or a version with a centre alignment pattern).
    static bool LogoPlate(int n, int mode, int* x0, int* y0, int* w, int* h);

    // Back pressed. True if it was consumed (the panel was showing and is now hidden).
    bool OnBack(int64_t nowMs);

    bool PanelVisible(int64_t nowMs) const;
    // "" when no toast is showing.
    const char* Toast(int64_t nowMs) const;

    // Fill `out` for a w x h surface. Returns true when the list differs
    // from the previous call's (the caller re-uploads only then).
    bool Build(int w, int h, int64_t nowMs, std::vector<PhonepadRect>* out);

    // The QR module grid Build draws (size x size, row-major, 1 = dark);
    // false if the URL could not be encoded. For the tests.
    static bool EncodeQr(const std::string& text, std::vector<uint8_t>* modules, int* size);

private:
    std::string url_, hostPort_, pin_;
    bool        endpoint_   = false;
    bool        connected_  = false;
    bool        hidden_     = false;   // Back pressed on the panel
    int64_t     toastUntil_ = 0;
    const char* toast_      = "";
    uint32_t    toastRgba_  = 0;
    int64_t     lostAt_     = -1;      // -1: never lost (or a phone is back)
    std::string lastKey_;
    int         logo_       = kLogoPlanet;
};

}  // namespace phonepad

#endif  // HAL_PHONEPAD_PHONEPAD_OVERLAY_H
