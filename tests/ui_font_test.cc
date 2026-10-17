// ui_font_test: the committed UI atlas (wfsource/source/game/ui-font.wfga, baked by
// scripts/bake-ui-font.py) against the engine's own reader, bitmaptext::Catalog, and
// the wfui layout. docs/plans/2026-10-17-settings-editor-font.md, verification 3 and 4.
//
//   ui_font_test <ui-font.wfga>
#include <game/ui_font.hp>

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

    std::printf("%s: %d failure(s)\n", failures ? "FAIL" : "PASS", failures);
    return failures ? 1 : 0;
}
