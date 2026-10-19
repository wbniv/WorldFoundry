// tests/touch_pad_test.cc — unit test for the platform-independent half of
// the iOS touch shim (wfsource/source/hal/ios/touch_pad.{hp,cc}).
// Built and run by tests/test_ios_touch_pad.py with the host g++; prints one
// line per failed check and exits non-zero on any failure.

#include "touch_pad.hp"

#include <cstdio>

using namespace wf_touch;

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

static bool Near(float a, float b) { return a - b < 0.01f && b - a < 0.01f; }

static bool Inside(const Rect& inner, float x0, float y0, float x1, float y1)
{
    return inner.x0 >= x0 && inner.y0 >= y0 && inner.x1 <= x1 && inner.y1 <= y1;
}

// Invariants every valid layout must satisfy, whatever the device.
static void CheckInvariants(const char* name, float w, float h, const Insets& in)
{
    const Layout l = ComputeLayout(w, h, in);
    const float sx0 = in.left, sy0 = in.top, sx1 = w - in.right, sy1 = h - in.bottom;
    const int before = gFailures;
    CHECK(l.valid);
    CHECK(Inside(l.dpad, sx0, sy0, sx1, sy1));
    CHECK(Inside(l.a,    sx0, sy0, sx1, sy1));
    CHECK(Inside(l.b,    sx0, sy0, sx1, sy1));
    CHECK(l.dpad.x1 + kMarginPt <= l.b.x0 + 0.01f);   // pad and B never overlap
    CHECK(Near(l.b.x1, l.a.x0));                      // B abuts A, as on Android
    CHECK(Near(l.a.x1, sx1 - kMarginPt));             // A in the corner
    CHECK(Near(l.a.y1, sy1 - kMarginPt));
    CHECK(Near(l.dpad.y1, sy1 - kMarginPt));          // same bottom row
    CHECK(Near(l.dpad.x0, sx0 + kMarginPt));
    CHECK(l.cell <= kMaxCellPt);
    // Every arm and both buttons hit exactly their own bit at their centre.
    float x, y;
    const uint32_t kSingles[] = { kBtnUp, kBtnDown, kBtnLeft, kBtnRight, kBtnA, kBtnB };
    for (uint32_t bit : kSingles) {
        CHECK(ButtonCenter(l, bit, &x, &y));
        CHECK_EQ(HitTest(l, x, y), bit);
    }
    if (gFailures != before)
        std::printf("  ^ in layout %s (%gx%g, cell %.2f)\n", name, w, h, l.cell);
}

static void TestDeviceSizes()
{
    // Landscape point sizes and safe-area insets (top, left, bottom, right).
    struct Dev { const char* name; float w, h; Insets in; float minCell, maxCell; };
    const Dev kDevs[] = {
        { "iPhone SE 1st gen", 568, 320, {0, 0, 0, 0},    44, 50 },
        { "iPhone SE 2/3",     667, 375, {0, 0, 0, 0},    55, 57 },
        { "iPhone 15",         852, 393, {0, 59, 21, 59}, 58, 60 },
        { "iPhone 15 Pro Max", 932, 430, {0, 59, 21, 59}, 64, 65 },
        { "iPad mini 6",      1133, 744, {24, 0, 20, 0},  72, 72 },
        { "iPad 9.7",         1024, 768, {20, 0, 0, 0},   72, 72 },
        { "iPad Air 11",      1180, 820, {24, 0, 20, 0},  72, 72 },
        { "iPad Pro 12.9",    1366,1024, {24, 0, 20, 0},  72, 72 },
    };
    for (const Dev& d : kDevs) {
        CheckInvariants(d.name, d.w, d.h, d.in);
        const Layout l = ComputeLayout(d.w, d.h, d.in);
        CHECK(l.cell >= d.minCell && l.cell <= d.maxCell);
        CHECK(l.cell >= kMinCellPt);               // never below a 44 pt target
    }
    // iPad: clamped, so the A button is ~131 pt, not a quarter of the screen.
    const Layout pro = ComputeLayout(1366, 1024, Insets{});
    CHECK(Near(pro.cell, kMaxCellPt));
    CHECK(pro.a.Width() < 140.0f);
}

