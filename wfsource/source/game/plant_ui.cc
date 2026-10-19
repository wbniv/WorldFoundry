#include "plant_ui.h"
#include "../../../engine/runtime_diagnostics.hpp"
#include "runtime_property_ui.h"
#include "runtime_property_controls.h"
#include <hal/remote_back_arrow.h>
namespace planted {
void uiInput(uint32_t buttons){propertyui::inputHost(buttons);}
void buildUI(int w,int h,std::vector<PhonepadRect>& out,std::vector<bitmaptext::Quad>* glyphs){
 auto& s=state();out.clear();if(glyphs)glyphs->clear();if(!s.active&&!wfprops::host().modal)return;
 float sx=w/1920.f,sy=h/1080.f;
 auto rect=[&](float x,float y,float width,float height,uint32_t color){out.push_back({x*sx,y*sy,(x+width)*sx,(y+height)*sy,color});};
 // The HUD strip: Regular 28 (small), the text's middle on the strip's.
 if(s.active){rect(42,984,890,54,0x102621ddu);
  propertyui::drawText(glyphs,sx,sy,60,1011-3.5f*3,3,"Seed: "+std::to_string(s.seed)+" | "+(s.salt?"Saltwater":"Freshwater")+" | Hold A: settings",0xf1f2e4ffu,wfui::Small);}
 propertyui::buildHost(w,h,out,glyphs);
}
}
