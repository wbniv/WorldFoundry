//=============================================================================
// game/level_menu.cc: the level menu of multi-level bundles (portable)
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// See level_menu.h. Layout is designed on a 1920x1080 canvas and scaled to the
// surface (the mockups in docs/plans/2026-10-01-level-menu-selector/).
//=============================================================================

#include "level_menu.h"

#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#if defined(__GNUC__)
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-function"
#pragma GCC diagnostic ignored "-Wsign-compare"
#pragma GCC diagnostic ignored "-Wcast-align"
#endif
#include "../../../engine/vendor/stb_easy_font.h"
#if defined(__GNUC__)
#pragma GCC diagnostic pop
#endif

namespace levelmenu
{

namespace
{

// The mockups' palette (0xRRGGBBAA).
constexpr uint32_t kBg      = 0x0E1726FFu;
constexpr uint32_t kTitle   = 0xFFB454FFu;
constexpr uint32_t kSub     = 0x8FA3BFFFu;
constexpr uint32_t kText    = 0xC9D4E3FFu;
constexpr uint32_t kSelBar  = 0x23406BFFu;
constexpr uint32_t kSelEdge = 0x56D364FFu;
constexpr uint32_t kSelText = 0xFFFFFFFFu;

// The 1920x1080 canvas.
constexpr float kListX0 = 360, kListX1 = 1560, kListY = 300, kRowH = 92, kRowGap = 8;
constexpr float kRowTextX = kListX0 + 48, kRowTextScale = 6.0f;
constexpr float kRowTextMaxW = kListX1 - 24 - kRowTextX;

uint32_t U32(const uint8_t* p) { return uint32_t(p[0]) | uint32_t(p[1]) << 8 | uint32_t(p[2]) << 16 | uint32_t(p[3]) << 24; }
uint16_t U16(const uint8_t* p) { return uint16_t(p[0] | p[1] << 8); }

bool Drawable(const std::string& s)
{
    if (s.empty() || s.size() > kMaxText) return false;
    for (char c : s)
        if (c < 32 || c > 126) return false;
    return true;
}

// stb_easy_font writes floats through a char*, so the buffer must be float aligned
// (an unaligned VFP store faults on 32-bit ARM). ~270 bytes per character.
float gTextBuf[16384];

float TextWidth(const std::string& text, float scale)
{
    stb_easy_font_spacing(-0.5f);   // as the phone panel: the 1-pixel gap looks loose scaled up
    return float(stb_easy_font_width(const_cast<char*>(text.c_str()))) * scale;
}

// Canvas units -> surface pixels, with the canvas centred when the aspect differs.
struct Painter
{
    std::vector<PhonepadRect>* out;
    float s, ox, oy;

