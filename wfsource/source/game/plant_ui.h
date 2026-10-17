#ifndef WF_PLANT_UI_H
#define WF_PLANT_UI_H
#include <game/plant_settings.h>
#include <hal/phonepad/phonepad_overlay.h>
namespace planted {
void uiInput(uint32_t buttons);
// The planted tank's HUD strip and any open settings screen: rectangles, plus the
// text as UI-font quads (wfui::Draw) when `glyphs` is given.
void buildUI(int w,int h,std::vector<PhonepadRect>& rectangles,std::vector<bitmaptext::Quad>* glyphs=nullptr);
}
#endif
