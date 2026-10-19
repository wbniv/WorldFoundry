// Shared remote Back symbol for rectangle-based UI painters.
// The UI font (game/ui_font.hp) has no arrows, so "←" in UI text is drawn
// as this shape, sized to the text's variant.
#pragma once
#include <cstdint>
#include "../game/ui_font.hp"
namespace remoteui {
constexpr const char* kBackArrow = "←";
// One "pixel" of the seven-row arrow for a variant: the arrow is as tall as
// the font's capitals (about 0.7 of the pixel size).
inline float BackArrowUnit(wfui::Variant v) {
    static const float kPixels[wfui::VariantCount] = {28, 36, 36, 46, 56, 56, 80};
    return kPixels[v] / 10.0f;
}
// The advance of the arrow, in canvas units.
inline float BackArrowAdvance(wfui::Variant v) { return 10.0f * BackArrowUnit(v); }
// Left-pointing arrow with its left edge at x and its middle at cy, the same
// middle as wfui::Text's Middle anchor.
template<class Painter>
void BackArrowMiddle(Painter& p, float x, float cy, wfui::Variant v, uint32_t color) {
    const float scale = BackArrowUnit(v), y = cy - 3.5f * scale;
    p.Rect(x, y+3*scale, x+8*scale, y+4*scale, color);
    for (int row=0; row<3; ++row) {
        const float dx=float(3-row)*scale;
        p.Rect(x+dx, y+row*scale, x+dx+scale, y+(row+1)*scale, color);
        p.Rect(x+dx, y+(6-row)*scale, x+dx+scale, y+(7-row)*scale, color);
    }
}
}
