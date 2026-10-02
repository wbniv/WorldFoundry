// Shared remote Back symbol for rectangle-based UI painters.
#pragma once
#include <cstdint>
namespace remoteui {
constexpr const char* kBackArrow = "←";
constexpr float kBackArrowAdvance = 10.0f;
template<class Painter>
void BackArrow(Painter& p, float x, float y, float scale, uint32_t color) {
    // Left-pointing arrow: seven pixel rows, aligned with the font's caps.
    p.Rect(x, y+3*scale, x+8*scale, y+4*scale, color);
    for (int row=0; row<3; ++row) {
        const float dx=float(3-row)*scale;
        p.Rect(x+dx, y+row*scale, x+dx+scale, y+(row+1)*scale, color);
        p.Rect(x+dx, y+(6-row)*scale, x+dx+scale, y+(7-row)*scale, color);
    }
}
}
