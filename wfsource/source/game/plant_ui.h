#ifndef WF_PLANT_UI_H
#define WF_PLANT_UI_H
#include <game/plant_settings.h>
#include <hal/phonepad/phonepad_overlay.h>
namespace planted {
void uiInput(uint32_t buttons);
void buildUI(int w,int h,std::vector<PhonepadRect>& rectangles);
}
#endif
