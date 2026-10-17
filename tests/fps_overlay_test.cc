#include <game/fps_overlay.hp>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <fstream>
#include <iterator>
#include <vector>

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
    // The number is drawn in the UI font (game/ui_font.hp): the source tree's bake.
    std::ifstream file(WF_UI_FONT_SOURCE_PATH, std::ios::binary);
    static const std::vector<char> atlas((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
    const char* error = nullptr;
    Check(wfui::Load(atlas.data(), atlas.size(), error), error ? error : "ui-font.wfga");

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
            const auto& glyphs = overlay.Glyphs();
            Check(count == 1 && glyphs.size() == std::strlen(sample.text), "a plate and one glyph per character");
            const auto& r = rects[0];
            Check(r.x0 >= 0 && r.y0 >= 0 && r.x1 <= size.first && r.y1 <= size.second &&
                  r.x1 > r.x0 && r.y1 > r.y0, "the plate fits the surface");
            Check(r.x0 > size.first * 0.5f && r.y0 > size.second * 0.5f, "overlay is in the bottom-right corner");
            float left = glyphs[0].x0, top = glyphs[0].y0, right = glyphs[0].x1, bottom = glyphs[0].y1;
            for (const auto& g : glyphs)
            {
                Check(g.x1 > g.x0 && g.y1 > g.y0 && g.u1 > g.u0 && g.v1 > g.v0, "every glyph is a textured quad");
                left = std::min(left, g.x0); top = std::min(top, g.y0);
                right = std::max(right, g.x1); bottom = std::max(bottom, g.y1);
            }
            const float pad = 1.5f * std::max(1.0f, std::min(float(size.first), float(size.second)) / 360.0f);
            Check(std::fabs(left - r.x0 - pad) < 0.001f && std::fabs(top - r.y0 - pad) < 0.001f &&
                  std::fabs(r.x1 - right - pad) < 0.001f && std::fabs(r.y1 - bottom - pad) < 0.001f,
                  "plate has tight equal padding around actual glyph bounds");
            Check(left == std::floor(left) && top == std::floor(top), "glyphs start on whole pixels");
            const auto* cached = rects;
            const auto* cachedGlyphs = glyphs.data();
            Check(overlay.Build(Scalar::FromFloat(sample.fps), size.first, size.second) == count && overlay.Rects() == cached
                  && overlay.Glyphs().data() == cachedGlyphs, "unchanged display reuses cached geometry");
        }
    }
    Check(overlay.Build(Scalar(1, 0), 0, 0) == 0 && overlay.Glyphs().empty(), "no geometry without a drawable surface");
    std::puts("PASS: number formatting, fractional stalls, reset, surface bounds, glyph plate, cached geometry");
}
