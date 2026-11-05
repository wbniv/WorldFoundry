// CTest authored_view: gfx/authored_view.hp, the view a level's authored frame
// needs on each screen (finding-your-way docs/plans/2026-11-02-fill-screen-
// keep-authored-frame.md). The device sizes are the measured ones from the
// plan; the expected angles are its table.
#include <gfx/authored_view.hp>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <initializer_list>
#include <cstring>

static int checks = 0;

static void Check(bool ok, const char* what)
{
    if (!ok) { std::fprintf(stderr, "authored_view_test: FAIL %s\n", what); std::exit(1); }
    ++checks;
}

static bool Near(double a, double b, double tol) { return std::fabs(a - b) <= tol; }

struct Device { const char* name; int w, h; double hfov, vfov; };

int main()
{
    const float A0 = 1.778f, M = 2.25f;

    // Off (A0 = 0, M = 0): today's 60 degrees and float(w) / float(h), bit for bit,
    // the full surface, no pillarbox, at every size including absurdly wide ones.
    const int sizes[][2] = {{1920, 1080}, {2131, 1008}, {2244, 1008}, {2622, 1206}, {2752, 2064},
                            {3440, 1440}, {3840, 1080}, {640, 480}, {1, 1}};
    for (const auto& s : sizes)
    {
        const wfview::View v = wfview::view(s[0], s[1], 0.0f, 0.0f);
        Check(v.verticalFov == 60.0f, "off: vertical view is exactly 60");
        Check(v.aspect == float(s[0]) / float(s[1]), "off: aspect is exactly float(w) / float(h)");
        Check(v.x == 0 && v.y == 0 && v.width == s[0] && v.height == s[1] && !v.pillarbox, "off: whole surface");
    }

    // The plan's table, A0 = 1.778 and M = 2.25.
    const Device devices[] = {
        {"Chromecast",           1920, 1080,  91.5, 60.0},
        {"Pixel 8 Pro (usable)", 2131, 1008, 101.3, 60.0},
        {"Pixel 8 Pro (panel)",  2244, 1008, 104.2, 60.0},
        {"iPhone 17 Pro",        2622, 1206, 102.9, 60.0},
        {"iPad Pro 13",          2752, 2064,  91.5, 75.2},
    };
    for (const Device& d : devices)
    {
        const wfview::View v = wfview::view(d.w, d.h, A0, M);
        char what[128];
        std::snprintf(what, sizeof what, "%s: hfov %.1f vfov %.1f (got %.2f %.2f)", d.name, d.hfov, d.vfov,
                      v.HorizontalFov(), v.verticalFov);
        Check(Near(v.HorizontalFov(), d.hfov, 0.05) && Near(v.verticalFov, d.vfov, 0.05), what);
        Check(!v.pillarbox && v.width == d.w && v.height == d.h && v.aspect == float(d.w) / float(d.h),
              "below the cap: whole surface, aspect unchanged");
        // The authored frame's horizontal view is visible in full everywhere.
        Check(v.HorizontalFov() >= 91.5 - 0.05, "the authored 16:9 width is always inside the view");
    }

    // a = A0: exactly the authored frame, 60 degrees.
    {
        const wfview::View v = wfview::view(1778, 1000, A0, M);
        Check(Near(v.verticalFov, 60.0, 1e-4) && Near(v.HorizontalFov(), 91.5, 0.05), "a = A0 gives 60 / 91.5");
    }
    // A screen narrower than 16:9 keeps the authored horizontal view exactly.
    {
        const wfview::View h0 = wfview::view(1778, 1000, A0, 0.0f);
        for (int w : {500, 1000, 1333, 1700})
        {
            const wfview::View v = wfview::view(w, 1000, A0, 0.0f);
            Check(Near(v.HorizontalFov(), h0.HorizontalFov(), 1e-3), "narrow: horizontal view stays the authored one");
            Check(v.verticalFov > 60.0f, "narrow: vertical view grows");
        }
    }

    // Over the cap: a centred rectangle of aspect 2.25 at full height.
    struct Wide { int w, h; } wide[] = {{2520, 1080}, {3840, 1080}, {3440, 1440}};   // 2.333, 3.556, 2.389
    for (const Wide& s : wide)
    {
        const wfview::View v = wfview::view(s.w, s.h, A0, M);
        const int expectW = int(std::lround(s.h * 2.25));
        Check(v.pillarbox, "over the cap: pillarbox");
        Check(v.height == s.h && v.y == 0, "over the cap: full height");
        Check(v.width == expectW && v.x == (s.w - expectW) / 2, "over the cap: centred, aspect 2.25");
        Check(Near(v.aspect, 2.25, 0.001) && Near(v.verticalFov, 60.0, 1e-4), "over the cap: 60 degrees at 2.25");
        Check(Near(v.HorizontalFov(), wfview::view(2250, 1000, A0, M).HorizontalFov(), 0.05),
              "over the cap: the same picture as a 2.25 screen");
    }
    // Exactly at the cap: no pillarbox.
    Check(!wfview::view(2250, 1000, A0, M).pillarbox, "a = M is not pillarboxed");
    // The cap works without an authored aspect.
    Check(wfview::view(3840, 1080, 0.0f, M).pillarbox, "the cap is independent of A0");

    // Runtime arguments override the level; malformed ones are ignored.
    wfview::levelSettings() = {0.0f, 0.0f};
    Check(!wfview::active(), "nothing set: inactive");
    Check(wfview::parseArgument("--authored-aspect=1.778"), "parses --authored-aspect=");
    Check(wfview::parseArgument("--maximum-aspect=2.25"), "parses --maximum-aspect=");
    Check(!wfview::parseArgument("--vram-width=5120"), "other arguments are not ours");
    Check(wfview::parseArgument("--maximum-aspect=wide"), "a malformed value is still ours");
    Check(Near(wfview::effective().authoredAspect, 1.778, 1e-6) && Near(wfview::effective().maximumAspect, 2.25, 1e-6),
          "arguments set the effective values; a malformed one leaves the earlier value");
    wfview::levelSettings() = {1.5f, 3.0f};
    Check(Near(wfview::effective().authoredAspect, 1.778, 1e-6), "an argument wins over the level");
    wfview::argumentOverrides() = {-1.0f, -1.0f};
    Check(Near(wfview::effective().authoredAspect, 1.5, 1e-6) && wfview::active(), "without arguments the level applies");

    // The VIEW line follows the applied surface (regression: Codemagic build 6ae7e5ed,
    // where a one-shot line at level load logged iOS's 800x600 fallback on the iPhone).
    wfview::argumentOverrides() = {1.778f, 2.25f};
    wfview::source() = "argument";
    Check(wfview::report(800, 600), "report: the first view is logged");
    Check(!wfview::report(800, 600), "report: an unchanged view is not logged again");
    Check(wfview::report(2622, 1206), "report: the real surface, once known, is logged");
    Check(!wfview::report(0, 0), "report: no surface, no line");
    wfview::argumentOverrides() = {0.0f, 2.25f};
    Check(wfview::report(2622, 1206), "report: a settings change is logged");
    wfview::source() = "level";
    Check(wfview::report(2622, 1206), "report: a source change is logged");
    {
        wfview::argumentOverrides() = {1.778f, 2.25f};
        wfview::source() = "argument";
        char line[256];
        wfview::formatLine(line, sizeof line, 2622, 1206);
        Check(std::strcmp(line, "VIEW authored=1.778 screen=2.174 hfov=102.9 vfov=60.0 maximum=2.250 "
                                "surface=2622x1206 viewport=0,0,2622x1206 pillarbox=0 source=argument") == 0,
              "formatLine: the iPhone 17 Pro line");
        wfview::formatLine(line, sizeof line, 2752, 2064);
        Check(std::strcmp(line, "VIEW authored=1.778 screen=1.333 hfov=91.5 vfov=75.2 maximum=2.250 "
                                "surface=2752x2064 viewport=0,0,2752x2064 pillarbox=0 source=argument") == 0,
              "formatLine: the iPad Pro 13 line");
    }

    std::printf("authored_view_test: PASS (%d checks)\n", checks);
    return 0;
}
