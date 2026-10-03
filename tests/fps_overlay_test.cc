#include <game/fps_overlay.hp>
#include <cstdio>
#include <cstdlib>
#include <cstring>

void _sys_assert(int, const char* expression, const char* file, int line)
{
    std::fprintf(stderr, "assert %s at %s:%d\n", expression, file, line);
    std::abort();
}

static void Check(bool ok, const char* message)
{
    if (!ok) { std::fprintf(stderr, "FAIL: %s\n", message); std::exit(1); }
}

int main()
{
    fpscounter::Overlay overlay;
    struct Sample { float fps; const char* text; };
    for (const auto& sample : {Sample{0, "0.0"}, Sample{59.75f, "59.8"},
                              Sample{2, "2.0"}, Sample{0.5f, "0.5"}, Sample{0.04f, "0.0"}})
    {
        for (const auto& size : {std::pair<int, int>{320, 240}, {1920, 1080}, {3840, 2160}})
        {
            const int count = overlay.Build(Scalar::FromFloat(sample.fps), size.first, size.second);
            Check(!std::strcmp(overlay.Text(), sample.text), "number only with one decimal, including reset");
            const auto* rects = overlay.Rects();
            Check(count > 1, "plate and text geometry are present");
            for (int i = 0; i < count; ++i)
            {
                const auto& r = rects[i];
                Check(r.x0 >= 0 && r.y0 >= 0 && r.x1 <= size.first && r.y1 <= size.second &&
                      r.x1 > r.x0 && r.y1 > r.y0, "all overlay geometry fits the surface");
            }
            Check(rects[0].x0 > size.first * 0.5f && rects[0].y0 > size.second * 0.5f,
                  "overlay is in the bottom-right corner");
            const auto* cached = rects;
            Check(overlay.Build(Scalar::FromFloat(sample.fps), size.first, size.second) == count && overlay.Rects() == cached,
                  "unchanged display reuses cached geometry");
        }
    }
    Check(overlay.Build(Scalar(1, 0), 0, 0) == 0, "no geometry without a drawable surface");
    std::puts("PASS: number formatting, fractional stalls, reset, surface bounds, cached geometry");
}