static void TestNarrowWindowShrinks()
{
    // iPad Split View sliver: pad + A/B do not fit at 44 pt, so both shrink
    // uniformly and still do not overlap.
    CheckInvariants("iPad split 1/3", 320, 768, Insets{});
    const Layout l = ComputeLayout(320, 768, Insets{});
    CHECK(l.cell < kMinCellPt);
    // Very short window: height limits the cell instead.
    CheckInvariants("short strip", 900, 120, Insets{});
    CHECK(ComputeLayout(900, 120, Insets{}).cell <= (120.0f - 2 * kMarginPt) / 3.0f + 0.01f);
}

static void TestSafeAreaInsets()
{
    // Landscape-left vs landscape-right: the notch side moves, the pad follows.
    const Layout left  = ComputeLayout(852, 393, Insets{0, 59, 21, 0});
    const Layout right = ComputeLayout(852, 393, Insets{0, 0, 21, 59});
    CHECK(Near(left.dpad.x0, 59 + kMarginPt));
    CHECK(Near(right.dpad.x0, kMarginPt));
    CHECK(Near(left.a.x1, 852 - kMarginPt));
    CHECK(Near(right.a.x1, 852 - 59 - kMarginPt));
    CHECK(Near(left.dpad.y1, 393 - 21 - kMarginPt));
    // A touch in the inset (under the home indicator) hits nothing.
    CHECK_EQ(HitTest(left, left.a.CenterX(), 393 - 5), 0u);
}

static void TestDPadCells()
{
    const Layout l = ComputeLayout(852, 393, Insets{});
    const float c = l.cell;
    auto at = [&](int col, int row) {
        return HitTest(l, l.dpad.x0 + c * (col + 0.5f), l.dpad.y0 + c * (row + 0.5f));
    };
    CHECK_EQ(at(1, 0), kBtnUp);
    CHECK_EQ(at(1, 2), kBtnDown);
    CHECK_EQ(at(0, 1), kBtnLeft);
    CHECK_EQ(at(2, 1), kBtnRight);
    CHECK_EQ(at(1, 1), 0u);                          // dead centre
    CHECK_EQ(at(0, 0), kBtnUp | kBtnLeft);           // diagonals
    CHECK_EQ(at(2, 0), kBtnUp | kBtnRight);
    CHECK_EQ(at(0, 2), kBtnDown | kBtnLeft);
    CHECK_EQ(at(2, 2), kBtnDown | kBtnRight);
    // Edges: inclusive top-left, exclusive bottom-right (Android's convention).
    CHECK_EQ(HitTest(l, l.dpad.x0, l.dpad.y0 + 1.5f * c), kBtnLeft);
    CHECK_EQ(HitTest(l, l.dpad.x1, l.dpad.y0 + 1.5f * c), 0u);
    CHECK_EQ(HitTest(l, l.dpad.x0 - 0.5f, l.dpad.y0 + 1.5f * c), 0u);
    // Nowhere near a control.
    CHECK_EQ(HitTest(l, 426, 100), 0u);
    // Invalid layout hits nothing.
    const Layout none = ComputeLayout(0, 0, Insets{});
    CHECK(!none.valid);
    CHECK_EQ(HitTest(none, 0, 0), 0u);
}