    void Rect(float x0, float y0, float x1, float y1, uint32_t rgba)
    {
        out->push_back({ox + x0 * s, oy + y0 * s, ox + x1 * s, oy + y1 * s, rgba});
    }
    // ASCII text with its top-left at (x, y), `scale` canvas units per font pixel.
    void Text(float x, float y, float scale, uint32_t rgba, const std::string& text)
    {
        stb_easy_font_spacing(-0.5f);
        const int quads = stb_easy_font_print(0.0f, 0.0f, const_cast<char*>(text.c_str()), nullptr, gTextBuf, int(sizeof(gTextBuf)));
        for (int q = 0; q < quads; ++q)
        {
            const float* v = gTextBuf + q * 16;    // 4 vertices x (x, y, z, rgba)
            float minx = v[0], maxx = v[0], miny = v[1], maxy = v[1];
            for (int k = 1; k < 4; ++k)
            {
                const float vx = v[k * 4], vy = v[k * 4 + 1];
                minx = vx < minx ? vx : minx;  maxx = vx > maxx ? vx : maxx;
                miny = vy < miny ? vy : miny;  maxy = vy > maxy ? vy : maxy;
            }
            Rect(x + minx * scale, y + miny * scale, x + maxx * scale, y + maxy * scale, rgba);
        }
    }
    void Centred(float y, float scale, uint32_t rgba, const std::string& text)
    {
        Text(960.0f - TextWidth(text, scale) / 2.0f, y, scale, rgba, text);
    }
    // A triangle pointing up (dir -1) or down (+1), apex at (cx, y), made of strips.
    void Arrow(float cx, float y, int dir, uint32_t rgba)
    {
        constexpr float kH = 30, kStep = 3;
        for (float k = 0; k < kH; k += kStep)
        {
            const float half = (k + kStep) * 0.8f;
            const float y0 = dir < 0 ? y + k : y + kH - k - kStep;
            Rect(cx - half, y0, cx + half, y0 + kStep, rgba);
        }
    }
};

std::atomic<bool> gReturnRequested{false};
DrawFn gDrawer = nullptr;

}  // namespace

uint32_t Tag(const char (&s)[5])
{
    return U32(reinterpret_cast<const uint8_t*>(s));
}

//-----------------------------------------------------------------------------

bool ParseToc(const uint8_t* p, size_t n, std::vector<TocEntry>* out)
{
    out->clear();
    if (n < 16 || std::memcmp(p, "GAME", 4) != 0 || std::memcmp(p + 8, "TOC\0", 4) != 0)
        return false;
    const uint32_t size = U32(p + 12);
    if (size == 0 || size % 12 != 0 || 16 + size_t(size) > n)
        return false;
    for (uint32_t off = 16; off < 16 + size; off += 12)
        out->push_back({U32(p + off), U32(p + off + 4), U32(p + off + 8)});
    return true;
}

bool FindMenu(const std::vector<TocEntry>& toc, TocEntry* menu, int* levelCount)
{
    // SHEL first, the levels, then MENU last (cdpack --manifest), so level n stays entry 1 + n.
    if (toc.size() < 3 || toc.front().tag != Tag("SHEL") || toc.back().tag != Tag("MENU"))
        return false;
    *menu = toc.back();
    *levelCount = int(toc.size()) - 2;
    return true;
}

bool ParseMenu(const uint8_t* p, size_t n, int levelCount, Bundle* out, std::string* err)
{
    *out = Bundle();
    size_t at = 0;
    auto need = [&](size_t k) {
        if (at + k <= n) return true;
        *err = "MENU chunk truncated at byte " + std::to_string(at);
        return false;
    };
    auto text = [&](std::string* s, const char* what) {
        if (!need(2)) return false;
        const uint16_t len = U16(p + at);
        at += 2;
        if (!need(len)) return false;
        s->assign(reinterpret_cast<const char*>(p + at), len);
        at += len;
        if (!Drawable(*s)) { *err = std::string(what) + " is not 1 to 60 printable ASCII characters"; return false; }
        return true;
    };
    if (!need(8) || std::memcmp(p, "MENU", 4) != 0) { if (err->empty()) *err = "no MENU tag"; return false; }
    const uint32_t payload = U32(p + 4);
    if (size_t(payload) + 8 > n) { *err = "MENU payload larger than its TOC entry"; return false; }
    n = size_t(payload) + 8;
    at = 8;
    if (!need(12)) return false;
    const uint32_t version = U32(p + at), levels = U32(p + at + 4), count = U32(p + at + 8);
    at += 12;
    if (version != 1) { *err = "MENU version " + std::to_string(version) + ", want 1"; return false; }
    if (int(levels) != levelCount)
    {
        *err = "MENU says " + std::to_string(levels) + " levels, the TOC has " + std::to_string(levelCount);
        return false;
    }
    if (count > 1000) { *err = "MENU entry count " + std::to_string(count); return false; }
    if (!text(&out->title, "title") || !text(&out->prompt, "prompt")) return false;
    for (uint32_t i = 0; i < count; ++i)
    {
        if (!need(4)) return false;
        const uint32_t level = U32(p + at);
        at += 4;
        if (int64_t(level) >= int64_t(levelCount))
        {
            *err = "MENU entry " + std::to_string(i) + " names level " + std::to_string(level) + " of " + std::to_string(levelCount);
            return false;
        }
        Entry e{int(level), {}};
        if (!text(&e.name, "a name")) return false;
        out->entries.push_back(e);
    }
    return true;
}

int AutoPick(const Bundle& bundle)
{
    if (bundle.entries.empty()) return 0;
    if (bundle.entries.size() == 1) return bundle.entries[0].level;
    return -1;
}

//-----------------------------------------------------------------------------

Menu::Menu(Bundle bundle, int cursor, std::string hint)
    : bundle_(std::move(bundle)), hint_(std::move(hint))
{
    const int n = int(bundle_.entries.size());
    cursor_ = n == 0 ? 0 : (cursor < 0 ? 0 : (cursor >= n ? n - 1 : cursor));
    first_ = cursor_ >= kVisibleRows ? cursor_ - kVisibleRows + 1 : 0;
}

void Menu::Move(int delta)
{
    const int n = int(bundle_.entries.size());
    int c = cursor_ + delta;
    c = c < 0 ? 0 : (c >= n ? n - 1 : c);   // the ends stop the cursor; no wrap
    cursor_ = c;
    if (cursor_ < first_) first_ = cursor_;
    if (cursor_ >= first_ + kVisibleRows) first_ = cursor_ - kVisibleRows + 1;
}

void Menu::Update(uint32_t buttons, int64_t nowMs)
{
    if (!primed_)
    {
        // Whatever is held as the menu appears (the A that ended the last level, a key
        // still down) only counts once it has been released and pressed again.
        primed_ = true;
        prev_ = buttons;
        return;
    }
    const uint32_t pressed = buttons & ~prev_;
    prev_ = buttons;
    switch (phase_)
    {
    case Phase::Choosing:
        if (bundle_.entries.empty())
            return;
        if (pressed & kButtonA)
        {
            // Start only once everything is released: the A must not reach the level.
            phase_ = Phase::WaitRelease;
            chosenAt_ = nowMs;
            if (buttons == 0) phase_ = Phase::Done;
            return;
        }
        if (pressed & (kButtonUp | kButtonDown))
        {
            heldDir_ = (pressed & kButtonUp) ? -1 : +1;
            Move(heldDir_);
            repeatAt_ = nowMs + kRepeatDelayMs;
        }
        else if (heldDir_ != 0)
        {
            const uint32_t bit = heldDir_ < 0 ? kButtonUp : kButtonDown;
            if (!(buttons & bit))
                heldDir_ = 0;
            else
                while (nowMs >= repeatAt_)
                {
                    Move(heldDir_);
                    repeatAt_ += kRepeatEveryMs;
                }
        }
        return;
    case Phase::WaitRelease:
        if (buttons == 0 || nowMs - chosenAt_ >= kReleaseWaitMs)
            phase_ = Phase::Done;
        return;
    case Phase::Done:
        return;
    }
}

std::string Menu::RowText(int i) const
{
    std::string name = bundle_.entries[size_t(i)].name;
    if (TextWidth(name, kRowTextScale) <= kRowTextMaxW)
        return name;
    while (!name.empty() && TextWidth(name + "...", kRowTextScale) > kRowTextMaxW)
        name.pop_back();
    while (!name.empty() && name.back() == ' ')
        name.pop_back();
    return name + "...";
}

bool Menu::Build(int w, int h, std::vector<PhonepadRect>* out)
{
    char key[96];
    std::snprintf(key, sizeof(key), "%dx%d c%d f%d", w, h, cursor_, first_);
    if (lastKey_ == key) return false;
    lastKey_ = key;
    out->clear();
    if (w <= 0 || h <= 0) return true;

    const float sx = float(w) / 1920.0f, sy = float(h) / 1080.0f, s = sx < sy ? sx : sy;
    Painter p{out, s, (float(w) - 1920.0f * s) / 2.0f, (float(h) - 1080.0f * s) / 2.0f};

    out->push_back({0.0f, 0.0f, float(w), float(h), kBg});   // nothing is loaded behind the menu
    p.Centred(70, 9.0f, kTitle, bundle_.title);
    p.Centred(180, 5.0f, kSub, bundle_.prompt);

    const int n = int(bundle_.entries.size());
    for (int row = 0; row < kVisibleRows && first_ + row < n; ++row)
    {
        const int   i = first_ + row;
        const float y = kListY + float(row) * (kRowH + kRowGap);
        if (i == cursor_)
        {
            p.Rect(kListX0, y, kListX1, y + kRowH, kSelBar);
            p.Rect(kListX0, y, kListX0 + 14, y + kRowH, kSelEdge);
        }
        p.Text(kRowTextX, y + 25, kRowTextScale, i == cursor_ ? kSelText : kText, RowText(i));
    }
    const float below = kListY + kVisibleRows * (kRowH + kRowGap);
    if (first_ > 0)
        p.Arrow(960, 254, -1, kSub);
    if (first_ + kVisibleRows < n)
        p.Arrow(960, below + 4, +1, kSub);
    if (n > 0)
    {
        const std::string count = std::to_string(cursor_ + 1) + " / " + std::to_string(n);
        p.Text(kListX1 - TextWidth(count, 4.5f), below + 8, 4.5f, kSub, count);
    }
    float hs = 4.5f;
    while (hs > 2.0f && TextWidth(hint_, hs) > 1800.0f)
        hs -= 0.25f;
    p.Centred(1000, hs, kSub, hint_);
    return true;
}

//-----------------------------------------------------------------------------

bool InputScript::Parse(const std::string& text, std::string* err)
{
    frames_.clear();
    active_ = false;
    size_t at = 0;
    while (at <= text.size())
    {
        size_t comma = text.find(',', at);
        if (comma == std::string::npos) comma = text.size();
        const std::string tok = text.substr(at, comma - at);
        at = comma + 1;
        ScriptFrame press;
        if (tok == "up")        press.buttons = kButtonUp;
        else if (tok == "down") press.buttons = kButtonDown;
        else if (tok == "a")    press.buttons = kButtonA;
        else if (tok == "back") press.back = true;
        else if (tok == "quit") press.quit = true;
        else if (tok.compare(0, 5, "wait:") == 0 && tok.size() > 5 && tok.find_first_not_of("0123456789", 5) == std::string::npos
                 && tok.size() <= 11)
        {
            frames_.insert(frames_.end(), size_t(std::atoi(tok.c_str() + 5)), ScriptFrame());
            continue;
        }
        else
        {
            *err = "unknown --menu-input token \"" + tok + "\" (want up, down, a, wait:N, back, quit)";
            frames_.clear();
            return false;
        }
        frames_.push_back(press);
        frames_.push_back(ScriptFrame());   // a released frame, so the next press is an edge
    }
    active_ = true;
    return true;
}

bool InputScript::Next(ScriptFrame* out)
{
    if (frames_.empty()) return false;
    *out = frames_.front();
    frames_.pop_front();
    return true;
}

InputScript& Script()
{
    static InputScript script;
    return script;
}

void SetDrawer(DrawFn fn) { gDrawer = fn; }
DrawFn Drawer() { return gDrawer; }

const char* PlatformHint()
{
#if defined(__ANDROID__)
    return "D-pad choose - OK starts - Hold Back in a game for this menu";
#else
    return "Up/Down choose - Space starts - Backspace in a game comes back here";
#endif
}

void RequestReturn() { gReturnRequested.store(true); }
bool ConsumeReturnRequest() { return gReturnRequested.exchange(false); }

}  // namespace levelmenu
