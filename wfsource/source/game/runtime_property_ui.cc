#include "runtime_property_ui.h"
#include "runtime_property_controls.h"
#include <algorithm>
#include <cstdlib>
#include <cmath>
#include <hal/remote_back_arrow.h>
#include "../../../engine/vendor/stb_easy_font.h"
namespace propertyui {
namespace { const bool registeredInput=[](){inputHandler()=&input;return true;}(); }
void build(wfprops::Form& editor,bool phone,int w,int h,std::vector<PhonepadRect>& out){
 float sx=w/1920.f,sy=h/1080.f;
 auto rect=[&](float x,float y,float width,float height,uint32_t color){out.push_back({x*sx,y*sy,(x+width)*sx,(y+height)*sy,color});};
 auto text=[&](float x,float y,float scale,const std::string& str,uint32_t color=0xf1f2e4ffu){auto& buf=editor.textVertices;int n=stb_easy_font_print(0,0,const_cast<char*>(str.c_str()),nullptr,buf,sizeof(buf));float* f=buf;for(int i=0;i<n;i++){float* v=f+i*16;float x0=v[0],y0=v[1],x1=x0,y1=y0;for(int k=1;k<4;k++){x0=std::min(x0,v[k*4]);x1=std::max(x1,v[k*4]);y0=std::min(y0,v[k*4+1]);y1=std::max(y1,v[k*4+1]);}rect(x+x0*scale,y+y0*scale,(x1-x0)*scale,(y1-y0)*scale,color);}};
 rect(0,0,1920,1080,0x061014ffu);rect(180,110,1560,820,0x142d25ffu);
 syncText(editor,phone);auto& f=editor;auto* object=f.edit.object();if(!object)return;text(225,150,4,object->title);
 struct ArrowPainter {decltype(rect)& draw;void Rect(float x0,float y0,float x1,float y1,uint32_t c){draw(x0,y0,x1-x0,y1-y0,c);}} painter{rect};
 auto item=[&](bool focused,float x,float y,float width,float height,const std::string& label,bool ghost=false){rect(x,y,width,height,focused?0x497b51ffu:ghost?0x1c302affu:0x233e31ffu);text(x+18,y+18,3,label.substr(0,size_t(width/19)),ghost?0x9eb1a7ffu:0xf1f2e4ffu);};
 if(phone){text(225,350,4,"Edit properties on your connected phone");}
 else {
  size_t sectionStart=f.section>5?f.section-5:0;
  for(size_t i=sectionStart;i<f.titles.size()&&i<sectionStart+6;++i)item(f.rail&&i==f.section,225,240+(i-sectionStart)*85,330,68,f.titles[i]);
  if(f.section<f.sections.size()){
   const auto& rows=f.sections[f.section];
   auto options=[](const wfprops::Field& field){std::vector<std::string> labels;size_t start=0;while(start<=field.choices.size()){auto end=field.choices.find('|',start);labels.push_back(field.choices.substr(start,end==std::string::npos?end:end-start));if(end==std::string::npos)break;start=end+1;}return labels;};
   auto columns=[&](const wfprops::Field& field){size_t longest=0;auto labels=options(field);for(const auto& label:labels)longest=std::max(longest,label.size());return std::max(1,std::min(int(labels.size()),int(1040/std::max(140.f,float(longest)*16+44))));};
   auto category=[&](size_t i){std::string group;for(size_t k=0;k<rows[i];++k){const auto& marker=object->fields[k];if(marker.kind==6)group=marker.label;else if(marker.kind==5||marker.kind==7)group.clear();}return group;};
   auto groupHeight=[&](size_t i){return !category(i).empty()&&(i==0||category(i)!=category(i-1))?30.f:0.f;};
   auto height=[&](size_t i){const auto& field=object->fields[rows[i]];float base=85.f;if(field.show==2&&field.kind<=2)base=128.f;else if(field.kind==2&&field.show==5)base=62.f+48.f*std::min(3,int((options(field).size()+columns(field)-1)/columns(field)));return base+groupHeight(i);};
   size_t first=std::min(f.row,rows.empty()?size_t(0):rows.size()-1);float used=rows.empty()?0:height(first);while(first>0&&used+height(first-1)<=515){used+=height(--first);}
   float y=240;
   for(size_t i=first;i<rows.size();++i){const auto& field=object->fields[rows[i]];float rowHeight=height(i);if(y+rowHeight>765)break;if(field.kind==10){y+=rowHeight;continue;}
    float heading=groupHeight(i);if(heading>0){text(605,y+2,2.5f,category(i),0xcbd4baffu);y+=heading;rowHeight-=heading;}
    auto v=f.edit.draft.find(field.id);std::string value=v==f.edit.draft.end()?"":v->second;
    if(field.kind==2){int index=std::atoi(value.c_str())-field.minimum;size_t from=0;for(int k=0;k<index;++k){size_t next=field.choices.find('|',from);if(next==std::string::npos)break;from=next+1;}size_t to=field.choices.find('|',from);value=field.choices.substr(from,to==std::string::npos?to:to-from);}
    if(field.kind==4)value=value=="1"?"On":"Off";
    std::replace(value.begin(),value.end(),'\n',' ');std::replace(value.begin(),value.end(),'\r',' ');
    if(colour(&field))value=hex(rgb(value));
    bool radio=field.kind==2&&field.show==5;
    item(!f.rail&&i==f.row,600,y,1080,rowHeight-12,field.kind==9?field.label:radio?field.label:field.label+": "+value+(field.readonly?" (read only)":""),field.readonly);
    if(colour(&field))rect(1570,y+16,70,40,(rgb(v==f.edit.draft.end()?"0":v->second)<<8)|255u);
    if(radio){auto labels=options(field);int cols=columns(field);int selected=std::atoi(v==f.edit.draft.end()?"0":v->second.c_str())-field.minimum;int firstOptionRow=std::max(0,selected/cols-2);float cell=1040.f/cols;
     for(size_t k=size_t(firstOptionRow*cols);k<labels.size()&&k<size_t((firstOptionRow+3)*cols);++k){float x=620+(k%cols)*cell,oy=y+62+(int(k)/cols-firstOptionRow)*48;rect(x,oy-17,cell-12,36,int(k)==selected?0xe4efd9ffu:0x19382dffu);text(x+12,oy-11,2.5f,labels[k].substr(0,size_t((cell-35)/16)),int(k)==selected?0x132b26ffu:0xe4efd9ffu);}
    }
    if(field.show==2&&field.kind<=2){double scale=field.kind==1&&field.scale?field.scale:1;double low=field.minimum/scale,high=field.maximum/scale;double current=std::strtod(v==f.edit.draft.end()?"0":v->second.c_str(),nullptr);float fraction=high>low?float(std::max(0.0,std::min(1.0,(current-low)/(high-low)))):0;
     const float left=630,width=1000,cy=y+62;rect(left,cy-2,width,4,0x8aab8affu);rect(left,cy-2,width*fraction,4,0xe4efd9ffu);
     auto labels=field.kind==2?options(field):std::vector<std::string>{};if(labels.size()>1&&labels.size()<=9){for(size_t k=0;k<labels.size();++k){float x=left+width*k/(labels.size()-1);rect(x-1,cy-6,2,12,0xe4efd9ffu);float labelWidth=labels[k].size()*15.f;text(std::max(left,std::min(left+width-labelWidth,x-labelWidth/2)),y+91,2.5f,labels[k]);}}
     else {text(left,y+91,2.5f,std::to_string(low));text(left+width-120,y+91,2.5f,std::to_string(high));}
     rect(left+width*fraction-7,cy-12,14,24,field.readonly?0x8aab8affu:0xefce83ffu);
    }
    y+=rowHeight;
   }
   if(rows.size()>6)text(605,775,2.5f,std::to_string(f.row+1)+" / "+std::to_string(rows.size()));
  }
  if(f.drawer){const auto* field=f.field();auto& ui=controls(f);
   if(colour(field)){rect(600,205,1080,625,0x102621ffu);text(630,235,3,field->label);
    auto outline=[&](float x,float y,float width,float height,uint32_t color){rect(x-4,y-4,width+8,4,color);rect(x-4,y+height,width+8,4,color);rect(x-4,y,4,height,color);rect(x+width,y,4,height,color);};
    auto swatch=[&](float x,float y,float size,uint32_t packed,bool focus){rect(x,y,size,size,(packed<<8)|255u);if(packed==ui.preview){rect(x+8,y+8,24,24,0x102621ffu);text(x+13,y+13,2,"X");}if(focus)outline(x,y,size,size,0xffffffffu);};
    text(1220,290,2.5f,"Original / Preview");rect(1220,325,170,90,(ui.original<<8)|255u);rect(1400,325,170,90,(ui.preview<<8)|255u);text(1220,450,3,hex(ui.preview));
    text(1220,500,2.2f,"RGB "+std::to_string((ui.preview>>16)&255)+" / "+std::to_string((ui.preview>>8)&255)+" / "+std::to_string(ui.preview&255));
    if(ui.page==0){for(int i=0;i<16;++i)swatch(645+(i%4)*130,290+(i/4)*100,80,palette()[i],ui.focus==i);
     text(645,703,2.3f,"Recent");int n=int(recentColours().size());for(int i=0;i<n;++i)swatch(760+i*65,690,44,recentColours()[i],ui.focus==16+i);
     int actions=16+n;item(ui.focus==actions,630,760,280,58,"Custom");item(ui.focus==actions+1,940,760,280,58,"Use colour");item(ui.focus==actions+2,1250,760,280,58,"Cancel");
    }else if(ui.page==1){
     // Bounded 24x24 grid uses the existing solid-rectangle overlay; no renderer API change.
     static double spectrumValue=-1;static std::array<uint32_t,576> spectrum;
     if(spectrumValue!=ui.value){spectrumValue=ui.value;for(int y=0;y<24;++y)for(int x=0;x<24;++x)spectrum[y*24+x]=(hsv(x*360./24,1-y/23.,ui.value)<<8)|255u;}
     for(int y=0;y<24;++y)for(int x=0;x<24;++x)rect(640+x*16,290+y*16,16,16,spectrum[y*24+x]);
     if(ui.focus==0)outline(640,290,384,384,ui.planeAdjust?0xefce83ffu:0xffffffffu);
     float px=640+ui.hue/360*384,py=290+(1-ui.saturation)*384;rect(px-8,py-8,16,16,0x000000ffu);rect(px-5,py-5,10,10,0xffffffffu);
     item(ui.focus==1,630,700,420,70,"Value: "+std::to_string(int(std::round(ui.value*100)))+"%");for(int x=0;x<72;++x)rect(645+x*5.3f,745,5.4f,16,(hsv(ui.hue,ui.saturation,x/71.)<<8)|255u);rect(645+ui.value*381-3,740,6,26,0xffffffffu);
     item(ui.focus==2,1100,565,510,60,"RGB / Hex details");item(ui.focus==3,1100,640,510,60,"Use colour");item(ui.focus==4,1100,715,510,60,"Palette");
     text(650,791,2,"H "+std::to_string(int(std::round(ui.hue)))+" / S "+std::to_string(int(std::round(ui.saturation*100)))+"% / V "+std::to_string(int(std::round(ui.value*100)))+"%");
    }else {const char* names[]={"Red","Green","Blue","Hex"};for(int i=0;i<4;++i)item(ui.focus==i,630,300+i*95,530, 70,names[i]+std::string(": ")+(i==3?hex(ui.preview):std::to_string((ui.preview>>((2-i)*8))&255)));item(ui.focus==4,630,700,530,65,"Custom colour");}
    if(ui.nativeOpen){rect(620,270,1030,500,0x102621ffu);text(655,330,3,"Editing with the system keyboard");}
   }else {rect(600,205,1080,300,0x102621ffu);text(630,235,3,field?field->label:"");text(630,330,3,"Editing with the system keyboard");}

  }
 }
 const auto* focused=f.field();
 if(!phone&&!f.drawer&&!f.rail&&focused&&!focused->help.empty()){
   std::string help=focused->help;std::replace(help.begin(),help.end(),'\n',' ');
   // Wrap at words; reserve two lines above the persistent Apply/Cancel footer.
   for(int line=0;line<2&&!help.empty();++line){size_t length=std::min(size_t(84),help.size());if(length<help.size()){auto split=help.rfind(' ',length);if(split!=std::string::npos&&split>0)length=split;}text(600,791+line*22,2,help.substr(0,length),0xb6c7baffu);help.erase(0,length);while(!help.empty()&&help[0]==' ')help.erase(0,1);}
 }
 bool direct=!f.rail&&focused&&!focused->readonly&&(focused->kind==2||focused->kind==4||focused->show==2);
 text(225,840,2.7f,f.edit.error.empty()?(f.drawer?(colour(focused)?(controls(f).planeAdjust?"Arrows: hue / saturation   A: finish":controls(f).page==1?"Up / down: select   Left / right: value":"Arrows: select   A: choose"):"Use the system text editor"):direct?"Up / down: select   Left / right: change":focused&&focused->readonly?"Read only: arrows select   Left: sections":"Arrows: select   A: edit"):f.edit.error,0xffdd99ffu);
 remoteui::BackArrow(painter,1260,840,4,0xf1f2e4ffu);text(1310,840,2.7f,f.drawer?(colour(focused)?(controls(f).planeAdjust?"Finish adjustment":"Cancel colour"):"Close editor"):"Apply / close");
}
}
