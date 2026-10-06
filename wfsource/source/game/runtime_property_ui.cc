#include "runtime_property_ui.h"
#include <algorithm>
#include <cstdlib>
#include <hal/remote_back_arrow.h>
#include "../../../engine/vendor/stb_easy_font.h"
namespace propertyui {
void build(wfprops::Form& editor,bool phone,int w,int h,std::vector<PhonepadRect>& out){
 float sx=w/1920.f,sy=h/1080.f;
 auto rect=[&](float x,float y,float width,float height,uint32_t color){out.push_back({x*sx,y*sy,(x+width)*sx,(y+height)*sy,color});};
 auto text=[&](float x,float y,float scale,const std::string& str,uint32_t color=0xf1f2e4ffu){alignas(float) char buf[24000];int n=stb_easy_font_print(0,0,const_cast<char*>(str.c_str()),nullptr,buf,sizeof(buf));float* f=reinterpret_cast<float*>(buf);for(int i=0;i<n;i++){float* v=f+i*16;float x0=v[0],y0=v[1],x1=x0,y1=y0;for(int k=1;k<4;k++){x0=std::min(x0,v[k*4]);x1=std::max(x1,v[k*4]);y0=std::min(y0,v[k*4+1]);y1=std::max(y1,v[k*4+1]);}rect(x+x0*scale,y+y0*scale,(x1-x0)*scale,(y1-y0)*scale,color);}};
 rect(0,0,1920,1080,0x061014ffu);rect(180,110,1560,820,0x142d25ffu);
 auto& f=editor;auto* object=f.edit.object();if(!object)return;text(225,150,4,object->title);
 struct ArrowPainter {decltype(rect)& draw;void Rect(float x0,float y0,float x1,float y1,uint32_t c){draw(x0,y0,x1-x0,y1-y0,c);}} painter{rect};
 auto item=[&](bool focused,float x,float y,float width,float height,const std::string& label){rect(x,y,width,height,focused?0x497b51ffu:0x233e31ffu);text(x+18,y+18,3,label.substr(0,size_t(width/19)));};
 if(phone){text(225,350,4,"Edit properties on your connected phone");}
 else {
  size_t sectionStart=f.section>5?f.section-5:0;
  for(size_t i=sectionStart;i<f.titles.size()&&i<sectionStart+6;++i)item(f.rail&&i==f.section,225,240+(i-sectionStart)*85,330,68,f.titles[i]);
  if(f.section<f.sections.size()){
   const auto& rows=f.sections[f.section];size_t first=f.row>5?f.row-5:0;
   for(size_t i=first;i<rows.size()&&i<first+6;++i){const auto& field=object->fields[rows[i]];float y=240+(i-first)*85;if(field.kind==10)continue;
    auto v=f.edit.draft.find(field.id);std::string value=v==f.edit.draft.end()?"":v->second;
    if(field.kind==2){int index=std::atoi(value.c_str())-field.minimum;size_t from=0;for(int k=0;k<index;++k){size_t next=field.choices.find('|',from);if(next==std::string::npos)break;from=next+1;}size_t to=field.choices.find('|',from);value=field.choices.substr(from,to==std::string::npos?to:to-from);}
    if(field.kind==4)value=value=="1"?"On":"Off";
    item(!f.rail&&i==f.row,600,y,1080,68,field.kind==9?field.label:field.label+": "+value+(field.readonly?" (read only)":""));
   }
   if(rows.size()>6)text(605,775,2.5f,std::to_string(f.row+1)+" / "+std::to_string(rows.size()));
  }
  if(f.drawer){rect(940,205,720,640,0x102621ffu);const auto* field=f.field();text(975,235,3,field?field->label:"");text(975,295,3,f.value());const char* keys[]={"1","2","3","4","5","6","7","8","9","<","0","Clear","-",".","Done"};for(int i=0;i<15;++i)item(i==f.key,975+(i%3)*210,355+(i/3)*85,195,68,keys[i]);}
 }
 text(225,840,2.7f,f.edit.error.empty()?(f.drawer?"Arrows: keypad   A: enter":f.adjust?"Left / right: adjust   A: finish":"Arrows: select   A: edit"):f.edit.error,0xffdd99ffu);
 remoteui::BackArrow(painter,1260,840,4,0xf1f2e4ffu);text(1310,840,2.7f,f.drawer?"Close keypad":"Apply / close");
}
}
