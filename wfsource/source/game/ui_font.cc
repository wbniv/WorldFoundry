//==============================================================================
// game/ui_font.cc — layout over the shared UI atlas (portable)
// Copyright ( c ) 2026 World Foundry Group
// This program is free software; you can redistribute it and/or modify it
// under the terms of the GNU General Public License Version 2.
// This program is distributed without ANY WARRANTY. See www.fsf.org.
//==============================================================================
// Description: see ui_font.hp. No engine dependency: the level-menu and phone
// overlay host harnesses compile this file with bitmap_text.cc alone.
//==============================================================================
#include "ui_font.hp"

#include <assert.h>
#include <math.h>
#include <string.h>

namespace wfui
{
namespace
{
bitmaptext::Catalog gCatalog;
bool gLoaded = false;
bitmaptext::Variant gVariant[VariantCount];
bitmaptext::Glyph gQuestion[VariantCount];

// The bake's variant table (scripts/bake-ui-font.py VARIANTS): face, pixels.
constexpr int kFace[VariantCount]   = {0, 0, 1, 1, 0, 1, 1};
constexpr int kPixels[VariantCount] = {28, 36, 36, 46, 56, 56, 80};

// The glyph for the code point at `offset`, advancing it; '?' for anything the
// atlas lacks, including malformed UTF-8 (one byte at a time).
const bitmaptext::Glyph& Next(Variant v, const char* s, int bytes, int& offset, int& cp, bitmaptext::Glyph& scratch)
{
    const int start = offset;
    if (!bitmaptext::Decode(s, bytes, offset, cp)) { offset = start + 1; cp = '?'; return gQuestion[v]; }
    if (gCatalog.FindGlyph(v, cp, scratch)) return scratch;
    cp = '?';
    return gQuestion[v];
}
}

bool Load(const void* bytes, size_t size, const char*& error)
{
    gLoaded = false;
    error = nullptr;
    if (!gCatalog.Load(bytes, size, error))
        return false;
    for (int v = 0; v < VariantCount; ++v)
    {
        if (gCatalog.SelectVariant(kFace[v], kPixels[v]) != v
            || gCatalog.GetVariant(v).pixels != kPixels[v] || gCatalog.GetVariant(v).face != kFace[v])
        {
            error = "the atlas does not have the seven UI variants in order (bake it with scripts/bake-ui-font.py)";
            return false;
        }
        gVariant[v] = gCatalog.GetVariant(v);
        if (!gCatalog.FindGlyph(v, '?', gQuestion[v]))
        {
            error = "the atlas has no '?' glyph";
            return false;
        }
    }
    gLoaded = true;
    return true;
}

bool Loaded() { return gLoaded; }
void Unload() { gLoaded = false; gCatalog = bitmaptext::Catalog(); }
const bitmaptext::Catalog& Catalog() { assert(gLoaded); return gCatalog; }

float Ascent(Variant v)     { assert(gLoaded && v >= 0 && v < VariantCount); return float(gVariant[v].ascent); }
float Descent(Variant v)    { assert(gLoaded && v >= 0 && v < VariantCount); return float(gVariant[v].descent); }
float LineHeight(Variant v) { assert(gLoaded && v >= 0 && v < VariantCount); return float(gVariant[v].lineStep); }

float Width(Variant v, const char* s, size_t bytes)
{
    assert(gLoaded && v >= 0 && v < VariantCount);
    int offset = 0, cp = 0, previous = 0, sum = 0;
    bitmaptext::Glyph scratch;
    while (offset < int(bytes))
    {
        const bitmaptext::Glyph& g = Next(v, s, int(bytes), offset, cp, scratch);
        if (previous) sum += gCatalog.Kerning(v, previous, cp);
        sum += g.advance;
        previous = cp;
    }
    return float(sum) / 64.0f;
}

float TextBytes(std::vector<bitmaptext::Quad>& out, float x, float y, Variant v, uint32_t rgba,
                const char* s, size_t bytes, Anchor anchor, Align align, const Transform& t)
{
    assert(gLoaded && v >= 0 && v < VariantCount);
    const float width = Width(v, s, bytes);
    if (align == Centre) x -= width * 0.5f;
    else if (align == Right) x -= width;
    const bitmaptext::Variant& var = gVariant[v];
    const float baseline = anchor == Top ? y + float(var.ascent)
                         : anchor == Middle ? y + float(var.ascent - var.descent) * 0.5f
                         : y;
    const float aw = float(gCatalog.Width()), ah = float(gCatalog.Height());
    // Whole surface pixels for the baseline, so every glyph of a line shares
    // its rows; at 1:1 the atlas texels then land exactly on screen pixels.
    const float by = floorf(t.oy + baseline * t.s + 0.5f);
    int offset = 0, cp = 0, previous = 0;
    float pen = x;
    bitmaptext::Glyph scratch;
    while (offset < int(bytes))
    {
        const bitmaptext::Glyph& g = Next(v, s, int(bytes), offset, cp, scratch);
        if (previous) pen += float(gCatalog.Kerning(v, previous, cp)) / 64.0f;
        if (g.width > 0 && g.height > 0)
        {
            const float left = floorf(t.ox + (pen + float(g.bearingX)) * t.s + 0.5f);
            const float top = by + floorf(float(g.bearingY) * t.s + 0.5f);
            out.push_back({left, top, left + float(g.width) * t.s, top + float(g.height) * t.s,
                           float(g.x) / aw, float(g.y) / ah, float(g.x + g.width) / aw, float(g.y + g.height) / ah,
                           0.0f, rgba});
        }
        pen += float(g.advance) / 64.0f;
        previous = cp;
    }
    return width;
}

std::string Fit(Variant v, const std::string& s, float maxWidth, const char* suffix)
{
    if (Width(v, s) <= maxWidth) return s;
    const std::string tail = suffix ? suffix : "";
    std::string cut = s;
    while (!cut.empty() && Width(v, cut + tail) > maxWidth)
    {
        // Drop one whole code point: its continuation bytes, then its lead byte.
        while (!cut.empty() && (static_cast<unsigned char>(cut.back()) & 0xC0) == 0x80) cut.pop_back();
        if (!cut.empty()) cut.pop_back();
    }
    while (!cut.empty() && cut.back() == ' ') cut.pop_back();
    return cut + tail;
}
}
