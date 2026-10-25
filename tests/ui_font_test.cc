// ui_font_test: the committed UI atlas (wfsource/source/game/ui-font.wfga, baked by
// scripts/bake-ui-font.py) against the engine's own reader, bitmaptext::Catalog, and
// the wfui layout. docs/plans/2026-10-17-settings-editor-font.md, verification 3 and 4.
//
//   ui_font_test <ui-font.wfga>
#include <game/ui_font.hp>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

static int failures = 0;
static void Check(bool ok, const std::string& what)
{
    std::printf("%s  %s\n", ok ? "ok  " : "FAIL", what.c_str());
    if (!ok) ++failures;
}

// UTF-8 for one code point.
static std::string Utf8(int cp)
{
    std::string s;
    if (cp < 0x80) s += char(cp);
    else if (cp < 0x800) { s += char(0xC0 | cp >> 6); s += char(0x80 | (cp & 63)); }
    else { s += char(0xE0 | cp >> 12); s += char(0x80 | (cp >> 6 & 63)); s += char(0x80 | (cp & 63)); }
    return s;
}

int main(int argc, char** argv)
{
    if (argc != 2 || !std::strcmp(argv[1], "-h") || !std::strcmp(argv[1], "--help"))
    {
        std::puts("usage: ui_font_test <ui-font.wfga>");
        return argc == 2 ? 0 : 2;
    }
    std::ifstream file(argv[1], std::ios::binary);
    const std::vector<char> bytes((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());

    // Catalog::Load's WFGA v1 checks, through the engine's own reader.
    bitmaptext::Catalog catalog;
    const char* error = nullptr;
    Check(catalog.Load(bytes.data(), bytes.size(), error), std::string("Catalog::Load accepts it") + (error ? std::string(": ") + error : ""));
    Check(catalog.Width() == 1024 && catalog.Height() == 2048, "the atlas is 1024x2048, 8-bit coverage");
    Check(catalog.Pixels()[0] == 255, "texel (0,0) is the reserved solid texel");
    Check(wfui::Load(bytes.data(), bytes.size(), error), std::string("wfui::Load accepts it") + (error ? std::string(": ") + error : ""));
    if (!wfui::Loaded()) { std::puts("FAIL"); return 1; }

    // The seven variants of F3, in order.
    const char* names[] = {"small", "body", "body-bold", "title", "menu", "menu-bold", "display"};
    const int faces[] = {0, 0, 1, 1, 0, 1, 1}, pixels[] = {28, 36, 36, 46, 56, 56, 80};
    for (int v = 0; v < wfui::VariantCount; ++v)
    {
        const bitmaptext::Variant var = catalog.GetVariant(v);
        Check(var.face == faces[v] && var.pixels == pixels[v],
              std::string("variant ") + names[v] + " is " + (faces[v] ? "SemiBold " : "Regular ") + std::to_string(pixels[v]));
    }

    // Coverage: printable ASCII, U+00A0-00FF and the nine punctuation marks, less the two
    // code points Atkinson Hyperlegible Next does not map (U+00AD soft hyphen, U+00B5 micro).
    std::vector<int> want;
    for (int cp = 0x20; cp < 0x7F; ++cp) want.push_back(cp);
    for (int cp = 0xA0; cp < 0x100; ++cp) if (cp != 0xAD && cp != 0xB5) want.push_back(cp);
    for (int cp : {0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2026, 0x2212}) want.push_back(cp);
    Check(want.size() == 198, "the coverage list has 198 code points");
    int missing = 0;
    for (int v = 0; v < wfui::VariantCount; ++v)
        for (int cp : want)
        {
            bitmaptext::Glyph g;
            if (!catalog.FindGlyph(v, cp, g)) { if (missing++ < 10) std::printf("  missing U+%04X in %s\n", cp, names[v]); }
        }
    Check(missing == 0, "every code point of the list has a glyph in all seven variants (" + std::to_string(missing) + " missing)");

    // U+2190 (the remote's Back arrow) is not in the font: it lays out as '?'.
    for (int v = 0; v < wfui::VariantCount; ++v)
    {
        bitmaptext::Glyph g;
        std::vector<bitmaptext::Quad> arrow, question;
        wfui::Text(arrow, 100, 100, wfui::Variant(v), 0xFFFFFFFFu, Utf8(0x2190));
        wfui::Text(question, 100, 100, wfui::Variant(v), 0xFFFFFFFFu, "?");
        const bool same = arrow.size() == 1 && question.size() == 1 && !std::memcmp(&arrow[0], &question[0], sizeof(arrow[0]));
        Check(!catalog.FindGlyph(v, 0x2190, g) && same && wfui::Width(wfui::Variant(v), Utf8(0x2190)) == wfui::Width(wfui::Variant(v), "?"),
              std::string("U+2190 lays out as '?' in ") + names[v]);
    }

    // "WF Aquarium" in display measures as the bundle's advances plus kerning.
    const char* title = "WF Aquarium";
    int sum = 0, previous = 0;
    for (const char* p = title; *p; ++p)
    {
        bitmaptext::Glyph g;
        catalog.FindGlyph(wfui::Display, *p, g);
        sum += g.advance + (previous ? catalog.Kerning(wfui::Display, previous, *p) : 0);
        previous = *p;
    }
    const float expected = float(sum) / 64.0f, measured = wfui::Width(wfui::Display, title);
    char line[160];
    std::snprintf(line, sizeof(line), "\"WF Aquarium\" in display: Width %.3f px, advances plus kerning %.3f px", measured, expected);
    Check(std::fabs(measured - expected) <= 0.5f, line);
    int kerned = 0;
    for (const char* p = title; p[0] && p[1]; ++p) kerned += catalog.Kerning(wfui::Display, p[0], p[1]) != 0;
    Check(kerned > 0, "at least one pair of \"WF Aquarium\" is kerned (" + std::to_string(kerned) + ")");
    // And the quads land where those advances put them: the last glyph's left edge.
    std::vector<bitmaptext::Quad> quads;
    wfui::Text(quads, 0, 0, wfui::Display, 0xFFFFFFFFu, title, wfui::Baseline);
    bitmaptext::Glyph m;
    catalog.FindGlyph(wfui::Display, 'm', m);
    const float pen = expected - float(m.advance) / 64.0f;
    Check(quads.size() == std::strlen(title) - 1 && std::fabs(quads.back().x0 - (pen + float(m.bearingX))) <= 0.5f,
          "the glyph quads follow the same advances (one quad per visible glyph)");

    // The proportional path, by default and by name, is the layout from before Pitch
    // existed: the same quads, bit for bit, as this restatement of it.
    struct Case { wfui::Variant v; const char* s; wfui::Anchor anchor; wfui::Align align; wfui::Transform t; };
    const wfui::Transform scaled = {0.5f, 13.25f, 7.75f}, big = {2.0f, 1914.0f, 1068.0f};
    for (const Case& c : {Case{wfui::Display, title, wfui::Top, wfui::Left, wfui::Transform()},
                          Case{wfui::Small, "59.8", wfui::Baseline, wfui::Right, scaled},
                          Case{wfui::Body, "Planted Tank \xE2\x80\x94 1 / 7", wfui::Middle, wfui::Centre, big},
                          Case{wfui::MenuBold, "AVAWAY 10.01", wfui::Top, wfui::Right, scaled}})
    {
        std::vector<bitmaptext::Quad> want, byDefault, byName;
        const float width = wfui::Width(c.v, c.s);
        float x = 3.0f;
        if (c.align == wfui::Centre) x -= width * 0.5f;
        else if (c.align == wfui::Right) x -= width;
        const bitmaptext::Variant var = catalog.GetVariant(c.v);
        const float baseline = c.anchor == wfui::Top ? 5.0f + float(var.ascent)
                             : c.anchor == wfui::Middle ? 5.0f + float(var.ascent - var.descent) * 0.5f : 5.0f;
        const float by = std::floor(c.t.oy + baseline * c.t.s + 0.5f);
        float pen = x;
        previous = 0;
        for (const char* p = c.s; *p; )
        {
            int offset = int(p - c.s), cp = 0;
            bitmaptext::Decode(c.s, int(std::strlen(c.s)), offset, cp);
            p = c.s + offset;
            bitmaptext::Glyph g;
            catalog.FindGlyph(c.v, cp, g);
            if (previous) pen += float(catalog.Kerning(c.v, previous, cp)) / 64.0f;
            if (g.width > 0 && g.height > 0)
            {
                const float left = std::floor(c.t.ox + (pen + float(g.bearingX)) * c.t.s + 0.5f);
                const float top = by + std::floor(float(g.bearingY) * c.t.s + 0.5f);
                const float aw = float(catalog.Width()), ah = float(catalog.Height());
                want.push_back({left, top, left + float(g.width) * c.t.s, top + float(g.height) * c.t.s,
                                float(g.x) / aw, float(g.y) / ah, float(g.x + g.width) / aw, float(g.y + g.height) / ah,
                                0.0f, 0xFFFFFFFFu});
            }
            pen += float(g.advance) / 64.0f;
            previous = cp;
        }
        wfui::Text(byDefault, 3.0f, 5.0f, c.v, 0xFFFFFFFFu, c.s, c.anchor, c.align, c.t);
        wfui::Text(byName, 3.0f, 5.0f, c.v, 0xFFFFFFFFu, c.s, c.anchor, c.align, c.t, wfui::Pitch::Proportional);
        const bool same = !want.empty() && want.size() == byDefault.size() && want.size() == byName.size()
                          && !std::memcmp(want.data(), byDefault.data(), want.size() * sizeof(want[0]))
                          && !std::memcmp(want.data(), byName.data(), want.size() * sizeof(want[0]));
        Check(same && wfui::Width(c.v, c.s, wfui::Pitch::Proportional) == width,
              std::string("proportional \"") + c.s + "\" in " + names[c.v] + ": " + std::to_string(want.size()) + " quads, unchanged");
    }

    // Fixed pitch: the cell is the widest digit, every code point takes one cell, and
    // each glyph's advance box is centred in its cell.
    const char* digits[] = {"0000", "1111", "1234", "5678", "9090", "59.8", "60.3", "1.11", "8.88"};
    for (int v = 0; v < wfui::VariantCount; ++v)
    {
        int widest = 0;
        for (int cp = '0'; cp <= '9'; ++cp)
        {
            bitmaptext::Glyph g;
            catalog.FindGlyph(v, cp, g);
            widest = std::max(widest, g.advance);
        }
        bool equal = wfui::CellWidth(wfui::Variant(v)) == float(widest) / 64.0f, centred = true;
        for (const char* s : digits)
        {
            std::vector<bitmaptext::Quad> quads;
            const float advance = wfui::Text(quads, 0, 0, wfui::Variant(v), 0xFFFFFFFFu, s, wfui::Baseline, wfui::Left,
                                             wfui::Transform(), wfui::Pitch::Fixed);
            equal = equal && advance == 4 * float(widest) / 64.0f && wfui::Width(wfui::Variant(v), s, wfui::Pitch::Fixed) == advance;
            size_t q = 0;
            for (int i = 0; s[i]; ++i)
            {
                bitmaptext::Glyph g;
                catalog.FindGlyph(v, s[i], g);
                if (g.width <= 0 || g.height <= 0) continue;
                const float origin = float(i * widest) / 64.0f + float(widest - g.advance) / 128.0f;
                centred = centred && q < quads.size() && quads[q++].x0 == std::floor(origin + float(g.bearingX) + 0.5f);
            }
            centred = centred && q == quads.size();
        }
        char what[160];
        std::snprintf(what, sizeof(what), "fixed pitch in %s: cell %.3f px (widest digit), every 4-character number %.3f px, glyphs centred in their cells",
                      names[v], wfui::CellWidth(wfui::Variant(v)), 4 * wfui::CellWidth(wfui::Variant(v)));
        Check(equal && centred, what);
    }
    std::vector<bitmaptext::Quad> one, two;
    wfui::Text(one, 0, 0, wfui::Small, 0xFFFFFFFFu, "AV", wfui::Top, wfui::Left, wfui::Transform(), wfui::Pitch::Fixed);
    wfui::Text(two, 0, 0, wfui::Small, 0xFFFFFFFFu, "A", wfui::Top, wfui::Left, wfui::Transform(), wfui::Pitch::Fixed);
    Check(catalog.Kerning(wfui::Small, 'A', 'V') != 0 && wfui::Width(wfui::Small, "AV", wfui::Pitch::Fixed) == 2 * wfui::CellWidth(wfui::Small)
          && one.size() == 2 && !std::memcmp(&one[0], &two[0], sizeof(one[0])), "fixed pitch does not kern (\"AV\" is two cells)");

    std::printf("%s: %d failure(s)\n", failures ? "FAIL" : "PASS", failures);
    return failures ? 1 : 0;
}
