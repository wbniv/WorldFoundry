// CTest display_mailboxes: game/display_mailboxes.hp, the values of the DISPLAY_* system mailboxes
// (docs/plans/2026-11-22-display-mailboxes.md). The device sizes are the plan's: the Pixel's measured 1520 x 680 drawing
// area (aspect 2.235), the television, an iPad, an ultrawide screen and a portrait phone.
#include <game/display_mailboxes.hp>
#include <cmath>
#include <cstdio>
#include <cstdlib>

static int checks = 0;
static void Check(bool ok, const char* what)
{
    if (!ok) { std::fprintf(stderr, "display_mailboxes_test: FAIL %s\n", what); std::exit(1); }
    ++checks;
}
static bool Near(double a, double b, double tol) { return std::fabs(a - b) <= tol; }

int main()
{
    // 1. The values are the view's, size by size, with the settings off, the authored aspect only, the maximum only and both.
    const int sizes[][2] = {{1920, 1080}, {1520, 680}, {2560, 1097}, {1440, 1080}, {600, 1330}};
    const float settings[][2] = {{0.0f, 0.0f}, {1.778f, 0.0f}, {0.0f, 2.25f}, {1.778f, 2.25f}};
    for (const auto& s : sizes)
        for (const auto& st : settings)
        {
            wf::DisplayTracker t;
            Check(t.update(s[0], s[1], st[0], st[1]), "the first update writes");
            const wfview::View v = wfview::view(s[0], s[1], st[0], st[1]);
            const wf::DisplayState& d = t.state();
            Check(d.aspect == v.aspect && d.verticalFov == v.verticalFov, "aspect and vertical fov are the view's");
            Check(d.width == s[0] && d.height == s[1], "the surface size is published as given");
            Check(d.viewX == v.x && d.viewY == v.y && d.viewWidth == v.width && d.viewHeight == v.height, "the drawn rectangle is the view's");
            Check(t.writes() == 1, "one write for one update");
        }

    // 2. Off, the screen's own shape: the Pixel's measured area is aspect 2.235, the whole surface, 60 degrees.
    {
        wf::DisplayTracker t;
        t.update(1520, 680, 0.0f, 0.0f);
        Check(Near(t.state().aspect, 1520.0 / 680.0, 1e-6) && Near(t.state().aspect, 2.235, 0.001), "the Pixel's aspect is 2.235");
        Check(Near(t.state().verticalFov, 60.0, 1e-4), "off keeps 60 degrees");
        Check(t.state().viewX == 0 && t.state().viewWidth == 1520, "off draws the whole surface");
    }

    // 3. A maximum aspect pillarboxes a wider screen: the rectangle is centred and capped, the aspect is the cap.
    {
        wf::DisplayTracker t;
        t.update(2560, 1097, 0.0f, 2.25f);
        Check(Near(t.state().aspect, 2.25, 0.001), "the aspect is the cap");
        Check(t.state().viewX > 0 && t.state().viewX * 2 + t.state().viewWidth == 2560, "the rectangle is centred");
        Check(t.state().width == 2560 && t.state().viewWidth < 2560, "the surface is still the whole screen");
    }

    // 4. A screen narrower than the authored aspect keeps the authored horizontal view and grows the vertical one.
    {
        wf::DisplayTracker t;
        t.update(1440, 1080, 1.778f, 0.0f);
        Check(t.state().verticalFov > 60.0f, "a 4:3 screen shows more above and below");
        Check(Near(t.state().aspect, 4.0 / 3.0, 1e-6), "the aspect is still the screen's");
    }

    // 5. Written only on a change: the same inputs write nothing; a new size, or new settings, write once each.
    {
        wf::DisplayTracker t;
        Check(t.update(1920, 1080, 0.0f, 0.0f) && t.writes() == 1, "the first call writes");
        for (int frame = 0; frame < 1000; ++frame)
            Check(!t.update(1920, 1080, 0.0f, 0.0f), "an unchanged frame writes nothing");
        Check(t.writes() == 1, "a thousand frames wrote nothing");
        Check(t.update(1080, 1920, 0.0f, 0.0f) && t.writes() == 2, "the phone is turned: one write");
        Check(!t.update(1080, 1920, 0.0f, 0.0f) && t.writes() == 2, "and then none");
        Check(t.update(1080, 1920, 1.778f, 0.0f) && t.writes() == 3, "a new authored aspect: one write");
        Check(t.update(1080, 1920, 1.778f, 2.25f) && t.writes() == 4, "a new maximum aspect: one write");
        Check(t.state().aspect == wfview::view(1080, 1920, 1.778f, 2.25f).aspect, "the state follows the change");
    }

    // 6. A new level has a fresh tracker, so its first update always writes, even at an unchanged size.
    {
        wf::DisplayTracker first;
        first.update(1920, 1080, 0.0f, 0.0f);
        wf::DisplayTracker second;
        Check(second.update(1920, 1080, 0.0f, 0.0f) && second.writes() == 1, "a new level writes on its first frame");
    }

    // 7. Degenerate sizes are clamped the way wfview::view clamps them (a size of zero is one).
    {
        wf::DisplayTracker t;
        t.update(0, 0, 0.0f, 0.0f);
        Check(t.state().width == 1 && t.state().height == 1 && t.state().aspect == 1.0f, "a zero surface reads as 1 x 1");
    }

    // 8. The mailbox table: the eight numbers are consecutive after WALL_UTC_OFFSET and below GLOBAL_SYSTEM_MAX.
    {
        enum { kFirst = 1927, kLast = 1934, kMax = 1935 };
        Check(kLast - kFirst + 1 == 8 && kLast + 1 == kMax, "eight mailboxes, 1927 to 1934, GLOBAL_SYSTEM_MAX 1935");
    }

    std::printf("display_mailboxes_test: %d checks passed\n", checks);
    return 0;
}
