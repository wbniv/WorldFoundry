#include "plant_ui.h"
#include "../../../engine/runtime_diagnostics.hpp"
#include "runtime_property_ui.h"
#include "runtime_property_controls.h"
#include <hal/remote_back_arrow.h>
#include "../../../engine/vendor/stb_easy_font.h"
namespace planted {
void uiInput(uint32_t buttons){propertyui::inputHost(buttons);}
void buildUI(int w,int h,std::vector<PhonepadRect>& out){
 auto& s=state();out.clear();if(!s.active&&!wfprops::host().modal)return;
 float sx=w/1920.f,sy=h/1080.f;
 auto rect=[&](float x,float y,float width,float height,uint32_t color){out.push_back({x*sx,y*sy,(x+width)*sx,(y+height)*sy,color});};
 auto text=[&](float x,float y,float scale,const std::string& str,uint32_t color=0xf1f2e4ffu){alignas(float) char buf[24000];int n=stb_easy_font_print(0,0,const_cast<char*>(str.c_str()),nullptr,buf,sizeof(buf));float* f=reinterpret_cast<float*>(buf);for(int i=0;i<n;i++){float* v=f+i*16;float x0=v[0],y0=v[1],x1=x0,y1=y0;for(int k=1;k<4;k++){x0=std::min(x0,v[k*4]);x1=std::max(x1,v[k*4]);y0=std::min(y0,v[k*4+1]);y1=std::max(y1,v[k*4+1]);}rect(x+x0*scale,y+y0*scale,(x1-x0)*scale,(y1-y0)*scale,color);}};
 if(s.active){rect(42,984,890,54,0x102621ddu);text(60,998,3,"Seed: "+std::to_string(s.seed)+" | "+(s.salt?"Saltwater":"Freshwater")+" | Hold A: settings");}
 propertyui::buildHost(w,h,out);
}
}