static void TestChordsAndDrags()
{
    const Layout l = ComputeLayout(852, 393, Insets{0, 59, 21, 59});
    float ax, ay, bx, by, rx, ry, lx, ly;
    ButtonCenter(l, kBtnA, &ax, &ay);
    ButtonCenter(l, kBtnB, &bx, &by);
    ButtonCenter(l, kBtnRight, &rx, &ry);
    ButtonCenter(l, kBtnLeft, &lx, &ly);

    TouchTracker t;
    CHECK_EQ(t.Buttons(l), 0u);

    // A+B chord with two fingers.
    t.Began(1, ax, ay);
    t.Began(2, bx, by);
    CHECK_EQ(t.Buttons(l), kBtnA | kBtnB);
    t.Ended(1);
    CHECK_EQ(t.Buttons(l), kBtnB);                  // lifting A keeps B held
    t.Ended(2);
    CHECK_EQ(t.Buttons(l), 0u);

    // D-pad and A held at the same time.
    t.Began(10, rx, ry);
    t.Began(11, ax, ay);
    CHECK_EQ(t.Buttons(l), kBtnRight | kBtnA);

    // Drag the D-pad finger across: right → centre → left → off the pad.
    t.Moved(10, l.dpad.CenterX(), l.dpad.CenterY());
    CHECK_EQ(t.Buttons(l), kBtnA);
    t.Moved(10, lx, ly);
    CHECK_EQ(t.Buttons(l), kBtnLeft | kBtnA);
    t.Moved(10, 426, 100);
    CHECK_EQ(t.Buttons(l), kBtnA);
    // Slide the A finger onto B.
    t.Moved(11, bx, by);
    CHECK_EQ(t.Buttons(l), kBtnB);

    // Cancel (UIKit touchesCancelled → Ended) clears only that finger;
    // ReleaseAll (suspend) clears everything.
    t.Moved(10, rx, ry);
    CHECK_EQ(t.Buttons(l), kBtnRight | kBtnB);
    t.Ended(11);
    CHECK_EQ(t.Buttons(l), kBtnRight);
    t.Began(12, ax, ay);
    t.ReleaseAll();
    CHECK_EQ(t.Count(), 0);
    CHECK_EQ(t.Buttons(l), 0u);

    // Ending an unknown touch is harmless; moving an unknown one adopts it
    // (a finger held across a suspend that was released by ReleaseAll).
    t.Ended(999);
    CHECK_EQ(t.Count(), 0);
    t.Moved(13, ax, ay);
    CHECK_EQ(t.Buttons(l), kBtnA);
    t.Began(13, bx, by);                            // re-Began updates, no dup
    CHECK_EQ(t.Count(), 1);
    CHECK_EQ(t.Buttons(l), kBtnB);
    t.ReleaseAll();

    // More fingers than slots: extras ignored, no overflow.
    for (int i = 0; i < TouchTracker::kMaxTouches + 4; ++i)
        t.Began(100 + i, ax, ay);
    CHECK_EQ(t.Count(), TouchTracker::kMaxTouches);
    CHECK_EQ(t.Buttons(l), kBtnA);

    // Layout change (rotation) while held: the stored point is re-hit-tested.
    t.ReleaseAll();
    t.Began(1, ax, ay);
    const Layout other = ComputeLayout(1366, 1024, Insets{});
    CHECK_EQ(t.Buttons(other), 0u);
}

static void TestScript()
{
    ScriptEntry e[kMaxScriptEntries];
    CHECK_EQ(ParseScript("", e, kMaxScriptEntries), 0);
    CHECK_EQ(ParseScript(nullptr, e, kMaxScriptEntries), 0);

    const int n = ParseScript("right@2+3,a@6+0.2,up@7.5+1,b@7.5+1", e, kMaxScriptEntries);
    CHECK_EQ(n, 4);
    CHECK_EQ(e[0].button, kBtnRight);
    CHECK(Near(e[0].start, 2) && Near(e[0].duration, 3));
    CHECK_EQ(e[1].button, kBtnA);
    CHECK(Near(e[1].duration, 0.2f));
    CHECK_EQ(e[2].button, kBtnUp);
    CHECK(Near(e[2].start, 7.5f));
    CHECK_EQ(e[3].button, kBtnB);

    const char* kBad[] = {
        "x@1+1", "a@+1", "a@1+", "a@1+0", "a@1", "a1+1", "a@1+1,", "a@1+1;b@2+1",
        "a@-1+1", "A@1+1", "a@1+1 ",
    };
    for (const char* s : kBad) {
        const int r = ParseScript(s, e, kMaxScriptEntries);
        if (r != -1) std::printf("  bad script accepted: \"%s\" -> %d\n", s, r);
        CHECK_EQ(r, -1);
    }
    CHECK_EQ(ParseScript("a@1+1,b@2+1", e, 1), -1);  // over capacity
}

int main()
{
    TestDeviceSizes();
    TestNarrowWindowShrinks();
    TestSafeAreaInsets();
    TestDPadCells();
    TestChordsAndDrags();
    TestScript();
    std::printf("%s: %d checks, %d failures\n",
                gFailures ? "FAIL" : "PASS", gChecks, gFailures);
    return gFailures ? 1 : 0;
}
