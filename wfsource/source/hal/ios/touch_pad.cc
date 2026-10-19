//=============================================================================
// hal/ios/touch_pad.cc: platform-independent on-screen touch pad logic
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// See touch_pad.hp. No UIKit, no engine headers: compiled into the iOS
// engine by the hal/ios glob and into tests/touch_pad_test.cc on Linux.
//=============================================================================

#include "touch_pad.hp"

#include <algorithm>
#include <cstdlib>
#include <cstring>

namespace wf_touch
{

Rect
Layout::Cell(int col, int row) const
{
    Rect r;
    r.x0 = dpad.x0 + cell * float(col);
    r.y0 = dpad.y0 + cell * float(row);
    r.x1 = r.x0 + cell;
    r.y1 = r.y0 + cell;
    return r;
}

Layout
ComputeLayout(float viewW, float viewH, const Insets& safe)
{
    Layout l;
    const float sx0 = safe.left;
    const float sy0 = safe.top;
    const float sx1 = viewW - safe.right;
    const float sy1 = viewH - safe.bottom;
    const float safeW = sx1 - sx0;
    const float safeH = sy1 - sy0;
    if (viewW <= 0 || viewH <= 0 || safeW <= 0 || safeH <= 0)
        return l;

    const float m = kMarginPt;
    float c = std::min(viewW, viewH) * kCellFraction;
    c = std::max(kMinCellPt, std::min(kMaxCellPt, c));

    // Fit: margin | D-pad (3c) | margin | B (kc) A (kc) | margin across the
    // safe width; margin + 3c + margin down the safe height (3c > kc).
    const float fitW = (safeW - 3.0f * m) / (3.0f + 2.0f * kActionScale);
    const float fitH = (safeH - 2.0f * m) / 3.0f;
    c = std::min(c, std::min(fitW, fitH));
    if (c <= 0)
        return l;

    const float s = c * kActionScale;
    l.cell = c;
    l.dpad.x0 = sx0 + m;
    l.dpad.x1 = l.dpad.x0 + 3.0f * c;
    l.dpad.y1 = sy1 - m;
    l.dpad.y0 = l.dpad.y1 - 3.0f * c;

    l.a.x1 = sx1 - m;
    l.a.x0 = l.a.x1 - s;
    l.a.y1 = sy1 - m;
    l.a.y0 = l.a.y1 - s;

    l.b    = l.a;
    l.b.x1 = l.a.x0;
    l.b.x0 = l.b.x1 - s;

    l.valid = true;
    return l;
}

uint32_t
HitTest(const Layout& l, float x, float y)
{
    if (!l.valid)
        return 0;

    if (l.dpad.Contains(x, y))
    {
        // Rows top→bottom, columns left→right. Centre is dead, as on Android.
        static const uint32_t kGrid[3][3] = {
            { kBtnUp   | kBtnLeft, kBtnUp,   kBtnUp   | kBtnRight },
            { kBtnLeft,            0,        kBtnRight            },
            { kBtnDown | kBtnLeft, kBtnDown, kBtnDown | kBtnRight },
        };
        const int col = std::min(2, std::max(0, int((x - l.dpad.x0) / l.cell)));
        const int row = std::min(2, std::max(0, int((y - l.dpad.y0) / l.cell)));
        return kGrid[row][col];
    }
    if (l.a.Contains(x, y)) return kBtnA;
    if (l.b.Contains(x, y)) return kBtnB;
    return 0;
}

//=============================================================================

int
TouchTracker::Find(uintptr_t id) const
{
    for (int i = 0; i < _count; ++i)
        if (_touches[i].id == id)
            return i;
    return -1;
}

void
TouchTracker::Began(uintptr_t id, float x, float y)
{
    const int i = Find(id);
    if (i >= 0) { _touches[i].x = x; _touches[i].y = y; return; }
    if (_count >= kMaxTouches) return;          // extra fingers are ignored
    _touches[_count++] = Touch{ id, x, y };
}

void
TouchTracker::Moved(uintptr_t id, float x, float y)
{
    Began(id, x, y);
}

void
TouchTracker::Ended(uintptr_t id)
{
    const int i = Find(id);
    if (i < 0) return;
    _touches[i] = _touches[--_count];
}

void
TouchTracker::ReleaseAll()
{
    _count = 0;
}

uint32_t
TouchTracker::Buttons(const Layout& layout) const
{
    uint32_t mask = 0;
    for (int i = 0; i < _count; ++i)
        mask |= HitTest(layout, _touches[i].x, _touches[i].y);
    return mask;
}

//=============================================================================

namespace
{

uint32_t
ButtonByName(const char* p, size_t n)
{
    struct Name { const char* s; uint32_t bit; };
    static const Name kNames[] = {
        { "up", kBtnUp }, { "down", kBtnDown }, { "left", kBtnLeft },
        { "right", kBtnRight }, { "a", kBtnA }, { "b", kBtnB },
    };
    for (const Name& nm : kNames)
        if (std::strlen(nm.s) == n && std::strncmp(nm.s, p, n) == 0)
            return nm.bit;
    return 0;
}

}  // namespace

int
ParseScript(const char* text, ScriptEntry* out, int max)
{
    if (!text || !*text)
        return 0;
    int n = 0;
    const char* p = text;
    for (;;)
    {
        const char* at = std::strchr(p, '@');
        if (!at) return -1;
        const uint32_t bit = ButtonByName(p, size_t(at - p));
        if (!bit) return -1;

        char* end = nullptr;
        const float start = std::strtof(at + 1, &end);
        if (end == at + 1 || *end != '+' || start < 0) return -1;
        const char* durp = end + 1;
        const float dur = std::strtof(durp, &end);
        if (end == durp || dur <= 0) return -1;
        if (*end != ',' && *end != '\0') return -1;

        if (n >= max) return -1;
        out[n].button   = bit;
        out[n].start    = start;
        out[n].duration = dur;
        ++n;

        if (*end == '\0') return n;
        p = end + 1;
    }
}

bool
ButtonCenter(const Layout& l, uint32_t button, float* x, float* y)
{
    if (!l.valid) return false;
    Rect r;
    switch (button)
    {
        case kBtnUp:    r = l.Up();    break;
        case kBtnDown:  r = l.Down();  break;
        case kBtnLeft:  r = l.Left();  break;
        case kBtnRight: r = l.Right(); break;
        case kBtnA:     r = l.a;       break;
        case kBtnB:     r = l.b;       break;
        default:        return false;
    }
    *x = r.CenterX();
    *y = r.CenterY();
    return true;
}

}  // namespace wf_touch
