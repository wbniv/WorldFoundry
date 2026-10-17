#include "runtime_property_ui.h"
#include <algorithm>
#include <cmath>
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
namespace {
// 3D object picker colours (docs/plans/2026-10-16-runtime-object-editing/picker.html).
constexpr uint32_t kInk=0xf1f2e4ffu,kGreen=0x8fe08affu,kDim=0x00000047u,kBar=0x09140fe6u,kTag=0x0d1f17f0u;
struct Painter {
 std::vector<PhonepadRect>& out;float sx,sy;float* buf;int bufSize;
 void rect(float x,float y,float w,float h,uint32_t c){out.push_back({x*sx,y*sy,(x+w)*sx,(y+h)*sy,c});}
 float width(const std::string& s,float scale){return stb_easy_font_width(const_cast<char*>(s.c_str()))*scale;}
 void text(float x,float y,float scale,const std::string& str,uint32_t color=kInk){int n=stb_easy_font_print(0,0,const_cast<char*>(str.c_str()),nullptr,buf,bufSize);for(int i=0;i<n;++i){float* v=buf+i*16;float x0=v[0],y0=v[1],x1=x0,y1=y0;for(int k=1;k<4;++k){x0=std::min(x0,v[k*4]);x1=std::max(x1,v[k*4]);y0=std::min(y0,v[k*4+1]);y1=std::max(y1,v[k*4+1]);}rect(x+x0*scale,y+y0*scale,(x1-x0)*scale,(y1-y0)*scale,color);}}
 void frame(float x,float y,float w,float h,float t,uint32_t c){rect(x,y,w,t,c);rect(x,y+h-t,w,t,c);rect(x,y,t,h,c);rect(x+w-t,y,t,h,c);}
 // Corner brackets around a rectangle.
 void brackets(float x0,float y0,float x1,float y1,float t,uint32_t c){
  const float arm=std::max(8.f,std::min(26.f,std::min(x1-x0,y1-y0)*.3f));
  rect(x0,y0,arm,t,c);rect(x0,y0,t,arm,c);rect(x1-arm,y0,arm,t,c);rect(x1-t,y0,t,arm,c);
  rect(x0,y1-t,arm,t,c);rect(x0,y1-arm,t,arm,c);rect(x1-arm,y1-t,arm,t,c);rect(x1-t,y1-arm,t,arm,c);}
 // A ring of small squares; a crosshair and a gear are built from it.
 void ring(float cx,float cy,float r,float dot,int n,uint32_t c){for(int i=0;i<n;++i){float a=6.2831853f*i/n;rect(cx+r*std::cos(a)-dot*.5f,cy+r*std::sin(a)-dot*.5f,dot,dot,c);}}
 void gear(float cx,float cy,uint32_t c){ring(cx,cy,11,5,18,c);ring(cx,cy,17,7,8,c);}
 void crosshair(float cx,float cy,uint32_t c){ring(cx,cy,11,3,20,c);rect(cx-1.5f,cy-18,3,9,c);rect(cx-1.5f,cy+9,3,9,c);rect(cx-18,cy-1.5f,9,3,c);rect(cx+9,cy-1.5f,9,3,c);}
 // A left arrow drawn from rectangles: the TV font has no arrow glyph.
 void leftArrow(float x,float cy,uint32_t c){rect(x+3,cy-1.5f,24,3,c);for(int i=0;i<9;++i){rect(x+i,cy-i-1.5f,3,3,c);rect(x+i,cy+i-1.5f,3,3,c);}}
};
void buildPick(wfprops::Host& host,Painter& p){
 using wfprops::PickMode;
 host.refreshPick();
 p.rect(0,0,1920,1080,kDim);
 const auto& targets=host.pickTargets;
 for(size_t i=0;i<targets.size();++i){
  const auto& t=targets[i];const bool lit=int(i)==host.highlight;
  if(t.gear)p.gear(t.cx,t.cy,lit?kGreen:kInk);
  p.brackets(t.x0,t.y0,t.x1,t.y1,lit?6:3,lit?kGreen:kInk);
 }
 if(host.highlight>=0&&size_t(host.highlight)<targets.size()){
  const auto& t=targets[size_t(host.highlight)];
  const std::string label=t.members.size()==1?host.pickCandidates[t.members[0]].label:std::to_string(t.members.size())+" objects here";
  const float scale=2.6f,w=p.width(label,scale)+28,h=40;
  float x=std::max(8.f,std::min(1912-w,(t.x0+t.x1)*.5f-w*.5f)),y=t.y0-h-10;if(y<8)y=t.y1+10;
  p.rect(x,y,w,h,kTag);p.frame(x,y,w,h,2,kGreen);p.text(x+14,y+10,scale,label,kGreen);
 }
 if(targets.empty()){
  const std::string msg="No editable objects in view";const float w=p.width(msg,4)+80;
  p.rect(960-w*.5f,470,w,110,kTag);p.frame(960-w*.5f,470,w,110,3,kGreen);p.text(1000-w*.5f,507,4,msg);
 }
 if(host.pick==PickMode::Group){
  const float x=600,w=720,rowH=72,y=300;const float h=110+rowH*host.group.size();
  p.rect(x,y,w,h,0x142d25f4u);p.frame(x,y,w,h,3,kGreen);p.text(x+36,y+30,3.4f,"Objects here");
  for(size_t i=0;i<host.group.size();++i){
   std::string title;for(const auto& o:host.owners)if(o.actor==host.group[i])title=o.title;
   const float ry=y+86+i*rowH;p.rect(x+30,ry,w-60,rowH-12,i==host.groupSelected?0x497b51ffu:0x233e31ffu);p.text(x+50,ry+16,3,title.substr(0,40));
  }
 }
 p.rect(0,1012,1920,68,kBar);
 if(host.pick==PickMode::Group)p.text(40,1032,3,"Up / down: select   OK: edit",kGreen);
 else if(!targets.empty())p.text(40,1032,3,"Arrows: move   OK: edit",kGreen);
 const std::string back=host.pick==PickMode::Group?"back":"list";
 const float bw=p.width(back,3);p.text(1880-bw,1032,3,back,kGreen);p.leftArrow(1880-bw-44,1045,kGreen);
}
}
void buildHost(int w,int h,std::vector<PhonepadRect>& out){
 auto& host=wfprops::host();host.checkOwner();
 if(!host.modal)return;
 if(!host.picker){build(host.form,host.phone,w,h,out);return;}
 Painter p{out,w/1920.f,h/1080.f,host.form.textVertices,int(sizeof(host.form.textVertices))};
 if(host.pick!=wfprops::PickMode::Off){buildPick(host,p);return;}
 p.rect(0,0,1920,1080,0x061014ffu);p.rect(180,110,1560,820,0x142d25ffu);p.text(225,150,4,"Choose an object");
 if(host.phone){p.text(225,350,4,"Choose on your connected phone");return;}
 // Row 0 is Pick in 3D (shown whenever the chooser is, i.e. two or more objects).
 const size_t rows=host.owners.size()+1;
 size_t first=host.selected>5?host.selected-5:0;
 for(size_t i=first;i<rows&&i<first+6;++i){
  float y=240+(i-first)*85;p.rect(225,y,1455,68,i==host.selected?0x497b51ffu:0x233e31ffu);
  if(i==0){p.crosshair(268,y+34,kInk);p.text(305,y+18,3,"Pick in 3D");continue;}
  const auto& owner=host.owners[i-1];p.text(245,y+18,3,owner.title.substr(0,66)+" ["+std::to_string(owner.actor)+"]");
 }
 p.text(225,840,2.7f,"Up / down: select   OK: open   Back: cancel");
}
}
