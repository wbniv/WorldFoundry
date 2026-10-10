#include "runtime_property_ui.h"
#include <algorithm>
#ifdef WF_RUNTIME_DIAGNOSTICS
#include "../../../engine/runtime_diagnostics.hpp"
#endif
#include "../../../engine/vendor/stb_easy_font.h"
namespace propertyui {
FormInput& inputHandler(){static FormInput handler=[](wfprops::Form& form,uint32_t buttons){form.input(buttons);};return handler;}
void inputHost(uint32_t buttons){
 auto& host=wfprops::host();host.checkOwner();
 if(!host.modal||host.picker)inputHandler()(host.form,buttons);
 if(!host.modal)return;
 const char* route=host.picker?"object-picker":host.phone?"phone-form":host.form.drawer?(host.form.field()&&host.form.field()->kind==0&&host.form.field()->show==7?"colour-picker":host.form.field()&&host.form.field()->kind==3&&host.form.field()->rule!=1?"text-keyboard":"keypad"):"form";
 #ifdef WF_RUNTIME_DIAGNOSTICS
 wfdiag::Route(route,"modal-capture");
#endif
 if(!host.phone){if(host.picker)host.inputPicker(buttons);else inputHandler()(host.form,buttons);}
 #ifdef WF_RUNTIME_DIAGNOSTICS
 wfdiag::Consume(route,"modal-capture",buttons);
#endif
}
void buildHost(int w,int h,std::vector<PhonepadRect>& out){
 auto& host=wfprops::host();host.checkOwner();
 if(!host.modal)return;
 if(!host.picker){build(host.form,host.phone,w,h,out);return;}
 float sx=w/1920.f,sy=h/1080.f;
 auto rect=[&](float x,float y,float width,float height,uint32_t color){out.push_back({x*sx,y*sy,(x+width)*sx,(y+height)*sy,color});};
 auto text=[&](float x,float y,float scale,const std::string& str){auto& buf=host.form.textVertices;int n=stb_easy_font_print(0,0,const_cast<char*>(str.c_str()),nullptr,buf,sizeof(buf));float* f=buf;for(int i=0;i<n;++i){float* v=f+i*16;float x0=v[0],y0=v[1],x1=x0,y1=y0;for(int k=1;k<4;++k){x0=std::min(x0,v[k*4]);x1=std::max(x1,v[k*4]);y0=std::min(y0,v[k*4+1]);y1=std::max(y1,v[k*4+1]);}rect(x+x0*scale,y+y0*scale,(x1-x0)*scale,(y1-y0)*scale,0xf1f2e4ffu);}};
 rect(0,0,1920,1080,0x061014ffu);rect(180,110,1560,820,0x142d25ffu);text(225,150,4,"Choose an object");
 if(host.phone){text(225,350,4,"Choose on your connected phone");return;}
 size_t first=host.selected>5?host.selected-5:0;
 for(size_t i=first;i<host.owners.size()&&i<first+6;++i){float y=240+(i-first)*85;rect(225,y,1455,68,i==host.selected?0x497b51ffu:0x233e31ffu);text(245,y+18,3,host.owners[i].title.substr(0,66)+" ["+std::to_string(host.owners[i].actor)+"]");}
 text(225,840,2.7f,"Up / down: select   OK: open   Back: cancel");
}
}
