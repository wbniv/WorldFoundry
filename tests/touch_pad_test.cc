// tests/touch_pad_test.cc — unit test for the iOS touch controls: the shared
// layout and finger logic (wfsource/source/hal/touch_controls.h, the code
// Android runs) as iOS drives it through wf_touch::Pad
// (wfsource/source/hal/ios/touch_pad.{hp,cc}).
// Built and run by tests/test_ios_touch_pad.py with the host g++; prints one
// line per failed check and exits non-zero on any failure.
// Plan: finding-your-way docs/plans/2026-11-08-ios-touch-parity.md.

#include "touch_pad.hp"

#include <cstdio>
#include <cstring>

using namespace wf_touch;
using wftouch::Insets;
using wftouch::Layout;
using wftouch::Rect;

static int gFailures = 0;
static int gChecks   = 0;

#define CHECK(cond)                                                          \
    do {                                                                     \
        ++gChecks;                                                           \
        if (!(cond)) {                                                       \
            ++gFailures;                                                     \
            std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);      \
        }                                                                    \
    } while (0)

#define CHECK_EQ(a, b)                                                       \
    do {                                                                     \
        ++gChecks;                                                           \
        const unsigned long _a = (unsigned long)(a), _b = (unsigned long)(b);\
        if (_a != _b) {                                                      \
            ++gFailures;                                                     \
            std::printf("FAIL %s:%d: %s == %s (0x%lx vs 0x%lx)\n",           \
                        __FILE__, __LINE__, #a, #b, _a, _b);                 \
        }                                                                    \
    } while (0)

struct Dev { const char* name; float w, h; Insets in; };

// Sizes and safe areas: the landscape ones are what the Codemagic simulator
// logged on 2026-11-01; portrait and the rest are Apple's published values.
static const Dev kDevices[] = {
    { "iPhone 17 Pro landscape", 874, 402,  { 0, 62, 20, 62 } },
    { "iPhone 17 Pro portrait",  402, 874,  { 62, 0, 34, 0 } },
    { "iPad Pro 13 landscape",  1376, 1032, { 0, 0, 25, 0 } },
    { "iPad Pro 13 portrait",   1032, 1376, { 0, 0, 20, 0 } },
    { "iPhone SE landscape",     667, 375,  { 0, 0, 0, 0 } },
    { "iPhone SE portrait",      375, 667,  { 20, 0, 0, 0 } },
    { "iPad split, narrow",      320, 1032, { 0, 0, 20, 0 } },
};

static float CX(const Rect& r) { return 0.5f * (r.x0 + r.x1); }
static float CY(const Rect& r) { return 0.5f * (r.y0 + r.y1); }

static bool Inside(const Rect& r, float x0, float y0, float x1, float y1)
{
    return r.x0 >= x0 - 0.01f && r.y0 >= y0 - 0.01f && r.x1 <= x1 + 0.01f && r.y1 <= y1 + 0.01f;
}

static bool SameBits(const Layout& a, const Layout& b)
{
    // Field by field (Layout holds pointers to string literals and padding).
    if (a.valid != b.valid || a.stick != b.stick || a.shown != b.shown) return false;
    if (std::memcmp(&a.cell, &b.cell, sizeof a.cell) || std::memcmp(&a.pad, &b.pad, sizeof a.pad)) return false;
    for (int i = 0; i < 8; ++i)
        if (std::memcmp(&a.controls[i].rect, &b.controls[i].rect, sizeof(Rect)) ||
            a.controls[i].bit != b.controls[i].bit)
            return false;
    return true;
}

static void TestLayouts()
{
    for (const Dev& d : kDevices)
    {
        const Layout l = wftouch::layout(d.w, d.h, 1.0f, d.in);
        CHECK(l.valid);
        // 48..64 pt cells, or smaller only when the screen forces it.
        CHECK(l.cell <= 64.0f + 0.01f);
        if (d.w >= 360) CHECK(l.cell >= 48.0f - 0.01f);
        // Nothing inside an inset; nothing overlaps the stick.
        const float sx0 = d.in.left, sy0 = d.in.top, sx1 = d.w - d.in.right, sy1 = d.h - d.in.bottom;
        CHECK(Inside(l.pad, sx0, sy0, sx1, sy1));
        for (int i = 4; i < 8; ++i)
        {
            const Rect& r = l.controls[i].rect;
            CHECK(Inside(r, sx0, sy0, sx1, sy1));
            CHECK(l.pad.x1 <= r.x0);
            CHECK_EQ(wftouch::hit(l, CX(r), CY(r)), l.controls[i].bit);
        }
        // Android's own call on the same safe rectangle, then moved: the
        // same numbers (the iOS overload adds nothing else).
        const Layout base = wftouch::layout(d.w - d.in.left - d.in.right, d.h - d.in.top, 1.0f, d.in.bottom);
        CHECK(SameBits(wftouch::offset(base, d.in.left, d.in.top), l));
        // With no side or top inset it IS Android's layout, bit for bit.
        const Insets bottomOnly{ 0, 0, d.in.bottom, 0 };
        CHECK(SameBits(wftouch::layout(d.w, d.h, 1.0f, bottomOnly), wftouch::layout(d.w, d.h, 1.0f, d.in.bottom)));
    }
    // The iPhone landscape numbers the plan's mockups show.
    const Layout iphone = wftouch::layout(874, 402, 1.0f, Insets{ 0, 62, 20, 62 });
    CHECK(iphone.cell > 53.99f && iphone.cell < 54.01f);
    CHECK(iphone.pad.x0 > 73.99f && iphone.pad.x0 < 74.01f);   // 62 inset + 12 margin
    CHECK(iphone.controls[4].rect.x1 > 799.99f && iphone.controls[4].rect.x1 < 800.01f);
    // Invalid views hit nothing.
    const Layout none = wftouch::layout(0, 0, 1.0f, Insets{});
    CHECK(!none.valid);
    CHECK_EQ(wftouch::hit(none, 10, 10), 0);
    const Layout eaten = wftouch::layout(100, 100, 1.0f, Insets{ 0, 60, 0, 60 });
    CHECK(!eaten.valid);
}

static void TestStick()
{
    Pad pad;
    pad.SetView(874, 402, Insets{ 0, 62, 20, 62 });
    const Layout& l = pad.CurrentLayout();
    const float cx = CX(l.pad), cy = CY(l.pad), r = wftouch::stickRadius(l);
    CHECK_EQ(wftouch::hit(l, cx, cy), 0);                               // dead centre
    CHECK_EQ(wftouch::hit(l, cx + r * 0.49f, cy), 0);                   // inside half the radius
    CHECK_EQ(wftouch::hit(l, cx + r * 0.6f, cy), kBtnRight);
    CHECK_EQ(wftouch::hit(l, cx, cy - r * 0.6f), kBtnUp);
    CHECK_EQ(wftouch::hit(l, cx - r * 0.6f, cy + r * 0.6f), kBtnLeft | kBtnDown);
    CHECK_EQ(wftouch::hit(l, cx + r * 1.01f, cy), 0);                   // outside the ring
    // A thumb that lands in the ring owns it; sliding outside keeps it, clamped.
    pad.Began(0xA000, cx, cy);
    CHECK_EQ(pad.Buttons(), 0);
    pad.Moved(0xA000, cx + r * 3, cy);
    CHECK_EQ(pad.Buttons(), kBtnRight);
    CHECK(pad.StickPosition().x > 0.999f);
    // A second thumb in the ring is ignored while the first holds it.
    pad.Began(0xB000, cx - r * 0.8f, cy);
    CHECK_EQ(pad.Buttons(), kBtnRight);
    pad.Ended(0xA000);
    CHECK_EQ(pad.Buttons(), 0);          // the second thumb never owned it
    pad.Ended(0xB000);
    CHECK_EQ(pad.Count(), 0);
    CHECK(pad.StickPosition().x == 0);
}

static void TestMultiTouch()
{
    Pad pad;
    pad.SetView(874, 402, Insets{ 0, 62, 20, 62 });
    const Layout& l = pad.CurrentLayout();
    const float cx = CX(l.pad), cy = CY(l.pad), r = wftouch::stickRadius(l);
    const Rect& a = l.controls[4].rect;
    const Rect& c = l.controls[6].rect;
    // UITouch-sized keys (heap pointers).
    const uintptr_t thumb = 0x600001234560, f1 = 0x600001234990, f2 = 0x600001235aa0;
    pad.Began(thumb, cx + r * 0.7f, cy - r * 0.7f);
    pad.Began(f1, CX(a), CY(a));
    pad.Began(f2, CX(c), CY(c));
    CHECK_EQ(pad.Buttons(), kBtnUp | kBtnRight | kBtnA | kBtnC);
    CHECK_EQ(pad.Buttons(), 0x2805);                  // the plan's three-finger mask
    // Sliding a button finger off its square keeps the button.
    pad.Moved(f1, 10, 10);
    CHECK_EQ(pad.Buttons(), 0x2805);
    // Lifting one finger keeps the others.
    pad.Ended(f1);
    CHECK_EQ(pad.Buttons(), kBtnUp | kBtnRight | kBtnC);
    pad.Ended(thumb);
    CHECK_EQ(pad.Buttons(), kBtnC);
    // A finger landing on nothing owns nothing, even if it slides onto a button.
    pad.Began(f1, 400, 100);
    pad.Moved(f1, CX(a), CY(a));
    CHECK_EQ(pad.Buttons(), kBtnC);
    pad.Ended(f1);
    pad.Ended(f2);
    CHECK_EQ(pad.Buttons(), 0);
    // An unknown Moved key behaves as a Began (UIKit can deliver a move first
    // after a view swap).
    pad.Moved(f2, CX(a), CY(a));
    CHECK_EQ(pad.Buttons(), kBtnA);
    // Ending an unknown key is ignored.
    pad.Ended(0x1234);
    CHECK_EQ(pad.Buttons(), kBtnA);
    pad.ReleaseAll();
    CHECK_EQ(pad.Buttons(), 0);
    CHECK_EQ(pad.Count(), 0);
    // Seventeen fingers: the 17th is ignored, the first 16 still count.
    for (int i = 0; i < Pad::kMaxTouches; ++i)
        pad.Began(0x1000 + i, 400, 100);
    pad.Began(0x2000, CX(a), CY(a));
    CHECK_EQ(pad.Count(), Pad::kMaxTouches);
    CHECK_EQ(pad.Buttons(), 0);
    pad.ReleaseAll();
    // Ids are fresh per landing: a key reused by UIKit after lifting is a new finger.
    pad.Began(thumb, CX(a), CY(a));
    pad.Ended(thumb);
    pad.Began(thumb, CX(c), CY(c));
    CHECK_EQ(pad.Buttons(), kBtnC);
    pad.ReleaseAll();
}

static void TestReading()
{
    for (const Dev& d : kDevices)
    {
        Pad pad;
        pad.SetView(d.w, d.h, d.in);
        const Layout full = pad.CurrentLayout();
        const float cx = CX(full.pad), cy = CY(full.pad), r = wftouch::stickRadius(full);
        const Rect& b = full.controls[5].rect;
        const Rect& c = full.controls[6].rect;
        // Thumb on the stick (LEFT) and a finger on B, then a card opens.
        pad.Began(1001, cx - r * 0.8f, cy);
        pad.Began(1002, CX(b), CY(b));
        CHECK_EQ(pad.Buttons(), kBtnLeft | kBtnB);
        pad.SetReading(true);
        CHECK(pad.Reading());
        CHECK_EQ(pad.Buttons(), 0);                           // both let go at once
        const Layout& card = pad.CurrentLayout();
        CHECK(!card.stick);
        CHECK_EQ(card.shown, kBtnA | kBtnC);
        // Neither drawn nor hit: the stick, B, D. Still hit: A, C, in place.
        CHECK_EQ(wftouch::hit(card, cx - r * 0.8f, cy), 0);   // LEFT would close the card
        for (int i = 4; i < 8; ++i)
        {
            const Rect& rr = card.controls[i].rect;
            const bool kept = card.controls[i].bit == kBtnA || card.controls[i].bit == kBtnC;
            CHECK(rr.x0 == full.controls[i].rect.x0 && rr.y0 == full.controls[i].rect.y0);
            CHECK_EQ(wftouch::shown(card, card.controls[i]), kept);
            CHECK_EQ(wftouch::hit(card, CX(rr), CY(rr)), kept ? card.controls[i].bit : 0u);
        }
        // Still-held fingers stay released; a new finger on C works.
        pad.Moved(1001, cx - r * 0.9f, cy);
        CHECK_EQ(pad.Buttons(), 0);
        pad.Began(1003, CX(c), CY(c));
        CHECK_EQ(pad.Buttons(), kBtnC);
        // A finger on C when the card closes keeps C; the full layout is back.
        pad.SetReading(false);
        CHECK_EQ(pad.Buttons(), kBtnC);
        CHECK(pad.CurrentLayout().stick);
        CHECK(SameBits(pad.CurrentLayout(), full));
        pad.Began(1004, cx - r * 0.8f, cy);
        CHECK_EQ(pad.Buttons(), kBtnC | kBtnLeft);
        pad.ReleaseAll();
        // A finger on A or C when a card opens keeps it.
        pad.Began(1005, CX(full.controls[4].rect), CY(full.controls[4].rect));
        pad.SetReading(true);
        CHECK_EQ(pad.Buttons(), kBtnA);
        pad.ReleaseAll();
        pad.SetReading(false);
    }
}

static void TestRotation()
{
    // A held button survives a rotation if the new layout still has it under
    // ownership (owners hold bits, not positions): Android semantics.
    Pad pad;
    pad.SetView(874, 402, Insets{ 0, 62, 20, 62 });
    const Rect a = pad.CurrentLayout().controls[4].rect;
    pad.Began(77, CX(a), CY(a));
    CHECK_EQ(pad.Buttons(), kBtnA);
    pad.SetView(402, 874, Insets{ 62, 0, 34, 0 });
    CHECK_EQ(pad.Buttons(), kBtnA);
    CHECK(pad.CurrentLayout().valid);
    pad.SetView(0, 0, Insets{});          // zero-size view: invalid, but owners keep bits until lifted
    CHECK(!pad.CurrentLayout().valid);
    pad.Ended(77);
    CHECK_EQ(pad.Buttons(), 0);
}

static void TestScript()
{
    ScriptEntry e[kMaxScriptEntries];
    CHECK_EQ(ParseScript("c@1+0.5,d@2+0.25,b@0+1", e, kMaxScriptEntries), 3);
    CHECK_EQ(e[0].button, kBtnC);
    CHECK_EQ(e[1].button, kBtnD);
    CHECK_EQ(e[2].button, kBtnB);
    CHECK_EQ(ParseScript("a@22+0.5,up@27+2,up@29.3+3.2,a@33.4+0.5,a@35.5+0.5", e, kMaxScriptEntries), 5);
    CHECK_EQ(ParseScript("e@1+1", e, kMaxScriptEntries), -1);
    CHECK_EQ(ParseScript("a@1", e, kMaxScriptEntries), -1);
    CHECK_EQ(ParseScript("a@1+0", e, kMaxScriptEntries), -1);
    CHECK_EQ(ParseScript("a@-1+1", e, kMaxScriptEntries), -1);
    CHECK_EQ(ParseScript("a@1+1,", e, kMaxScriptEntries), -1);
    CHECK_EQ(ParseScript("", e, kMaxScriptEntries), 0);
    CHECK_EQ(ParseScript("a@1+1,b@1+1", e, 1), -1);

    const uint32_t all[] = { kBtnUp, kBtnDown, kBtnLeft, kBtnRight, kBtnA, kBtnB, kBtnC, kBtnD };
    for (const Dev& d : kDevices)
    {
        Pad pad;
        pad.SetView(d.w, d.h, d.in);
        for (uint32_t bit : all)
        {
            float x = 0, y = 0;
            CHECK(ButtonCenter(pad.CurrentLayout(), bit, &x, &y));
            pad.Began(0x10, x, y);
            CHECK_EQ(pad.Buttons(), bit);
            pad.Ended(0x10);
        }
        // Over a card, the same points press only A and C.
        pad.SetReading(true);
        for (uint32_t bit : all)
        {
            float x = 0, y = 0;
            CHECK(ButtonCenter(pad.CurrentLayout(), bit, &x, &y));
            pad.Began(0x10, x, y);
            CHECK_EQ(pad.Buttons(), (bit == kBtnA || bit == kBtnC) ? bit : 0u);
            pad.Ended(0x10);
        }
    }
    float x, y;
    CHECK(!ButtonCenter(wftouch::Layout{}, kBtnA, &x, &y));
    Pad pad;
    pad.SetView(874, 402, Insets{});
    CHECK(!ButtonCenter(pad.CurrentLayout(), 1u << 20, &x, &y));
}

int main()
{
    TestLayouts();
    TestStick();
    TestMultiTouch();
    TestReading();
    TestRotation();
    TestScript();
    if (gFailures)
    {
        std::printf("FAIL: %d of %d iOS touch checks\n", gFailures, gChecks);
        return 1;
    }
    std::printf("PASS: %d iOS touch checks (shared hal/touch_controls.h through wf_touch::Pad)\n", gChecks);
    return 0;
}
