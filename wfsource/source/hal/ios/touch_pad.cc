//=============================================================================
// hal/ios/touch_pad.cc: the iOS side of the shared on-screen touch controls
// Copyright ( c ) 2026 World Foundry Group
// Part of the World Foundry 3D video game engine/production environment
// for more information about World Foundry, see www.worldfoundry.org
//=============================================================================
// See touch_pad.hp. No UIKit, no engine headers: compiled into the iOS
// engine by the hal/ios glob and into tests/touch_pad_test.cc on Linux.
//=============================================================================

#include "touch_pad.hp"

#include <cstdlib>
#include <cstring>

namespace wf_touch
{

int
Pad::Find(uintptr_t key) const
{
    for (int i = 0; i < _count; ++i)
        if (_fingers[i].key == key)
            return i;
    return -1;
}

void
Pad::Update(wftouch::Action action, int changed)
{
    wftouch::Point points[kMaxTouches];
    for (int i = 0; i < _count; ++i)
        points[i] = wftouch::Point{ _fingers[i].x, _fingers[i].y, _fingers[i].id };
    _mask = _state.update(_layout, points, size_t(_count), action, changed);
}

void
Pad::SetView(float viewW, float viewH, const wftouch::Insets& safe)
{
    _full   = wftouch::layout(viewW, viewH, 1.0f, safe);
    _layout = _reading ? wftouch::reading(_full) : _full;
    Update(wftouch::Action::Move, -1);
}

void
Pad::SetReading(bool reading)
{
    _reading = reading;
    _layout  = _reading ? wftouch::reading(_full) : _full;
    Update(wftouch::Action::Move, -1);   // drops fingers on what is now hidden
}

void
Pad::Began(uintptr_t key, float x, float y)
{
    if (Find(key) >= 0) { Moved(key, x, y); return; }
    if (_count >= kMaxTouches) return;          // extra fingers are ignored
    _fingers[_count++] = Finger{ key, _nextId, x, y };
    _nextId = _nextId == 0x7fffffff ? 1 : _nextId + 1;
    Update(wftouch::Action::Down, _count - 1);
}

void
Pad::Moved(uintptr_t key, float x, float y)
{
    const int i = Find(key);
    if (i < 0) { Began(key, x, y); return; }
    _fingers[i].x = x;
    _fingers[i].y = y;
    Update(wftouch::Action::Move, -1);
}

void
Pad::Ended(uintptr_t key)
{
    const int i = Find(key);
    if (i < 0) return;
    Update(wftouch::Action::Up, i);              // the lifting finger is still listed
    for (int j = i; j + 1 < _count; ++j)
        _fingers[j] = _fingers[j + 1];
    --_count;
    if (_count == 0) { _state.clear(); _mask = 0; }
    else Update(wftouch::Action::Move, -1);
}

void
Pad::ReleaseAll()
{
    _count = 0;
    _state.clear();
    _mask = 0;
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
        { "c", kBtnC }, { "d", kBtnD },
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
ButtonCenter(const wftouch::Layout& l, uint32_t button, float* x, float* y)
{
    if (!l.valid) return false;
    for (int i = 4; i < 8; ++i)
        if (l.controls[i].bit == button)
        {
            const wftouch::Rect& r = l.controls[i].rect;
            *x = 0.5f * (r.x0 + r.x1);
            *y = 0.5f * (r.y0 + r.y1);
            return true;
        }
    float dx = 0, dy = 0;
    switch (button)
    {
        case kBtnUp:    dy = -1; break;
        case kBtnDown:  dy =  1; break;
        case kBtnLeft:  dx = -1; break;
        case kBtnRight: dx =  1; break;
        default:        return false;
    }
    const float reach = 0.9f * wftouch::stickRadius(l);
    *x = 0.5f * (l.pad.x0 + l.pad.x1) + dx * reach;
    *y = 0.5f * (l.pad.y0 + l.pad.y1) + dy * reach;
    return true;
}

}  // namespace wf_touch
